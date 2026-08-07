#!/usr/bin/env python3
"""Tests for backend/migrate_to_postgres.py against real Mongo and Postgres
containers - matches this repo's existing "real database" test convention."""

import sys
import time

import pytest

import migrate_to_postgres as migrate
from db.mongo_adapter import MongoClientAdapter
from db.postgres_adapter import PostgresClientAdapter

# migrate_to_postgres.main() intentionally opens its own fresh Mongo/Postgres
# connections (matching how an operator would actually run this script,
# rather than reusing a pytest fixture's already-open ones). In this
# particular sandboxed test environment (not a real deployment concern - see
# MONGO_MIGRATION.md), a brand-new pymongo.MongoClient's first query can lag
# behind a write made moments earlier via a different, already-open
# connection to the same standalone mongod - and the lag isn't a fixed
# settling time (empirically non-monotonic under load), so a fixed sleep
# isn't reliable. These tests write their fixture data, then immediately
# hand off to main()'s fresh connections; _wait_until_visible_on_fresh_connection
# polls with a real fresh connection (mirroring exactly what main() will do)
# until the write is actually visible, instead of guessing a delay.
# Real-world usage never has this insert-then-open-a-different-fresh-client-
# immediately pattern, so this is purely a test-environment concern.


def _wait_until_visible_on_fresh_connection(count_fn, expected, timeout=10.0):
    deadline = time.monotonic() + timeout
    last_seen = None
    while time.monotonic() < deadline:
        last_seen = count_fn()
        if last_seen == expected:
            return
        time.sleep(0.1)
    raise AssertionError(
        "Fresh connection never saw expected count {} (last saw {}) within {}s".format(
            expected, last_seen, timeout
        )
    )


@pytest.fixture
def dbs():
    mongo_client = MongoClientAdapter()
    pg_client = PostgresClientAdapter()
    mongo_db = mongo_client["labyrinth"]
    pg_db = pg_client["labyrinth"]

    for name in migrate.COLLECTIONS:
        mongo_db[name].delete_many({})
        pg_db[name].delete_many({})

    yield mongo_db, pg_db

    for name in migrate.COLLECTIONS:
        mongo_db[name].delete_many({})
        pg_db[name].delete_many({})


def test_copy_collection_jsonb(dbs):
    mongo_db, pg_db = dbs
    mongo_db["hosts"].insert_one({"mac": "AA:BB", "ip": "10.0.0.1"})
    mongo_db["hosts"].insert_one({"mac": "CC:DD", "ip": "10.0.0.2"})

    count = migrate._copy_collection(mongo_db, pg_db, "hosts", dry_run=False)
    assert count == 2

    copied = {h["mac"]: h["ip"] for h in pg_db["hosts"].find({})}
    assert copied == {"AA:BB": "10.0.0.1", "CC:DD": "10.0.0.2"}


def test_copy_collection_dry_run_writes_nothing(dbs):
    mongo_db, pg_db = dbs
    mongo_db["hosts"].insert_one({"mac": "AA:BB"})

    count = migrate._copy_collection(mongo_db, pg_db, "hosts", dry_run=True)
    assert count == 1
    assert pg_db["hosts"].count_documents({}) == 0


def test_copy_collection_metrics(dbs):
    import datetime

    mongo_db, pg_db = dbs
    mongo_db["metrics"].insert_one(
        {
            "name": "check_hd",
            "tags": {"host": "h1"},
            "fields": {"used": 42},
            "timestamp": datetime.datetime.now(),
        }
    )

    count = migrate._copy_collection(mongo_db, pg_db, "metrics", dry_run=False)
    assert count == 1

    copied = list(pg_db["metrics"].find({}))
    assert len(copied) == 1
    assert copied[0]["name"] == "check_hd"
    assert copied[0]["fields"]["used"] == 42


def test_copy_preserves_id(dbs):
    mongo_db, pg_db = dbs
    result = mongo_db["proxmox_clusters"].insert_one({"name": "c1"})
    mongo_id = str(result.inserted_id)

    migrate._copy_collection(mongo_db, pg_db, "proxmox_clusters", dry_run=False)

    found = pg_db["proxmox_clusters"].find_one({"_id": mongo_id})
    assert found is not None
    assert found["name"] == "c1"


def test_rerun_is_idempotent_upsert(dbs):
    mongo_db, pg_db = dbs
    result = mongo_db["hosts"].insert_one({"mac": "AA:BB", "group": "a"})

    migrate._copy_collection(mongo_db, pg_db, "hosts", dry_run=False)
    # Simulate the source doc changing before a second run.
    mongo_db["hosts"].update_one({"_id": result.inserted_id}, {"$set": {"group": "b"}})
    migrate._copy_collection(mongo_db, pg_db, "hosts", dry_run=False)

    assert pg_db["hosts"].count_documents({}) == 1
    assert pg_db["hosts"].find_one({"mac": "AA:BB"})["group"] == "b"


def test_verify_counts_match(dbs, capsys):
    mongo_db, pg_db = dbs
    mongo_db["hosts"].insert_one({"mac": "AA:BB"})
    pg_db["hosts"].insert_one({"mac": "AA:BB"})

    for name in migrate.COLLECTIONS:
        if name != "hosts":
            mongo_db[name].delete_many({})
            pg_db[name].delete_many({})

    ok = migrate._verify_counts(mongo_db, pg_db)
    assert ok is True
    assert "OK" in capsys.readouterr().out


def test_verify_counts_mismatch(dbs, capsys):
    mongo_db, pg_db = dbs
    mongo_db["hosts"].insert_one({"mac": "AA:BB"})
    mongo_db["hosts"].insert_one({"mac": "CC:DD"})
    pg_db["hosts"].insert_one({"mac": "AA:BB"})

    ok = migrate._verify_counts(mongo_db, pg_db)
    assert ok is False
    assert "MISMATCH" in capsys.readouterr().out


def test_main_dry_run(dbs, monkeypatch, capsys):
    mongo_db, _pg_db = dbs
    mongo_db["hosts"].insert_one({"mac": "AA:BB"})
    _wait_until_visible_on_fresh_connection(
        lambda: MongoClientAdapter()["labyrinth"]["hosts"].count_documents({}), 1
    )

    monkeypatch.setattr(sys, "argv", ["migrate_to_postgres.py", "--dry-run"])
    migrate.main()

    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "not written" in out


def test_main_verify_only(dbs, monkeypatch, capsys):
    mongo_db, pg_db = dbs
    mongo_db["hosts"].insert_one({"mac": "AA:BB"})
    pg_db["hosts"].insert_one({"mac": "AA:BB"})
    for name in migrate.COLLECTIONS:
        if name != "hosts":
            mongo_db[name].delete_many({})
            pg_db[name].delete_many({})
    _wait_until_visible_on_fresh_connection(
        lambda: MongoClientAdapter()["labyrinth"]["hosts"].count_documents({}), 1
    )

    monkeypatch.setattr(sys, "argv", ["migrate_to_postgres.py", "--verify-only"])
    with pytest.raises(SystemExit) as exc:
        migrate.main()
    assert exc.value.code == 0


def test_main_live_migration(dbs, monkeypatch, capsys):
    mongo_db, _pg_db = dbs
    mongo_db["hosts"].insert_one({"mac": "AA:BB"})
    _wait_until_visible_on_fresh_connection(
        lambda: MongoClientAdapter()["labyrinth"]["hosts"].count_documents({}), 1
    )

    monkeypatch.setattr(sys, "argv", ["migrate_to_postgres.py"])
    migrate.main()

    out = capsys.readouterr().out
    assert "Migration complete and verified" in out
