# Changelog: Scanning

- Armada session: `Scanning`
- Branch: `armada/Scanning-4387b6`
- Base branch: `master`
- Started: 2026-09-03 18:27 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-09-03 14:56 CDT
Fixed port scanning stalling out and scan results going missing.

`finder.py`: worker threads could die on any exception raised outside the small
per-host `try/except` (an empty subnet made the ping parser raise `KeyError:
'host'`, and a missing Redis output key made the progress callback raise
`AttributeError`). A dead worker never requeued its subnet, so subnets leaked out
of the queue one at a time until the survivors blocked forever on an empty queue
while still holding the `labyrinth-finder` pid file - which meant cron could
never start a replacement and scanning stopped entirely until the container was
restarted. Workers now always requeue in a `finally`, the ping sweep tolerates a
subnet with no live hosts, and the progress callback can no longer raise. The
port scan also gained `-T4 --max-retries 2 --host-timeout 15m` so one firewalled
host can't hold a 2500-port connect scan open for hours, plus a rescan delay, a
capped/expiring Redis scan log, and a max process lifetime so a wedged run heals
itself on the next cron tick. `/scan/` now runs a single pass instead of
submitting the never-returning loop into the backend's two-thread executor.

`serve.py` (`bulk_insert`): the Redis-to-Mongo throttle was keyed on the host's
IP, so the first metric series drained for a host suppressed every *other* series
for that host in the same pass. With Telegraf posting many series per host, the
finder's `open_ports` metric usually lost that race and expired out of Redis
unwritten - the reason port data only refreshed about once a day. The throttle is
now per metric series. Also fixed `bulk_insert` aborting the whole batch on a
metric with no tags, an expired key, or unparseable JSON.
