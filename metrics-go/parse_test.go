package main

import (
	"errors"
	"strconv"
	"strings"
	"testing"
)

const telegrafBatch = `{"metrics":[
	{"fields":{"usage_idle":97.4},"name":"cpu","tags":{"mac":"02:42:ac:13:00:02","host":"web01","ip":"172.19.0.2"},"timestamp":1625683390},
	{"fields":{"used_percent":41.2},"name":"mem","tags":{"mac":"02:42:ac:13:00:02","host":"web01","ip":"172.19.0.2"},"timestamp":1625683390}
]}`

func TestParseBatchStoresEveryMetric(t *testing.T) {
	batch, err := parseBatch(strings.NewReader(telegrafBatch), "remote:127.0.0.1")
	if err != nil {
		t.Fatalf("parseBatch: %v", err)
	}

	if len(batch.writes) != 2 {
		t.Fatalf("expected 2 writes, got %d", len(batch.writes))
	}
	if batch.received != 2 || batch.skipped != 0 {
		t.Errorf("received=%d skipped=%d, want 2/0", batch.received, batch.skipped)
	}

	want := `METRIC-{"name": "cpu", "tags": {"mac": "02:42:ac:13:00:02", "host": "web01", "ip": "172.19.0.2"}}`
	if batch.writes[0].key != want {
		t.Errorf("key mismatch\n got: %s\nwant: %s", batch.writes[0].key, want)
	}

	// The stored value has to be the untouched metric, since bulk_insert
	// json.loads() it straight back out again.
	if !strings.Contains(string(batch.writes[0].value), `"usage_idle":97.4`) {
		t.Errorf("value was rewritten: %s", batch.writes[0].value)
	}
}

func TestParseBatchTalliesOneClientPerAgent(t *testing.T) {
	batch, err := parseBatch(strings.NewReader(telegrafBatch), "remote:127.0.0.1")
	if err != nil {
		t.Fatalf("parseBatch: %v", err)
	}

	if len(batch.clients) != 1 {
		t.Fatalf("expected a single client, got %d", len(batch.clients))
	}

	client := batch.clients[0]
	if client.id != "02:42:AC:13:00:02" {
		t.Errorf("client id %q, want the upper-cased MAC", client.id)
	}
	if client.metrics != 2 {
		t.Errorf("client metrics %d, want 2", client.metrics)
	}
	if client.ip != "172.19.0.2" || client.host != "web01" {
		t.Errorf("unexpected client identity: %+v", client)
	}
}

func TestParseBatchSeparatesClients(t *testing.T) {
	payload := `{"metrics":[
		{"name":"cpu","tags":{"mac":"AA:AA:AA:AA:AA:AA"},"fields":{}},
		{"name":"cpu","tags":{"ip":"10.0.0.9"},"fields":{}},
		{"name":"cpu","tags":{"mac":"aa:aa:aa:aa:aa:aa"},"fields":{}}
	]}`

	batch, err := parseBatch(strings.NewReader(payload), "remote:127.0.0.1")
	if err != nil {
		t.Fatalf("parseBatch: %v", err)
	}

	if len(batch.clients) != 2 {
		t.Fatalf("expected 2 clients, got %d", len(batch.clients))
	}
	// Case-insensitive MAC matching keeps one host from splitting in two.
	if batch.clients[0].id != "AA:AA:AA:AA:AA:AA" || batch.clients[0].metrics != 2 {
		t.Errorf("unexpected first client: %+v", batch.clients[0])
	}
	if batch.clients[1].id != "10.0.0.9" || batch.clients[1].metrics != 1 {
		t.Errorf("unexpected second client: %+v", batch.clients[1])
	}
}

func TestParseBatchSkipsMetricsWithoutNameOrTags(t *testing.T) {
	payload := `{"metrics":[
		{"measurement":"cpu","fields":{"x":1}},
		{"name":"cpu","fields":{"x":1}},
		{"tags":{"ip":"10.0.0.1"},"fields":{"x":1}},
		{"name":"ok","tags":{"ip":"10.0.0.1"},"fields":{"x":1}}
	]}`

	batch, err := parseBatch(strings.NewReader(payload), "remote:127.0.0.1")
	if err != nil {
		t.Fatalf("parseBatch: %v", err)
	}

	if len(batch.writes) != 1 {
		t.Errorf("expected only the complete metric to be stored, got %d", len(batch.writes))
	}
	if batch.received != 4 || batch.skipped != 3 {
		t.Errorf("received=%d skipped=%d, want 4/3", batch.received, batch.skipped)
	}

	// Unattributable metrics still get counted, under the transport address.
	fallback, ok := batch.byID["remote:127.0.0.1"]
	if !ok || fallback.metrics != 3 {
		t.Errorf("expected 3 metrics against the fallback id, got %+v", fallback)
	}
}

