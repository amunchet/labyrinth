#!/usr/bin/env python3
"""
Tests for services and metrics
"""
import pytest
import time
from serve import mongo_client
import metrics


@pytest.fixture
def setup():
    """
    Sets up and tearsdown
    """

    yield "Setting up..."
    return "Finished"


def test_metric_judge(setup):
    """
    Tests Judging a metric against a service
    """
    port_service = {
        "name": "port_ssh",
        "type": "port",
        "port": 22,
        "state": "open"
    }
    check_service = {
        "name": "check_hd",
        "type": "check",
        "metric": "diskio",
        "field": "read_time",
        "comparison": "greater",
        "value": 1000
    }

    port_scan = {
        "fields": {
            "ports": [
                22,
                23
            ],
            "ip": "192.168.0.6"
        },
        "name": "open_ports",
        "tags": {
            "host": '02:42:C0:A8:00:02',
        },
        "timestamp": time.time()
    }
    telegraf = {
        "fields": {
            "boot_time": 1625587759,
            "context_switches": 4143261228,
            "entropy_avail": 3760,
            "interrupts": 1578002983,
            "processes_forked": 884284
        },
        "name": "check_hd",
        "tags": {
                "host": "aacd4239ee68"
        },
        "timestamp": 1625683390
    }

    # Check metrics against service definition

    # No metric found
    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output

    # Check if names don't match
    telegraf["name"] = "notright"
    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output
    
    telegraf["name"] = "check_hd"


    # Check simple metric
    telegraf["fields"] = {
        "diskio" : 5000
    }

    output = metrics.judge(metric=telegraf, service=check_service)
    assert output
    
    # Check changing comparison
    check_service["comparison"] = "less"
    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output

    telegraf["fields"] = {
        "diskio" : 5
    }

    output = metrics.judge(metric=telegraf, service=check_service)
    assert output

    check_service["comparison"] = "equals"
    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output

    telegraf["fields"] = {
        "diskio" : 1000
    }

    output = metrics.judge(metric=telegraf, service=check_service)
    assert output

    # Check mismatched types - port and check

    output = metrics.judge(metric=telegraf, service=port_service)
    assert not output


    # Compound metrics (deep meterics)
    telegraf["fields"] = {
        "diskio" : {
            "second": 1000
        }
    }
    check_service["metric"] = "diskio.second"
    output = metrics.judge(metric=telegraf, service=check_service)
    assert output

    telegraf["fields"] = {
        "diskio" : {
            "second": 5000
        }
    }

    output = metrics.judge(metric=telegraf, service=check_service)
    assert not output


    ## Port scan checks

    output = metrics.judge(metric=port_scan, service=port_service)
    assert output

    port_service["port"] = 25

    output = metrics.judge(metric=port_scan, service=port_service)
    assert not output
    
    port_service["port"] = 22
    port_service["state"] = "closed"
    output = metrics.judge(metric=port_scan, service=port_service)
    assert not output

