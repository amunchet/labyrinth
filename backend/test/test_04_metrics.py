#!/usr/bin/env python3
"""
Tests for services and metrics
"""
import time
import json

import pytest

import metrics
import serve
from common.test import unwrap


@pytest.fixture
def setup():
    """
    Sets up the Watcher
    """
    serve.mongo_client["labyrinth"]["metrics"].delete_many({})
    serve.mongo_client["labyrinth"]["metrics-latest"].delete_many({})
    serve.mongo_client["labyrinth"]["services"].delete_many({"display_name": "test"})

    serve.mongo_client["labyrinth"]["metrics"].insert_one({"timestamp": 1})
    serve.mongo_client["labyrinth"]["metrics"].insert_one(
        {
            "timestamp": 2,
            "name": "test",
            "tags": {
                "host": 1234,
                "ip": 1234,
                "mac": "test",
            },
        }
    )
    serve.mongo_client["labyrinth"]["metrics-latest"].insert_one({"timestamp": 1})
    serve.mongo_client["labyrinth"]["metrics-latest"].insert_one(
        {
            "timestamp": 2,
            "name": "test",
            "tags": {
                "host": 1234,
                "ip": 1234,
                "mac": "test",
            },
        }
    )

    serve.mongo_client["labyrinth"]["services"].insert_one(
        {"display_name": "test", "name": "test"}
    )

    yield "Setting up..."
    return "Finished"


def test_get_latest_metrics(setup):
    """
    Pull latest metrics from REDIS?

    May just do Mongo for the time being
    """
    a = unwrap(serve.last_metrics)(1)
    assert a[1] == 200
    b = json.loads(a[0])
    print(b)
    assert b[0]["timestamp"] == 1  # Only once, since using latest metrics


def test_read_metrics(setup):
    """
    Tests reading in the metrics
    """
    a = unwrap(serve.read_metrics)("test")
    assert a[1] == 200
    b = json.loads(a[0])
    print(b)
    assert b[0]["timestamp"] == 2

    a = unwrap(serve.read_metrics)("test", "test")
    assert a[1] == 200
    b = json.loads(a[0])
    print(b)
    if b:  # There's an empty metric
        assert b[0]["timestamp"] == 2


def test_time_judge(setup):
    """
    Tests time judgement
    """

    metric = {
        "fields": {"old": time.time_ns() - (1e9 * 100)},
        "name": "check_hd",
        "tags": {"host": "aacd4239ee68"},
        "timestamp": time.time(),
    }
    check_service = {
        "display_name": "test-1",
        "name": "check_hd",
        "metric": "old",
        "field": "old",
        "comparison": "time",
        "value": 200,
    }

    assert metrics.judge_check(metric, check_service)

    check_service["value"] = 1

    assert not metrics.judge_check(metric, check_service)


