#!/usr/bin/env python3
"""
Alert manager
"""
import os
import json

import pytest
import requests

import serve
import watcher
from common.test import unwrap


# Serve items
def test_alertmanager_pass():
    """
    Tests alertmanager_pass - reads in the file `pass`
    """
    fname = "/alertmanager/pass"
    if not os.path.exists(fname):  # pragma: no cover
        with open(fname, "w") as f:
            f.write("test")

    with open(fname) as f:
        a = f.read()

    b = unwrap(serve.alertmanager_pass)()
    assert b[1] == 200
    assert b[0] == a


def test_alertmanager_load():
    """
    Tests alertmanager_load
    """
    fname = "/alertmanager/alertmanager.yml"
    if not os.path.exists(fname):  # pragma: no cover
        with open(fname, "w") as f:
            f.write("test")

    with open(fname) as f:
        a = f.read()

    b = unwrap(serve.alertmanager_load)()
    assert b[1] == 200
    assert b[0] == a


def test_alertmanager_save():
    """
    Tests alertmanager_save
    """
    fname = "/alertmanager/alertmanager.yml"
    if not os.path.exists(fname):  # pragma: no cover
        with open(fname, "w") as f:
            f.write("test")

    with open(fname) as f:
        a = f.read()

    os.remove(fname)
    assert not os.path.exists(fname)

    b = unwrap(serve.alertmanager_save)(a)
    assert b[1] == 200
    fname = "/alertmanager/alertmanager.yml"
    if not os.path.exists(fname):
        with open(fname, "w") as f:
            f.write("test")

    with open(fname) as f:
        c = f.read()

    assert a == c


# Action items
def test_send_alert():
    """
    Tests sending an alert to alertmanager
        - Will just print out URL and payload
    """
    a = unwrap(serve.list_alerts)()
    print(a[0])
    assert a[1] == 200
    b = json.loads(a[0])

    output= watcher.send_alert(
        "test-alert",
        "test-service",
        "test-host",
    )
    print(output.text)
    assert output
    a = unwrap(serve.list_alerts)()
    assert a[1] == 200

    b = json.loads(a[0])

    assert b[-1]["labels"]["alertname"] == "test-alert"
    assert b[-1]["labels"]["instance"] == "test-host"
    assert b[-1]["labels"]["service"] == "test-service"


def test_restart_and_resolve_alert():
    """
    Resolves a given alert
    """

    a = unwrap(serve.restart_alertmanager)()
    assert a[1] == 200

    a = unwrap(serve.list_alerts)()
    assert a[1] == 200
    if a[0] == "[]":  # pragma: no cover
        test_send_alert()

    a = unwrap(serve.list_alerts)()
    assert a[1] == 200
    b = json.loads(a[0])

    data = b[0]

    a = unwrap(serve.resolve_alert)(data)

    print(a[0])

    assert a[1] == 200

    a = unwrap(serve.list_alerts)()
    assert a[1] == 200
    b = json.loads(a[0])
    assert b == []
