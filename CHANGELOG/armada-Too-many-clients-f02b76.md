# Changelog: Too many clients

- Armada session: `Too many clients`
- Branch: `armada/Too-many-clients-f02b76`
- Base branch: `master`
- Started: 2026-08-07 20:06 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-08-07 20:50 UTC
Merged `origin/master` into the session branch (36 commits, including the
Postgres/TimescaleDB migration and the Go metrics ingest service). Resolved a
CLAUDE.md conflict by keeping both master's new `MONGO_MIGRATION.md` pointer
and the Armada session block.

## 2026-08-07 20:52 UTC
Fixed Postgres running out of connections (`FATAL: sorry, too many clients
already`) and made the Redis -> Postgres metrics transfer wait rather than
overlap.

Connection handling — four independent problems, all confirmed against a live
Postgres rather than reasoned about:

- The `timescale/timescaledb` image runs `timescaledb-tune` on first start,
  which sets `max_connections = 50`, not Postgres' usual 100. Nobody had
  budgeted against that number. Against it, 8 gunicorn workers + mcp + ~4
  overlapping cron jobs at the old hardcoded pool max of 5 is 65 connections
  of demand versus ~47 available — the stack could exhaust the server with no
  leak involved at all. Pool bounds are now `POSTGRES_POOL_MIN`/`_MAX`
  (default 1/2, so 26), and both compose files pin `max_connections`
  explicitly so the ceiling is a decision in the compose file instead of a
  side effect of the image and the host's RAM.
- `_PoolCursor.__enter__` set `autocommit` before the try/finally that returns
  the connection. On a dead pooled connection — which is *every* pooled
  connection after Postgres restarts, is OOM-killed, or fails over — that
  raises `InterfaceError` and the pool slot was lost permanently. Enough of
  those and the process could never reach Postgres again without a restart.
  Setup failures now discard the connection via `putconn(close=True)`.
  (An ordinary failed query was always safe; that path was never the bug.)
- `get_db()` builds a *new* client, and on Postgres a new pool that nothing
  closes. `ai_settings`/`proxmox_disk_check`/`ec2_unmatched_check`/
  `session_store` called it per invocation, so every AI-alert, disk and EC2
  test-email click from the UI added another permanent pool to a long-lived
  gunicorn worker. Application code now uses a process-wide client.
- `serve.py`'s module-level client was eager, so every cron entrypoint that
  imports `serve` merely to reuse a route handler (`finder.py`, `alive.py`,
  `serve.py updater`) opened a pool and ran the bootstrap DDL's advisory-lock
  transaction just to import — several times a minute, including on ticks
  that exit immediately on a contended lock. It is now a lazy proxy;
  `import serve` measurably opens zero connections.

Metrics transfer: replaced `pid.PidFile` on `bulk_insert` with a Redis lock
(`backend/common/single_run.py`). PidFile was wrong on two counts — it is
per-container, so two cron containers would each run their own "single"
transfer and double-write, and it *aborts* on contention rather than waiting,
dropping that window's transfer. The new lock uses a fencing token so an
overrunning run can't delete its successor's lock, a heartbeat so a long
transfer keeps its lock instead of losing it mid-run, and a TTL so a
SIGKILLed holder frees it within 120s. Waiting is capped at 240s (giving up
is not data loss — the metrics are still in Redis and the next tick retries),
which stops a stuck holder from piling up blocked cron processes. Because
`serve.db` is now lazy and `index_helper()` moved inside the lock, a waiting
tick holds no Postgres connections at all.

Tests: 24 new cases across `test_27_db_connections.py` (asserting against
`pg_stat_activity` through an independent observer connection, so they measure
real server-side backends rather than pool bookkeeping) and
`test_27_single_run.py`. The two pool-leak tests were verified to fail with
`PoolError` against the pre-fix code.
