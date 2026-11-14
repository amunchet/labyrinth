#!/usr/bin/env python3
"""
MCP tools covering the rest of the API: the judged dashboard, host
addresses/groups, generic settings, alert backoff, integrations (Proxmox,
AWS, UniFi) and test emails.
"""

import json
from unittest.mock import patch

import pytest

import serve
from ai.mcp.client import LabyrinthClient
from common.test import unwrap

COLLECTIONS = [
    "hosts",
    "subnets",
    "services",
    "settings",
    "proxmox_clusters",
    "aws_accounts",
    "unifi_controllers",
    "metrics-latest",
]


def tearDown():
    for collection in COLLECTIONS:
        serve.db["labyrinth"][collection].delete_many({})


@pytest.fixture
def client():
    tearDown()
    for host in [
        {"ip": "192.168.9.6", "mac": "aa:01", "host": "core", "group": "Net"},
        {"ip": "192.168.9.7", "mac": "aa:02", "host": "edge", "group": "Net"},
    ]:
        assert unwrap(serve.create_edit_host)({"services": [], **host})[1] == 200
    yield LabyrinthClient()
    tearDown()


def test_dashboard_states_and_problems_only(client):
    board = [
        {
            "subnet": "192.168.9",
            "groups": [
                {
                    "name": "Net",
                    "hosts": [
                        {
                            "mac": "aa:01",
                            "host": "core",
                            "ip": "192.168.9.6",
                            "services": [
                                {"name": "ping", "state": True},
                                {"name": "disk", "state": -1},
                            ],
                        },
                        {
                            "mac": "aa:02",
                            "services": [{"name": "ping", "state": True}],
                        },
                    ],
                }
            ],
        },
        {"subnet": "10.0.0", "groups": []},
    ]
    with patch("serve.dashboard") as handler:
        handler.__wrapped__ = lambda: (json.dumps(board), 200)
        full = client.get_dashboard()
        problems = client.get_dashboard(problems_only=True)
        one = client.get_dashboard("10.0.0")

    assert [x["subnet"] for x in full] == ["192.168.9", "10.0.0"]
    assert full[0]["groups"][0]["hosts"][0]["services"] == [
        {"name": "ping", "state": "ok"},
        {"name": "disk", "state": "stale"},
    ]
    # Only the stale service survives, and healthy hosts/subnets drop out
    assert problems == [
        {
            "subnet": "192.168.9",
            "groups": [
                {
                    "name": "Net",
                    "hosts": [
                        {
                            "key": "aa:01",
                            "name": "core",
                            "ip": "192.168.9.6",
                            "monitor": False,
                            "services": [{"name": "disk", "state": "stale"}],
                        }
                    ],
                }
            ],
        }
    ]
    assert one == [{"subnet": "10.0.0", "groups": []}]


def test_host_group_and_address(client):
    assert client.set_host_group("core", "Core")["group"] == "Core"

    moved = client.change_host_address("aa:02", new_ip="192.168.9.70")
    assert moved["ip"] == "192.168.9.70" and moved["mac"] == "aa:02"

    rekeyed = client.change_host_address(
        "aa:02", new_mac="bb:02", new_ip="192.168.9.71"
    )
    assert (rekeyed["mac"], rekeyed["ip"]) == ("bb:02", "192.168.9.71")
    assert client.get_host("aa:02") is None

    with pytest.raises(ValueError, match="already exists"):
        client.change_host_address("bb:02", new_mac="aa:01")
    with pytest.raises(ValueError, match="Host not found"):
        client.set_host_group("nope", "x")


def test_delete_service_removes_it_from_hosts(client):
    client.create_or_update_service({"name": "ping", "display_name": "ping"})
    client.add_service_to_host("aa:01", "ping")
    assert client.delete_service("ping") == "Success"
    assert client.get_host("aa:01")["services"] == []
    with pytest.raises(ValueError, match="No service"):
        client.delete_service("ping")


def test_latest_metrics_filter_and_delete(client):
    rows = serve.db["labyrinth"]["metrics-latest"]
    for name, ip in [
        ("cpu", "192.168.9.6"),
        ("mem", "192.168.9.6"),
        ("cpu", "192.168.9.7"),
    ]:
        rows.insert_one({"name": name, "tags": {"ip": ip}, "fields": {}})
    assert len(client.list_latest_metrics(2)) == 2
    cpu = client.list_latest_metrics(0, "cpu")
    assert len(cpu) == 2
    client.delete_metric(str(cpu[0]["_id"]))
    assert len(client.list_latest_metrics(0, "cpu")) == 1


