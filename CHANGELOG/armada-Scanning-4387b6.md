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
