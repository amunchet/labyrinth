#!/usr/bin/env python3

import datetime
import json

import pytest
import serve

from common.test import unwrap


def cleanup_test_data():
    """Clean up Telegraf check test data."""
    serve.db["labyrinth"]["hosts"].delete_many({})
    serve.db["labyrinth"]["proxmox_clusters"].delete_many({})
    serve.db["labyrinth"]["metrics-latest"].delete_many({})


@pytest.fixture
def setup():
    """Sets up tests."""
    cleanup_test_data()
    yield "Setting up..."
    cleanup_test_data()


def _host(ip, host, monitor="true", services=None):
    return {
        "ip": ip,
        "subnet": ip.rsplit(".", 1)[0],
        "mac": f"mac-{ip}",
        "host": host,
        "group": "Proxmox",
        "icon": "linux",
        "services": services or [],
        "class": "health",
        "monitor": monitor,
        "tags": "",
    }


def _guest(vmid, name, status="running"):
    return {"id": vmid, "name": name, "status": status}


def _run(monkeypatch, payload, query=""):
    monkeypatch.setattr(
        serve.proxmox_helper,
        "get_proxmox_disk_data_cached",
        lambda cluster, redis_client=None: payload,
    )
    monkeypatch.setattr(serve.proxmox_helper, "get_redis_client", lambda: None)
    with serve.app.test_request_context(
        f"/disk-space/proxmox/telegraf-check{query}", method="GET"
    ):
        response = unwrap(serve.get_proxmox_telegraf_check)()
    assert response[1] == 200
    payload = json.loads(response[0])
    return payload, {g["name"]: g for g in payload["guests"]}


def test_telegraf_check_classifies_every_guest(setup, monkeypatch):
    """Each VM/LXC is classified by Labyrinth host match, monitoring, and Telegraf freshness."""
    now = datetime.datetime.now()
    serve.db["labyrinth"]["proxmox_clusters"].insert_one(
        {"name": "home", "host": "10.0.0.1"}
    )
    serve.db["labyrinth"]["hosts"].insert_many(
        [
            _host("10.0.0.10", "web01"),
            _host("10.0.0.11", "db01.lan"),
            _host("10.0.0.12", "cache01", monitor="false"),
        ]
    )
    serve.db["labyrinth"]["metrics-latest"].insert_many(
        [
            {"name": "cpu", "tags": {"ip": "10.0.0.10"}, "timestamp": now},
            # Reporting, but long stale
            {
                "name": "cpu",
                "tags": {"ip": "10.0.0.11"},
                "timestamp": now - datetime.timedelta(hours=3),
            },
        ]
    )

    payload, guests = _run(
        monkeypatch,
        {
            "nodes": [
                {
                    "name": "pv3",
                    "vms": [_guest(100, "WEB01"), _guest(101, "db01")],
                    "containers": [_guest(200, "cache01"), _guest(201, "orphan")],
                },
                {
                    "name": "pv4",
                    "vms": [_guest(102, "template", status="stopped")],
                    "containers": [],
                },
            ]
        },
    )

    assert guests["WEB01"]["check_status"] == "ok"
    assert guests["WEB01"]["node"] == "pv3"
    assert guests["WEB01"]["type"] == "vm"
    assert guests["WEB01"]["labyrinth_matches"][0]["ip"] == "10.0.0.10"
    assert guests["db01"]["check_status"] == "no_telegraf"
    assert guests["db01"]["telegraf_last_seen"] is not None
    assert guests["cache01"]["check_status"] == "not_monitored"
    assert guests["cache01"]["type"] == "lxc"
    assert guests["orphan"]["check_status"] == "unmatched"
    assert guests["template"]["check_status"] == "stopped"

    summary = payload["summary"]
    assert summary["guest_count"] == 5
    assert summary["ok_count"] == 1
    assert summary["no_telegraf_count"] == 1
    assert summary["not_monitored_count"] == 1
    assert summary["unmatched_count"] == 1
    assert summary["stopped_count"] == 1


def test_telegraf_check_matches_metrics_by_hostname_and_honors_stale_window(
    setup, monkeypatch
):
    """Metrics tagged only by hostname still count, and stale_minutes widens the window."""
    serve.db["labyrinth"]["proxmox_clusters"].insert_one(
        {"name": "home", "host": "10.0.0.1"}
    )
    serve.db["labyrinth"]["hosts"].insert_one(_host("10.0.0.20", "app01"))
    serve.db["labyrinth"]["metrics-latest"].insert_one(
        {
            "name": "mem",
            "tags": {"host": "app01"},
            "timestamp": datetime.datetime.now() - datetime.timedelta(minutes=30),
        }
    )
    payload = {"nodes": [{"name": "pv5", "vms": [_guest(300, "app01")]}]}

    _, guests = _run(monkeypatch, payload)
    assert guests["app01"]["check_status"] == "no_telegraf"

    _, guests = _run(monkeypatch, payload, "?stale_minutes=60")
    assert guests["app01"]["check_status"] == "ok"


def test_telegraf_check_reports_cluster_errors(setup, monkeypatch):
    """A cluster that can't be queried is surfaced as an error, not silently empty."""
    serve.db["labyrinth"]["proxmox_clusters"].insert_one(
        {"name": "broken", "host": "10.0.0.2"}
    )

    payload, guests = _run(
        monkeypatch, {"error": "Failed to get Proxmox data", "host": "10.0.0.2"}
    )

    assert guests == {}
    assert payload["errors"] == [
        {"cluster_name": "broken", "error": "Failed to get Proxmox data"}
    ]
