# Migrating off MongoDB - PostgreSQL/TimescaleDB Adapter

## Overview

Labyrinth's database layer is now a pluggable adapter ecosystem
(`backend/db/`) instead of hardcoded `pymongo` calls. **PostgreSQL 16 with
the TimescaleDB extension is the new default backend** (`DB_BACKEND=postgres`).
MongoDB remains fully supported as an explicit fallback (`DB_BACKEND=mongo`)
- nothing was ripped out, and existing Mongo deployments keep working
unchanged until you choose to cut over.

**Why Postgres + TimescaleDB:** the app is a hybrid workload - eight
low-volume, flexible-schema config collections (hosts, subnets, services,
settings, proxmox_clusters, aws_accounts, themes, dashboards) plus one
high-frequency time-series stream (metrics). Postgres covers both in a
single engine (JSONB tables for the former, a TimescaleDB hypertable for
the latter), which matters for "docker friendly": one container, one
connection pool, one `pg_dump` backup story, instead of running two
different databases side by side. Pure time-series stores (InfluxDB,
VictoriaMetrics) were considered and rejected for exactly that reason - they
have no sensible way to hold the config collections. SQLite was rejected as
unsafe under `gunicorn --workers 8` plus several concurrent cron writers.
MySQL was rejected in favor of Postgres's stronger JSONB/GIN indexing story.

## Configuration

New env vars (see `backend/.env.sample` for the full annotated list):

| Var | Default | Notes |
|---|---|---|
| `DB_BACKEND` | `postgres` | `postgres` or `mongo` |
| `POSTGRES_HOST` | `postgres` | |
| `POSTGRES_PORT` | `5432` | |
| `POSTGRES_USER` | `labyrinth` | |
| `POSTGRES_PASSWORD` | *(required)* | |
| `POSTGRES_DB` | `labyrinth` | |
| `METRICS_RAW_RETENTION_DAYS` | `30` | Postgres only - see Compaction below |
| `METRICS_DAILY_RETENTION_DAYS` | unset (unlimited) | Postgres only |
| `BACKUP_RETENTION_DAYS` | `14` | local `/backups` retention, separate from whatever your offsite system does |

`MONGO_USERNAME`/`MONGO_PASSWORD`/`MONGO_HOST` are unchanged and still used
when `DB_BACKEND=mongo`.

In **dev** (`docker-compose-development.yml`), both `postgres` and `mongo`
services run side by side so either backend is testable at any time.
In **production** (`docker-compose-production.yml`), this is genuinely new
infrastructure - prod never ran a self-hosted Mongo (its `mongo:` block was
always commented out, pointing at an external `mongodb+srv://` cluster via
`backend/.env` instead). The `postgres` service is real and uncommented
there; `POSTGRES_PASSWORD` etc. come from a root-level `.env` file (see
`.env.sample`) via docker-compose variable substitution, the same pattern
already used for `TZ`.

## Architecture

See `backend/db/README.md` for the adapter contract (what's supported, what
isn't) and `CLAUDE.md`'s "Database adapter ecosystem" section for a quick
orientation. In short: `db.get_db()` returns a `Client` implementing
`backend/db/base.py`'s interface; every route/module goes through it
(`serve.py`'s `db = get_db()`, `proxmox_disk_check.py`, `proxmox_refresh.py`,
`utils.py`, `backend/ai/mcp/server.py`). The Postgres adapter translates a
deliberately narrow set of pymongo operators - exactly what this codebase
was found to actually use after an exhaustive audit, not a general Mongo
query language emulator.

### Schema

Eight collections become `(id TEXT PRIMARY KEY, seq BIGSERIAL, data JSONB)`
tables with expression indexes matching the fields Mongo had indexed
(`ip`/`mac`/`subnet` on hosts, `name`/`display_name` on services, etc.).
`metrics` is a TimescaleDB hypertable with typed columns
(`ts, name, tags, fields`) - note its primary key is `(id, ts)`, not `id`
alone, because TimescaleDB requires any unique constraint on a hypertable to
include the partitioning column. `metrics-latest` uses the same typed shape
but stays a plain table (small, constantly-upserted, doesn't benefit from
hypertable partitioning) with a unique index on `(name, tags)` and a
`metrics_daily` table for compacted aggregates (see below). Full DDL lives
in `backend/db/postgres_adapter.py`'s `_bootstrap_schema()`, which runs
eagerly at client construction - **not** lazily like Mongo's
`index_helper()`, which only ever ran from the cron container (never from
gunicorn workers) and would leave a fresh Postgres install 500ing on the
first request if schema setup were similarly lazy.

### IDs

Every id is a string shaped like a Mongo `ObjectId` hex
(`str(bson.ObjectId())`), generated without an actual Mongo connection -
`bson` is kept purely as an ID scheme. `_validate_object_id()` in `serve.py`
and the frontend's `_id` handling (always treated as an opaque string
token) work unchanged on both backends.

