#!/usr/bin/env python3
"""
Tests for Watcher
    - CRON
    - Email functionality
    - [FUTURE] Slack, Discord, etc.
"""
import json
import pytest
import serve
from common.test import unwrap

def test_watcher():
    """
    - Walk over subnets
    - Walk over hosts
    - For each host, get a list of associated services and metrics
        + Check each services vs latest metric, alert if failed
    
    Redis server integration here somehow? - May just do Mongo for the time being
    """

    subnets = {}

    hosts = {}
    
    services = {}

    metrics = {}

def test_stale_metrics():
    """
    Tests stale metrics
    """
def test_unexpected_host():
    """Want alerts on an unexpected host"""