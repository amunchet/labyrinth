#!/usr/bin/env python3
"""
Alert manager
"""
import os
import pytest
import serve
from common.test import unwrap

@pytest.fixture
def setup():
    """
    Setup
    """

    yield "Setting up..."

    return "Finished"

# Serve items
def test_alertmanager_pass():
    """
    Tests alertmanager_pass - reads in the file `pass`
    """
    fname = "/alertmanager/pass"
    if not os.path.exists(fname):
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
    if not os.path.exists(fname):
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
    if not os.path.exists(fname):
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