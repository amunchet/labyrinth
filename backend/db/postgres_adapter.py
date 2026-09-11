"""
PostgreSQL/TimescaleDB adapter - the new default backend (`DB_BACKEND=postgres`).

Every JSONB-flexible Mongo collection (hosts, subnets, services, settings,
proxmox_clusters, aws_accounts, themes, dashboards) becomes a table shaped
`(id TEXT PRIMARY KEY, seq BIGSERIAL, data JSONB)`. `metrics`/`metrics-latest`
get typed columns instead (`ts, name, tags, fields`) and `metrics` is a
TimescaleDB hypertable. See MONGO_MIGRATION.md for the full design and
rationale.

This module deliberately translates only the pymongo filter/update operators
that are actually used anywhere in this codebase ($set, $or, $pull, $in,
$regex as an anchored prefix, $exists, $unset, upsert=True, and $lt - the
last one added solely to emulate Mongo's metrics-latest TTL index, since
Postgres has no per-row TTL primitive). It is not a general Mongo query
language emulator - see backend/db/README.md.
"""

import datetime
import json
import os
import re
import time

import bson
import psycopg2
import psycopg2.extras
import psycopg2.pool

from db import base

_SAFE_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z_][A-Za-z0-9_-]*)*$")

_JSONB_TABLE_INDEXES = {
    "hosts": [("ip", False), ("mac", False), ("subnet", False)],
    "subnets": [("subnet", False)],
    "services": [("name", False), ("display_name", False)],
    "settings": [("name", True)],
    "proxmox_clusters": [("name", False), ("name_key", False)],
    "aws_accounts": [("name", False)],
    "themes": [("name", False)],
    "dashboards": [("name", False)],
    "ai_chat_sessions": [("updated_at", False)],
}

_METRICS_TABLES = ("metrics", "metrics_latest")

_BOOTSTRAP_LOCK_KEY = 891234765


def _connection_dsn():
    return "host={} port={} user={} password={} dbname={}".format(
        os.environ.get("POSTGRES_HOST", "postgres"),
        os.environ.get("POSTGRES_PORT", "5432"),
        os.environ.get("POSTGRES_USER", "labyrinth"),
        os.environ.get("POSTGRES_PASSWORD", ""),
        os.environ.get("POSTGRES_DB", "labyrinth"),
    )


# Per-process pool bounds. Deliberately small, because the connection budget
# is much tighter than Postgres' stock 100: the `timescale/timescaledb` image
# runs timescaledb-tune at first start, which sets `max_connections = 50`.
#
# Against 50 (minus superuser_reserved_connections=3) the steady-state demand
# is roughly:
#
#   backend    8 gunicorn workers x POSTGRES_POOL_MAX
#   mcp        1 process          x POSTGRES_POOL_MAX
#   cron       up to ~4 overlapping jobs on the same minute (finder,
#              bulk_write, proxmox_refresh x2) x POSTGRES_POOL_MAX
#
# At the old hardcoded maxconn=5 that is 8*5 + 5 + 4*5 = 65 > 47, i.e. the
# stack could exhaust the server without a single leak. Sync gunicorn workers
# serve one request at a time and need exactly one connection; the headroom
# above 1 is for the AI chat background threads. 13*2 = 26 leaves real room.
_DEFAULT_POOL_MIN = 1
_DEFAULT_POOL_MAX = 2


def _pool_bounds():
    """Pool size from env, clamped so a bad value can't wedge the pool."""

    def _read(name, default):
        try:
            return max(1, int(os.environ.get(name) or default))
        except (TypeError, ValueError):
            return default

    minconn = _read("POSTGRES_POOL_MIN", _DEFAULT_POOL_MIN)
    maxconn = _read("POSTGRES_POOL_MAX", _DEFAULT_POOL_MAX)
    return minconn, max(minconn, maxconn)


