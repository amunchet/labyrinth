# backend/db/ - Database Adapter Ecosystem

Pluggable database backend for Labyrinth. Selected via the `DB_BACKEND` env
var (`postgres` - default, or `mongo`). See `MONGO_MIGRATION.md` at the repo
root for the full design rationale, schema, and operational runbook. This
file documents the adapter *contract* - what to rely on, what not to.

## Usage

```python
from db import shared_db

db = shared_db()                    # lazy proxy onto the process-wide Client
hosts = db["labyrinth"]["hosts"]    # Collection - same shape on both backends
hosts.insert_one({"mac": "AA:BB"})
found = hosts.find_one({"mac": "AA:BB"})
```

Every call site in this codebase programs against this interface
(`backend/db/base.py`: `Client`, `Database`, `Collection`, `Cursor`) - never
against `pymongo` or `psycopg2` directly. `backend/db/mongo_adapter.py` and
`backend/db/postgres_adapter.py` are the two implementations.

## Connection ownership - pick the right entry point

On Postgres a `Client` owns a `ThreadedConnectionPool`, and nothing reaps
pools. Which entry point you use is therefore a connection-budget decision,
not a style preference:

| Function | Builds | Use for |
|---|---|---|
| `shared_db()` | nothing until first use | **application code** - module-level `db = shared_db()` |
| `get_shared_client()` | the one client, on first call | helpers reached from routes/jobs that need a `Client` now |
| `get_db()` | a **new** client every call | tests and one-shot tooling that will `close()` it |

Rules that follow from that:

- **Never call `get_db()` per request, per job, or per helper invocation.**
  Each call is another pool of up to `POSTGRES_POOL_MAX` connections that
  nobody closes. Doing this in a gunicorn worker is how the backend ran the
  server out of connections (`FATAL: sorry, too many clients already`).
- **Module-level clients must be lazy.** `finder.py`, `alive.py` and
  `serve.py updater` all `import serve` purely to reuse route handlers, and
  several then exit immediately on a contended lock. `shared_db()` returns a
  proxy so importing costs nothing; the pool is built on first real query.
- `close_shared_client()` is registered with `atexit`, so short-lived cron
  processes hand their connections back on the way out.

### Sizing the pool

`POSTGRES_POOL_MIN` / `POSTGRES_POOL_MAX` (default 1 / 2) bound each
process's pool. The default is small on purpose - see the budget comment in
`postgres_adapter.py`. The ceiling it is budgeted against is
`max_connections`, which the compose files pin explicitly because the
`timescale/timescaledb` image's autotuner otherwise sets it to **50**, not
Postgres' usual 100.

## What's supported

Methods: `find`, `find_one`, `insert_one`, `insert_many`, `update_one`,
`update_many`, `delete_one`, `delete_many`, `bulk_write` (with `InsertOne`,
`ReplaceOne`, `UpdateOne`, `DeleteOne` from `db.base`), `count_documents`,
`create_index`, `drop_index`.

`Cursor` supports `.sort(key_or_list, direction=None)` (both the
`"field", direction` and `[(field, direction), ...]` forms), `.limit(n)`,
and plain iteration.

Filter/update operators (Postgres backend only - see below): `$or`,
`$pull` (either a scalar, matched exactly, or a criteria document, matched
as a subset of each array element the way Mongo does), `$push`, `$in`,
`$regex` (anchored prefix, e.g. `"^prefix"` - not general regex),
`$exists`, `$set`, `$unset`, `upsert=True`, and `$lt` (added specifically
to emulate Mongo's `metrics-latest` TTL index).

## Mongo adapter: full fidelity, zero restrictions

`mongo_adapter.py` is a thin passthrough onto real `pymongo`. It forwards
raw filter/update dicts straight to the server, so it supports the **full**
MongoDB query language - not just the list above. If you're running
`DB_BACKEND=mongo`, anything real MongoDB supports works.

## Postgres adapter: narrow by design

`postgres_adapter.py` translates only the operators listed above, because
that's the complete, exhaustively-grepped set actually used anywhere in this
codebase (see `MONGO_MIGRATION.md`'s research findings). It is **not** a
general Mongo-query-language emulator. If you add a call site that needs a
new operator (`$gt`, `$ne`, `$and`, aggregation pipelines, etc.), you need
to add support for it in `PostgresCollectionAdapter._translate_filter` /
`_translate_operator` / `_translate_update` first - it will raise
`ValueError` otherwise, not silently do the wrong thing.

Schema: every JSONB-flexible collection (`hosts`, `subnets`, `services`,
`settings`, `proxmox_clusters`, `aws_accounts`, `themes`, `dashboards`) is a
table shaped `(id TEXT PRIMARY KEY, seq BIGSERIAL, data JSONB)`. `metrics`
(a TimescaleDB hypertable) and `metrics-latest` have typed columns instead
(`ts`, `name`, `tags`, `fields`). Schema bootstrap runs eagerly at
`PostgresClientAdapter()` construction (not lazily, unlike Mongo's
`index_helper()`) - see `_bootstrap_schema()`.

IDs: `str(bson.ObjectId())` - `bson` is used purely as an ID-shape
generator/validator here, decoupled from Mongo-the-server (it's still a
dependency for the Mongo adapter). This keeps `_validate_object_id()` in
`serve.py` and the frontend's `_id` handling unchanged across both backends.

## Testing

`backend/test/test_18_db_adapters.py` runs the same black-box scenarios
against both adapters, against real ephemeral `mongo` and `postgres`
containers - matching this repo's existing convention of testing against
real services rather than mocks. Run it (or the full suite) against either
backend explicitly:

```bash
DB_BACKEND=postgres PYTHONPATH=. pytest test/test_18_db_adapters.py -q
DB_BACKEND=mongo     PYTHONPATH=. pytest test/test_18_db_adapters.py -q
```

(Note `test_18_db_adapters.py` itself constructs both adapters directly and
doesn't read `DB_BACKEND` - the env var above only matters for the rest of
the suite, which goes through `serve.db` / `get_db()`.)
