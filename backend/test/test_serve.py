#!/usr/bin/env python3

import requests
import pytest
import serve

from common.test import unwrap


def test_insecure():
    """Try to access open resource (success) and protected (fail)"""

    a = requests.get("http://localhost:7000/insecure")
    assert a.status_code == 200


def test_secure():
    """Checks access to a protected resource"""

    a = requests.get("http://localhost:7000/secure")
    assert a.status_code == 500  # Production would be 401


# Labyrinth main functions

def teardown():
    """Tears down tests"""
    serve.mongo_client["labyrinth"]["subnets"].delete_many({})
    serve.mongo_client["labyrinth"]["groups"].delete_many({})
    serve.mongo_client["labyrinth"]["hosts"].delete_many({})
    serve.mongo_client["labyrinth"]["services"].delete_many({})
    serve.mongo_client["labyrinth"]["settings"].delete_many({})
    

@pytest.fixture
def setup():
    """Sets up tests"""
    teardown()
    yield "Setting up..."
    teardown()
    return "Done"


def test_create_edit_subnet(setup):
    """
    Creates/Edits a subnet in the database
        - (_id)
        - Entry point (can be 127.0.0.1)
        - Link to other subnet
    """
    sample_subnet = {
        "subnet" : "192.168.0",
        "origin" : {
            "ip" : "127.0.0.1",
            "icon" : "VMWare"
        },
        "links" : {
            "ref" : "start_1",
            "ip" : ".175",
            "icon" : "Router",
            "color": "orange"
        }
    }

    # Create it
    a = unwrap(serve.create_edit_subnet)(sample_subnet)
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["subnets"].find({})
    c = [x for x in b]
    assert len(c) == 1

    assert c[0]["subnet"] == "192.168.0"
    assert c[0]["links"] == sample_subnet["links"]

    # Edit it

    sample_subnet["links"]["ref"] = "start_2"
    a = unwrap(serve.create_edit_subnet)(sample_subnet)
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["subnets"].find({})
    c = [x for x in b]
    assert len(c) == 1

    assert c[0]["subnet"] == "192.168.0"
    assert c[0]["groups"] == sample_subnet["groups"]
    assert c[0]["links"] != sample_subnet["links"]
    assert c[0]["links"]["ref"] == "start_2"

def test_create_group(setup):
    """
    Creates/Edits Group
        - (_id)
        - Name
        - Children MACs

    """
    sample_group = {
        "name" : "Linux Servers",
        "members": ["00-00-00-01", "00-00-00-02"]
    }
    a = unwrap(serve.create_edit_group)(sample_group)
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["groups"].find({})
    c = [x for x in b]
    assert len(c) == 1

    assert c[0]["name"] == sample_group["name"]
    assert c[0]["members"] == sample_group["members"]

def test_create_edit_host(setup):
    """
    Creates/Edits a host for the given subnet
        - (_id)
        - IP address
        - Subnet
        - MAC Address
        - Icon
        - Services
        - Class: this determines if we are monitoring standard vitals (PC) or not (phone)

    """
    sample_host = {
        "ip" : "192.168.0.172",
        "subnet" : "192.168.0",
        "mac" : "00-00-00-00-01",
        "group" : "Linux Servers",
        "icon" : "linux",
        "services": [
            "port_ssh",
            "metric_cpu",
            "metric_hd",
            "metric_ram"
        ],
        "class" : "health"
    }

    # Create Host - what are the implications for the group and subnet?
    a = unwrap(serve.create_edit_host)(sample_host)
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["hosts"]
    b = serve.mongo_client["labyrinth"]["groups"]
    b = serve.mongo_client["labyrinth"]["subnets"]



    # Edit Host - what are the implications for the group and subnet?


def test_create_edit_link(setup):
    """Creates/Edits a link between two subnets"""
    

def test_delete_subnet(setup):
    """Deletes a subnet"""

def test_delete_group(setup):
    """Deletes a Group"""

def test_delete_host(setup):
    """Deletes a Host"""

def test_list_dashboard(setup):
    """
    Lists all items for the dashboard
        - Subnets
        - Hosts
        - Services
        - Links

    - This will be interesting, as localhost (whatever the scanner is) will be the top
    - Graph traversal for the given links
    """

"""
Tests for Services
    - Services are definitions of how to interpret the received metrics
    - For example, a service could be reading the metric of "mem" for a host and seeing if "free" was greater than 1000
"""

def test_create_service(setup):
    """
    Creating services is difficult.  
        - Need to have the JSON definiton
        - Type: service can be a port scan, a telegraf input, or data to be pulled
        - Need to have the boolean comparison operations - and, not, or, contains, etc.
    """

def test_read_services(setup):
    """Returns the services for a given host"""

def test_delete_service(setup):
    """Deletes a Service"""

    # Implications for hosts that have this service enabled