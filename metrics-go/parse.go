package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
)

// metricKeyPrefix is the literal head of every Redis key written for a metric.
// cron/bulk_write.sh finds them with KEYS METRIC-*, so nothing else in Redis
// may use this prefix.
const metricKeyPrefix = `METRIC-{"name": `

// errNoMetricsField mirrors the Flask endpoint's "Invalid data", 421 response
// for a body that parses but carries no metrics array.
var errNoMetricsField = errors.New(`payload has no "metrics" array`)

// metricWrite is one METRIC- key and the raw metric JSON stored under it.
// The value is the untouched bytes Telegraf sent, so nothing is re-serialised.
type metricWrite struct {
	key   string
	value []byte
}

// clientTally accumulates one agent's share of a batch.  A batch normally
// carries a single agent's metrics, but the tally is keyed so a shared
// endpoint (or a relay) still attributes metrics to the right host.
type clientTally struct {
	id      string
	mac     string
	ip      string
	host    string
	metrics int64
}

type parsedBatch struct {
	writes  []metricWrite
	clients []*clientTally
	byID    map[string]*clientTally

	// received counts every metric in the payload, stored or not, because
	// "this host is shouting at us" is exactly what the counters are for.
	received int64
	// skipped counts metrics dropped for missing name/tags, matching the
	// Flask endpoint's behaviour of silently ignoring them.
	skipped int64
}

// metricHeader picks the two fields that decide the Redis key out of a metric
// without disturbing the raw bytes that get stored.
type metricHeader struct {
	Name json.RawMessage `json:"name"`
	Tags json.RawMessage `json:"tags"`
}

type tagInfo struct {
	mac  string
	ip   string
	host string
}

// parseBatch streams a Telegraf JSON batch, producing the Redis writes and the
// per-client tallies.  fallbackID labels metrics that carry neither a mac nor
// an ip tag, so an unlabelled agent still shows up somewhere.
func parseBatch(r io.Reader, fallbackID string) (*parsedBatch, error) {
	dec := json.NewDecoder(r)

	token, err := dec.Token()
	if err != nil {
		return nil, fmt.Errorf("reading payload: %w", err)
	}
	if delim, ok := token.(json.Delim); !ok || delim != '{' {
		return nil, fmt.Errorf("payload is not a JSON object")
	}

	batch := &parsedBatch{byID: make(map[string]*clientTally, 1)}
	seenMetrics := false

	for dec.More() {
		keyToken, err := dec.Token()
		if err != nil {
			return nil, err
		}
		key, ok := keyToken.(string)
		if !ok {
			return nil, fmt.Errorf("unexpected object key %v", keyToken)
		}

		if key != "metrics" {
			var skip json.RawMessage
			if err := dec.Decode(&skip); err != nil {
				return nil, err
			}
			continue
		}

		seenMetrics = true
		if err := batch.consumeMetrics(dec, fallbackID); err != nil {
			return nil, err
		}
	}

	if _, err := dec.Token(); err != nil { // closing brace
		return nil, err
	}

	if !seenMetrics {
		return nil, errNoMetricsField
	}

	return batch, nil
}

func (b *parsedBatch) consumeMetrics(dec *json.Decoder, fallbackID string) error {
	token, err := dec.Token()
	if err != nil {
		return err
	}
	if delim, ok := token.(json.Delim); !ok || delim != '[' {
		return fmt.Errorf(`"metrics" is not an array`)
	}

	for dec.More() {
		var raw json.RawMessage
		if err := dec.Decode(&raw); err != nil {
			return err
		}
		if err := b.addMetric(raw, fallbackID); err != nil {
			return err
		}
	}

	_, err = dec.Token() // closing bracket
	return err
}

func (b *parsedBatch) addMetric(raw json.RawMessage, fallbackID string) error {
	b.received++

	var header metricHeader
	if err := json.Unmarshal(raw, &header); err != nil {
		return err
	}

	// serve.py stores a metric only when both fields are present.
	if len(header.Name) == 0 || len(header.Tags) == 0 {
		b.skipped++
		b.tally(fallbackID, tagInfo{})
		return nil
	}

	key, tags, err := buildMetricKey(header.Name, header.Tags)
	if err != nil {
		return err
	}

	b.writes = append(b.writes, metricWrite{key: key, value: raw})
	b.tally(clientID(tags, fallbackID), tags)

	return nil
}

func (b *parsedBatch) tally(id string, tags tagInfo) {
	tally, ok := b.byID[id]
	if !ok {
		tally = &clientTally{id: id}
		b.byID[id] = tally
		b.clients = append(b.clients, tally)
	}

	tally.metrics++

	// Later metrics fill in identity tags the first one may have lacked.
	if tags.mac != "" {
		tally.mac = tags.mac
	}
	if tags.ip != "" {
		tally.ip = tags.ip
	}
	if tags.host != "" {
		tally.host = tags.host
	}
}

// clientID picks the identity the dashboard looks a host up by: MAC first
// (stable across DHCP), then IP, then whatever the transport could tell us.
func clientID(tags tagInfo, fallbackID string) string {
	if tags.mac != "" {
		return normalizeMAC(tags.mac)
	}
	if tags.ip != "" {
		return tags.ip
	}
	return fallbackID
}

// normalizeMAC upper-cases the address so a Telegraf tag matches the host
// record regardless of which case the scanner or the operator typed.
func normalizeMAC(mac string) string {
	return strings.ToUpper(strings.TrimSpace(mac))
}

// buildMetricKey renders the METRIC- key for one metric and, in the same pass
// over the tags, pulls out the identity tags used for the ingest counters.
func buildMetricKey(name, tags json.RawMessage) (string, tagInfo, error) {
	dst := make([]byte, 0, 160)
	dst = append(dst, metricKeyPrefix...)

	var err error
	if dst, err = appendPyJSON(dst, name); err != nil {
		return "", tagInfo{}, err
	}

	dst = append(dst, `, "tags": `...)

	var info tagInfo
	if dst, err = appendTags(dst, tags, &info); err != nil {
		return "", tagInfo{}, err
	}

	return string(append(dst, '}')), info, nil
}

func appendTags(dst []byte, tags json.RawMessage, info *tagInfo) ([]byte, error) {
	trimmed := bytes.TrimSpace(tags)
	if len(trimmed) == 0 || trimmed[0] != '{' {
		// Telegraf always sends an object; anything else is still stored so
		// the metric is not lost, it just has no identity to count against.
		return appendPyJSON(dst, tags)
	}

	return appendPyObject(dst, trimmed, func(key string, value json.RawMessage) {
		switch key {
		case "mac":
			info.mac = jsonString(value)
		case "ip":
			info.ip = jsonString(value)
		case "host":
			info.host = jsonString(value)
		}
	})
}

// jsonString decodes a tag value when it is a string, and returns "" for any
// other JSON type rather than inventing an identity out of a number.
func jsonString(raw json.RawMessage) string {
	trimmed := bytes.TrimSpace(raw)
	if len(trimmed) == 0 || trimmed[0] != '"' {
		return ""
	}

	if isPlainASCIIString(trimmed) {
		return string(trimmed[1 : len(trimmed)-1])
	}

	var s string
	if err := json.Unmarshal(trimmed, &s); err != nil {
		return ""
	}

	return s
}