def _connect_with_retry(dsn, minconn=None, maxconn=None, attempts=15, delay=2):
    """
    docker-compose `depends_on` only waits for the postgres *container* to
    start, not for it to be ready to accept connections - retry so gunicorn
    workers don't crash-loop on a normal startup race.
    """
    if minconn is None or maxconn is None:
        default_min, default_max = _pool_bounds()
        minconn = default_min if minconn is None else minconn
        maxconn = default_max if maxconn is None else maxconn
    last_exc = None
    for _ in range(attempts):
        try:
            return psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, dsn)
        except psycopg2.OperationalError as exc:  # pragma: no cover
            last_exc = exc
            time.sleep(delay)
    raise last_exc  # pragma: no cover


def _bootstrap_schema(pool):
    """
    Eagerly creates every table/index/hypertable this app needs. Must run
    eagerly (not lazily from index_helper(), which only ever runs from the
    cron container - see serve.py's `if __name__ == "__main__"` block and
    backend/entrypoint.sh's gunicorn invocation) or a fresh install's first
    API request would 500 with "relation does not exist" before cron ever
    ticks. Guarded by an advisory lock so the 8 concurrently-starting
    gunicorn workers don't race each other's `CREATE TABLE IF NOT EXISTS`.
    """
    conn = pool.getconn()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (_BOOTSTRAP_LOCK_KEY,))
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

                for table, indexes in _JSONB_TABLE_INDEXES.items():
                    cur.execute(
                        "CREATE TABLE IF NOT EXISTS {} "
                        "(id TEXT PRIMARY KEY, seq BIGSERIAL, data JSONB NOT NULL)".format(
                            table
                        )
                    )
                    for field, pattern_ops in indexes:
                        opclass = " text_pattern_ops" if pattern_ops else ""
                        cur.execute(
                            "CREATE INDEX IF NOT EXISTS {}_{}_idx ON {} "
                            "((data->>'{}'){})".format(
                                table, field, table, field, opclass
                            )
                        )

                # TimescaleDB requires any unique constraint on a hypertable to
                # include the partitioning column, so `id` alone can't be the
                # PRIMARY KEY here (unlike every other table in this schema) -
                # `id` values are still globally unique (ObjectId-derived) in
                # practice, this composite key is a partitioning technicality,
                # not a behavior change.
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS metrics ("
                    "id TEXT NOT NULL, seq BIGSERIAL, "
                    "ts TIMESTAMPTZ NOT NULL DEFAULT now(), "
                    "name TEXT, tags JSONB, fields JSONB, "
                    "PRIMARY KEY (id, ts))"
                )
                cur.execute(
                    "SELECT create_hypertable('metrics', 'ts', "
                    "if_not_exists => TRUE, migrate_data => TRUE)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS metrics_tags_idx ON metrics USING GIN (tags)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS metrics_name_idx ON metrics (name)"
                )
                cur.execute("CREATE INDEX IF NOT EXISTS metrics_id_idx ON metrics (id)")

                cur.execute(
                    "CREATE TABLE IF NOT EXISTS metrics_latest ("
                    "id TEXT PRIMARY KEY, seq BIGSERIAL, "
                    "ts TIMESTAMPTZ NOT NULL DEFAULT now(), "
                    "name TEXT, tags JSONB, fields JSONB)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS metrics_latest_tags_idx "
                    "ON metrics_latest USING GIN (tags)"
                )
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS metrics_latest_name_tags_uidx "
                    "ON metrics_latest (name, tags)"
                )

                # Compacted daily rollups (backend/compact_metrics.py). Postgres-only,
                # no Mongo-mode equivalent - see MONGO_MIGRATION.md.
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS metrics_daily ("
                    "day DATE NOT NULL, "
                    "name TEXT NOT NULL, "
                    "tags JSONB NOT NULL, "
                    "tags_key TEXT GENERATED ALWAYS AS (md5(tags::text)) STORED, "
                    "fields JSONB NOT NULL, "
                    "sample_count INTEGER NOT NULL, "
                    "PRIMARY KEY (day, name, tags_key))"
                )
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_BOOTSTRAP_LOCK_KEY,))
    finally:
        pool.putconn(conn)


def _cursor(pool):
    """Context manager yielding a dict-row cursor from the pool."""
    return _PoolCursor(pool)