def test_metric_judge(setup):
    """
    Tests Judging a metric against a service
    """
    check_service = {
        "name": "check_hd",
        "type": "check",
        "metric": "diskio",
        "field": "read_time",
        "comparison": "greater",
        "value": 1000,
    }
    odd_service = {
        "name": "check_hd",
        "type": "check",
        "metric": "diskio",
        "field": "random_field",
        "comparison": "greater",
        "value": 5,
    }

    host = {"open_ports": [22, 23]}

    port_scan = {
        "fields": {"ports": [22, 23], "ip": "192.168.0.6"},
        "name": "open_ports",
        "tags": {
            "host": "02:42:C0:A8:00:02",
        },
        "timestamp": time.time(),
    }
    telegraf = {
        "fields": {
            "boot_time": 1625587759,
            "context_switches": 4143261228,
            "entropy_avail": 3760,
            "interrupts": 1578002983,
            "processes_forked": 884284,
            "random_field": "AAAA",
        },
        "name": "check_hd",
        "tags": {"host": "aacd4239ee68"},
        "timestamp": time.time(),
    }

    # Check metrics against service definition

    # No metric found
    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output

    # Check if names don't match
    telegraf["name"] = "notright"
    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output

    del telegraf["name"]
    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output

    telegraf["name"] = "check_hd"
    temp = telegraf["fields"]
    del telegraf["fields"]

    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output
    telegraf["fields"] = temp

    telegraf["name"] = "check_hd"

    # Check Odd Service
    telegraf["fields"] = {"diskio": "AAAAAA"}
    output = metrics.judge(metric=telegraf, service=odd_service)
    assert output

    odd_service["comparison"] = "equals"
    output = metrics.judge(metric=telegraf, service=odd_service)
    assert not output

    odd_service["comparison"] = "less"
    output = metrics.judge(metric=telegraf, service=odd_service)
    assert not output

    telegraf["fields"] = {"diskio": "5.32"}
    odd_service["comparison"] = "greater"
    output = metrics.judge(metric=telegraf, service=odd_service)
    assert output

    odd_service["comparison"] = "equals"
    output = metrics.judge(metric=telegraf, service=odd_service)
    assert not output

    odd_service["comparison"] = "less"
    output = metrics.judge(metric=telegraf, service=odd_service)
    assert not output

    # Check simple metric
    telegraf["fields"] = {"diskio": 5000}

    output = metrics.judge(metric=telegraf, service=check_service)
    assert output

    # Check changing comparison
    check_service["comparison"] = "INVALID"
    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output

    check_service["comparison"] = "less"
    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output

    telegraf["fields"] = {"diskio": 5}

    output = metrics.judge(metric=telegraf, service=check_service)
    assert output

    check_service["comparison"] = "equals"
    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output

    telegraf["fields"] = {"diskio": 1000}

    output = metrics.judge(metric=telegraf, service=check_service)
    assert output

    # Compound metrics (deep meterics)
    telegraf["fields"] = {"diskio": {"second": 1000}}
    check_service["metric"] = "diskio.second"
    output = metrics.judge(metric=telegraf, service=check_service)
    assert output

    telegraf["fields"] = {"diskio": {"second": 5000}}

    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output

    ## Port scan checks

    # Open Ports - Passing
    output = metrics.judge_port(metric=port_scan, service="open_ports", host=host)
    assert output

    # Closed Ports - Passing

    output = metrics.judge_port(metric=port_scan, service="closed_ports", host=host)
    assert output

    # Open Ports - Failing
    port_scan["fields"]["ports"] = []

    output = metrics.judge_port(metric=port_scan, service="open_ports", host=host)
    assert not output

    # Closed Ports - Failing
    host["open_ports"] = [22, 23, 27, 28]
    output = metrics.judge_port(metric=port_scan, service="open_ports", host=host)
    assert not output


def test_read_metrics_history_not_judged_stale(setup):
    """
    History rows are always older than any sane stale_time relative to "now",
    so read_metrics must not let the default staleness check blank out their
    real pass/fail judgement (regression test for the always -1 bug).
    """
    serve.mongo_client["labyrinth"]["services"].delete_many(
        {"display_name": "history-test"}
    )
    serve.mongo_client["labyrinth"]["services"].insert_one(
        {
            "display_name": "history-test",
            "name": "history_check",
            "type": "check",
            "metric": "value",
            "comparison": "equals",
            "value": "ok",
        }
    )

    old_timestamp = time.time() - 100000  # far past any stale_time default

    serve.mongo_client["labyrinth"]["metrics"].insert_one(
        {
            "timestamp": old_timestamp,
            "name": "history_check",
            "fields": {"value": "ok"},
            "tags": {
                "host": "history-host",
                "ip": "10.0.0.55",
                "mac": "aa:bb:cc",
                "labyrinth_name": "history_check",
            },
        }
    )

    a = unwrap(serve.read_metrics)("history-host", "history-test", 10)
    assert a[1] == 200
    b = json.loads(a[0])
    matches = [x for x in b if x["timestamp"] == old_timestamp]
    assert matches
    assert matches[0]["judgement"] is True


def test_read_metrics_latest_still_goes_stale(setup):
    """
    The "latest" option is meant to reflect current freshness, so an old
    metrics-latest row must still judge as -1 (unlike history rows above).
    """
    serve.mongo_client["labyrinth"]["services"].delete_many(
        {"display_name": "latest-stale-test"}
    )
    serve.mongo_client["labyrinth"]["services"].insert_one(
        {
            "display_name": "latest-stale-test",
            "name": "latest_stale_check",
            "type": "check",
            "metric": "value",
            "comparison": "equals",
            "value": "ok",
        }
    )

    old_timestamp = time.time() - 100000

    serve.mongo_client["labyrinth"]["metrics-latest"].insert_one(
        {
            "timestamp": old_timestamp,
            "name": "latest_stale_check",
            "fields": {"value": "ok"},
            "tags": {
                "host": "latest-stale-host",
                "ip": "10.0.0.56",
                "mac": "aa:bb:cd",
                "labyrinth_name": "latest_stale_check",
            },
        }
    )

    a = unwrap(serve.read_metrics)(
        "latest-stale-host", "latest-stale-test", 10, "latest"
    )
    assert a[1] == 200
    b = json.loads(a[0])
    matches = [x for x in b if x["timestamp"] == old_timestamp]
    assert matches
    assert matches[0]["judgement"] == -1
