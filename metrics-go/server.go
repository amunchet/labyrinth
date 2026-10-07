package main

import (
	"compress/gzip"
	"context"
	"crypto/subtle"
	"errors"
	"io"
	"log"
	"net"
	"net/http"
	"strings"
	"sync/atomic"
	"time"

	"github.com/redis/go-redis/v9"
)

// Server accepts Telegraf batches and turns each one into a single pipelined
// Redis round trip.  The Flask endpoint it replaces built a fresh connection
// pool per metric, which is what pushed a 100-200 host network into timeouts.
type Server struct {
	cfg    Config
	rdb    redis.UniversalClient
	logger *log.Logger
	stats  stats

	// now is swappable so tests can pin the minute bucket.
	now func() time.Time
}

type stats struct {
	requests     atomic.Int64
	metrics      atomic.Int64
	unauthorized atomic.Int64
	failures     atomic.Int64
}

func NewServer(cfg Config, rdb redis.UniversalClient, logger *log.Logger) *Server {
	return &Server{cfg: cfg, rdb: rdb, logger: logger, now: time.Now}
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Single-purpose service: everything that is not the health probe is an
	// ingest POST, whatever path Telegraf was pointed at ("/metrics/" through
	// Caddy, "/" for agents aimed straight at the container).
	if r.URL.Path == "/health" {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, "ok")
		return
	}

	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	s.handleIngest(w, r)
}

func (s *Server) handleIngest(w http.ResponseWriter, r *http.Request) {
	if !s.authorized(r) {
		s.stats.unauthorized.Add(1)
		http.Error(w, "Invalid Header", http.StatusUnauthorized)
		return
	}

	body, closeBody, err := s.bodyReader(w, r)
	if err != nil {
		s.stats.failures.Add(1)
		http.Error(w, "Invalid body encoding", http.StatusBadRequest)
		return
	}
	defer closeBody()

	batch, err := parseBatch(body, "remote:"+clientIP(r))
	switch {
	case errors.Is(err, errNoMetricsField):
		s.stats.failures.Add(1)
		http.Error(w, "Invalid data", http.StatusMisdirectedRequest)
		return
	case isBodyTooLarge(err):
		s.stats.failures.Add(1)
		http.Error(w, "Payload too large", http.StatusRequestEntityTooLarge)
		return
	case err != nil:
		s.stats.failures.Add(1)
		s.logger.Printf("rejecting batch from %s: %v", clientIP(r), err)
		http.Error(w, "Invalid data", http.StatusBadRequest)
		return
	}

	// Deliberately not r.Context(): a Telegraf-side timeout must not cancel a
	// write that is already in flight, or the metric is lost on both ends.
	ctx, cancel := context.WithTimeout(context.Background(), s.cfg.RedisTimeout)
	defer cancel()

	if err := s.write(ctx, batch); err != nil {
		s.stats.failures.Add(1)
		s.logger.Printf("redis write failed for %s: %v", clientIP(r), err)
		// 5xx so Telegraf keeps the batch buffered and retries.
		http.Error(w, "Storage unavailable", http.StatusInternalServerError)
		return
	}

	s.stats.requests.Add(1)
	s.stats.metrics.Add(batch.received)

	if s.cfg.LogRequests {
		s.logger.Printf("stored %d/%d metrics from %s", len(batch.writes), batch.received, describeClients(batch))
	}

	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = io.WriteString(w, "Success")
}

// write pushes the whole batch - metrics and counters alike - in one pipeline.
func (s *Server) write(ctx context.Context, batch *parsedBatch) error {
	if len(batch.writes) == 0 && len(batch.clients) == 0 {
		return nil
	}

	pipe := s.rdb.Pipeline()

	for _, metric := range batch.writes {
		pipe.Set(ctx, metric.key, metric.value, s.cfg.MetricTTL)
	}

	s.queueCounters(ctx, pipe, batch, s.now())

	_, err := pipe.Exec(ctx)
	return err
}

// authorized reproduces serve.py's requires_header check, in constant time.
func (s *Server) authorized(r *http.Request) bool {
	provided := r.Header.Get("Authorization")
	return subtle.ConstantTimeCompare([]byte(provided), []byte(s.cfg.TelegrafKey)) == 1
}

// bodyReader caps the request size and transparently handles the gzip request
// encoding Telegraf can be configured to send.
func (s *Server) bodyReader(w http.ResponseWriter, r *http.Request) (io.Reader, func(), error) {
	limited := http.MaxBytesReader(w, r.Body, s.cfg.MaxBodyBytes)

	if !strings.Contains(strings.ToLower(r.Header.Get("Content-Encoding")), "gzip") {
		return limited, func() { _ = limited.Close() }, nil
	}

	unzipped, err := gzip.NewReader(limited)
	if err != nil {
		_ = limited.Close()
		return nil, func() {}, err
	}

	return unzipped, func() {
		_ = unzipped.Close()
		_ = limited.Close()
	}, nil
}

func isBodyTooLarge(err error) bool {
	var maxBytes *http.MaxBytesError
	return errors.As(err, &maxBytes)
}

// clientIP prefers the address Caddy forwards, since every request otherwise
// arrives from the proxy's container IP.
func clientIP(r *http.Request) string {
	if forwarded := r.Header.Get("X-Forwarded-For"); forwarded != "" {
		first, _, _ := strings.Cut(forwarded, ",")
		if first = strings.TrimSpace(first); first != "" {
			return first
		}
	}

	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}

	return host
}

func describeClients(batch *parsedBatch) string {
	ids := make([]string, 0, len(batch.clients))
	for _, client := range batch.clients {
		ids = append(ids, client.id)
	}
	return strings.Join(ids, ",")
}

// logStats emits a periodic summary instead of a line per request: at a few
// hundred agents, per-request logging is itself a load problem.
func (s *Server) logStats(ctx context.Context) {
	if s.cfg.StatsInterval <= 0 {
		return
	}

	ticker := time.NewTicker(s.cfg.StatsInterval)
	defer ticker.Stop()

	var lastRequests, lastMetrics int64

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			requests := s.stats.requests.Load()
			metrics := s.stats.metrics.Load()

			// Stay quiet while idle, but never sit on rejections: a key
			// mismatch shows up as nothing but 401s.
			if requests == lastRequests && s.stats.failures.Load() == 0 && s.stats.unauthorized.Load() == 0 {
				continue
			}

			s.logger.Printf(
				"last %s: %d requests, %d metrics (totals: %d requests, %d metrics, %d unauthorized, %d failed)",
				s.cfg.StatsInterval, requests-lastRequests, metrics-lastMetrics,
				requests, metrics, s.stats.unauthorized.Load(), s.stats.failures.Load(),
			)

			lastRequests, lastMetrics = requests, metrics
		}
	}
}