class _PoolCursor:
    """Checks a connection out of the pool for the body of a `with` block.

    Every exit path must `putconn`. psycopg2's pool tracks checked-out
    connections in `_used`, and one that is never returned is gone for good:
    the pool slot stays occupied forever.

    The path that actually bites is setup, not teardown. After Postgres
    restarts (upgrade, OOM, failover) every connection sitting idle in the
    pool is dead, and `conn.autocommit = True` on a dead connection raises
    InterfaceError *before* the try/finally that would have returned it. Do
    that `maxconn` times and the pool is permanently exhausted while its
    backends are still counted server-side - the process then needs a
    restart to talk to the database again.

    An ordinary failed query (UndefinedTable and friends) is safe either
    way: the cursor still closes cleanly and the connection goes back.
    """

    def __init__(self, pool):
        self._pool = pool
        self._conn = None
        self._cur = None

    def __enter__(self):
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            self._cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        except Exception:
            # Setting autocommit or opening a cursor only fails on an
            # already-dead connection - discard rather than recycle it.
            self._pool.putconn(conn, close=True)
            raise
        self._conn = conn
        return self._cur

    def __exit__(self, exc_type, exc, tb):
        conn, cur = self._conn, self._cur
        self._conn = self._cur = None

        # A connection-level failure poisons the connection: handing it back
        # to the pool just deals the same broken socket to the next caller.
        broken = bool(conn.closed) or (
            exc_type is not None
            and issubclass(
                exc_type, (psycopg2.OperationalError, psycopg2.InterfaceError)
            )
        )
        try:
            if cur is not None and not broken:
                cur.close()
        except Exception:
            broken = True
        finally:
            self._pool.putconn(conn, close=broken)
        return False


def _id_str(value):
    return str(value)


def _new_id():
    return str(bson.ObjectId())


def _as_utc(value):
    """Pin a naive datetime to UTC.

    The `ts` columns are TIMESTAMPTZ, so a naive value would otherwise be
    interpreted in whatever the session TimeZone happens to be. pymongo
    treats naive datetimes as UTC, so doing the same here keeps the numbers
    a document round-trips through identical on both backends.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value


def _from_utc(value):
    """Inverse of _as_utc: hand callers the naive UTC datetime Mongo would.

    psycopg2 returns TIMESTAMPTZ as offset-aware, but pymongo returns naive
    datetimes, and app code mixes stored timestamps with naive ones built by
    datetime.now()/fromtimestamp() (serve.py's find_metric, metrics.py's
    judge). Returning aware values here makes those comparisons raise
    "can't compare offset-naive and offset-aware datetimes".
    """
    if isinstance(value, datetime.datetime) and value.tzinfo is not None:
        return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return value


def _coerce_timestamp(value):
    if value is None:
        return _as_utc(datetime.datetime.now())
    if isinstance(value, datetime.datetime):
        return _as_utc(value)
    if isinstance(value, (int, float)):
        return _as_utc(datetime.datetime.fromtimestamp(value))
    if isinstance(value, str):
        try:
            return _as_utc(
                datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            )
        except ValueError:
            return _as_utc(datetime.datetime.now())
    return _as_utc(datetime.datetime.now())


def _to_jsonb_param(value):
    return json.dumps(value, default=str)


def _filter_to_doc(filt):
    """Best-effort reconstruction of a document from a filter's plain
    equality assertions, used only by the (rarely exercised) upsert path
    of update_one/update_many/UpdateOne - real app code always upserts via
    bulk_write's ReplaceOne, which supplies a full replacement document."""
    doc = {}
    for key, value in filt.items():
        if key.startswith("$") or isinstance(value, dict):
            continue
        doc[key] = value
    return doc


