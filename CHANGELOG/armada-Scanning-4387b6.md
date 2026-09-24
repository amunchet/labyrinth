# Changelog: Scanning

- Armada session: `Scanning`
- Branch: `armada/Scanning-4387b6`
- Base branch: `master`
- Started: 2026-09-03 18:27 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-09-03 14:56 CDT
First pass at the scanning fixes, written against the pre-merge base. Master
had since landed its own scanning rework (one-pass finder, Redis run locks), so
most of this was superseded by the merge below; only the fixes master had not
already made were carried forward.

## 2026-09-03 15:09 CDT
Merged `master` and re-applied the scanning fixes that master had not already
made.

`finder.py`:
- The all-ports scan (`-sT -PU0 -Pn -p-`) had no timing template, retry cap, or
  host timeout. A host that silently drops packets spends the full retry budget
  on each of 65535 ports, so a single firewalled host held the pass open for
  hours - and since a pass, not cron, is the scan cadence (cron ticks are
  no-ops while the run lock is held), that is what stretched the interval
  between rescans out to about a day. Now `-T4 --max-retries 2 --host-timeout
  20m`, with the whole argument string env-overridable.
- The ping sweep raised `KeyError: 'host'` on a subnet where nothing answered
  and handed nmap an empty target list when the sweep found nobody, either of
  which cost the subnet its entire pass. Parsing moved into a tested
  `parse_ping_results`, the sweep got a timeout, and an empty subnet is now a
  normal empty result.
- `update_redis` did `rclient.get(key).decode()` and blew up on a missing key
  from inside the scan callback, aborting the subnet. It now appends (rather
  than rewriting the whole log each tick), is capped, carries a TTL, and never
  raises.
- The per-subnet lock was a plain `set(nx, ex=7200)` deleted unconditionally in
  a `finally`. A scan longer than the guessed TTL lost its lock mid-scan and
  then deleted the *next* scan's lock on its way out. It now uses the same
  heartbeat-extended `RedisSingleRunLock` as the global lock.

`serve.py`:
- `bulk_insert` keyed its Redis-to-database throttle on the host's IP, so the
  first metric series drained for a host suppressed every *other* series for
  that host in the same pass. With Telegraf posting many series per host, the
  finder's `open_ports` metric usually lost that race and expired out of Redis
  unwritten - port data reaching the dashboard roughly once a day even when
  scans completed. The throttle is now per metric series.
- `bulk_insert` also lost the whole batch to a metric with no tags (the guard
  ran after the dereference), an expired key, or unparseable JSON; each is now
  skipped individually. `read_redis` had the same expired-key crash.

## 2026-09-15 15:17 CDT
Each subnet now rescans continuously on its own, instead of every subnet
waiting for the slowest one before any of them gets another look.

`finder.py` used to be one pass per cron tick: scan every subnet once, exit,
and let the next tick start over. Since a pass only ended when its *slowest*
subnet finished, a five-minute subnet was rescanned as often as a two-hour
subnet. The finder is now a resident process (`scan_subnets(loop=True)`):
every subnet gets its own worker thread that rescans as soon as its previous
scan finishes (after `FINDER_RESCAN_DELAY_SECONDS`, default 60s - the floor
cron used to impose). `FINDER_THREADS` still caps how many subnets are inside
nmap at once, via a FIFO-fair `ScanSlots` so a fast subnet cycles through
without starving the queue (`0` = uncapped).

The resident design was previously removed because a fixed 3600s lock TTL
let a new immortal finder start every hour; the heartbeat-extended
`labyrinth_finder_lock` from the earlier fix is what makes a single resident
finder safe now - later cron ticks exit immediately. The process re-reads the
subnet list every minute (new subnets start, removed ones retire after their
current scan), and recycles itself after `FINDER_MAX_RUNTIME_SECONDS` (6h):
it hands the global lock back *before* draining so the next tick starts a
fresh finder with no gap, then gives in-flight scans
`FINDER_SHUTDOWN_GRACE_SECONDS` (2h) to finish; the per-subnet locks keep the
two processes off the same subnet. SIGTERM/SIGINT trigger the same drain.
`/scan/` runs `main(loop=False)` - one scan of each subnet - so it still
cannot park forever in the backend's executor.

Verified with the full backend suite against Postgres (1045 passed, coverage
95.28%); the only failures were `test_01_alertmanager`, which needs a live
alertmanager the throwaway test container did not have.
