# Changelog: Performance Issues

- Armada session: `Performance Issues`
- Branch: `armada/Performance-Issues-4bd5fb`
- Base branch: `master`
- Started: 2026-10-15 05:01 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-15 00:34 CDT
Fix the main cause of Labyrinth's slowness and MCP hangs: per-host metric reads
(`read_metrics` - host pages, every service history graph, `mcp_read_metrics`)
filtered with `tags->'ip' = ...`, which the GIN index on `tags` cannot serve, so
each read scanned the whole 30-day metrics hypertable. For a host or service with
few or no rows that never stops early - over 5 minutes in production, 43s on a
3.6M-row local copy. The Postgres adapter now matches the identity tags
(`host`/`ip`/`mac`) with indexed `tags @>` containment: 43s -> 8ms locally, with
dense host+service reads unchanged (~0.2s). No schema change.

The MCP server ran every blocking DB call inline inside `async def` tools, so one
slow call froze the event loop and timed out every other MCP request. Tools now run
on worker threads, capped at the DB pool size (raised to 4 for `mcp`).

Production `backend` and `mcp` now set `statement_timeout` (110s, just under
gunicorn's 120s), so queries orphaned by killed workers stop piling up as
concurrent full scans.

## 2026-10-15 01:59 CDT
Schema bootstrap now runs its DDL only when a table or index is missing (checked
with lock-free catalog lookups). Every process start - each per-minute cron job -
used to run `CREATE INDEX IF NOT EXISTS`, whose SHARE locks queued metric writes and
starved autovacuum's ANALYZE (`skipping analyze of "metrics_latest" --- lock not
available` in the Postgres logs). Adding a relation to the bootstrap later still
triggers the full run on existing installs.

Redis now persists to a named `redis_data` volume in both compose files. Its
append-only file previously lived in the container layer: lost on recreate,
rewritten from near-empty (the "6727531600% growth" AOF rewrite in the logs). A
named volume rather than `./redis_data` because bitnami runs as uid 1001 and
cannot write a root-owned bind mount.

## 2026-10-15 02:36 CDT
Post-deploy check: Postgres ran parallel plans for large metric reads (e.g. the
1000-row service history graph), and every parallel worker died with `could not
resize shared memory segment ... No space left on device` - Docker's default 64MB
`/dev/shm`. Postgres now gets `shm_size: 1g` in both compose files.

## 2026-10-15 03:09 CDT
Post-deploy, `mcp_read_metrics` for a host with no metrics still hit the 110s
statement timeout. Postgres ran the new indexed filter, but with `ORDER BY id
LIMIT 5` the planner walked the whole id index. The query shape alone can't fix
that, so (approved schema addition) btree indexes on `((tags->>'host'|'ip'|'mac'),
id)` are now built by the nightly compaction job, one chunk per transaction. They
are not built at startup, because each build takes minutes on a populated table.
With a limit, the adapter now runs each host/ip/mac branch as its own ordered
index scan and merges them, with bitmap and parallel scans off for those
statements only. On 6M local rows every case (empty, sparse, dense host; limit 5
to 1000) takes 5-260 ms warm, against 60s+ before. **Run the index build once
right after deploying** - see "Per-host metric reads" in MONGO_MIGRATION.md.

## 2026-10-17 02:33 CDT
Metric timestamps are now real UTC. `bulk_insert` stored `datetime.fromtimestamp()`
(container local time) in a UTC column, and `judge()` read it back with
`.timestamp()` (local again). The two shifts cancelled out inside the app, but
every stored metric was 5 hours off under `TZ=America/Chicago`, which skewed
retention cutoffs, chunk boundaries and outside readers like the MCP. A naive
datetime now means UTC everywhere, through the new `backend/common/utc.py`:
- bulk_insert, the dashboard's float->datetime conversion, and the Postgres
  adapter's numeric/default timestamps
- judge()/judge_port(), the read_metrics sort
- the metrics-latest TTL sweep, the compaction cutoff, and the Proxmox
  Telegraf/Graylog staleness cutoffs

The Proxmox disk and EC2 emails, which printed local time labelled "UTC", now
print UTC. The four frontend spots that printed raw naive strings now render
local time through `Helper.formatUTC()`. Per the user, rows stored before the fix
keep their offset and age out through retention.