class PostgresCursor(base.Cursor):
    def __init__(self, collection, where_sql, params):
        self._collection = collection
        self._where_sql = where_sql
        self._params = params
        self._order_sql = None
        self._limit_n = None

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, str):
            items = [(key_or_list, direction if direction is not None else 1)]
        else:
            items = list(key_or_list)
        parts = []
        for key, key_direction in items:
            col = self._collection._text_path(key)
            parts.append("{} {}".format(col, "DESC" if key_direction < 0 else "ASC"))
        self._order_sql = ", ".join(parts)
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def __iter__(self):
        order = self._order_sql or "seq ASC"
        sql = "SELECT * FROM {} WHERE {} ORDER BY {}".format(
            self._collection._table, self._where_sql, order
        )
        params = list(self._params)
        if self._limit_n is not None:
            sql += " LIMIT %s"
            params.append(self._limit_n)
        with _cursor(self._collection._pool) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return iter(self._collection._row_to_doc(row) for row in rows)


class PostgresCollectionAdapter(base.Collection):
    def __init__(self, pool, table, kind):
        self._pool = pool
        self._table = table
        self._kind = kind  # "jsonb" or "metrics"

    # ---- field path resolution -------------------------------------------------

    def _jsonb_path(self, key):
        """SQL expression yielding the JSONB value at `key` (for equality/$in)."""
        if key == "_id":
            return "to_jsonb(id)"
        if not _SAFE_KEY_RE.match(key):
            raise ValueError("Unsupported field key: {!r}".format(key))
        parts = key.split(".")
        if self._kind == "metrics":
            head, rest = parts[0], parts[1:]
            if head in ("tags", "fields"):
                expr = head
                for part in rest:
                    expr = "{}->'{}'".format(expr, part)
                return expr
            if head == "name" and not rest:
                return "to_jsonb(name)"
            if head == "timestamp" and not rest:
                return "to_jsonb(ts)"
            return "NULL::jsonb"
        expr = "data"
        for part in parts:
            expr = "{}->'{}'".format(expr, part)
        return expr

    def _text_path(self, key):
        """SQL expression yielding the TEXT value at `key` (for LIKE/sort)."""
        if key == "_id":
            return "id"
        if not _SAFE_KEY_RE.match(key):
            raise ValueError("Unsupported field key: {!r}".format(key))
        parts = key.split(".")
        if self._kind == "metrics":
            head, rest = parts[0], parts[1:]
            if head == "timestamp" and not rest:
                return "ts"
            if head == "name" and not rest:
                return "name"
            if head in ("tags", "fields"):
                expr = head
                for part in rest[:-1]:
                    expr = "{}->'{}'".format(expr, part)
                if rest:
                    return "{}->>'{}'".format(expr, rest[-1])
                return "{}::text".format(expr)
            # Unrecognized top-level key on a metrics-kind table - degrade to
            # a neutral, non-crashing sort/compare key instead of raising.
            # This specifically preserves a real, currently-shipping quirk:
            # last_metrics() sorts by the literal, nonexistent field name
            # "metrics-latest.timestamp" (see serve.py) - real MongoDB just
            # treats that as an absent field and sorts everything as equal,
            # rather than erroring, so we match that instead of crashing.
            return "NULL::text"
        expr = "data"
        for part in parts[:-1]:
            expr = "{}->'{}'".format(expr, part)
        return "{}->>'{}'".format(expr, parts[-1])

    # ---- filter / update translation -------------------------------------------

    def _translate_filter(self, filt):
        if not filt:
            return "TRUE", []

        clauses = []
        params = []
        for key, value in filt.items():
            if key == "$or":
                sub_clauses = []
                for sub in value:
                    sub_sql, sub_params = self._translate_filter(sub)
                    sub_clauses.append("({})".format(sub_sql))
                    params.extend(sub_params)
                clauses.append("(" + " OR ".join(sub_clauses) + ")")
                continue

            if key == "_id":
                if isinstance(value, dict):
                    raise ValueError("Operator filters on _id are not supported")
                clauses.append("id = %s")
                params.append(_id_str(value))
                continue

            if (
                isinstance(value, dict)
                and value
                and all(k.startswith("$") for k in value.keys())
            ):
                # An operator expression (e.g. {"$regex": ...}) - as opposed
                # to a plain dict being compared for structural equality
                # (e.g. the whole-tags-object match in bulk_insert()'s
                # ReplaceOne filter, {"tags": item["tags"], ...}), which
                # falls through to the literal-equality branch below, same
                # as real MongoDB's own query-matching rule.
                op_sql, op_params = self._translate_operator(key, value)
                clauses.append(op_sql)
                params.extend(op_params)
                continue

            clauses.append("{} = %s::jsonb".format(self._jsonb_path(key)))
            params.append(_to_jsonb_param(value))

        if not clauses:
            return "TRUE", []
        return " AND ".join(clauses), params

    def _translate_operator(self, key, op_dict):
        clauses = []
        params = []
        for op, value in op_dict.items():
            if op == "$regex":
                prefix = value[1:] if value.startswith("^") else value
                escaped = (
                    prefix.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
                )
                clauses.append("{} LIKE %s".format(self._text_path(key)))
                params.append(escaped + "%")
            elif op == "$exists":
                top_key = key.split(".")[0]
                if self._kind == "jsonb":
                    clauses.append(
                        "{}(data ? '{}')".format("" if value else "NOT ", top_key)
                    )
                else:
                    clauses.append(
                        "{} IS {}".format(top_key, "NOT NULL" if value else "NULL")
                    )
            elif op == "$in":
                clauses.append("{} ?| %s::text[]".format(self._jsonb_path(key)))
                params.append([str(v) for v in value])
            elif op == "$lt":
                target = _coerce_timestamp(value) if key == "timestamp" else value
                clauses.append("{} < %s".format(self._text_path(key)))
                params.append(target)
            else:
                raise ValueError("Unsupported operator: {!r}".format(op))
        return " AND ".join(clauses), params

    def _translate_update(self, update):
        """Returns (data_column_sql_expr, params). JSONB-kind only - no
        real app code ever runs $set/$unset/$pull/$push against a metrics
        table."""
        expr = "data"
        params = []
        if update.get("$set"):
            expr = "({} || %s::jsonb)".format(expr)
            params.append(_to_jsonb_param(update["$set"]))
        if update.get("$unset"):
            for key in update["$unset"].keys():
                expr = "({} - '{}')".format(expr, key)
        if update.get("$pull"):
            for key, value in update["$pull"].items():
                # Mongo treats a document value as a *condition* matched against
                # each array element (so {"service": x} pulls every element whose
                # service is x, whatever else it carries), while a scalar value
                # has to match exactly. `@>` containment is the JSONB equivalent
                # of that subset match.
                match = (
                    "elem @> %s::jsonb"
                    if isinstance(value, dict)
                    else "elem = %s::jsonb"
                )
                # expr is interpolated twice below, so whatever placeholders it
                # already carries appear twice as well - repeat their params in
                # the same order rather than letting the counts drift apart.
                params = params + params
                expr = (
                    "jsonb_set({expr}, ARRAY['{key}'], COALESCE("
                    "(SELECT jsonb_agg(elem) FROM jsonb_array_elements({expr}->'{key}') elem "
                    "WHERE NOT ({match})), '[]'::jsonb))"
                ).format(expr=expr, key=key, match=match)
                params.append(_to_jsonb_param(value))
        if update.get("$push"):
            for key, value in update["$push"].items():
                # Same double-interpolation caveat as $pull above. Missing (or
                # null) arrays start as [], matching Mongo's $push semantics.
                params = params + params
                expr = (
                    "jsonb_set({expr}, ARRAY['{key}'], "
                    "COALESCE({expr}->'{key}', '[]'::jsonb) || "
                    "jsonb_build_array(%s::jsonb))"
                ).format(expr=expr, key=key)
                params.append(_to_jsonb_param(value))
        return expr, params

    # ---- row <-> document conversion -------------------------------------------

    def _row_to_doc(self, row):
        if self._kind == "jsonb":
            doc = dict(row["data"])
            doc["_id"] = row["id"]
            return doc
        return {
            "_id": row["id"],
            "name": row["name"],
            "tags": row["tags"],
            "fields": row["fields"],
            "timestamp": _from_utc(row["ts"]),
        }

    def _insert_row(self, cur, document):
        doc = dict(document)
        supplied_id = doc.pop("_id", None)
        doc_id = _id_str(supplied_id) if supplied_id is not None else _new_id()
        if self._kind == "jsonb":
            cur.execute(
                "INSERT INTO {} (id, data) VALUES (%s, %s::jsonb)".format(self._table),
                [doc_id, _to_jsonb_param(doc)],
            )
        else:
            ts = _coerce_timestamp(doc.get("timestamp"))
            tags = doc.get("tags")
            fields = doc.get("fields")
            cur.execute(
                "INSERT INTO {} (id, ts, name, tags, fields) "
                "VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)".format(self._table),
                [
                    doc_id,
                    ts,
                    doc.get("name"),
                    _to_jsonb_param(tags) if tags is not None else None,
                    _to_jsonb_param(fields) if fields is not None else None,
                ],
            )
        return doc_id

    def _replace_row_sql(self, document):
        doc = {k: v for k, v in document.items() if k != "_id"}
        if self._kind == "jsonb":
            return "data = %s::jsonb", [_to_jsonb_param(doc)]
        ts = _coerce_timestamp(doc.get("timestamp"))
        tags = doc.get("tags")
        fields = doc.get("fields")
        return (
            "ts = %s, name = %s, tags = %s::jsonb, fields = %s::jsonb",
            [
                ts,
                doc.get("name"),
                _to_jsonb_param(tags) if tags is not None else None,
                _to_jsonb_param(fields) if fields is not None else None,
            ],
        )

    # ---- base.Collection interface ---------------------------------------------

    def find(self, filter=None, sort=None, limit=None):
        where_sql, params = self._translate_filter(filter or {})
        cursor = PostgresCursor(self, where_sql, params)
        if sort is not None:
            cursor.sort(sort)
        if limit is not None:
            cursor.limit(limit)
        return cursor

    def find_one(self, filter=None):
        where_sql, params = self._translate_filter(filter or {})
        with _cursor(self._pool) as cur:
            cur.execute(
                "SELECT * FROM {} WHERE {} ORDER BY seq ASC LIMIT 1".format(
                    self._table, where_sql
                ),
                params,
            )
            row = cur.fetchone()
        return self._row_to_doc(row) if row else None

    def insert_one(self, document):
        with _cursor(self._pool) as cur:
            doc_id = self._insert_row(cur, document)
        return base.InsertOneResult(doc_id)

    def insert_many(self, documents):
        ids = []
        with _cursor(self._pool) as cur:
            for document in documents:
                ids.append(self._insert_row(cur, document))
        return base.InsertManyResult(ids)

    def _do_update(self, filter, update, upsert, multi):
        where_sql, where_params = self._translate_filter(filter)
        set_expr, set_params = self._translate_update(update)
        with _cursor(self._pool) as cur:
            if multi:
                sql = "UPDATE {} SET data = {} WHERE {} RETURNING id".format(
                    self._table, set_expr, where_sql
                )
                cur.execute(sql, set_params + where_params)
            else:
                sql = (
                    "UPDATE {table} SET data = {set_expr} WHERE id = "
                    "(SELECT id FROM {table} WHERE {where} ORDER BY seq ASC LIMIT 1) "
                    "RETURNING id"
                ).format(table=self._table, set_expr=set_expr, where=where_sql)
                cur.execute(sql, set_params + where_params)
            matched = len(cur.fetchall())
            upserted_id = None
            if matched == 0 and upsert:
                doc = _filter_to_doc(filter)
                doc.update(update.get("$set", {}))
                upserted_id = self._insert_row(cur, doc)
        return base.UpdateResult(matched, matched, upserted_id)

    def update_one(self, filter, update, upsert=False):
        return self._do_update(filter, update, upsert, multi=False)

    def update_many(self, filter, update, upsert=False):
        return self._do_update(filter, update, upsert, multi=True)

    def delete_one(self, filter):
        where_sql, params = self._translate_filter(filter)
        with _cursor(self._pool) as cur:
            cur.execute(
                (
                    "DELETE FROM {table} WHERE id = "
                    "(SELECT id FROM {table} WHERE {where} ORDER BY seq ASC LIMIT 1)"
                ).format(table=self._table, where=where_sql),
                params,
            )
            count = cur.rowcount
        return base.DeleteResult(count)

    def delete_many(self, filter):
        where_sql, params = self._translate_filter(filter)
        with _cursor(self._pool) as cur:
            cur.execute(
                "DELETE FROM {} WHERE {}".format(self._table, where_sql), params
            )
            count = cur.rowcount
        return base.DeleteResult(count)

    def bulk_write(self, operations):
        inserted = matched = modified = deleted = upserted = 0
        with _cursor(self._pool) as cur:
            for op in operations:
                if isinstance(op, base.InsertOne):
                    self._insert_row(cur, op.document)
                    inserted += 1
                elif isinstance(op, base.ReplaceOne):
                    where_sql, where_params = self._translate_filter(op.filter)
                    set_sql, set_params = self._replace_row_sql(op.replacement)
                    sql = (
                        "UPDATE {table} SET {set_sql} WHERE id = "
                        "(SELECT id FROM {table} WHERE {where} ORDER BY seq ASC LIMIT 1) "
                        "RETURNING id"
                    ).format(table=self._table, set_sql=set_sql, where=where_sql)
                    cur.execute(sql, set_params + where_params)
                    if cur.fetchone():
                        matched += 1
                        modified += 1
                    elif op.upsert:
                        self._insert_row(cur, op.replacement)
                        upserted += 1
                elif isinstance(op, base.UpdateOne):
                    where_sql, where_params = self._translate_filter(op.filter)
                    set_expr, set_params = self._translate_update(op.update)
                    sql = (
                        "UPDATE {table} SET data = {set_expr} WHERE id = "
                        "(SELECT id FROM {table} WHERE {where} ORDER BY seq ASC LIMIT 1) "
                        "RETURNING id"
                    ).format(table=self._table, set_expr=set_expr, where=where_sql)
                    cur.execute(sql, set_params + where_params)
                    if cur.fetchone():
                        matched += 1
                        modified += 1
                    elif op.upsert:
                        doc = _filter_to_doc(op.filter)
                        doc.update(op.update.get("$set", {}))
                        self._insert_row(cur, doc)
                        upserted += 1
                elif isinstance(op, base.DeleteOne):
                    where_sql, where_params = self._translate_filter(op.filter)
                    sql = (
                        "DELETE FROM {table} WHERE id = "
                        "(SELECT id FROM {table} WHERE {where} ORDER BY seq ASC LIMIT 1)"
                    ).format(table=self._table, where=where_sql)
                    cur.execute(sql, where_params)
                    deleted += cur.rowcount
                else:
                    raise TypeError("Unsupported bulk op: {}".format(type(op).__name__))
        return base.BulkWriteResult(inserted, matched, modified, deleted, upserted)

    def count_documents(self, filter=None):
        where_sql, params = self._translate_filter(filter or {})
        with _cursor(self._pool) as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM {} WHERE {}".format(self._table, where_sql),
                params,
            )
            row = cur.fetchone()
        return row["c"]

    def create_index(self, keys, **kwargs):
        # Schema bootstrap (_bootstrap_schema) already creates every index
        # this codebase needs; index_helper()'s calls (cron-only - see
        # serve.py) are therefore idempotent no-ops here.
        return None

    def drop_index(self, name_or_keys):
        return None


class PostgresDatabaseAdapter(base.Database):
    def __init__(self, pool):
        self._pool = pool

    def __getitem__(self, collection_name):
        table = collection_name.replace("-", "_")
        kind = "metrics" if table in _METRICS_TABLES else "jsonb"
        return PostgresCollectionAdapter(self._pool, table, kind)


class PostgresClientAdapter(base.Client):
    def __init__(self):
        self._pool = _connect_with_retry(_connection_dsn())
        _bootstrap_schema(self._pool)

    def __getitem__(self, database_name):
        return PostgresDatabaseAdapter(self._pool)

    def get_pool(self):
        """Escape hatch for Postgres-only tooling (compaction, backups) that
        needs raw SQL access outside the cross-backend Collection interface."""
        return self._pool

    def close(self):
        self._pool.closeall()
