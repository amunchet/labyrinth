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
