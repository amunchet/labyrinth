#!/usr/bin/env python3

import json
import bson

import pytest
import serve

from common.test import unwrap


def tearDown():
    """Tears down AWS test data."""
    serve.mongo_client["labyrinth"]["hosts"].delete_many({})
    serve.mongo_client["labyrinth"]["aws_accounts"].delete_many({})


@pytest.fixture
def setup():
    """Sets up tests."""
    tearDown()
    yield "Setting up..."
    tearDown()
    return "Done"


def test_aws_account_crud(setup):
    """Creates, lists, updates, and deletes AWS account configurations."""
    with serve.app.test_request_context(
        "/aws/accounts",
        method="POST",
        json={
            "name": "prod-account",
            "region": "us-east-1",
            "access_key_id": "AKIAXXXXX",
            "secret_access_key": "secret-value",
            "session_token": "session-token",
        },
    ):
        create_resp = unwrap(serve.create_aws_account)()

    assert create_resp[1] == 201
    created = json.loads(create_resp[0])
    account_id = created["id"]
    assert created["status"] == "created"

    list_resp = unwrap(serve.list_aws_accounts)()
    assert list_resp[1] == 200
    listed = json.loads(list_resp[0])
    assert len(listed) == 1
    assert listed[0]["name"] == "prod-account"
    assert listed[0]["access_key_id"] == "AKIAXXXXX"
    assert "secret_access_key" not in listed[0]
    assert "session_token" not in listed[0]

    get_resp = unwrap(serve.get_aws_account)(account_id)
    assert get_resp[1] == 200
    fetched = json.loads(get_resp[0])
    assert fetched["region"] == "us-east-1"
    assert "secret_access_key" not in fetched

    with serve.app.test_request_context(
        f"/aws/accounts/{account_id}",
        method="PUT",
        json={
            "region": "us-west-2",
            "secret_access_key": "updated-secret",
        },
    ):
        update_resp = unwrap(serve.update_aws_account)(account_id)

    assert update_resp[1] == 200
    updated = json.loads(update_resp[0])
    assert updated["region"] == "us-west-2"
    assert "secret_access_key" not in updated

    db_account = serve.mongo_client["labyrinth"]["aws_accounts"].find_one(
        {"_id": bson.ObjectId(account_id)}
    )
    assert db_account["secret_access_key"] == "updated-secret"

    delete_resp = unwrap(serve.delete_aws_account)(account_id)
    assert delete_resp[1] == 200

    list_resp = unwrap(serve.list_aws_accounts)()
    assert list_resp[1] == 200
    assert json.loads(list_resp[0]) == []


def test_aws_account_create_requires_fields(setup):
    """Validates required fields for AWS account creation."""
    with serve.app.test_request_context(
        "/aws/accounts",
        method="POST",
        json={"name": "missing-fields"},
    ):
        resp = unwrap(serve.create_aws_account)()

    assert resp[1] == 400
    assert "Missing required fields" in json.loads(resp[0])["error"]


def test_aws_account_duplicate_name_rejected(setup):
    """Rejects duplicate AWS account names."""
    account_data = {
        "name": "duplicate-account",
        "region": "us-east-1",
        "access_key_id": "AKIA123",
        "secret_access_key": "secret-123",
    }

    with serve.app.test_request_context("/aws/accounts", method="POST", json=account_data):
        resp1 = unwrap(serve.create_aws_account)()
    assert resp1[1] == 201

    with serve.app.test_request_context("/aws/accounts", method="POST", json=account_data):
        resp2 = unwrap(serve.create_aws_account)()
    assert resp2[1] == 409
    assert "already exists" in json.loads(resp2[0])["error"]


