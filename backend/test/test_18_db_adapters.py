#!/usr/bin/env python3
"""
Black-box parity tests for the database adapter ecosystem (backend/db/).

Runs the same scenarios against both MongoClientAdapter and
PostgresClientAdapter - the narrow pymongo-shaped surface actually used by
serve.py and friends (see MONGO_MIGRATION.md for the full catalog) - against
real, ephemeral containers, matching this repo's existing test convention of
not mocking the database.
"""

import datetime

import pytest

from db import base
from db.mongo_adapter import MongoClientAdapter
from db.postgres_adapter import PostgresClientAdapter

BACKENDS = ["mongo", "postgres"]


@pytest.fixture(params=BACKENDS)
def client(request):
    if request.param == "mongo":
        c = MongoClientAdapter()
    else:
        c = PostgresClientAdapter()
    yield c
    c.close() if hasattr(c, "close") else None


@pytest.fixture
def db(client):
    database = client["labyrinth"]
    for name in [
        "hosts",
        "subnets",
        "services",
        "settings",
        "metrics",
        "metrics-latest",
    ]:
        database[name].delete_many({})
    yield database
    for name in [
        "hosts",
        "subnets",
        "services",
        "settings",
        "metrics",
        "metrics-latest",
    ]:
        database[name].delete_many({})


def test_insert_one_and_find_one(db):
    result = db["hosts"].insert_one({"mac": "AA:BB", "ip": "10.0.0.1"})
    assert result.inserted_id

    found = db["hosts"].find_one({"mac": "AA:BB"})
    assert found["ip"] == "10.0.0.1"
    assert found["_id"] == result.inserted_id

    assert db["hosts"].find_one({"mac": "does-not-exist"}) is None


def test_find_returns_all_matching(db):
    db["hosts"].insert_one({"mac": "AA:BB", "subnet": "10.0.0"})
    db["hosts"].insert_one({"mac": "CC:DD", "subnet": "10.0.0"})
    db["hosts"].insert_one({"mac": "EE:FF", "subnet": "10.0.1"})

    matched = list(db["hosts"].find({"subnet": "10.0.0"}))
    assert len(matched) == 2
    assert {h["mac"] for h in matched} == {"AA:BB", "CC:DD"}

    assert len(list(db["hosts"].find({}))) == 3


def test_or_filter(db):
    db["hosts"].insert_one({"mac": "AA:BB", "ip": "10.0.0.1"})
    db["hosts"].insert_one({"mac": "CC:DD", "ip": "10.0.0.2"})
    db["hosts"].insert_one({"mac": "EE:FF", "ip": "10.0.0.3"})

    matched = list(db["hosts"].find({"$or": [{"mac": "AA:BB"}, {"ip": "10.0.0.2"}]}))
    assert len(matched) == 2
    assert {h["mac"] for h in matched} == {"AA:BB", "CC:DD"}


def test_update_one_set(db):
    db["hosts"].insert_one({"mac": "AA:BB", "group": "old"})
    result = db["hosts"].update_one({"mac": "AA:BB"}, {"$set": {"group": "new"}})
    assert result.matched_count == 1

    assert db["hosts"].find_one({"mac": "AA:BB"})["group"] == "new"


def test_update_many_set(db):
    db["hosts"].insert_one({"mac": "AA:BB", "subnet": "10.0.0", "group": "a"})
    db["hosts"].insert_one({"mac": "CC:DD", "subnet": "10.0.0", "group": "a"})
    db["hosts"].insert_one({"mac": "EE:FF", "subnet": "10.0.1", "group": "a"})

    result = db["hosts"].update_many({"subnet": "10.0.0"}, {"$set": {"group": "b"}})
    assert result.matched_count == 2

    groups = {h["mac"]: h["group"] for h in db["hosts"].find({})}
    assert groups == {"AA:BB": "b", "CC:DD": "b", "EE:FF": "a"}


def test_exists_and_unset(db):
    db["hosts"].insert_one({"mac": "AA:BB", "service_level_expire_date": "2020-01-01"})
    db["hosts"].insert_one({"mac": "CC:DD"})

    expiring = list(db["hosts"].find({"service_level_expire_date": {"$exists": True}}))
    assert len(expiring) == 1
    assert expiring[0]["mac"] == "AA:BB"

    db["hosts"].update_one(
        {"mac": "AA:BB"}, {"$unset": {"service_level_expire_date": ""}}
    )
    assert (
        list(db["hosts"].find({"service_level_expire_date": {"$exists": True}})) == []
    )


