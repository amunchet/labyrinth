package main

import (
	"bytes"
	"compress/gzip"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

const testKey = "super-secret-telegraf-key"

// frozenNow pins the minute bucket so the counter keys are predictable.
var frozenNow = time.Unix(1753988580, 0).UTC()

func newTestServer(t *testing.T) (*Server, *miniredis.Miniredis) {
	t.Helper()

	mr := miniredis.RunT(t)

	cfg := LoadConfig(func(key string) (string, bool) {
		switch key {
		case "TELEGRAF_KEY":
			return testKey, true
		case "REDIS_ADDR":
			return mr.Addr(), true
		}
		return "", false
	}, nil)

	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = rdb.Close() })

	server := NewServer(cfg, rdb, log.New(io.Discard, "", 0))
	server.now = func() time.Time { return frozenNow }

	return server, mr
}

func post(t *testing.T, server *Server, body string, decorate func(*http.Request)) *httptest.ResponseRecorder {
	t.Helper()

	request := httptest.NewRequest(http.MethodPost, "/metrics/", strings.NewReader(body))
	request.Header.Set("Authorization", testKey)
	if decorate != nil {
		decorate(request)
	}

	recorder := httptest.NewRecorder()
	server.ServeHTTP(recorder, request)

	return recorder
}

func TestIngestStoresMetricsAndCounters(t *testing.T) {
	server, mr := newTestServer(t)

	response := post(t, server, telegrafBatch, nil)
	if response.Code != http.StatusOK {
		t.Fatalf("status %d, body %q", response.Code, response.Body.String())
	}
	if response.Body.String() != "Success" {
		t.Errorf("body %q, want Success", response.Body.String())
	}

	metricKey := `METRIC-{"name": "cpu", "tags": {"mac": "02:42:ac:13:00:02", "host": "web01", "ip": "172.19.0.2"}}`
	stored, err := mr.Get(metricKey)
	if err != nil {
		t.Fatalf("metric key missing: %v", err)
	}
	if !strings.Contains(stored, `"usage_idle":97.4`) {
		t.Errorf("unexpected stored value %q", stored)
	}
	if ttl := mr.TTL(metricKey); ttl != 120*time.Second {
		t.Errorf("ttl %s, want 120s (bulk_write.sh relies on it)", ttl)
	}

	counter := counterKey("02:42:AC:13:00:02")
	if got := mr.HGet(counter, fieldRequests); got != "1" {
		t.Errorf("requests %q, want 1", got)
	}
	if got := mr.HGet(counter, fieldMetrics); got != "2" {
		t.Errorf("metrics %q, want 2", got)
	}
	if got := mr.HGet(counter, fieldLastBatch); got != "2" {
		t.Errorf("last_batch %q, want 2", got)
	}
	if got := mr.HGet(counter, fieldIP); got != "172.19.0.2" {
		t.Errorf("ip %q, want 172.19.0.2", got)
	}
	if got := mr.HGet(counter, fieldMAC); got != "02:42:AC:13:00:02" {
		t.Errorf("mac %q, want the normalised MAC", got)
	}
	if got := mr.HGet(counter, fieldHost); got != "web01" {
		t.Errorf("host %q, want web01", got)
	}

	seen := strconv.FormatInt(frozenNow.Unix(), 10)
	if got := mr.HGet(counter, fieldFirstSeen); got != seen {
		t.Errorf("first_seen %q, want %s", got, seen)
	}
	if got := mr.HGet(counter, fieldLastSeen); got != seen {
		t.Errorf("last_seen %q, want %s", got, seen)
	}

	minute := frozenNow.Unix() / 60
	if got, _ := mr.Get(bucketKey("02:42:AC:13:00:02", minute, "r")); got != "1" {
		t.Errorf("request bucket %q, want 1", got)
	}
	if got, _ := mr.Get(bucketKey("02:42:AC:13:00:02", minute, "m")); got != "2" {
		t.Errorf("metric bucket %q, want 2", got)
	}
	if ttl := mr.TTL(bucketKey("02:42:AC:13:00:02", minute, "r")); ttl != 65*time.Minute {
		t.Errorf("bucket ttl %s, want 65m", ttl)
	}
}

func TestIngestAccumulatesAcrossRequests(t *testing.T) {
	server, mr := newTestServer(t)

	for i := 0; i < 3; i++ {
		if response := post(t, server, telegrafBatch, nil); response.Code != http.StatusOK {
			t.Fatalf("request %d: status %d", i, response.Code)
		}
	}

	counter := counterKey("02:42:AC:13:00:02")
	if got := mr.HGet(counter, fieldRequests); got != "3" {
		t.Errorf("requests %q, want 3", got)
	}
	if got := mr.HGet(counter, fieldMetrics); got != "6" {
		t.Errorf("metrics %q, want 6", got)
	}

	minute := frozenNow.Unix() / 60
	if got, _ := mr.Get(bucketKey("02:42:AC:13:00:02", minute, "r")); got != "3" {
		t.Errorf("request bucket %q, want 3", got)
	}
}

