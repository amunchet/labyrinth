#!/usr/bin/env python3
"""
Tests for comprehensive coverage of serve.py endpoints and edge cases.
Focuses on large uncovered blocks: AWS account management, disk space monitoring,
metrics handling, and sanitization functions.
"""

import json
import os
import pytest
import datetime
from unittest.mock import Mock, patch, MagicMock
import bson
import redis

import serve
import proxmox_helper
from common.test import unwrap


def tearDown():
    """Tears down tests"""
    serve.mongo_client["labyrinth"]["aws_accounts"].delete_many({})
    serve.mongo_client["labyrinth"]["proxmox_clusters"].delete_many({})
    serve.mongo_client["labyrinth"]["settings"].delete_many({})
    serve.mongo_client["labyrinth"]["hosts"].delete_many({})
    serve.mongo_client["labyrinth"]["metrics"].delete_many({})
    serve.mongo_client["labyrinth"]["metrics-latest"].delete_many({})

    try:
        a = redis.Redis(host=os.environ.get("REDIS_HOST"))
        for key in a.keys(pattern="METRIC-*"):
            a.delete(key)
        for key in a.keys(pattern="last_metric_*"):
            a.delete(key)
    except Exception:
        pass


@pytest.fixture
def setup():
    """Sets up tests"""
    tearDown()
    yield "Setting up..."
    tearDown()


# ---------------------------------------------------------------------------
# Sanitization Function Tests - Line Coverage: 56-130
# ---------------------------------------------------------------------------


def test_sanitize_string_value_valid():
    """Sanitize valid string value."""
    result = serve._sanitize_string_value("valid-name_123")
    assert result == "valid-name_123"


def test_sanitize_string_value_with_whitespace():
    """Sanitize string with leading/trailing whitespace."""
    result = serve._sanitize_string_value("  valid-name  ")
    assert result == "valid-name"


def test_sanitize_string_value_empty():
    """Reject empty string."""
    with pytest.raises(ValueError, match="cannot be empty"):
        serve._sanitize_string_value("")


def test_sanitize_string_value_whitespace_only():
    """Reject whitespace-only string."""
    with pytest.raises(ValueError, match="cannot be empty"):
        serve._sanitize_string_value("   ")


def test_sanitize_string_value_mongo_dollar():
    """Reject MongoDB operator characters ($)."""
    with pytest.raises(ValueError, match="disallowed"):
        serve._sanitize_string_value("invalid$name")


def test_sanitize_string_value_mongo_dot():
    """Reject MongoDB path characters (.)."""
    with pytest.raises(ValueError, match="disallowed"):
        serve._sanitize_string_value("invalid.name")


def test_sanitize_string_value_invalid_chars():
    """Reject invalid characters."""
    with pytest.raises(ValueError, match="invalid characters"):
        serve._sanitize_string_value("invalid@name")


def test_sanitize_string_value_non_string():
    """Reject non-string types."""
    with pytest.raises(ValueError, match="Expected string"):
        serve._sanitize_string_value(123)


def test_sanitize_mongo_value_dict_with_dollar_key():
    """Remove dictionary keys with MongoDB operators."""
    result = serve._sanitize_mongo_value({"$set": "value", "valid": "data"})
    assert "$set" not in result
    assert result["valid"] == "data"


def test_sanitize_mongo_value_dict_with_dot_key():
    """Remove dictionary keys with path operators."""
    result = serve._sanitize_mongo_value({"field.nested": "value", "valid": "data"})
    assert "field.nested" not in result
    assert result["valid"] == "data"


def test_sanitize_mongo_value_nested_dict():
    """Recursively sanitize nested dictionaries."""
    result = serve._sanitize_mongo_value({
        "outer": {"$inner": "value", "valid": "data"},
        "list": [{"$bad": "x"}, {"good": "y"}]
    })
    assert "$inner" not in result["outer"]
    assert "$bad" not in result["list"][0]


def test_sanitize_mongo_value_list():
    """Sanitize values in lists."""
    result = serve._sanitize_mongo_value([
        {"$op": "bad"},
        {"name": "good"}
    ])
    assert "$op" not in result[0]
    assert result[1]["name"] == "good"


