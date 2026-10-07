# Changelog: Scaling issue

- Armada session: `Scaling issue`
- Branch: `armada/Scaling-issue-57e998`
- Base branch: `master`
- Started: 2026-08-21 19:06 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-08-24 15:41 UTC
Evaluated the `no-mistakes` static-analysis CLI (v0.47.0) as a session tool. No
application code changed; this entry records the findings so they are not
rediscovered later.

- Installed globally in the session container along with its Claude Code skill,
  but deliberately **not** added to `frontend/labyrinth/package.json`. The
  package ships glibc-2.35+ Linux binaries only, so its postinstall exits 1 on
  musl/Alpine and would break `npm install` for anyone building on one. Running
  it here needed `--ignore-scripts`, a checksum-verified manual binary fetch
  from the GitHub release, and the `gcompat` shim.
- Its TS/JS module graph cannot parse `.vue` SFCs (it parses them as TypeScript
  and errors), so it reports nothing useful for the Vue 2 frontend.
- Its Python graph does work on `backend/` given a three-line
  `backend/.no-mistakes.yml` containing `tests.python.packages: ["."]`. With
  that, `no-mistakes tests plan python --changed-file proxmox_helper.py` selects
  23 of 32 test files at high confidence with no fallback, tracing real import
  paths (`proxmox_helper.py -> serve.py -> test/test_03_serve.py`). Potentially
  useful for trimming runs against the 95% coverage gate. The config file was
  tested and then removed; it is not part of this branch.

## 2026-08-24 12:39 CDT
Fixed the Postgres connection exhaustion: `finder.py` was a daemon being
launched by cron once a minute, so it accumulated one permanently-running
process per hour, each holding a database pool.

Diagnosed on the live stack. `ss` inside the Postgres container's network
namespace showed 113 connections from a single peer, climbing to 131 within
seconds; stopping the `samplecron` container dropped them all. The `backend`
container was healthy throughout at 8 idle connections (8 gunicorn workers x
`POSTGRES_POOL_MIN`), and `max_connections` was correctly 100 — so this was
neither the pool budget nor Telegraf ingest, which cannot reach Postgres at
all (`metrics-go` has no Postgres driver).

Two independent defects combined:

- `worker()` put each subnet **back** on the queue after scanning it, and
  `main()` ended in `for t in threads: t.join()`. `finder.py` never returned,
  while `cron/cron.d/crontab` launches it every minute. The trailing
  `finally: rclient.delete(global_lock_key)` was therefore unreachable.
- The global lock used a fixed `ex=GLOBAL_LOCK_TIMEOUT_SECONDS` (3600) with
  no heartbeat, so it expired out from under a still-running finder. The next
  cron tick then found no lock and started a second immortal finder on top of
  the first. Roughly one new resident process — and 1-2 leaked connections —
  per hour, until Postgres answered "sorry, too many clients already".

Fixes:

- New `scan_all_subnets()` drains the subnet queue exactly once across a
  worker pool and returns; cron's minute tick is now the scan cadence. Extracted
  to module level so the one-pass contract is directly testable, which the old
  closure inside `# pragma: no cover` `main()` was not. A raising `scan_subnet`
  no longer kills its worker and strands the remaining subnets.
- The global lock is now `RedisSingleRunLock` (`common/single_run.py`,
  already used by the metrics transfer) with `wait=0` for abort-on-contention.
  Its heartbeat extends the TTL for as long as the holder lives, so the TTL
  drops from 3600s to 120s and only has to outlive a crash — a killed finder
  frees discovery within two cron ticks instead of an hour. Release is now
  token-checked and actually reachable.

Regression tests in `test/test_05_finder_extended.py` run `scan_all_subnets`
on a timed daemon thread and fail if it does not return, so a reintroduced
re-queue fails the suite instead of hanging CI. Verified the harness is not
vacuous: the old worker never returns and calls `scan_subnet` ~91,000 times in
3 seconds.

Operational note for deploying this: the stale `labyrinth_finder_lock` key
written by the old code carries up to a 3600s TTL and its value is not a
valid token, so delete it once (`redis-cli DEL labyrinth_finder_lock`) after
restarting the cron container, or the first scan waits up to an hour.

## 2026-08-24 13:05 CDT
Follow-up to the finder fix above: a `no-mistakes` Python graph query
(`dependents finder.py --relationship python`) reported `serve.py` as a
dependent of `finder.py`, which looked backwards — `finder.py` imports
`serve`, not the reverse. It was right. `serve.py:348` has a *deferred*
import inside the `/scan/` route:

```python
@app.route("/scan/")
def scan():
    from finder import main
    executor.submit(main)          # executor = ThreadPoolExecutor(2)
```

So the never-returning `main()` was not only a cron problem. Every click of
Scan in the UI permanently consumed one of that gunicorn worker's **two**
executor threads. Two clicks wedged the pool, after which every later scan
request in that worker queued forever and silently never ran, while the two
stuck threads kept nmap-scanning in a tight loop and held the worker's
database pool. It also explains why `/scan/` would appear dead in a
long-running deployment: the first immortal finder took the global lock and
never released it, so every subsequent UI scan aborted on contention forever.

Both are fixed by the same change — `main()` now returns, releasing the
executor thread and the lock. UI-triggered scans now abort only while a scan
is genuinely in progress, rather than permanently.

No code change in this entry; the fix above already covers it. Recorded
because the `/scan/` path is easy to miss when reading `finder.py` alone —
the import is deferred, so it does not appear in either file's import block.