func TestIngestCountsSkippedMetrics(t *testing.T) {
	server, mr := newTestServer(t)

	body := `{"metrics":[
		{"name":"ok","tags":{"mac":"AA:BB:CC:DD:EE:FF"},"fields":{}},
		{"fields":{"x":1}}
	]}`

	if response := post(t, server, body, nil); response.Code != http.StatusOK {
		t.Fatalf("status %d", response.Code)
	}

	if got := mr.HGet(counterKey("AA:BB:CC:DD:EE:FF"), fieldSkipped); got != "1" {
		t.Errorf("skipped %q, want 1", got)
	}
}

func TestIngestRejectsBadKey(t *testing.T) {
	server, mr := newTestServer(t)

	for _, test := range []struct {
		label string
		value string
	}{
		{"wrong key", "nope"},
		{"missing key", ""},
		{"prefix of the real key", testKey[:5]},
	} {
		t.Run(test.label, func(t *testing.T) {
			response := post(t, server, telegrafBatch, func(r *http.Request) {
				r.Header.Set("Authorization", test.value)
			})
			if response.Code != http.StatusUnauthorized {
				t.Errorf("status %d, want 401", response.Code)
			}
		})
	}

	if len(mr.Keys()) != 0 {
		t.Errorf("unauthorized requests wrote to redis: %v", mr.Keys())
	}
}

func TestIngestAcceptsGzip(t *testing.T) {
	server, mr := newTestServer(t)

	var compressed bytes.Buffer
	writer := gzip.NewWriter(&compressed)
	if _, err := writer.Write([]byte(telegrafBatch)); err != nil {
		t.Fatalf("gzip write: %v", err)
	}
	if err := writer.Close(); err != nil {
		t.Fatalf("gzip close: %v", err)
	}

	request := httptest.NewRequest(http.MethodPost, "/metrics/", bytes.NewReader(compressed.Bytes()))
	request.Header.Set("Authorization", testKey)
	request.Header.Set("Content-Encoding", "gzip")

	recorder := httptest.NewRecorder()
	server.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status %d, body %q", recorder.Code, recorder.Body.String())
	}
	if got := mr.HGet(counterKey("02:42:AC:13:00:02"), fieldMetrics); got != "2" {
		t.Errorf("metrics %q, want 2", got)
	}
}

func TestIngestRejectsCorruptGzip(t *testing.T) {
	server, _ := newTestServer(t)

	response := post(t, server, "definitely not gzip", func(r *http.Request) {
		r.Header.Set("Content-Encoding", "gzip")
	})
	if response.Code != http.StatusBadRequest {
		t.Errorf("status %d, want 400", response.Code)
	}
}

func TestIngestInvalidPayloads(t *testing.T) {
	server, _ := newTestServer(t)

	tests := []struct {
		label string
		body  string
		want  int
	}{
		// serve.py answers 421 for a body with no metrics array; keeping the
		// code identical means dashboards and agent logs read the same.
		{"no metrics array", `{"agent":"telegraf"}`, http.StatusMisdirectedRequest},
		{"malformed json", `{"metrics":[`, http.StatusBadRequest},
		{"empty body", ``, http.StatusBadRequest},
	}

	for _, test := range tests {
		t.Run(test.label, func(t *testing.T) {
			if response := post(t, server, test.body, nil); response.Code != test.want {
				t.Errorf("status %d, want %d", response.Code, test.want)
			}
		})
	}
}

func TestIngestRejectsOversizedBody(t *testing.T) {
	server, _ := newTestServer(t)
	server.cfg.MaxBodyBytes = 32

	response := post(t, server, telegrafBatch, nil)
	if response.Code != http.StatusRequestEntityTooLarge {
		t.Errorf("status %d, want 413", response.Code)
	}
}

func TestIngestReportsRedisFailure(t *testing.T) {
	server, mr := newTestServer(t)
	mr.Close()

	response := post(t, server, telegrafBatch, nil)
	// 5xx keeps the batch in Telegraf's buffer for the next flush.
	if response.Code != http.StatusInternalServerError {
		t.Errorf("status %d, want 500", response.Code)
	}
}

func TestCountersCanBeDisabled(t *testing.T) {
	server, mr := newTestServer(t)
	server.cfg.CountersEnabled = false

	if response := post(t, server, telegrafBatch, nil); response.Code != http.StatusOK {
		t.Fatalf("status %d", response.Code)
	}

	if mr.Exists(counterKey("02:42:AC:13:00:02")) {
		t.Error("counters were written even though they are disabled")
	}
	if !mr.Exists(`METRIC-{"name": "cpu", "tags": {"mac": "02:42:ac:13:00:02", "host": "web01", "ip": "172.19.0.2"}}`) {
		t.Error("metrics should still be stored when counters are off")
	}
}

