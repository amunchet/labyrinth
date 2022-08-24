#!/usr/bin/env python3

import os
import json
import shutil

import pytest
import serve

from copy import deepcopy

from common.test import unwrap


def tearDown():
    """Tear down"""
    serve.mongo_client["labyrinth"]["themes"].delete_many({})


@pytest.fixture
def setup():
    """Sets up"""
    tearDown()
    yield "Setting up..."
    tearDown()
    return "Done"


def test_list_themes(setup):
    """
    Tests Listing themes
        - Check to see that the collection has the defaults created
    """
    x = list(serve.mongo_client["labyrinth"]["themes"].find({}))
    assert len(x) == 0

    a = unwrap(serve.list_themes)()
    assert a[1] == 200
    b = json.loads(a[0])
    c = [x["name"] for x in b]
    assert "Blue" in c
    assert "Red" in c

    x = list(serve.mongo_client["labyrinth"]["themes"].find({}))
    assert len(x) == 3


def test_create_edit_theme(setup):
    """
    Creates/Edits Theme
    """

    sample = {
        "name": "TEST",
        "show": {},
        "border": {},
        "background": {},
        "text": {},
        "connection": {},
    }

    a = unwrap(serve.create_edit_theme)({"asdfasdf": "asdsfasd"})
    assert a[1] == 485

    a = unwrap(serve.create_edit_theme)(sample)
    assert a[1] == 200

    a = unwrap(serve.list_themes)()
    assert a[1] == 200

    b = json.loads(a[0])
    c = [x["name"] for x in b]
    assert "TEST" in c

    # Deletes theme

    a = unwrap(serve.delete_theme)("TEST")

    assert a[1] == 200

    a = unwrap(serve.list_themes)()
    assert a[1] == 200
    b = json.loads(a[0])
    c = [x["name"] for x in b]
    assert "TEST" not in c
