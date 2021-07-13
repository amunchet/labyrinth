#!/usr/bin/env python3
"""
Tests for services and metrics
"""
import pytest
import time
from serve import mongo_client


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
        "name": "kernel",
        "tags": {
                "host": "aacd4239ee68"
        },
        "timestamp": 1625683390
    }

    # TODO: Check metrics against service definition
    assert False