def test_get_aws_ec2_instances_enriches_labyrinth_matches(setup, monkeypatch):
    """Returns EC2 inventory plus match status against Labyrinth hosts."""
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one({
        "name": "prod-account",
        "region": "us-east-1",
        "access_key_id": "AKIAXXXXX",
        "secret_access_key": "secret-value",
    })

    serve.mongo_client["labyrinth"]["hosts"].insert_many([
        {
            "ip": "10.0.0.10",
            "subnet": "10.0.0",
            "mac": "00-11-22-33-44-55",
            "host": "ip-10-0-0-10",
            "group": "AWS",
            "icon": "linux",
            "services": ["check_hd-1"],
            "class": "health",
            "monitor": "true",
            "tags": "aws,prod",
        },
        {
            "ip": "192.168.0.20",
            "subnet": "192.168.0",
            "mac": "AA-BB-CC-DD-EE-FF",
            "host": "other-host",
            "group": "Linux",
            "icon": "linux",
            "services": [],
            "class": "health",
            "monitor": "false",
            "tags": "linux",
        },
    ])

    def fake_list_ec2_instances(account_config):
        return {
            "account_name": account_config["name"],
            "region": account_config["region"],
            "instances": [
                {
                    "instance_id": "i-1234567890",
                    "name": "app-server-1",
                    "state": "running",
                    "instance_type": "t3.medium",
                    "private_ip": "10.0.0.10",
                    "public_ip": "54.1.2.3",
                    "private_dns_name": "ip-10-0-0-10.ec2.internal",
                    "public_dns_name": "ec2-54-1-2-3.compute.amazonaws.com",
                    "availability_zone": "us-east-1a",
                    "subnet_id": "subnet-123",
                    "vpc_id": "vpc-123",
                    "platform": "linux",
                    "architecture": "x86_64",
                    "monitoring_state": "enabled",
                    "launch_time": "2026-07-08T00:00:00",
                    "tags": {"Name": "app-server-1", "Environment": "prod"},
                    "security_groups": ["web"],
                    "account_id": "123456789012",
                    "region": account_config["region"],
                    "account_name": account_config["name"],
                },
                {
                    "instance_id": "i-unmatched",
                    "name": "db-server-1",
                    "state": "stopped",
                    "instance_type": "t3.large",
                    "private_ip": "10.0.0.99",
                    "public_ip": None,
                    "private_dns_name": "ip-10-0-0-99.ec2.internal",
                    "public_dns_name": "",
                    "availability_zone": "us-east-1b",
                    "subnet_id": "subnet-999",
                    "vpc_id": "vpc-123",
                    "platform": "linux",
                    "architecture": "x86_64",
                    "monitoring_state": "disabled",
                    "launch_time": "2026-07-08T00:00:00",
                    "tags": {"Name": "db-server-1"},
                    "security_groups": ["db"],
                    "account_id": "123456789012",
                    "region": account_config["region"],
                    "account_name": account_config["name"],
                },
            ],
        }

    monkeypatch.setattr(serve.aws_helper, "list_ec2_instances", fake_list_ec2_instances)

    response = unwrap(serve.get_aws_ec2_instances)()
    assert response[1] == 200

    payload = json.loads(response[0])
    assert payload["summary"]["account_count"] == 1
    assert payload["summary"]["instance_count"] == 2
    assert payload["summary"]["matched_instance_count"] == 1
    assert payload["summary"]["unmatched_instance_count"] == 1

    matched = [item for item in payload["instances"] if item["instance_id"] == "i-1234567890"][0]
    assert matched["matched"] is True
    assert matched["monitoring_enabled"] is True
    assert matched["labyrinth_matches"][0]["host"] == "ip-10-0-0-10"
    assert "ip" in matched["labyrinth_matches"][0]["match_reasons"]
    assert "hostname" in matched["labyrinth_matches"][0]["match_reasons"]

    unmatched = [item for item in payload["instances"] if item["instance_id"] == "i-unmatched"][0]
    assert unmatched["matched"] is False
    assert unmatched["labyrinth_matches"] == []


def test_get_aws_ec2_instances_collects_account_errors(setup, monkeypatch):
    """Surfaces per-account AWS inventory errors without failing the whole response."""
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one({
        "name": "broken-account",
        "region": "us-east-1",
        "access_key_id": "AKIAFAIL",
        "secret_access_key": "secret-value",
    })

    def fake_list_ec2_instances(account_config):
        return {
            "account_name": account_config["name"],
            "region": account_config["region"],
            "error": "AuthFailure",
            "instances": [],
        }

    monkeypatch.setattr(serve.aws_helper, "list_ec2_instances", fake_list_ec2_instances)

    response = unwrap(serve.get_aws_ec2_instances)()
    assert response[1] == 200

    payload = json.loads(response[0])
    assert payload["instances"] == []
    assert len(payload["errors"]) == 1
    assert payload["errors"][0]["account_name"] == "broken-account"
    assert payload["errors"][0]["error"] == "AuthFailure"
