#!/usr/bin/env python3
"""
Tests for settings
    - Alerting settings - email addresses?
    - Frequency of alerts
    - Possibly ignore alerts, unsure.
"""
import json
import os

import pytest
import serve

from common.test import unwrap


def teardown():
    """
    Removes all stored settings
    """
    serve.mongo_client["labyrinth"]["settings"].delete_many({})
    temp_file = "/public/icons/test.svg"
    if os.path.exists(temp_file):
        os.remove(temp_file)


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
    assert json.loads(c[0]) == [{"test": "test"}]


def test_delete_setting(setup):
    test_save_and_get_settings(setup)

    b = unwrap(serve.get_setting)("test")
    assert b[1] == 200

    d = unwrap(serve.delete_setting)("test")

    b = unwrap(serve.get_setting)("test")
    assert b[1] == 481


# Icons


def test_list_icons(setup):
    """
    Lists icons
    """
    a = unwrap(serve.list_icons)()
    assert a[1] == 200

    b = json.loads(a[0])

    assert "Camera" in b
    assert "Cloud" in b
    assert "NAS" in b
    assert "Default" in b


def test_delete_icon(setup):
    """
    Removes an icon
    """

    # Creates a temporary icon
    temp_file = "/public/icons/test.svg"
    if not os.path.exists(temp_file):
        with open(temp_file, "w") as f:
            f.write("test")

    assert os.path.exists(temp_file)
    # Deletes it

    a = unwrap(serve.delete_icon)("test")
    assert a[1] == 200

    assert not os.path.exists(temp_file)

def test_create_edit_icon(setup):
    """
    Creates/Edits an icon
    """
    temp_file = "/tmp/test.svg"
    if not os.path.exists(temp_file):
        with open(temp_file, "w") as f:
            f.write("test")

    a = unwrap(serve.list_icons)()
    assert a[1] == 200

    b = json.loads(a[0])
    assert "test" not in b

    a = unwrap(serve.upload_icon)(override=temp_file)
    assert a[1] == 200

    a = unwrap(serve.list_icons)()
    assert a[1] == 200
    b = json.loads(a[0])
    assert "test" in b
