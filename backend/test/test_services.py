#!/usr/bin/env python3
"""
Tests for the TOML work
"""
import json

import redis
import pytest

import services
import serve
import toml

from common.test import unwrap

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

def test_generate_structure(setup):
    """
    Tests generating an object from the TOML
    """
    lines,decoder = setup
    x = services.parse(lines["inputs"]["postgresql_extensible"][0])

    assert x["address"] == "host=localhost user=postgres sslmode=disable"
    assert x["query"] == [{'measurement': '', 'sqlquery': 'SELECT * FROM pg_stat_bgwriter', 'version': 901, 'withdbname': False, 'tagvalue': 'postgresql.stats'}]

# Redis


def test_redis_comments():
    """
    Store all comments into Redis
        - Renamed - put the parent + . + name split before = and stripped
        - Call these by their keys in `decoder.before_tags`

    """
    a = unwrap(serve.put_comments)()
    assert a[1] == 200

    name = "inputs.sysstat.device_tags.sda"
    b = unwrap(serve.get_comment)(name)
    assert b[1] == 200
    
    assert json.loads(b[0])["comments"] == ['Currently supported formats:']

    name = "inputs.execd.command"
    b = unwrap(serve.get_comment)(name)
    assert b[1] == 200
    
    assert json.loads(b[0])["comments"] ==  ['- "EVENTHUB_NAME"']



def test_redis_structure():
    """
    Push JSON of the actual structure to Redis
        - Called "master.data"

    """
    a = services.generate_structure()
    
    b = unwrap(serve.put_structure)()
    assert b[1] == 200

    c = unwrap(serve.get_structure)()
    assert c[1] == 200
    assert a == c[0]


# Compile

def compile_snippets():
    """
    Compile selected snippets into working TOML files
    """
    assert False
def test_telegraf_conf():
    """
    Tests that the resultant conf is valid for telegraf
    """
    assert False