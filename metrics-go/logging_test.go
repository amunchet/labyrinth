package main

import (
	"bytes"
	"context"
	"log"
	"strings"
	"sync"
	"testing"
	"time"
)

// syncBuffer collects log output from the stats goroutine without racing the
// test that reads it.
type syncBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (s *syncBuffer) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.buf.Write(p)
}

func (s *syncBuffer) String() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.buf.String()
}

func TestLogRequestsNamesTheClient(t *testing.T) {
	server, _ := newTestServer(t)

	output := &syncBuffer{}
	server.logger = log.New(output, "", 0)
	server.cfg.LogRequests = true

	post(t, server, telegrafBatch, nil)

	logged := output.String()
	if !strings.Contains(logged, "02:42:AC:13:00:02") {
		t.Errorf("log line does not name the client: %q", logged)
	}
	if !strings.Contains(logged, "stored 2/2 metrics") {
		t.Errorf("log line does not report the batch size: %q", logged)
	}
}

func TestLogStatsSummarisesAndStops(t *testing.T) {
	server, _ := newTestServer(t)

	output := &syncBuffer{}
	server.logger = log.New(output, "", 0)
	server.cfg.StatsInterval = 5 * time.Millisecond

	server.stats.requests.Add(4)
	server.stats.metrics.Add(40)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	stopped := make(chan struct{})
	go func() {
		server.logStats(ctx)
		close(stopped)
	}()

	deadline := time.Now().Add(5 * time.Second)
	for !strings.Contains(output.String(), "4 requests, 40 metrics") {
		if time.Now().After(deadline) {
			t.Fatalf("no summary was logged: %q", output.String())
		}
		time.Sleep(time.Millisecond)
	}

	// Idle ticks stay quiet so a healthy stack does not fill the log.
	quiet := output.String()
	time.Sleep(50 * time.Millisecond)
	if output.String() != quiet {
		t.Errorf("expected silence while idle, got %q", output.String())
	}

	cancel()
	select {
	case <-stopped:
	case <-time.After(2 * time.Second):
		t.Fatal("logStats ignored context cancellation")
	}
}

func TestLogStatsDisabled(t *testing.T) {
	server, _ := newTestServer(t)
	server.cfg.StatsInterval = 0

	// Returns immediately rather than spinning on a zero-duration ticker.
	done := make(chan struct{})
	go func() {
		server.logStats(context.Background())
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("logStats should return when the interval is disabled")
	}
}