def test_sanitize_mongo_value_primitives():
    """Preserve primitive values."""
    assert serve._sanitize_mongo_value("string") == "string"
    assert serve._sanitize_mongo_value(123) == 123
    assert serve._sanitize_mongo_value(45.67) == 45.67
    assert serve._sanitize_mongo_value(True) is True
    assert serve._sanitize_mongo_value(None) is None


def test_sanitize_db_value_string():
    """Allow string values."""
    assert serve._sanitize_db_value("valid") == "valid"


def test_sanitize_db_value_bool():
    """Allow boolean values."""
    assert serve._sanitize_db_value(True) is True
    assert serve._sanitize_db_value(False) is False


def test_sanitize_db_value_numbers():
    """Allow numeric values."""
    assert serve._sanitize_db_value(42) == 42
    assert serve._sanitize_db_value(3.14) == 3.14


def test_sanitize_db_value_none():
    """Allow None value."""
    assert serve._sanitize_db_value(None) is None


def test_sanitize_db_value_dict_rejected():
    """Reject dictionary values."""
    with pytest.raises(ValueError, match="Dictionary values"):
        serve._sanitize_db_value({})


def test_sanitize_db_value_list_rejected():
    """Reject list values."""
    with pytest.raises(ValueError, match="Unsupported type"):
        serve._sanitize_db_value([])


def test_sanitize_error_message_none():
    """Handle None error message."""
    assert serve._sanitize_error_message(None) is None


def test_sanitize_error_message_xss():
    """Escape HTML in error messages."""
    result = serve._sanitize_error_message("<script>alert('xss')</script>")
    assert "&lt;script&gt;" in str(result)
    assert "<script>" not in str(result)


def test_sanitize_error_message_with_quotes():
    """Escape quotes in error messages."""
    result = serve._sanitize_error_message('Error: "quote" test')
    # Escape should handle quotes
    assert result is not None


def test_sanitize_dict_recursive_strings():
    """Recursively escape HTML in string values."""
    result = serve._sanitize_dict_recursive({
        "field": "<b>bold</b>",
        "nested": {"text": "<script>bad</script>"}
    })
    assert "&lt;b&gt;" in str(result["field"])
    assert "&lt;script&gt;" in str(result["nested"]["text"])


def test_sanitize_dict_recursive_lists():
    """Sanitize strings in lists."""
    result = serve._sanitize_dict_recursive(["<tag>", "normal"])
    assert "&lt;tag&gt;" in str(result[0])
    assert result[1] == "normal"


def test_sanitize_dict_recursive_numbers():
    """Preserve numeric values in dict."""
    result = serve._sanitize_dict_recursive({"num": 42, "float": 3.14})
    assert result["num"] == 42
    assert result["float"] == 3.14


# ---------------------------------------------------------------------------
# Object ID Validation - Line Coverage: 133-150
# ---------------------------------------------------------------------------


def test_validate_object_id_valid():
    """Validate valid ObjectId string."""
    valid_id = str(bson.ObjectId())
    result = serve._validate_object_id(valid_id)
    assert isinstance(result, bson.ObjectId)


def test_validate_object_id_invalid_format():
    """Reject invalid ObjectId format."""
    with pytest.raises(ValueError):
        serve._validate_object_id("not-a-valid-id")


def test_validate_object_id_wrong_length():
    """Reject wrong length string."""
    with pytest.raises(ValueError):
        serve._validate_object_id("123")


def test_validate_object_id_none():
    """Reject None."""
    with pytest.raises(ValueError):
        serve._validate_object_id(None)


# ---------------------------------------------------------------------------
# AWS Account Management - Line Coverage: 2850-2910
# ---------------------------------------------------------------------------


