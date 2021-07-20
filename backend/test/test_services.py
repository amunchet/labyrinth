#!/usr/bin/env python3
"""
Tests for the TOML work
"""
import pytest

import services
import toml

@pytest.fixture
def setup():
    lines = services.prepare("/src/backend/test/sample_telegraf.json")
    decoder = toml.TomlPreserveCommendDecoder(beforeComments = True)

    x = toml.loads("\n".join(lines), decoder=decoder)

    assert x["agent"]["interval"].val.val == "10s"
    assert [x for x in decoder.before_tags if "interval" in x["name"]][0]["comments"] == ['Default data collection interval for all inputs'] 


    # TODO: Test duplicate sections

    # TODO: Test Duplicate keys

    # TODO: Multiline Arrays
    yield (x, decoder)

# Redis


def test_put_comments():
    """
    Store all comments into Redis
        - Renamed - put the parent + . + name split before = and stripped
        - Call these by their keys in `decoder.before_tags`

    """

def test_put_structure():
    """
    Push JSON of the actual structure to Redis
        - Called "master.data"

    """

# Get data

def test_get_structure():
    """
    Gets stored Redis structure
    """

def test_get_comment():
    """
    Gets comment
    """

# Compile

def compile_snippets():
    """
    Compile selected snippets into working TOML files
    """

def test_telegraf_conf():
    """
    Tests that the resultant conf is valid for telegraf
    """