#!/usr/bin/env python3
"""
Tests for Watcher
    - CRON
    - Email functionality
    - [FUTURE] Slack, Discord, etc.
"""
import pytest

@pytest.fixture
def setup():
    """
    Sets up the Watcher
        
    """


def test_get_latest_metrics():
    """
    Pull latest metrics from REDIS?

    May just do Mongo for the time being
    """
def test_watcher():
    """
    - Walk over subnets
    - Walk over hosts
    - For each host, get a list of associated services and metrics
        + Check each services vs latest metric, alert if failed
    
    Redis server integration here somehow? - May just do Mongo for the time being
    """
def test_stale_metrics():
    """
    Tests stale metrics
    """
def test_unexpected_host():
    """Want alerts on an unexpected host"""