# metrics-go - Telegraf ingest service

A small Go service that replaces the Flask `POST /metrics/` route for Telegraf
agents. It runs as the `metrics` container and Caddy routes `POST /api/metrics/`
to it; every other `/api/` route still goes to `backend:7000`.

## Why

`serve.py`'s handler looked like this:

```python
for item in data["metrics"]:
    a = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")   # per metric!
    a.set(f"METRIC-{name}", json.dumps(item, default=str))
    a.expire(f"METRIC-{name}", 120)
```

A Telegraf flush carries up to `metric_batch_size` (default 1000) metrics, so a
single request built up to 1000 Redis connection pools and issued 2000 round
trips inside one synchronous gunicorn worker. With 100-200 agents - all flushing
on the same tick, because `round_interval = true` and `flush_jitter = "0s"` -
workers stayed busy long enough for agents to give up with
`context deadline exceeded (Client.Timeout exceeded while awaiting headers)`.

Here a whole batch is **one pipelined Redis round trip**, on a shared pool.

## What it keeps identical

- The `Authorization: <TELEGRAF_KEY>` header check (now constant-time, and
  answered with 401 instead of a 500 from a raised exception).
- The Redis key: `METRIC-` followed by
  `json.dumps({"name": ..., "tags": ...}, default=str)`. `pyjson.go` reproduces
  CPython's formatting byte for byte - `", "`/`": "` separators, insertion
  order, `ensure_ascii=True` - so both implementations write the same key for
  the same metric and can run side by side or be rolled back cleanly.
- The stored value: the metric's own JSON, untouched.
- The 120 second expiry that `cron/bulk_write.sh` depends on.
- `421` for a body with no `metrics` array.

Additions: gzip request bodies, a request size cap, `GET /health`, and the
per-client counters below.

## Ingest counters

Written in the same pipeline as the metrics, so they cost no extra round trip.
Read back by `backend/ingest_counters.py` and shown in a host's settings modal.

| Key | Type | Contents |
| --- | --- | --- |
| `ingest:count:<client>` | hash | `requests`, `metrics`, `skipped`, `first_seen`, `last_seen`, `last_batch`, `mac`, `ip`, `host` |
| `ingest:min:<client>:<minute>:r` | int | requests in that wall-clock minute |
| `ingest:min:<client>:<minute>:m` | int | metrics in that wall-clock minute |

`<client>` is the metric's `mac` tag upper-cased, or its `ip` tag, or
`remote:<address>` for an agent whose metrics carry neither. `<minute>` is
`unix_seconds / 60`.

The prefix deliberately is **not** `METRIC-`: `bulk_insert` runs
`KEYS METRIC-*` and `GET`s every result, so a hash under that prefix would fail
the bulk writer with `WRONGTYPE`.

Buckets expire on their own (65 minutes by default), so the last hour of
history needs no pruning job. Totals expire 30 days after a client goes quiet.

## Configuration

Read from the process environment first, then from the dotenv file at
`LABYRINTH_ENV_FILE` (default `/backend/.env`, the same file python-dotenv
gives the Flask backend) - matching python-dotenv, an exported variable wins.

| Variable | Default | Notes |
| --- | --- | --- |
| `TELEGRAF_KEY` | `TEST` | Must match the backend's, same as `serve.py` |
| `METRICS_PORT` | `9000` | |
| `REDIS_HOST` / `REDIS_PORT` | `redis` / `6379` | Or set `REDIS_ADDR` directly |
| `REDIS_PASSWORD`, `REDIS_DB` | empty, `0` | |
| `REDIS_POOL_SIZE` | go-redis default (10x GOMAXPROCS) | |
| `METRIC_TTL_SECONDS` | `120` | Keep >= the `bulk_write.sh` cron interval |
| `INGEST_COUNTER_TTL_SECONDS` | `2592000` (30d) | |
| `INGEST_BUCKET_TTL_SECONDS` | `3900` (65m) | How much per-minute history the UI can show |
| `INGEST_COUNTERS_ENABLED` | `true` | |
| `MAX_BODY_BYTES` | `67108864` (64 MiB) | |
| `REDIS_TIMEOUT_SECONDS` | `5` | |
| `READ_TIMEOUT_SECONDS` / `WRITE_TIMEOUT_SECONDS` / `IDLE_TIMEOUT_SECONDS` | `30` / `30` / `120` | |
| `LOG_REQUESTS` | `false` | Per-request logging; noisy above a handful of agents |
| `STATS_INTERVAL_SECONDS` | `60` | Periodic throughput summary, silent while idle |
| `GOMAXPROCS` | all host cores | Go does not see container CPU limits; set it if you cap the container |

## Responses

| Status | When | Telegraf's reaction |
| --- | --- | --- |
| 200 `Success` | Stored | Batch dropped from the buffer |
| 401 | Wrong or missing `Authorization` | Non-retryable |
| 405 | Anything but POST (except `GET /health`) | Non-retryable |
| 400 | Body is not JSON / bad gzip | Non-retryable |
| 421 | No `metrics` array | Non-retryable |
| 413 | Body over `MAX_BODY_BYTES` | Non-retryable |
| 500 | Redis write failed | **Retried** - the batch stays buffered |

The Redis write runs on its own timeout rather than the request context, so an
agent hitting its own client timeout cannot cancel a write already in flight.

## Development

There is no Go toolchain in the stack's containers; use the official image:

```bash
cd metrics-go
docker run --rm -v "$PWD":/src -w /src golang:1.23-alpine \
  sh -c 'gofmt -l . && go vet ./... && go test ./... -cover'
```

Benchmarks (`go test -run=XXX -bench=. ./...`) cover a 1000-metric flush:
`BenchmarkParseBatch` is the pure CPU cost of parsing and key building,
`BenchmarkIngestBatch` the full handler against an in-process Redis. On a
Xeon E5-2667 a 1000-metric batch parses in ~29 ms (~29 us per metric), which at
a few hundred agents is a small fraction of one core.

If agents still bunch up, set `flush_jitter` in `uploads/master.conf`: with
`round_interval = true` and no jitter, every agent on the network flushes on the
same second.