func TestParseBatchIgnoresOtherTopLevelKeys(t *testing.T) {
	payload := `{"agent":"telegraf","metrics":[{"name":"cpu","tags":{"ip":"1.1.1.1"},"fields":{}}],"trailing":{"a":[1,2]}}`

	batch, err := parseBatch(strings.NewReader(payload), "remote:127.0.0.1")
	if err != nil {
		t.Fatalf("parseBatch: %v", err)
	}
	if len(batch.writes) != 1 {
		t.Errorf("expected 1 write, got %d", len(batch.writes))
	}
}

func TestParseBatchErrors(t *testing.T) {
	tests := []struct {
		label   string
		payload string
		wantErr error
	}{
		{"no metrics key", `{"agent":"telegraf"}`, errNoMetricsField},
		{"empty object", `{}`, errNoMetricsField},
		{"not an object", `[1,2,3]`, nil},
		{"metrics is not an array", `{"metrics":{"name":"cpu"}}`, nil},
		{"truncated", `{"metrics":[{"name":"cpu"`, nil},
		{"garbage", `not json at all`, nil},
		{"empty body", ``, nil},
	}

	for _, test := range tests {
		t.Run(test.label, func(t *testing.T) {
			_, err := parseBatch(strings.NewReader(test.payload), "remote:127.0.0.1")
			if err == nil {
				t.Fatal("expected an error")
			}
			if test.wantErr != nil && !errors.Is(err, test.wantErr) {
				t.Fatalf("got %v, want %v", err, test.wantErr)
			}
		})
	}
}

func TestParseBatchEmptyMetricsArray(t *testing.T) {
	batch, err := parseBatch(strings.NewReader(`{"metrics":[]}`), "remote:127.0.0.1")
	if err != nil {
		t.Fatalf("parseBatch: %v", err)
	}
	if len(batch.writes) != 0 || len(batch.clients) != 0 {
		t.Errorf("expected nothing to store, got %+v", batch)
	}
}

func TestClientIDPrecedence(t *testing.T) {
	tests := []struct {
		label string
		tags  tagInfo
		want  string
	}{
		{"mac wins", tagInfo{mac: "aa:bb", ip: "1.2.3.4", host: "h"}, "AA:BB"},
		{"ip when there is no mac", tagInfo{ip: "1.2.3.4", host: "h"}, "1.2.3.4"},
		{"fallback when unlabelled", tagInfo{host: "h"}, "remote:9.9.9.9"},
	}

	for _, test := range tests {
		t.Run(test.label, func(t *testing.T) {
			if got := clientID(test.tags, "remote:9.9.9.9"); got != test.want {
				t.Errorf("got %q, want %q", got, test.want)
			}
		})
	}
}

// BenchmarkParseBatch measures the CPU cost of a full Telegraf flush
// (metric_batch_size defaults to 1000) with Redis taken out of the picture.
func BenchmarkParseBatch(b *testing.B) {
	var payload strings.Builder
	payload.WriteString(`{"metrics":[`)
	for i := 0; i < 1000; i++ {
		if i > 0 {
			payload.WriteByte(',')
		}
		payload.WriteString(`{"fields":{"usage_idle":97.4,"usage_user":1.2},"name":"cpu","tags":{"mac":"02:42:AC:13:00:02","host":"web01","ip":"172.19.0.2","cpu":"cpu`)
		payload.WriteString(strconv.Itoa(i))
		payload.WriteString(`"},"timestamp":1625683390}`)
	}
	payload.WriteString(`]}`)
	body := payload.String()

	b.SetBytes(int64(len(body)))
	b.ReportAllocs()
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		if _, err := parseBatch(strings.NewReader(body), "remote:127.0.0.1"); err != nil {
			b.Fatal(err)
		}
	}
}
