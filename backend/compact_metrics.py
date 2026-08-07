#!/usr/bin/env python3
"""
Compacts `metrics` rows older than METRICS_RAW_RETENTION_DAYS (default 30
days) into daily aggregates in `metrics_daily` - one row per (day, name,
tags) storing min/max/avg/count for each *numeric* field found under
`fields` (non-numeric fields are intentionally dropped at this stage - see
MONGO_MIGRATION.md for why) - then deletes the now-compacted raw rows.

Postgres/TimescaleDB-only (no-ops cleanly under DB_BACKEND=mongo, which has
no equivalent capability). Intended to run daily via cron/compact_metrics.sh,
ahead of the nightly backup (cron/backup_db.sh) so backups capture the
already-compacted, smaller data. Safe to re-run: each run only looks at rows
still in `metrics` older than the cutoff, and upserts into `metrics_daily`.
"""

import collections
import datetime
import json
import os
import statistics


def _raw_retention_days():
    value = (os.environ.get("METRICS_RAW_RETENTION_DAYS") or "30").strip()
    return int(value) if value else 30


def _daily_retention_days():
    value = (os.environ.get("METRICS_DAILY_RETENTION_DAYS") or "").strip()
    return int(value) if value else None


def _numeric(value):
    # bool is a valid jsonb scalar distinct from number; isinstance(True, int)
    # is True in Python, so exclude it explicitly to avoid averaging booleans.
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _group_key(row):
    day = row["ts"].date()
    tags = row["tags"] or {}
    # sort_keys so two structurally-identical tag dicts with different
    # Python dict iteration order still group together.
    return day, row["name"], json.dumps(tags, sort_keys=True, default=str)


def compact_metrics():
    backend = (os.environ.get("DB_BACKEND") or "postgres").strip().lower()
    if backend != "postgres":
        print(
            "DB_BACKEND={!r} (not postgres) - skipping metrics compaction.".format(
                backend
            )
        )
        return 0

    import psycopg2.extras

    from db.postgres_adapter import PostgresClientAdapter

    client = PostgresClientAdapter()
    pool = client.get_pool()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=_raw_retention_days())

    conn = pool.getconn()
    try:
        conn.autocommit = True
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, ts, name, tags, fields FROM metrics WHERE ts < %s "
                "ORDER BY ts ASC",
                [cutoff],
            )
            rows = cur.fetchall()

            if not rows:
                print(
                    "No metrics rows older than {} days - nothing to compact.".format(
                        _raw_retention_days()
                    )
                )
            else:
                groups = collections.defaultdict(list)
                for row in rows:
                    groups[_group_key(row)].append(row)

                compacted_ids = []
                for (day, name, _tags_sort_key), group_rows in groups.items():
                    field_values = collections.defaultdict(list)
                    for row in group_rows:
                        for key, value in (row["fields"] or {}).items():
                            numeric = _numeric(value)
                            if numeric is not None:
                                field_values[key].append(numeric)

                    aggregated_fields = {
                        key: {
                            "min": min(values),
                            "max": max(values),
                            "avg": statistics.fmean(values),
                            "count": len(values),
                        }
                        for key, values in field_values.items()
                    }

                    tags = group_rows[0]["tags"] or {}
                    cur.execute(
                        "INSERT INTO metrics_daily (day, name, tags, fields, sample_count) "
                        "VALUES (%s, %s, %s::jsonb, %s::jsonb, %s) "
                        "ON CONFLICT (day, name, tags_key) DO UPDATE SET "
                        "fields = EXCLUDED.fields, sample_count = EXCLUDED.sample_count",
                        [
                            day,
                            name,
                            json.dumps(tags, default=str),
                            json.dumps(aggregated_fields, default=str),
                            len(group_rows),
                        ],
                    )
                    compacted_ids.extend(row["id"] for row in group_rows)

                for i in range(0, len(compacted_ids), 5000):
                    cur.execute(
                        "DELETE FROM metrics WHERE id = ANY(%s)",
                        [compacted_ids[i : i + 5000]],
                    )

                print(
                    "Compacted {} raw metrics rows (older than {} days) into "
                    "{} daily aggregate rows.".format(
                        len(compacted_ids), _raw_retention_days(), len(groups)
                    )
                )

            daily_retention = _daily_retention_days()
            if daily_retention:
                daily_cutoff = datetime.date.today() - datetime.timedelta(
                    days=daily_retention
                )
                cur.execute("DELETE FROM metrics_daily WHERE day < %s", [daily_cutoff])
                print(
                    "Pruned {} metrics_daily rows older than {} days.".format(
                        cur.rowcount, daily_retention
                    )
                )

            return len(rows)
    finally:
        pool.putconn(conn)
        # Own pool, own responsibility: compaction can run for a while, so
        # don't leave it to interpreter exit to hand the connections back.
        client.close()


if __name__ == "__main__":  # pragma: no cover
    compact_metrics()
