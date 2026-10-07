#!/usr/bin/env python3
"""
Tests for the Telegraf ingest counters written by the Go ingest service
(metrics-go) and read back by backend/ingest_counters.py.
"""

import json

import pytest

import ingest_counters
import serve
from common.test import unwrap


class FakeRedis:
    """
    Just enough Redis to stand in for the counters: hashes for the running
    totals and strings for the per-minute buckets.  Values come back as bytes,
    the way redis-py returns them without decode_responses.
    """

    def __init__(self, hashes=None, strings=None):
        self.hashes = {}
        for key, fields in (hashes or {}).items():
            self.hashes[key] = {
                _bytes(field): _bytes(value) for field, value in fields.items()
            }

        self.strings = {key: _bytes(value) for key, value in (strings or {}).items()}

        self.mget_calls = 0
        self.deleted = []

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def mget(self, keys):
        self.mget_calls += 1
        return [self.strings.get(key) for key in keys]

    def delete(self, *keys):
        self.deleted.extend(keys)
        removed = 0
        for key in keys:
            removed += self.hashes.pop(key, None) is not None
            removed += self.strings.pop(key, None) is not None
        return removed


def _bytes(value):
    if isinstance(value, bytes):
        return value
    return str(value).encode()


# Frozen so the minute buckets are predictable: 1753988580 // 60.
NOW = 1753988580
MINUTE = NOW // 60


def counter_hash(**overrides):
    fields = {
        "requests": 120,
        "metrics": 4800,
        "skipped": 0,
        "last_batch": 40,
        "first_seen": NOW - 3600,
        "last_seen": NOW,
        "mac": "02:42:AC:13:00:02",
        "ip": "172.19.0.2",
        "host": "web01",
    }
    fields.update(overrides)
    return fields


@pytest.fixture
def hosts_collection():
    """Keeps the hosts collection clean around the route tests."""
    serve.db["labyrinth"]["hosts"].delete_many({})
    yield serve.db["labyrinth"]["hosts"]
    serve.db["labyrinth"]["hosts"].delete_many({})


# ---------------------------------------------------------------------------
# candidate_ids
# ---------------------------------------------------------------------------


def test_candidate_ids_prefers_the_upper_cased_mac():
    # metrics-go keys a client by upper(mac) first, then ip.
    assert ingest_counters.candidate_ids(
        mac="02:42:ac:13:00:02", ip="172.19.0.2", requested="172.19.0.2"
    ) == ["02:42:AC:13:00:02", "172.19.0.2"]


def test_candidate_ids_includes_the_requested_value():
    assert ingest_counters.candidate_ids(requested="aa:bb:cc:dd:ee:ff") == [
        "AA:BB:CC:DD:EE:FF",
        "aa:bb:cc:dd:ee:ff",
    ]


def test_candidate_ids_skips_blanks_and_duplicates():
    assert ingest_counters.candidate_ids(
        mac="  ", ip="10.0.0.1", requested="10.0.0.1"
    ) == ["10.0.0.1"]
    assert ingest_counters.candidate_ids() == []


# ---------------------------------------------------------------------------
# read_counts
# ---------------------------------------------------------------------------


def test_read_counts_returns_totals_and_history():
    fake = FakeRedis(
        hashes={"ingest:count:02:42:AC:13:00:02": counter_hash()},
        strings={
            "ingest:min:02:42:AC:13:00:02:{}:r".format(MINUTE): 6,
            "ingest:min:02:42:AC:13:00:02:{}:m".format(MINUTE): 240,
            "ingest:min:02:42:AC:13:00:02:{}:r".format(MINUTE - 1): 6,
            "ingest:min:02:42:AC:13:00:02:{}:m".format(MINUTE - 1): 200,
        },
    )

    result = ingest_counters.read_counts(
        mac="02:42:ac:13:00:02", ip="172.19.0.2", redis_client=fake, now=NOW
    )

    assert result["found"] is True
    assert result["client_id"] == "02:42:AC:13:00:02"
    assert result["requests"] == 120
    assert result["metrics"] == 4800
    assert result["last_batch"] == 40
    assert result["host"] == "web01"
    assert result["mac"] == "02:42:AC:13:00:02"

    # The window is zero-filled so the dashboard can plot it straight through.
    assert len(result["per_minute"]) == ingest_counters.HISTORY_MINUTES
    assert result["per_minute"][-1] == {
        "minute": MINUTE,
        "timestamp": MINUTE * 60,
        "requests": 6,
        "metrics": 240,
    }
    assert result["per_minute"][-2]["metrics"] == 200
    assert result["per_minute"][0]["requests"] == 0

    assert result["requests_last_hour"] == 12
    assert result["metrics_last_hour"] == 440

    # One MGET, not one round trip per bucket.
    assert fake.mget_calls == 1


