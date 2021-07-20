#!/usr/bin/env python3
"""
Tests for the TOML work
"""
import services
import toml

def test_prepare():
    lines = services.prepare("/src/backend/test/sample_telegraf.json")
    decoder = toml.TomlPreserveCommendDecoder(beforeComments = True)

    x = toml.loads("\n".join(lines), decoder=decoder)

    assert x["agent"]["interval"].val.val == "10s"
    assert [x for x in decoder.before_tags if "interval" in x["name"]][0]["comments"] == ['Default data collection interval for all inputs'] 

    # TODO: Other tests - multiline comments, etc

def test_put_parents():
    """
    Store tags without children (actually without a parent tag) into Redis
    """

def test_put_children():
    """
    Store all children by their parents into Redis
    """

def test_list_roots():
    """
    List the root elements
    E.g. ['global_tags', 'agent', 'outputs', 'processors', 'aggregators', 'inputs', 'client']
    """

def test_list_services():
    """
    Lists available services for a root element
    E.g. ['dc', 'rack', 'user'] for "global_tags"
    """

def compile_snippets():
    """
    Compile selected snippets into working TOML files
    """

def test_telegraf_conf():
    """
    Tests that the resultant conf is valid for telegraf
    """