def test_in_and_pull(db):
    db["hosts"].insert_one({"mac": "AA:BB", "services": ["ssh", "http"]})
    db["hosts"].insert_one({"mac": "CC:DD", "services": ["http"]})

    db["hosts"].update_many(
        {"services": {"$in": ["ssh"]}}, {"$pull": {"services": "ssh"}}
    )
    assert db["hosts"].find_one({"mac": "AA:BB"})["services"] == ["http"]
    assert db["hosts"].find_one({"mac": "CC:DD"})["services"] == ["http"]


def test_regex_prefix(db):
    db["settings"].insert_one({"name": "manual_disk_host_abc", "value": "1"})
    db["settings"].insert_one({"name": "manual_disk_host_def", "value": "2"})
    db["settings"].insert_one({"name": "unrelated_setting", "value": "3"})

    matched = list(db["settings"].find({"name": {"$regex": "^manual_disk_host_"}}))
    assert len(matched) == 2
    assert {m["name"] for m in matched} == {
        "manual_disk_host_abc",
        "manual_disk_host_def",
    }


def test_delete_one_and_delete_many(db):
    db["hosts"].insert_one({"mac": "AA:BB"})
    db["hosts"].insert_one({"mac": "CC:DD"})

    result = db["hosts"].delete_one({"mac": "AA:BB"})
    assert result.deleted_count == 1
    assert db["hosts"].count_documents({}) == 1

    result = db["hosts"].delete_many({})
    assert result.deleted_count == 1
    assert db["hosts"].count_documents({}) == 0


def test_id_lookup_round_trip(db):
    result = db["proxmox_clusters"].insert_one({"name": "c1"})
    found = db["proxmox_clusters"].find_one({"_id": result.inserted_id})
    assert found["name"] == "c1"

    db["proxmox_clusters"].update_one(
        {"_id": result.inserted_id}, {"$set": {"host": "10.1.1.1"}}
    )
    assert db["proxmox_clusters"].find_one({"_id": result.inserted_id})["host"] == (
        "10.1.1.1"
    )

    deleted = db["proxmox_clusters"].delete_one({"_id": result.inserted_id})
    assert deleted.deleted_count == 1
    db["proxmox_clusters"].delete_many({})


def test_insert_many_and_count(db):
    result = db["hosts"].insert_many(
        [{"mac": "AA:BB"}, {"mac": "CC:DD"}, {"mac": "EE:FF"}]
    )
    assert len(result.inserted_ids) == 3
    assert db["hosts"].count_documents({}) == 3
    assert db["hosts"].count_documents({"mac": "AA:BB"}) == 1


def test_sort_and_limit_chaining(db):
    db["hosts"].insert_one({"mac": "AA:BB", "n": 1})
    db["hosts"].insert_one({"mac": "CC:DD", "n": 2})
    db["hosts"].insert_one({"mac": "EE:FF", "n": 3})

    ordered = list(db["hosts"].find({}).sort("_id", -1).limit(2))
    assert len(ordered) == 2
    # Most-recently-inserted first.
    assert ordered[0]["mac"] == "EE:FF"


def test_find_sort_kwarg_form(db):
    db["hosts"].insert_one({"mac": "AA:BB"})
    db["hosts"].insert_one({"mac": "CC:DD"})

    ordered = list(db["hosts"].find({}, sort=[("_id", 1)]))
    assert [h["mac"] for h in ordered] == ["AA:BB", "CC:DD"]


def test_sort_by_nonexistent_field_does_not_crash(db):
    db["metrics-latest"].insert_one(
        {"name": "check_hd", "tags": {"ip": "10.0.0.1"}, "fields": {}}
    )
    # Mirrors serve.py's last_metrics(), which sorts by a field name that
    # doesn't exist on any document - must degrade gracefully, not crash.
    result = list(db["metrics-latest"].find({}).sort([("metrics-latest.timestamp", 1)]))
    assert len(result) == 1


