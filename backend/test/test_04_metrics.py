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
    assert b[0]["timestamp"] == 2


def test_time_judge(setup):
    """
    Tests time judgement
    """
    

    metric = {
        "fields": {
            "old" : time.time_ns() - (1e9 * 100)
        },
        "name": "check_hd",
        "tags": {"host": "aacd4239ee68"},
        "timestamp": time.time(),
    }
    check_service = {
        "display_name" : "test-1",
        "name" : "check_hd",
        "metric" : "old",
        "field" : "old",
        "comparison" : "time",
        "value" : 200
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
