// Command metrics is Labyrinth's Telegraf ingest endpoint.
//
// It is a drop-in replacement for the Flask "POST /metrics/" route: the same
// TELEGRAF_KEY header check, the same METRIC-<json> Redis entries with the same
// 120 second expiry, so cron/bulk_write.sh keeps draining Redis into MongoDB
// untouched.  What changes is the cost of accepting a batch.  serve.py built a
// new Redis connection pool for every metric in the payload and issued a SET
// plus an EXPIRE for each, so a 1000-metric Telegraf flush meant 1000 pools and
// 2000 round trips inside a synchronous gunicorn worker.  Here a batch is one
// pipelined round trip, which is what keeps agents from hitting their
// "context deadline exceeded" timeout.
//
// It also records per-client ingest counters (see counters.go) so the
// dashboard can point at whichever host is sending far more than its share.
package main

import (
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"runtime"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"
)

func main() {
	logger := log.New(os.Stdout, "[metrics] ", log.LstdFlags|log.LUTC)

	fileEnv, err := ReadEnvFile(os.Getenv(envFileVar))
	if err != nil {
		logger.Printf("WARNING: could not read %s: %v", os.Getenv(envFileVar), err)
	}

	cfg := LoadConfig(os.LookupEnv, fileEnv)

	if cfg.TelegrafKey == "TEST" {
		logger.Print("WARNING: TELEGRAF_KEY is unset, falling back to the development default - agents using a real key will get 401s")
	}

	rdb := redis.NewClient(&redis.Options{
		Addr:            cfg.RedisAddr,
		Password:        cfg.RedisPassword,
		DB:              cfg.RedisDB,
		PoolSize:        cfg.RedisPoolSize,
		DialTimeout:     cfg.RedisTimeout,
		ReadTimeout:     cfg.RedisTimeout,
		WriteTimeout:    cfg.RedisTimeout,
		MaxRetries:      2,
		MinIdleConns:    runtime.GOMAXPROCS(0),
		ConnMaxIdleTime: 5 * time.Minute,
	})
	defer func() { _ = rdb.Close() }()

	server := NewServer(cfg, rdb, logger)

	httpServer := &http.Server{
		Addr:              cfg.Addr,
		Handler:           server,
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       cfg.ReadTimeout,
		WriteTimeout:      cfg.WriteTimeout,
		IdleTimeout:       cfg.IdleTimeout,
		ErrorLog:          logger,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go server.logStats(ctx)

	go func() {
		<-ctx.Done()
		logger.Print("shutting down")

		shutdownCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()

		if err := httpServer.Shutdown(shutdownCtx); err != nil {
			logger.Printf("graceful shutdown failed: %v", err)
		}
	}()

	logger.Printf(
		"listening on %s (redis %s, metric ttl %s, counters %t, GOMAXPROCS %d)",
		cfg.Addr, cfg.RedisAddr, cfg.MetricTTL, cfg.CountersEnabled, runtime.GOMAXPROCS(0),
	)

	if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		logger.Fatalf("server error: %v", err)
	}

	logger.Print("stopped")
}