def test_metrics_bulk_write_insert_and_upsert(db):
    item = {
        "name": "check_hd",
        "tags": {"host": "h1", "ip": "10.0.0.5", "labyrinth_name": "check_hd"},
        "fields": {"used_percent": 42.5},
        "timestamp": datetime.datetime.now(),
    }
    db["metrics-latest"].bulk_write(
        [
            base.ReplaceOne(
                {"tags": item["tags"], "name": item["name"]}, item, upsert=True
            )
        ]
    )
    db["metrics"].bulk_write([base.InsertOne(item)])

    latest = list(db["metrics-latest"].find({}))
    assert len(latest) == 1
    assert latest[0]["fields"]["used_percent"] == 42.5
    assert len(list(db["metrics"].find({}))) == 1

    # Re-upsert with the same tags/name updates in place, not duplicates.
    updated = {
        "name": "check_hd",
        "tags": {"host": "h1", "ip": "10.0.0.5", "labyrinth_name": "check_hd"},
        "fields": {"used_percent": 55.0},
        "timestamp": datetime.datetime.now(),
    }
    db["metrics-latest"].bulk_write(
        [
            base.ReplaceOne(
                {"tags": updated["tags"], "name": updated["name"]}, updated, upsert=True
            )
        ]
    )
    latest = list(db["metrics-latest"].find({}))
    assert len(latest) == 1
    assert latest[0]["fields"]["used_percent"] == 55.0


def test_dotted_tag_or_filter(db):
    db["metrics"].insert_one(
        {
            "name": "check_hd",
            "tags": {
                "host": "h1",
                "ip": "10.0.0.5",
                "mac": "AA:BB",
                "labyrinth_name": "check_hd",
            },
            "fields": {},
            "timestamp": datetime.datetime.now(),
        }
    )
    db["metrics"].insert_one(
        {
            "name": "other_check",
            "tags": {
                "host": "h2",
                "ip": "10.0.0.6",
                "mac": "CC:DD",
                "labyrinth_name": "other_check",
            },
            "fields": {},
            "timestamp": datetime.datetime.now(),
        }
    )

    or_clause = {
        "$or": [{"tags.host": "h1"}, {"tags.ip": "h1"}, {"tags.mac": "h1"}],
        "tags.labyrinth_name": "check_hd",
    }
    matched = list(db["metrics"].find(or_clause).sort("_id", -1).limit(10))
    assert len(matched) == 1
    assert matched[0]["name"] == "check_hd"


def test_ttl_emulation_lt_delete(db):
    old_item = {
        "name": "stale",
        "tags": {"host": "h1"},
        "fields": {},
        "timestamp": datetime.datetime.now() - datetime.timedelta(hours=11),
    }
    fresh_item = {
        "name": "fresh",
        "tags": {"host": "h1"},
        "fields": {},
        "timestamp": datetime.datetime.now(),
    }
    db["metrics-latest"].insert_one(old_item)
    db["metrics-latest"].insert_one(fresh_item)

    cutoff = datetime.datetime.now() - datetime.timedelta(seconds=36000)
    result = db["metrics-latest"].delete_many({"timestamp": {"$lt": cutoff}})
    assert result.deleted_count == 1

    remaining = list(db["metrics-latest"].find({}))
    assert len(remaining) == 1
    assert remaining[0]["name"] == "fresh"


def test_drop_index_is_tolerant(db):
    # Mirrors test_03_serve.py's try/except cleanup-before-test-run pattern.
    try:
        db["metrics"].drop_index("metrics.timestamp_1")
    except Exception:
        pass


def test_create_index_is_idempotent(db):
    db["hosts"].create_index("ip")
    db["hosts"].create_index("ip")


def test_get_db_factory(monkeypatch):
    import db as db_pkg

    monkeypatch.setenv("DB_BACKEND", "postgres")
    client = db_pkg.get_db()
    assert isinstance(client, PostgresClientAdapter)
    client.close()

    monkeypatch.setenv("DB_BACKEND", "mongo")
    client = db_pkg.get_db()
    assert isinstance(client, MongoClientAdapter)
    client.close()

    monkeypatch.delenv("DB_BACKEND", raising=False)
    client = db_pkg.get_db()
    assert isinstance(client, PostgresClientAdapter)  # default
    client.close()

    monkeypatch.setenv("DB_BACKEND", "not-a-real-backend")
    with pytest.raises(ValueError):
        db_pkg.get_db()
