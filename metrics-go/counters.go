package main

// Per-client ingest counters.
//
// These answer "which host is hammering the endpoint?" from the host's own
// settings panel.  Two things are recorded per agent: running totals that
// survive restarts, and one-minute buckets that expire on their own so the
// dashboard can show the recent rate without any pruning job.
//
// The key prefix deliberately avoids METRIC-: cron/bulk_write.sh does
// `KEYS METRIC-*` and then GETs every result, so a hash under that prefix
// would break the bulk writer with a WRONGTYPE error.
//
// backend/ingest_counters.py reads these keys; the two files have to agree.

import (
	"context"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	// counterKeyPrefix + client id -> hash of running totals.
	counterKeyPrefix = "ingest:count:"
	// bucketKeyPrefix + client id + ":" + minute -> per-minute counters,
	// suffixed with :r for requests and :m for metrics.
	bucketKeyPrefix = "ingest:min:"

	fieldRequests  = "requests"
	fieldMetrics   = "metrics"
	fieldSkipped   = "skipped"
	fieldFirstSeen = "first_seen"
	fieldLastSeen  = "last_seen"
	fieldLastBatch = "last_batch"
	fieldMAC       = "mac"
	fieldIP        = "ip"
	fieldHost      = "host"
)

func counterKey(clientID string) string {
	return counterKeyPrefix + clientID
}

// bucketKey names the counter for one client and one wall-clock minute.
// suffix is "r" (requests) or "m" (metrics).
func bucketKey(clientID string, minute int64, suffix string) string {
	return bucketKeyPrefix + clientID + ":" + strconv.FormatInt(minute, 10) + ":" + suffix
}

// queueCounters adds every counter update for a batch to the pipeline that is
// already carrying the metric writes, so counting costs no extra round trip.
func (s *Server) queueCounters(ctx context.Context, pipe redis.Pipeliner, batch *parsedBatch, now time.Time) {
	if !s.cfg.CountersEnabled {
		return
	}

	unix := now.Unix()
	minute := unix / 60
	seen := strconv.FormatInt(unix, 10)

	for _, client := range batch.clients {
		key := counterKey(client.id)

		pipe.HIncrBy(ctx, key, fieldRequests, 1)
		pipe.HIncrBy(ctx, key, fieldMetrics, client.metrics)

		identity := []any{
			fieldLastSeen, seen,
			fieldLastBatch, strconv.FormatInt(client.metrics, 10),
		}
		if client.mac != "" {
			identity = append(identity, fieldMAC, normalizeMAC(client.mac))
		}
		if client.ip != "" {
			identity = append(identity, fieldIP, client.ip)
		}
		if client.host != "" {
			identity = append(identity, fieldHost, client.host)
		}
		pipe.HSet(ctx, key, identity...)

		pipe.HSetNX(ctx, key, fieldFirstSeen, seen)
		pipe.Expire(ctx, key, s.cfg.CounterTTL)

		requestsBucket := bucketKey(client.id, minute, "r")
		pipe.IncrBy(ctx, requestsBucket, 1)
		pipe.Expire(ctx, requestsBucket, s.cfg.BucketTTL)

		metricsBucket := bucketKey(client.id, minute, "m")
		pipe.IncrBy(ctx, metricsBucket, client.metrics)
		pipe.Expire(ctx, metricsBucket, s.cfg.BucketTTL)
	}

	// Metrics dropped for missing name/tags are worth surfacing: a client
	// sending malformed batches looks identical to a healthy one otherwise.
	if batch.skipped > 0 && len(batch.clients) > 0 {
		pipe.HIncrBy(ctx, counterKey(batch.clients[0].id), fieldSkipped, batch.skipped)
	}
}
