#!/usr/bin/env python3
"""
Tests for settings
    - Alerting settings - email addresses?
    - Frequency of alerts
    - Possibly ignore alerts, unsure.
"""
import json

import pytest
import serve

from common.test import unwrap

def teardown():
    """
    Removes all stored settings
    """
    serve.mongo_client["labyrinth"]["settings"].delete_many({})


@pytest.fixture
def setup():
    """
    Sets up and tears down
    """
    yield "Setting up"
    return "Done"

def test_save_and_get_settings(setup):
    a = unwrap(serve.save_setting)("test", "test")
    assert a[1] == 200

    b = unwrap(serve.get_setting)("test")
    assert b[1] == 200
    assert b[0] == "test"

    b = unwrap(serve.get_setting)("asdfasftest")
    assert b[1] == 481

    c = unwrap(serve.get_setting)()
    assert c[1] == 200
    assert json.loads(c[0]) == [{"test" : "test"}]


def test_delete_setting(setup):
    test_save_and_get_settings(setup)

    b = unwrap(serve.get_setting)("test")
    assert b[1] == 200

    d = unwrap(serve.delete_setting)("test")

    b = unwrap(serve.get_setting)("test")
    assert b[1] == 481