## Migrating an existing deployment

`backend/migrate_to_postgres.py` is a one-time, idempotent, operator-run
script - it is never invoked automatically by the app or by cron.

```bash
# from inside the backend container/venv, with both MONGO_* and POSTGRES_*
# env vars set (it needs to reach both databases regardless of DB_BACKEND):

python3 migrate_to_postgres.py --dry-run       # counts only, writes nothing
python3 migrate_to_postgres.py                 # copies everything, then verifies counts
python3 migrate_to_postgres.py --verify-only   # re-check counts without copying
```

It copies all ten collections (small ones first, `metrics`/`metrics-latest`
batched last), preserving original Mongo `_id`s as the new string ids, and
is safe to re-run (upsert-by-id) if a prior run was interrupted or you want
to pick up new documents written since. A real run ends by printing a
count-comparison table and exits non-zero if source/destination counts
don't match.

**Cutover steps for an existing deployment:**
1. Run the migration script against your live Mongo (as above).
2. Confirm the verification table matches.
3. Set `DB_BACKEND=postgres` in `backend/.env` and restart the backend/cron/mcp services.
4. If your MongoDB is Atlas and has the scheduled Trigger described below, disable it.
5. Once you're confident, `DB_BACKEND=mongo` remains available as an instant rollback - no data migration needed to go back, since Mongo itself hasn't been touched.

The script does **not** touch any MongoDB Atlas Trigger - see the
decommissioning note below.

## Backups

`cron/backup_db.sh` (daily, `cron/cron.d/crontab`) runs
`backend/backup_db.py`, which shells out to `pg_dump --format=custom` and
writes timestamped files to `/backups` (bind-mounted in both compose
files). An external system - out of scope here, already exists per the
original ask - is expected to pick files up from `/backups` for offsite
storage; this repo only keeps `BACKUP_RETENTION_DAYS` of local history so
the directory itself doesn't grow unboundedly. The script verifies the dump
is non-empty and passes a `pg_restore --list` sanity check before declaring
success, and prints an unambiguous `BACKUP OK: ...` / `BACKUP FAILED: ...`
final line so failures are greppable. No-ops cleanly under `DB_BACKEND=mongo`.

To restore: `pg_restore --clean --if-exists -d <database> <dumpfile>`.

## Metrics retention and compaction

