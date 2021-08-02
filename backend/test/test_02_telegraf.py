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
    # Clear redis
    rc = redis.Redis(host="redis")
    for key in rc.keys("*"):
        rc.delete(key)

    lines = services.prepare("/src/test/sample_telegraf.conf")
    decoder = toml.TomlPreserveCommentDecoder(beforeComments = True)

    x = toml.loads("\n".join(lines), decoder=decoder)

    assert x["agent"]["interval"].val.val == "10s"
    assert [x for x in decoder.before_tags if "interval" in x["name"]][0]["comments"] == ['Default data collection interval for all inputs'] 


    # TODO: Test duplicate sections

    # TODO: Test Duplicate keys

    # TODO: Multiline Arrays
    yield (x, decoder)

def test_generate(setup):
    """
    Tests generating an object from the TOML
    """
    lines,decoder = setup
    x = services.parse(lines["inputs"]["postgresql_extensible"][0])

    assert x["address"] == "host=localhost user=postgres sslmode=disable"
    assert x["query"] == [{'measurement': '', 'sqlquery': 'SELECT * FROM pg_stat_bgwriter', 'version': 901, 'withdbname': False, 'tagvalue': 'postgresql.stats'}]

# Redis

def test_redis_structure(setup):
    """
    Push JSON of the actual structure to Redis
        - Called "master.data"

    """

    b = unwrap(serve.put_structure)()
    assert b[1] == 200

    c = unwrap(serve.get_structure)()
    assert c[1] == 200
    lines = json.loads(c[0])
    x = lines["inputs"]["postgresql_extensible"][0]
    print(x)

    assert x["address"] == "host=localhost user=postgres sslmode=disable"
    assert x["query"] == [{'measurement': '', 'sqlquery': 'SELECT * FROM pg_stat_bgwriter', 'version': 901, 'withdbname': False, 'tagvalue': 'postgresql.stats'}]


def test_redis_comments(setup):
    """
    Store all comments into Redis
        - Renamed - put the parent + . + name split before = and stripped
        - Call these by their keys in `decoder.before_tags`

    """
    a = unwrap(serve.put_structure)()
    assert a[1] == 200

    name = "inputs.sysstat.device_tags.sda"
    b = unwrap(serve.get_comment)(name)
    assert b[1] == 200
    
    assert json.loads(b[0])["comments"] == ['#   ## Device tags can be used to add additional tags for devices.', '#   ## For example the configuration below adds a tag vg with value rootvg for', '#   ## all metrics with sda devices.']
    assert json.loads(b[0])["multiple"] == True

    name = "inputs.execd.command"
    b = unwrap(serve.get_comment)(name)
    assert b[1] == 200
    
    assert json.loads(b[0])["comments"] ==  ['#   ## Program to run as daemon']

    # Test the last entry too to check for comment drift
    expected = {'name': '[[inputs.zipkin]].port', 'comments': [' Port on which Telegraf listens'], 'parent': '[[inputs.zipkin]]', 'value': '9411            # Port on which Telegraf listens'}
    name = "inputs.zipkin.port"
    b = unwrap(serve.get_comment)(name)
    assert b[1] == 200

    assert json.loads(b[0]) == expected

def test_output():
    """
    Missing from `services.py` coverage
    """
    assert False

def test_load():
    assert False

def test_run():
    assert False