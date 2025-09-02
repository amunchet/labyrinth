#!/usr/bin/env python3
import re
from datetime import datetime, timezone
import pytest

import serve
import utils

TEST_HOST_PREFIX = "testutils_"  # used to ensure we only clean up what we created


def _hosts_coll():
    return serve.mongo_client["labyrinth"]["hosts"]


def _cleanup_test_hosts():
    # delete ONLY hosts we created for these tests
    _hosts_coll().delete_many({"host": {"$regex": f"^{re.escape(TEST_HOST_PREFIX)}"}})


@pytest.fixture
def setup():
    """Create a clean slate for our test hosts only."""
    _cleanup_test_hosts()
    yield "Setting up..."
    _cleanup_test_hosts()
    return "Done"


def test_update_service_expire_dates_clears_only_expired_and_spares_others(setup):
    coll = _hosts_coll()

    expired_iso = "2020-01-01T00:00:00+00:00"
    future_iso = "2999-01-01T00:00:00+00:00"

    # Control doc that should NEVER be touched (not ours)
    control_id = coll.insert_one(
        {
            "host": "production-db-01",
            "service_level": "warning",
            "service_level_expire_date": future_iso,
        }
    ).inserted_id

    # Test docs (ours) with the prefix
    docs = [
        {
            "_id": f"{TEST_HOST_PREFIX}expired_string",
            "host": f"{TEST_HOST_PREFIX}expired.example",
            "service_level": "warning",
            "service_level_expire_date": expired_iso,  # should be removed
        },
        {
            "_id": f"{TEST_HOST_PREFIX}future_string",
            "host": f"{TEST_HOST_PREFIX}future.example",
            "service_level": "warning",
            "service_level_expire_date": future_iso,  # should remain
        },
        {
            "_id": f"{TEST_HOST_PREFIX}none_value",
            "host": f"{TEST_HOST_PREFIX}none.example",
            "service_level": "warning",
            "service_level_expire_date": None,  # ignored by job
        },
        {
            "_id": f"{TEST_HOST_PREFIX}invalid_string",
            "host": f"{TEST_HOST_PREFIX}invalid.example",
            "service_level": "warning",
            "service_level_expire_date": "not a date",  # parsing fails -> ignored
        },
        {
            "_id": f"{TEST_HOST_PREFIX}missing_field",
            "host": f"{TEST_HOST_PREFIX}missing.example",
            "service_level": "warning",
            # no service_level_expire_date
        },
    ]
    coll.insert_many(docs)

    modified = utils.update_service_expire_dates()
    assert modified == 1  # only the expired one should be cleared

    # Verify our expired doc is cleared
    d = coll.find_one({"_id": f"{TEST_HOST_PREFIX}expired_string"})
    assert d is not None
    assert "service_level_expire_date" not in d
    assert "service_level" not in d

    # Verify our future doc remains intact
    d = coll.find_one({"_id": f"{TEST_HOST_PREFIX}future_string"})
    assert d is not None
    assert d.get("service_level_expire_date") == future_iso
    assert d.get("service_level") == "warning"

    # None value unchanged
    d = coll.find_one({"_id": f"{TEST_HOST_PREFIX}none_value"})
    assert d is not None
    assert "service_level_expire_date" in d and d["service_level_expire_date"] is None
    assert d.get("service_level") == "warning"

    # Invalid string unchanged
    d = coll.find_one({"_id": f"{TEST_HOST_PREFIX}invalid_string"})
    assert d is not None
    assert d.get("service_level_expire_date") == "not a date"
    assert d.get("service_level") == "warning"

    # Missing field unchanged
    d = coll.find_one({"_id": f"{TEST_HOST_PREFIX}missing_field"})
    assert d is not None
    assert "service_level_expire_date" not in d
    assert d.get("service_level") == "warning"

    # Control doc (non-test) not touched
    control = coll.find_one({"_id": control_id})
    assert control is not None
    assert control.get("service_level_expire_date") == future_iso
    assert control.get("service_level") == "warning"


def test_update_service_expire_dates_idempotent(setup):
    coll = _hosts_coll()
    expired_iso = "2020-01-01T00:00:00+00:00"

    coll.insert_one(
        {
            "_id": f"{TEST_HOST_PREFIX}once_only",
            "host": f"{TEST_HOST_PREFIX}expired.example",
            "service_level": "warning",
            "service_level_expire_date": expired_iso,
        }
    )

    first = utils.update_service_expire_dates()
    assert first == 1

    second = utils.update_service_expire_dates()
    assert second == 0

    doc = coll.find_one({"_id": f"{TEST_HOST_PREFIX}once_only"})
    assert doc is not None
    assert "service_level_expire_date" not in doc
    assert "service_level" not in doc


def test_update_service_expire_dates_handles_multiple(setup):
    coll = _hosts_coll()

    expired_ids = [f"{TEST_HOST_PREFIX}expired_{i}" for i in range(5)]
    future_ids = [f"{TEST_HOST_PREFIX}future_{i}" for i in range(3)]

    expired_iso = "2021-01-01T00:00:00+00:00"
    future_iso = "2099-01-01T00:00:00+00:00"

    coll.insert_many(
        [
            {
                "_id": _id,
                "host": f"{TEST_HOST_PREFIX}{_id}.example",
                "service_level": "critical",
                "service_level_expire_date": expired_iso,
            }
            for _id in expired_ids
        ]
        + [
            {
                "_id": _id,
                "host": f"{TEST_HOST_PREFIX}{_id}.example",
                "service_level": "critical",
                "service_level_expire_date": future_iso,
            }
            for _id in future_ids
        ]
    )

    modified = utils.update_service_expire_dates()
    assert modified == len(expired_ids)

    # expired cleared
    for _id in expired_ids:
        d = coll.find_one({"_id": _id})
        assert d is not None
        assert "service_level_expire_date" not in d
        assert "service_level" not in d

    # future unchanged
    for _id in future_ids:
        d = coll.find_one({"_id": _id})
        assert d is not None
        assert d.get("service_level_expire_date") == future_iso
        assert d.get("service_level") == "critical"