def test_read_counts_falls_back_to_the_ip_key():
    fake = FakeRedis(hashes={"ingest:count:10.0.0.7": counter_hash(requests=5)})

    result = ingest_counters.read_counts(
        mac="AA:BB:CC:DD:EE:FF", ip="10.0.0.7", redis_client=fake, now=NOW
    )

    assert result["client_id"] == "10.0.0.7"
    assert result["requests"] == 5


def test_read_counts_when_nothing_has_been_recorded():
    fake = FakeRedis()

    result = ingest_counters.read_counts(
        mac="AA:BB:CC:DD:EE:FF", ip="10.0.0.7", redis_client=fake, now=NOW
    )

    assert result["found"] is False
    assert result["client_id"] == "AA:BB:CC:DD:EE:FF"
    assert result["requests"] == 0
    assert result["per_minute"] == []
    assert fake.mget_calls == 0


def test_read_counts_with_no_identifiers_at_all():
    result = ingest_counters.read_counts(redis_client=FakeRedis(), now=NOW)

    assert result["found"] is False
    assert result["client_id"] == ""
    assert result["candidates"] == []


def test_read_counts_tolerates_junk_values():
    fake = FakeRedis(
        hashes={
            "ingest:count:10.0.0.7": {
                b"requests": b"not-a-number",
                "metrics": "",
                "host": "web01",
            }
        },
        strings={"ingest:min:10.0.0.7:{}:r".format(MINUTE): "oops"},
    )

    # A client that somehow decoded responses would hand back plain strings.
    fake.hashes["ingest:count:10.0.0.7"][b"last_batch"] = 12

    result = ingest_counters.read_counts(ip="10.0.0.7", redis_client=fake, now=NOW)

    assert result["requests"] == 0
    assert result["metrics"] == 0
    assert result["first_seen"] == 0
    assert result["last_batch"] == 12
    assert result["mac"] == ""
    assert result["requests_last_hour"] == 0


def test_read_counts_handles_a_short_mget_response():
    class ShortRedis(FakeRedis):
        def mget(self, keys):
            super().mget(keys)
            return []

    fake = ShortRedis(hashes={"ingest:count:10.0.0.7": counter_hash()})

    result = ingest_counters.read_counts(ip="10.0.0.7", redis_client=fake, now=NOW)

    assert result["requests_last_hour"] == 0
    assert len(result["per_minute"]) == ingest_counters.HISTORY_MINUTES


def test_read_counts_honours_a_custom_window():
    fake = FakeRedis(hashes={"ingest:count:10.0.0.7": counter_hash()})

    result = ingest_counters.read_counts(
        ip="10.0.0.7", minutes=5, redis_client=fake, now=NOW
    )

    assert result["window_minutes"] == 5
    assert len(result["per_minute"]) == 5
    assert result["per_minute"][0]["minute"] == MINUTE - 4


def test_read_counts_uses_the_current_time_by_default():
    fake = FakeRedis(hashes={"ingest:count:10.0.0.7": counter_hash()})

    result = ingest_counters.read_counts(ip="10.0.0.7", minutes=2, redis_client=fake)

    assert len(result["per_minute"]) == 2
    assert result["per_minute"][1]["minute"] == result["per_minute"][0]["minute"] + 1


# ---------------------------------------------------------------------------
# reset_counts
# ---------------------------------------------------------------------------