def test_settings_and_reserved_names(client):
    client.save_setting("port_stale_hours", "4")
    assert client.get_settings("port_stale_hours") == {"port_stale_hours": "4"}
    assert client.get_settings()["port_stale_hours"] == "4"

    # Backoff and manual disk hosts go through their validated tools
    for name in ["alert_backoff", "manual_disk_host_x"]:
        with pytest.raises(ValueError, match="own tool"):
            client.save_setting(name, "1")
        with pytest.raises(ValueError, match="own tool"):
            client.delete_setting(name)

    client.delete_setting("port_stale_hours")
    with pytest.raises(ValueError, match="No setting"):
        client.get_settings("port_stale_hours")


def test_alert_backoff_is_validated(client):
    saved = client.save_alert_backoff({"first_minutes": 30, "multiplier": 3})
    assert (saved["first_minutes"], saved["multiplier"]) == (30, 3)
    assert client.get_alert_backoff()["multiplier"] == 3
    with pytest.raises(RuntimeError, match="multiplier"):
        client.save_alert_backoff({"multiplier": 1000})


def test_manual_disk_hosts(client):
    created = client.add_manual_disk_host(
        {"name": "vbox", "ip": "10.0.0.5", "type": "oraclevbox"}
    )
    with patch("serve.proxmox_helper.get_qemu_agent_ignore_list", return_value=[]):
        settings = client.get_disk_space_settings()
    assert [x["name"] for x in settings["manual_hosts"]] == ["vbox"]
    assert "disk_space_alert_threshold" in settings
    assert client.delete_manual_disk_host(created["id"]) == "Success"
    with pytest.raises(RuntimeError, match="404"):
        client.delete_manual_disk_host(created["id"])


def test_proxmox_cluster_secret_is_write_only(client):
    created = client.save_proxmox_cluster(
        {
            "name": "pve",
            "host": "10.0.0.2",
            "user": "root@pam",
            "token_id": "t",
            "token_secret": "s3cret",
        }
    )
    # A blank secret on update keeps the saved one rather than erasing it
    updated = client.save_proxmox_cluster(
        {"_id": created["id"], "host": "10.0.0.3", "token_secret": ""}
    )
    assert updated["host"] == "10.0.0.3" and "token_secret" not in updated
    stored = serve.db["labyrinth"]["proxmox_clusters"].find_one({"name": "pve"})
    assert stored["token_secret"] == "s3cret"
    assert client.delete_proxmox_cluster(created["id"]) == "Success"


def test_aws_accounts(client):
    created = client.save_aws_account(
        {
            "name": "prod",
            "region": "us-east-1",
            "access_key_id": "AKIA",
            "secret_access_key": "s3cret",
        }
    )
    client.save_aws_account({"_id": created["id"], "region": "us-west-2"})
    accounts = client.get_aws_settings()["accounts"]
    assert [(x["name"], x["region"]) for x in accounts] == [("prod", "us-west-2")]
    assert "secret_access_key" not in accounts[0]
    assert client.delete_aws_account(created["id"]) == "Success"
    assert client.get_aws_settings()["accounts"] == []


def test_unifi_controllers(client):
    saved = client.save_unifi_controller(
        {"name": "UDM", "url": "https://192.168.1.1", "auth": "api_key", "api_key": "k"}
    )
    client.save_unifi_controller({"_id": saved["_id"], "verify_ssl": True})
    [found] = client.list_unifi_controllers()
    assert found["has_api_key"] and "api_key" not in found and found["verify_ssl"]
    assert client.delete_unifi_controller(saved["_id"]) == "Success"
    assert client.list_unifi_controllers() == []
    with pytest.raises(RuntimeError, match="needs a name"):
        client.save_unifi_controller({"url": "https://192.168.1.1"})


def test_send_test_email_routes_by_kind(client):
    with patch("serve.send_ec2_unmatched_test_email") as handler:
        handler.__wrapped__ = lambda: (json.dumps(serve.request.get_json()), 200)
        assert client.send_test_email("ec2", "full", "a@b.c") == {
            "mode": "full",
            "recipients": "a@b.c",
        }
    with pytest.raises(ValueError, match="kind must be"):
        client.send_test_email("sms", "simple", "")


def test_list_uploads_refuses_unknown_types(client):
    with pytest.raises(ValueError, match="file_type must be"):
        client.list_uploads("../etc")
