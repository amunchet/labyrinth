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
    serve.db["labyrinth"]["settings"].delete_many({})


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


def _run(monkeypatch, payload, query="", route="telegraf-check"):
    monkeypatch.setattr(
        serve.proxmox_helper,
        "get_proxmox_disk_data_cached",
        lambda cluster, redis_client=None: payload,
    )
    monkeypatch.setattr(serve.proxmox_helper, "get_redis_client", lambda: None)
    with serve.app.test_request_context(
        f"/disk-space/proxmox/{route}{query}", method="GET"
    ):
        handler = {
            "telegraf-check": serve.get_proxmox_telegraf_check,
            "graylog-check": serve.get_proxmox_graylog_check,
        }[route]
        response = unwrap(handler)()
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


def _graylog_metric(ip, ok, age=datetime.timedelta(0), name="check_graylog"):
    return {
        "name": name,
        "tags": {"ip": ip, "target": "graylog.lan:1514"},
        "fields": {
            "ok": 1 if ok else 0,
            "status": "ok" if ok else "rsyslog not running",
        },
        "timestamp": datetime.datetime.now() - age,
    }


def test_graylog_check_classifies_and_honors_deferrals(setup, monkeypatch):
    """check_graylog results drive status; only failures are hard, deferrals hide issues until they expire."""
    serve.db["labyrinth"]["proxmox_clusters"].insert_one(
        {"name": "home", "host": "10.0.0.1"}
    )
    serve.db["labyrinth"]["hosts"].insert_many(
        [
            _host("10.0.0.10", "web01"),
            _host("10.0.0.11", "db01"),
            _host("10.0.0.12", "cache01"),
            _host("10.0.0.13", "old01"),
            _host("10.0.0.14", "app01"),
            _host("10.0.0.15", "lapsed01"),
        ]
    )
    serve.db["labyrinth"]["metrics-latest"].insert_many(
        [
            _graylog_metric("10.0.0.10", True),
            _graylog_metric("10.0.0.11", False),
            _graylog_metric("10.0.0.13", True, age=datetime.timedelta(days=3)),
            _graylog_metric("10.0.0.14", False),
            _graylog_metric("10.0.0.15", False),
            # Other metrics never count as a Graylog result
            {
                "name": "cpu",
                "tags": {"ip": "10.0.0.12"},
                "fields": {"ok": 1},
                "timestamp": datetime.datetime.now(),
            },
        ]
    )
    unwrap(serve.save_setting)(
        "proxmox_graylog_deferrals",
        json.dumps(
            [
                {
                    "cluster_name": "home",
                    "id": 104,
                    "until": None,
                    "reason": "appliance",
                },
                {"cluster_name": "home", "id": 105, "until": "2000-01-01"},
            ]
        ),
    )

    payload, guests = _run(
        monkeypatch,
        {
            "nodes": [
                {
                    "name": "pv3",
                    "vms": [
                        _guest(100, "web01"),
                        _guest(101, "db01"),
                        _guest(102, "cache01"),
                        _guest(103, "old01"),
                        _guest(104, "app01"),
                        _guest(105, "lapsed01"),
                    ],
                    "containers": [_guest(200, "orphan")],
                }
            ]
        },
        route="graylog-check",
    )

    assert guests["web01"]["check_status"] == "ok"
    assert guests["web01"]["graylog_target"] == "graylog.lan:1514"
    assert guests["db01"]["check_status"] == "failing"
    assert guests["db01"]["graylog_fields"]["status"] == "rsyslog not running"
    assert guests["cache01"]["check_status"] == "not_deployed"
    assert guests["old01"]["check_status"] == "stale"
    assert guests["app01"]["check_status"] == "deferred"
    assert guests["app01"]["result_status"] == "failing"
    assert guests["app01"]["deferral"]["reason"] == "appliance"
    assert guests["lapsed01"]["check_status"] == "failing"
    assert guests["orphan"]["check_status"] == "unmatched"

    summary = payload["summary"]
    assert summary["metric_name"] == "check_graylog"
    assert summary["stale_hours"] == 24
    assert summary["failing_count"] == 2
    assert summary["deferred_count"] == 1


def test_graylog_check_uses_configured_metric_name_and_window(setup, monkeypatch):
    """The check metric name and freshness window come from the settings."""
    serve.db["labyrinth"]["proxmox_clusters"].insert_one(
        {"name": "home", "host": "10.0.0.1"}
    )
    serve.db["labyrinth"]["hosts"].insert_one(_host("10.0.0.10", "web01"))
    serve.db["labyrinth"]["metrics-latest"].insert_one(
        _graylog_metric(
            "10.0.0.10", True, age=datetime.timedelta(hours=60), name="rsyslog_graylog"
        )
    )
    unwrap(serve.save_setting)(
        "proxmox_graylog_check",
        json.dumps({"metric_name": "rsyslog_graylog", "stale_hours": 72}),
    )

    payload, guests = _run(
        monkeypatch,
        {"nodes": [{"name": "pv3", "vms": [_guest(100, "web01")]}]},
        route="graylog-check",
    )

    assert payload["settings"] == {"metric_name": "rsyslog_graylog", "stale_hours": 72}
    assert guests["web01"]["check_status"] == "ok"
