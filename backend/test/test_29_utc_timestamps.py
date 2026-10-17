#!/usr/bin/env python3
"""
Metric timestamps are naive UTC end to end (common/utc.py).  Production
containers run with TZ=America/Chicago, where local-time conversions stored
every metric five hours off while still judging it correctly - so these run
under that zone, where the bug shows.
"""
import datetime
import os
import time
import uuid

import pytest

import metrics
import serve
from common import utc
from common.test import unwrap


@pytest.fixture
def chicago():
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "America/Chicago"
    time.tzset()
    yield
    if previous is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = previous
    time.tzset()


def test_helpers_ignore_the_local_zone(chicago):
    assert utc.from_epoch(0) == datetime.datetime(1970, 1, 1)
    assert utc.to_epoch(datetime.datetime(1970, 1, 1)) == 0
    assert abs(utc.to_epoch(utc.now()) - time.time()) < 5


def test_bulk_insert_stores_utc_and_judges_fresh(chicago):
    """A metric written now is stored as now in UTC, and is not stale."""
    host = "utc-{}".format(uuid.uuid4().hex[:8])
    sent = int(time.time())
    metric = {
        "name": "utc_check",
        "tags": {"host": host, "ip": host},
        "fields": {"value": 1},
        "timestamp": sent,
    }
    assert unwrap(serve.insert_metric)({"metrics": [metric]})[1] == 200
    unwrap(serve.bulk_insert)()

    latest = serve.db["labyrinth"]["metrics-latest"].find_one({"tags.host": host})
    history = serve.db["labyrinth"]["metrics"].find_one({"tags.host": host})
    try:
        for row in [latest, history]:
            assert row["timestamp"] == utc.from_epoch(sent)
            assert row["timestamp"].tzinfo is None

        service = {
            "name": "utc_check",
            "type": "check",
            "metric": "value",
            "comparison": "greater",
            "value": 0,
        }
        # Read as local time it would land five hours in the future/past
        assert metrics.judge(dict(latest), service, stale_time=600) is True
        assert utc.to_epoch(latest["timestamp"]) == sent
    finally:
        serve.db["labyrinth"]["metrics-latest"].delete_many({"tags.host": host})
        serve.db["labyrinth"]["metrics"].delete_many({"tags.host": host})


def test_metrics_latest_ttl_uses_utc(chicago):
    """The 10h TTL sweep: a local-time cutoff kept rows 15h under this zone."""
    host = "utc-{}".format(uuid.uuid4().hex[:8])
    collection = serve.db["labyrinth"]["metrics-latest"]
    for name, hours in [("kept", 9), ("expired", 11)]:
        collection.insert_one(
            {
                "name": name,
                "tags": {"host": host},
                "fields": {},
                "timestamp": utc.now() - datetime.timedelta(hours=hours),
            }
        )
    try:
        unwrap(serve.bulk_insert)()
        remaining = [m["name"] for m in collection.find({"tags.host": host})]
        assert remaining == ["kept"]
    finally:
        collection.delete_many({"tags.host": host})