def test_reset_counts_removes_totals_and_buckets():
    fake = FakeRedis(
        hashes={"ingest:count:10.0.0.7": counter_hash()},
        strings={"ingest:min:10.0.0.7:{}:r".format(MINUTE): 3},
    )

    removed = ingest_counters.reset_counts(
        ip="10.0.0.7", minutes=2, redis_client=fake, now=NOW
    )

    assert removed == 2
    assert "ingest:count:10.0.0.7" in fake.deleted
    assert "ingest:min:10.0.0.7:{}:r".format(MINUTE) in fake.deleted
    # Both the counter key and every bucket in the window.
    assert len(fake.deleted) == 1 + 2 * 2


def test_reset_counts_with_nothing_to_target():
    fake = FakeRedis()

    assert ingest_counters.reset_counts(redis_client=fake) == 0
    assert fake.deleted == []


def test_reset_counts_when_redis_returns_nothing():
    class NoneRedis(FakeRedis):
        def delete(self, *keys):
            super().delete(*keys)
            return None

    assert ingest_counters.reset_counts(ip="10.0.0.7", redis_client=NoneRedis()) == 0


# ---------------------------------------------------------------------------
# get_redis
# ---------------------------------------------------------------------------


def test_get_redis_returns_the_supplied_client():
    fake = FakeRedis()
    assert ingest_counters.get_redis(fake) is fake


def test_get_redis_builds_a_client(monkeypatch):
    created = {}

    def fake_redis(host=None):
        created["host"] = host
        return "connection"

    monkeypatch.setattr(ingest_counters.redis, "Redis", fake_redis)
    monkeypatch.setenv("REDIS_HOST", "cache")

    assert ingest_counters.get_redis() == "connection"
    assert created["host"] == "cache"


def test_get_redis_defaults_the_host(monkeypatch):
    created = {}

    def fake_redis(host=None):
        created["host"] = host
        return "connection"

    monkeypatch.setattr(ingest_counters.redis, "Redis", fake_redis)
    monkeypatch.delenv("REDIS_HOST", raising=False)

    ingest_counters.get_redis()
    assert created["host"] == "redis"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def test_read_metric_counts_route_resolves_the_host(hosts_collection, monkeypatch):
    hosts_collection.insert_one(
        {"ip": "172.19.0.2", "mac": "02:42:ac:13:00:02", "host": "web01"}
    )

    captured = {}

    def fake_read(mac="", ip="", requested="", **kwargs):
        captured.update({"mac": mac, "ip": ip, "requested": requested})
        return {"found": True, "requests": 7}

    monkeypatch.setattr(ingest_counters, "read_counts", fake_read)

    body, status = unwrap(serve.read_metric_counts)("172.19.0.2")

    assert status == 200
    assert json.loads(body)["requests"] == 7
    # The host record supplies the MAC even though it was looked up by IP.
    assert captured == {
        "mac": "02:42:ac:13:00:02",
        "ip": "172.19.0.2",
        "requested": "172.19.0.2",
    }


def test_read_metric_counts_route_for_an_unknown_host(hosts_collection, monkeypatch):
    captured = {}

    def fake_read(mac="", ip="", requested="", **kwargs):
        captured.update({"mac": mac, "ip": ip, "requested": requested})
        return {"found": False}

    monkeypatch.setattr(ingest_counters, "read_counts", fake_read)

    body, status = unwrap(serve.read_metric_counts)("10.9.9.9")

    assert status == 200
    assert json.loads(body)["found"] is False
    assert captured == {"mac": "", "ip": "", "requested": "10.9.9.9"}


def test_reset_metric_counts_route(hosts_collection, monkeypatch):
    hosts_collection.insert_one({"ip": "172.19.0.2", "mac": "02:42:ac:13:00:02"})

    captured = {}

    def fake_reset(mac="", ip="", requested="", **kwargs):
        captured.update({"mac": mac, "ip": ip, "requested": requested})
        return 4

    monkeypatch.setattr(ingest_counters, "reset_counts", fake_reset)

    body, status = unwrap(serve.reset_metric_counts)("02:42:ac:13:00:02")

    assert status == 200
    assert json.loads(body) == {"deleted": 4}
    assert captured["mac"] == "02:42:ac:13:00:02"
    assert captured["requested"] == "02:42:ac:13:00:02"
