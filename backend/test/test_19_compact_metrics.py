#!/usr/bin/env python3
"""Tests for backend/compact_metrics.py against a real Postgres/TimescaleDB
instance - matches this repo's existing "real database, not mocks"
convention for anything that's fundamentally a SQL/aggregation problem."""

import datetime
import os

import pytest

import compact_metrics
from db.postgres_adapter import PostgresClientAdapter, _cursor


@pytest.fixture
def pg():
    client = PostgresClientAdapter()
    pool = client.get_pool()
    with _cursor(pool) as cur:
        cur.execute("DELETE FROM metrics")
        cur.execute("DELETE FROM metrics_daily")
    yield client
    with _cursor(pool) as cur:
        cur.execute("DELETE FROM metrics")
        cur.execute("DELETE FROM metrics_daily")


def _insert_raw_metric(pg, name, tags, fields, ts):
    import json

    pool = pg.get_pool()
    with _cursor(pool) as cur:
        cur.execute(
            "INSERT INTO metrics (id, ts, name, tags, fields) "
            "VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)",
            [
                "test-{}-{}".format(name, ts.timestamp()),
                ts,
                name,
                json.dumps(tags),
                json.dumps(fields),
            ],
        )


def test_skips_when_not_postgres_backend(monkeypatch, pg):
    monkeypatch.setenv("DB_BACKEND", "mongo")
    assert compact_metrics.compact_metrics() == 0


def test_no_rows_older_than_retention_is_a_noop(monkeypatch, pg):
    monkeypatch.setenv("DB_BACKEND", "postgres")
    _insert_raw_metric(
        pg, "check_hd", {"host": "h1"}, {"used_percent": 50}, datetime.datetime.now()
    )
    compact_metrics.compact_metrics()

    assert len(list(pg["labyrinth"]["metrics"].find({}))) == 1
    with _cursor(pg.get_pool()) as cur:
        cur.execute("SELECT COUNT(*) AS c FROM metrics_daily")
        assert cur.fetchone()["c"] == 0


def test_compacts_old_rows_into_daily_aggregate(monkeypatch, pg):
    monkeypatch.setenv("DB_BACKEND", "postgres")
    monkeypatch.setenv("METRICS_RAW_RETENTION_DAYS", "30")

    old_ts = datetime.datetime.now() - datetime.timedelta(days=35)
    tags = {"host": "h1", "ip": "10.0.0.1"}
    _insert_raw_metric(pg, "check_hd", tags, {"used_percent": 40.0}, old_ts)
    _insert_raw_metric(
        pg,
        "check_hd",
        tags,
        {"used_percent": 60.0},
        old_ts + datetime.timedelta(minutes=1),
    )
    _insert_raw_metric(
        pg,
        "check_hd",
        tags,
        {"used_percent": 80.0},
        old_ts + datetime.timedelta(minutes=2),
    )
    # A recent row (within retention) should NOT be compacted.
    _insert_raw_metric(
        pg, "check_hd", tags, {"used_percent": 99.0}, datetime.datetime.now()
    )

    compacted_count = compact_metrics.compact_metrics()
    assert compacted_count == 3  # only rows older than the retention cutoff

    remaining_raw = list(pg["labyrinth"]["metrics"].find({}))
    assert len(remaining_raw) == 1
    assert remaining_raw[0]["fields"]["used_percent"] == 99.0

    with _cursor(pg.get_pool()) as cur:
        cur.execute("SELECT day, name, tags, fields, sample_count FROM metrics_daily")
        rows = cur.fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "check_hd"
    assert row["sample_count"] == 3
    stats = row["fields"]["used_percent"]
    assert stats["min"] == 40.0
    assert stats["max"] == 80.0
    assert stats["avg"] == 60.0
    assert stats["count"] == 3


def test_non_numeric_fields_are_dropped_during_compaction(monkeypatch, pg):
    monkeypatch.setenv("DB_BACKEND", "postgres")
    monkeypatch.setenv("METRICS_RAW_RETENTION_DAYS", "30")

    old_ts = datetime.datetime.now() - datetime.timedelta(days=40)
    tags = {"host": "h1"}
    _insert_raw_metric(
        pg, "check_status", tags, {"status": "ok", "used_percent": 10.0}, old_ts
    )

    compact_metrics.compact_metrics()

    with _cursor(pg.get_pool()) as cur:
        cur.execute("SELECT fields FROM metrics_daily")
        fields = cur.fetchone()["fields"]
    assert "used_percent" in fields
    assert "status" not in fields


def test_daily_retention_prunes_old_aggregates(monkeypatch, pg):
    monkeypatch.setenv("DB_BACKEND", "postgres")
    monkeypatch.setenv("METRICS_RAW_RETENTION_DAYS", "30")
    monkeypatch.setenv("METRICS_DAILY_RETENTION_DAYS", "10")

    with _cursor(pg.get_pool()) as cur:
        old_day = datetime.date.today() - datetime.timedelta(days=20)
        cur.execute(
            "INSERT INTO metrics_daily (day, name, tags, fields, sample_count) "
            "VALUES (%s, %s, %s::jsonb, %s::jsonb, %s)",
            [old_day, "check_hd", "{}", "{}", 1],
        )

    compact_metrics.compact_metrics()

    with _cursor(pg.get_pool()) as cur:
        cur.execute("SELECT COUNT(*) AS c FROM metrics_daily")
        assert cur.fetchone()["c"] == 0


def test_rerun_is_idempotent(monkeypatch, pg):
    monkeypatch.setenv("DB_BACKEND", "postgres")
    monkeypatch.setenv("METRICS_RAW_RETENTION_DAYS", "30")

    old_ts = datetime.datetime.now() - datetime.timedelta(days=35)
    tags = {"host": "h1"}
    _insert_raw_metric(pg, "check_hd", tags, {"used_percent": 50.0}, old_ts)

    compact_metrics.compact_metrics()
    first_count = compact_metrics.compact_metrics()  # nothing left to compact

    assert first_count == 0
    with _cursor(pg.get_pool()) as cur:
        cur.execute("SELECT COUNT(*) AS c FROM metrics_daily")
        assert cur.fetchone()["c"] == 1