func TestEmptyBatchIsAccepted(t *testing.T) {
	server, mr := newTestServer(t)

	if response := post(t, server, `{"metrics":[]}`, nil); response.Code != http.StatusOK {
		t.Fatalf("status %d", response.Code)
	}
	if len(mr.Keys()) != 0 {
		t.Errorf("empty batch wrote %v", mr.Keys())
	}
}

func TestHealthAndMethodHandling(t *testing.T) {
	server, _ := newTestServer(t)

	recorder := httptest.NewRecorder()
	server.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/health", nil))
	if recorder.Code != http.StatusOK || recorder.Body.String() != "ok" {
		t.Errorf("health returned %d %q", recorder.Code, recorder.Body.String())
	}

	recorder = httptest.NewRecorder()
	server.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/metrics/", nil))
	if recorder.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET /metrics/ returned %d, want 405", recorder.Code)
	}
	if allow := recorder.Header().Get("Allow"); allow != http.MethodPost {
		t.Errorf("Allow header %q, want POST", allow)
	}
}

func TestIngestAcceptsAnyPath(t *testing.T) {
	// Older per-host Telegraf configs post to the container root rather than
	// to /metrics/, so the path must not be part of the contract.
	server, mr := newTestServer(t)

	request := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(telegrafBatch))
	request.Header.Set("Authorization", testKey)

	recorder := httptest.NewRecorder()
	server.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status %d", recorder.Code)
	}
	if !mr.Exists(counterKey("02:42:AC:13:00:02")) {
		t.Error("expected the batch to be counted")
	}
}

func TestUnlabelledClientFallsBackToForwardedAddress(t *testing.T) {
	server, mr := newTestServer(t)

	body := `{"metrics":[{"name":"cpu","fields":{"x":1}}]}`
	response := post(t, server, body, func(r *http.Request) {
		r.Header.Set("X-Forwarded-For", "192.168.5.20, 10.0.0.1")
	})
	if response.Code != http.StatusOK {
		t.Fatalf("status %d", response.Code)
	}

	if !mr.Exists(counterKey("remote:192.168.5.20")) {
		t.Errorf("expected a counter for the forwarded address, got %v", mr.Keys())
	}
}

func TestClientIPSources(t *testing.T) {
	tests := []struct {
		label      string
		remoteAddr string
		forwarded  string
		want       string
	}{
		{"forwarded wins", "10.0.0.1:5000", "192.168.5.20", "192.168.5.20"},
		{"forwarded list takes the first hop", "10.0.0.1:5000", " 192.168.5.20 , 10.0.0.1", "192.168.5.20"},
		{"empty forwarded falls through", "10.0.0.1:5000", " , ", "10.0.0.1"},
		{"remote address without a port", "10.0.0.1", "", "10.0.0.1"},
	}

	for _, test := range tests {
		t.Run(test.label, func(t *testing.T) {
			request := httptest.NewRequest(http.MethodPost, "/", nil)
			request.RemoteAddr = test.remoteAddr
			if test.forwarded != "" {
				request.Header.Set("X-Forwarded-For", test.forwarded)
			}

			if got := clientIP(request); got != test.want {
				t.Errorf("got %q, want %q", got, test.want)
			}
		})
	}
}

// A full Telegraf flush has to stay a single Redis round trip; this is the
// property the whole service exists for.
func BenchmarkIngestBatch(b *testing.B) {
	mr := miniredis.RunT(b)
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	defer func() { _ = rdb.Close() }()

	cfg := LoadConfig(func(string) (string, bool) { return "", false }, nil)
	cfg.TelegrafKey = testKey
	server := NewServer(cfg, rdb, log.New(io.Discard, "", 0))

	var payload strings.Builder
	payload.WriteString(`{"metrics":[`)
	for i := 0; i < 1000; i++ {
		if i > 0 {
			payload.WriteByte(',')
		}
		payload.WriteString(`{"fields":{"value":`)
		payload.WriteString(strconv.Itoa(i))
		payload.WriteString(`},"name":"cpu`)
		payload.WriteString(strconv.Itoa(i))
		payload.WriteString(`","tags":{"mac":"02:42:AC:13:00:02","ip":"172.19.0.2"},"timestamp":1625683390}`)
	}
	payload.WriteString(`]}`)
	body := payload.String()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		request := httptest.NewRequest(http.MethodPost, "/metrics/", strings.NewReader(body))
		request.Header.Set("Authorization", testKey)
		recorder := httptest.NewRecorder()
		server.ServeHTTP(recorder, request)
		if recorder.Code != http.StatusOK {
			b.Fatalf("status %d", recorder.Code)
		}
	}
}