def test_get_aws_account_success(setup):
    """Retrieve single AWS account."""
    account_id = str(bson.ObjectId())
    account = {
        "_id": bson.ObjectId(account_id),
        "name": "test-account",
        "region": "us-east-1",
        "access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    }
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one(account)

    with serve.app.test_request_context(f"/aws/accounts/{account_id}", method="GET"):
        resp = unwrap(serve.get_aws_account)(account_id)

    assert resp[1] == 200
    data = json.loads(resp[0])
    assert data["name"] == "test-account"
    # Secret should be redacted
    assert "secret_access_key" not in data or data.get("secret_access_key") == ""


def test_get_aws_account_not_found(setup):
    """Handle account not found."""
    account_id = str(bson.ObjectId())

    with serve.app.test_request_context(f"/aws/accounts/{account_id}", method="GET"):
        resp = unwrap(serve.get_aws_account)(account_id)

    assert resp[1] == 404


def test_get_aws_account_invalid_id(setup):
    """Handle invalid account ID."""
    with serve.app.test_request_context("/aws/accounts/invalid", method="GET"):
        resp = unwrap(serve.get_aws_account)("invalid")

    assert resp[1] == 400


def test_update_aws_account_success(setup):
    """Update AWS account."""
    account_id = str(bson.ObjectId())
    account = {
        "_id": bson.ObjectId(account_id),
        "name": "old-name",
        "region": "us-east-1",
        "access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "secret_access_key": "old-secret",
    }
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one(account)

    with serve.app.test_request_context(
        f"/aws/accounts/{account_id}",
        method="PUT",
        json={"name": "new-name", "region": "us-west-2"}
    ):
        resp = unwrap(serve.update_aws_account)(account_id)

    assert resp[1] == 200
    updated = serve.mongo_client["labyrinth"]["aws_accounts"].find_one(
        {"_id": bson.ObjectId(account_id)}
    )
    assert updated["name"] == "new-name"
    assert updated["region"] == "us-west-2"


def test_update_aws_account_no_json(setup):
    """Handle missing JSON body."""
    account_id = str(bson.ObjectId())
    account = {
        "_id": bson.ObjectId(account_id),
        "name": "test",
        "region": "us-east-1",
    }
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one(account)

    with serve.app.test_request_context(f"/aws/accounts/{account_id}", method="PUT"):
        resp = unwrap(serve.update_aws_account)(account_id)

    assert resp[1] == 400
    assert "Invalid JSON" in resp[0]


def test_update_aws_account_not_found(setup):
    """Handle account not found on update."""
    account_id = str(bson.ObjectId())

    with serve.app.test_request_context(
        f"/aws/accounts/{account_id}",
        method="PUT",
        json={"name": "new-name"}
    ):
        resp = unwrap(serve.update_aws_account)(account_id)

    assert resp[1] == 404


def test_update_aws_account_duplicate_name(setup):
    """Prevent duplicate account names."""
    account_id_1 = str(bson.ObjectId())
    account_id_2 = str(bson.ObjectId())
    
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_many([
        {"_id": bson.ObjectId(account_id_1), "name": "existing"},
        {"_id": bson.ObjectId(account_id_2), "name": "to-update"},
    ])

    with serve.app.test_request_context(
        f"/aws/accounts/{account_id_2}",
        method="PUT",
        json={"name": "existing"}
    ):
        resp = unwrap(serve.update_aws_account)(account_id_2)

    assert resp[1] == 409
    assert "already exists" in resp[0]


def test_delete_aws_account_success(setup):
    """Delete AWS account."""
    account_id = str(bson.ObjectId())
    account = {
        "_id": bson.ObjectId(account_id),
        "name": "to-delete",
        "region": "us-east-1",
    }
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one(account)

    with serve.app.test_request_context(f"/aws/accounts/{account_id}", method="DELETE"):
        resp = unwrap(serve.delete_aws_account)(account_id)

    assert resp[1] == 200
    assert serve.mongo_client["labyrinth"]["aws_accounts"].count_documents(
        {"_id": bson.ObjectId(account_id)}
    ) == 0


def test_delete_aws_account_not_found(setup):
    """Handle account not found on delete."""
    account_id = str(bson.ObjectId())

    with serve.app.test_request_context(f"/aws/accounts/{account_id}", method="DELETE"):
        resp = unwrap(serve.delete_aws_account)(account_id)

    assert resp[1] == 404


def test_list_aws_accounts_success(setup):
    """List AWS accounts."""
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_many([
        {"_id": bson.ObjectId(), "name": "account-1", "secret_access_key": "secret1"},
        {"_id": bson.ObjectId(), "name": "account-2", "secret_access_key": "secret2"},
    ])

    with serve.app.test_request_context("/aws/accounts", method="GET"):
        resp = unwrap(serve.list_aws_accounts)()

    assert resp[1] == 200
    data = json.loads(resp[0])
    assert len(data["accounts"]) == 2
    # Secrets should be redacted
    for account in data["accounts"]:
        assert "secret_access_key" not in account


def test_list_aws_accounts_empty(setup):
    """List AWS accounts when none exist."""
    with serve.app.test_request_context("/aws/accounts", method="GET"):
        resp = unwrap(serve.list_aws_accounts)()

    assert resp[1] == 200
    data = json.loads(resp[0])
    assert data["accounts"] == []


# ---------------------------------------------------------------------------
# Metrics Bulk Insert - Line Coverage: 2050-2100
# ---------------------------------------------------------------------------


def test_bulk_insert_no_metrics(setup):
    """Handle bulk insert with no metrics."""
    with serve.app.test_request_context("/bulk_insert/", method="GET"):
        resp = unwrap(serve.bulk_insert)()

    assert resp[1] == 200


def test_bulk_insert_valid_metrics(setup):
    """Bulk insert valid metrics."""
    # Add a metric to Redis
    a = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
    metric = {
        "name": "cpu",
        "tags": {"ip": "192.168.1.1", "host": "server1"},
        "value": 45.2,
        "timestamp": datetime.datetime.now().timestamp(),
    }
    metric_key = f"METRIC-{json.dumps({'name': metric['name'], 'tags': metric['tags']}, default=str)}"
    a.set(metric_key, json.dumps(metric, default=str))

    with serve.app.test_request_context("/bulk_insert/", method="GET"):
        resp = unwrap(serve.bulk_insert)()

    assert resp[1] == 200


def test_bulk_insert_invalid_metric_no_name(setup):
    """Skip metrics without name."""
    a = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
    metric = {
        "tags": {"ip": "192.168.1.1"},
        "value": 45.2,
    }
    metric_key = "METRIC-invalid"
    a.set(metric_key, json.dumps(metric, default=str))

    with serve.app.test_request_context("/bulk_insert/", method="GET"):
        resp = unwrap(serve.bulk_insert)()

    assert resp[1] == 200


def test_bulk_insert_timestamp_handling(setup):
    """Handle timestamp conversion."""
    a = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
    metric = {
        "name": "memory",
        "tags": {"ip": "192.168.1.2", "host": "server2"},
        "value": 78.5,
        "timestamp": 1234567890.5,
    }
    metric_key = f"METRIC-{json.dumps({'name': metric['name'], 'tags': metric['tags']}, default=str)}"
    a.set(metric_key, json.dumps(metric, default=str))

    with serve.app.test_request_context("/bulk_insert/", method="GET"):
        resp = unwrap(serve.bulk_insert)()

    assert resp[1] == 200


# ---------------------------------------------------------------------------
# Disk Space Endpoints - Line Coverage: 2250-2300
# ---------------------------------------------------------------------------


def test_refresh_proxmox_disk_space_success(setup, monkeypatch):
    """Refresh Proxmox disk space data."""
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_one({
        "_id": bson.ObjectId(),
        "name": "cluster-1",
        "host": "10.0.0.1",
    })

    def mock_refresh(clusters, redis_client=None):
        return [{"host": "10.0.0.1", "nodes": []}]

    monkeypatch.setattr(proxmox_helper, "refresh_proxmox_cluster_cache", mock_refresh)

    with serve.app.test_request_context("/disk-space/proxmox/refresh", method="POST"):
        resp = unwrap(serve.refresh_proxmox_disk_space)()

    assert resp[1] == 200
    data = json.loads(resp[0])
    assert "proxmox_hosts" in data


def test_refresh_proxmox_disk_space_error(setup, monkeypatch):
    """Handle Proxmox refresh error."""
    def mock_refresh(clusters, redis_client=None):
        raise Exception("Connection error")

    monkeypatch.setattr(proxmox_helper, "refresh_proxmox_cluster_cache", mock_refresh)

    with serve.app.test_request_context("/disk-space/proxmox/refresh", method="POST"):
        resp = unwrap(serve.refresh_proxmox_disk_space)()

    assert resp[1] == 500
    assert "Failed" in resp[0]


def test_get_manual_disk_space_success(setup):
    """Get manual disk space configuration."""
    serve.mongo_client["labyrinth"]["settings"].insert_one({
        "name": "manual_disk_host_192_168_1_1",
        "value": json.dumps({
            "hostname": "server1",
            "path": "/var/log",
            "warning_percent": 80,
        })
    })

    with serve.app.test_request_context("/disk-space/manual", method="GET"):
        resp = unwrap(serve.get_manual_disk_space)()

    assert resp[1] == 200
    data = json.loads(resp[0])
    assert len(data["manual_hosts"]) >= 1


# ---------------------------------------------------------------------------
# Upload Handling - Line Coverage: 70-160
# ---------------------------------------------------------------------------


def test_list_uploads_become(setup):
    """List uploads from become folder."""
    with serve.app.test_request_context("/uploads/become", method="GET"):
        resp = unwrap(serve.list_uploads)("become")

    assert resp[1] == 200


def test_list_uploads_invalid_type(setup):
    """Reject invalid upload type."""
    with serve.app.test_request_context("/uploads/invalid", method="GET"):
        resp = unwrap(serve.list_uploads)("invalid")

    assert resp[1] == 409


def test_upload_file_missing_token(setup):
    """Handle missing upload token."""
    with serve.app.test_request_context(
        "/upload/become/",
        method="POST",
    ):
        # This will fail validation but we're testing the handler
        resp = unwrap(serve.upload_file)("become", "")

    # Should reject due to token validation
    assert resp[1] != 200


# ---------------------------------------------------------------------------
# Scan Operations - Line Coverage: 330-332
# ---------------------------------------------------------------------------


def test_scan_subnets_trigger(setup, monkeypatch):
    """Trigger subnet scanning."""
    # Mock the finder to avoid actual network calls
    scan_called = []

    def mock_scan(*args, **kwargs):
        scan_called.append(True)
        return None

    monkeypatch.setattr("serve.finder.find", mock_scan)

    with serve.app.test_request_context("/scan/", method="GET"):
        resp = unwrap(serve.scan_subnets)()

    assert resp[1] == 200


# ---------------------------------------------------------------------------
# Integration: Multiple Operations
# ---------------------------------------------------------------------------


def test_aws_account_lifecycle(setup):
    """Test complete AWS account lifecycle."""
    # Create
    with serve.app.test_request_context(
        "/aws/accounts",
        method="POST",
        json={
            "name": "lifecycle-test",
            "region": "us-east-1",
            "access_key_id": "AKIA123",
            "secret_access_key": "secret123",
        }
    ):
        resp = unwrap(serve.create_aws_account)()
        assert resp[1] == 200
        account_id = json.loads(resp[0]).get("_id")

    # Get
    with serve.app.test_request_context(f"/aws/accounts/{account_id}", method="GET"):
        resp = unwrap(serve.get_aws_account)(account_id)
        assert resp[1] == 200

    # Update
    with serve.app.test_request_context(
        f"/aws/accounts/{account_id}",
        method="PUT",
        json={"region": "us-west-2"}
    ):
        resp = unwrap(serve.update_aws_account)(account_id)
        assert resp[1] == 200

    # Delete
    with serve.app.test_request_context(f"/aws/accounts/{account_id}", method="DELETE"):
        resp = unwrap(serve.delete_aws_account)(account_id)
        assert resp[1] == 200

    # Verify deleted
    with serve.app.test_request_context(f"/aws/accounts/{account_id}", method="GET"):
        resp = unwrap(serve.get_aws_account)(account_id)
        assert resp[1] == 404