Raw `metrics` rows keep full per-sample fidelity for
`METRICS_RAW_RETENTION_DAYS` (default 30). Once a row crosses that age,
`cron/compact_metrics.sh` (daily, before the backup job) rolls it into
`metrics_daily` - one row per `(day, name, tags)` storing `min`/`max`/`avg`/
`count` for each **numeric** field found under `fields` - and deletes the
compacted raw row. Non-numeric fields are intentionally dropped at
compaction time (that's what "summarize" means here, not a bug). Compacted
daily aggregates are kept indefinitely by default
(`METRICS_DAILY_RETENTION_DAYS` unset); set it if you also want to cap
those.

This is a genuinely new capability - Mongo never had retention for the raw
`metrics` collection (its indexes were commented out in code; unbounded
growth was the actual shipped behavior). The default (30 days raw, then
compacted) was a deliberate choice: existing behavior is preserved by
default in the sense that nothing is silently deleted - old data is
compacted, not discarded. If you want the pre-migration "keep everything at
full fidelity forever" behavior, set `METRICS_RAW_RETENTION_DAYS` to a very
large number.

This is Postgres/TimescaleDB-only tooling - there's no Mongo-mode
equivalent, and `compact_metrics.sh` no-ops cleanly under `DB_BACKEND=mongo`.
Blending `metrics` and `metrics_daily` into the dashboard/graphing UI for
queries spanning older data is **not** implemented - this migration ships
the storage/compaction mechanism only; no existing route currently queries
metrics far enough back for this to matter, and wiring it into the frontend
would be a separate feature.

## Known behavior notes carried forward unchanged

- **Metrics throttle bug** (`serve.py`'s `bulk_insert()`): the per-host
  throttle key `last_metric_{ip}` is keyed by IP only, not `(ip, metric
  name)`. Within one cron tick, whichever metric type for a host is
  processed first refreshes the shared key, causing every other metric type
  for that same host processed later in the same tick to look
  "recently written" and get skipped. In practice, a host reporting N
  distinct measurement types typically gets only ~1 persisted per cron
  tick. This is pre-existing, unrelated to the database backend, and
  intentionally preserved as-is (fixing it wasn't in scope for a migration
  meant to be behavior-neutral) - both adapters see identical `bulk_insert()`
  Python logic, only the final `bulk_write()` call is backend-specific.
- **`last_metrics()`'s sort key** (`serve.py`) sorts by the literal string
  `"metrics-latest.timestamp"`, which doesn't exist as a field on any
  document/row - a pre-existing bug carried forward as-is. Both adapters
  handle this gracefully (no crash, order is simply not meaningfully
  affected by that sort key) rather than either backend erroring on it.
- **`last_metrics()`'s `count` path parameter is accepted but never applied
  as a limit** - it returns the entire `metrics-latest` collection
  regardless of the value passed. Also pre-existing, also unrelated to the
  database backend.

## MongoDB Atlas Trigger (decommissioning checklist)

`README.md` documents a MongoDB Atlas scheduled Trigger (a `$merge` from
`metrics-latest` into `metrics`, configured to run every 15 minutes) as part
of an earlier iteration of the metrics design. This trigger lives entirely
in Atlas's control plane - it is not represented anywhere in this repo, and
neither the migration script nor any code change here can see or touch it.
If your deployment has one configured:

- It's already redundant with `bulk_insert()`'s own direct writes to both
  collections (confirmed via `README.md`'s "Attempt 2" notes, which match
  current `serve.py` behavior).
- After cutting over to `DB_BACKEND=postgres`, it will keep firing forever
  against an abandoned Mongo cluster, doing nothing useful, unless you
  disable it yourself in the Atlas console.
- Nothing in this codebase will ever remind you of this again - it's a
  purely manual, one-time cleanup step.

## Testing

`backend/test/test_18_db_adapters.py` runs identical black-box scenarios
against both `MongoClientAdapter` and `PostgresClientAdapter` (real
ephemeral containers, matching this repo's existing "don't mock the
database" convention). `test_19_compact_metrics.py`, `test_20_backup_db.py`,
and `test_21_migrate_to_postgres.py` cover the new cron/migration tooling.
The pre-existing suite's `setup`/`tearDown` fixtures were mechanically
updated from `serve.mongo_client[...]` to `serve.db[...]` across the 11
files that touch the database directly - see `CLAUDE.md` for how to run
everything, including against the `DB_BACKEND=mongo` fallback explicitly.

One existing test fixture (`test_04_metrics.py`) previously inserted bare
integer placeholders (`{"timestamp": 1}`) that can't round-trip through a
typed `TIMESTAMPTZ` column the way they could through a schemaless Mongo
field; it was updated to use realistic epoch timestamps and assert on
`name` instead of the placeholder value - a real writes-path document never
looked like the old fixture anyway (`bulk_insert()` always overwrites
`timestamp` with `datetime.now()`).
