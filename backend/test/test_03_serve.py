#!/usr/bin/env python3

import os
import json

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
    serve.mongo_client["labyrinth"]["hosts"].delete_many({})
    serve.mongo_client["labyrinth"]["services"].delete_many({})
    serve.mongo_client["labyrinth"]["settings"].delete_many({})
    serve.mongo_client["labyrinth"]["metrics"].delete_many({})



@pytest.fixture
def setup():
    """Sets up tests"""
    teardown()
    yield "Setting up..."
    teardown()
    return "Done"

def test_list_subnets(setup):
    """Lists all subnets"""
    sample_subnet = {

        "subnet": "192.168.0",
        "origin": {
            "ip": "127.0.0.1",
            "icon": "VMWare"
        },
        "links": {
            "ref": "start_1",
            "ip": ".175",
            "icon": "Router",
            "color": "orange"
        }
    }
    sample_subnet_two = {

        "subnet": "192.168.1",
        "origin": {
            "ip": "127.0.0.1",
            "icon": "VMWare"
        },
        "links": {
            "ref": "start_1",
            "ip": ".175",
            "icon": "Router",
            "color": "orange"
        }
    }

    # Create it
    a = unwrap(serve.create_edit_subnet)(sample_subnet)
    assert a[1] == 200

    a = unwrap(serve.create_edit_subnet)(sample_subnet)
    assert a[1] == 200


    a = unwrap(serve.create_edit_subnet)(sample_subnet_two)
    assert a[1] == 200

    a = unwrap(serve.list_subnets)()
    assert a[1] == 200
    assert json.loads(a[0]) == ["192.168.0", "192.168.1"]

def test_list_subnet(setup):
    """
    Lists all entries for a given subnet
    """
    sample_subnet = {
        "subnet": "192.168.0",
        "origin": {
            "ip": "127.0.0.1",
            "icon": "VMWare"
        },
        "links": {
            "ref": "start_1",
            "ip": ".175",
            "icon": "Router",
            "color": "orange"
        }
    }

    # Create it
    a = unwrap(serve.create_edit_subnet)(sample_subnet)
    assert a[1] == 200

    a = unwrap(serve.list_subnet)("192.168.88")
    assert a[1] == 404

    a = unwrap(serve.list_subnet)("192.168.0")
    assert a[1] == 200

    b = json.loads(a[0])
    for item in [x for x in sample_subnet.keys() if x != "_id"]:
        assert b[item] == sample_subnet[item]


def test_create_edit_subnet(setup):
    """
    Creates/Edits a subnet in the database
        - (_id)
        - Entry point (can be 127.0.0.1)
        - Link to other subnet
    """
    sample_subnet = {
        "subnet": "192.168.0",
        "origin": {
            "ip": "127.0.0.1",
            "icon": "VMWare"
        },
        "links": {
            "ref": "start_1",
            "ip": ".175",
            "icon": "Router",
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
    d = [x for x in b]
    assert len(d) == 1

    assert d[0]["subnet"] == "192.168.0"
    assert d[0]["links"]["ref"] == "start_2"


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
        "ip": "192.168.0.172",
        "subnet": "192.168.0",
        "mac": "00-00-00-00-01",
        "group": "Linux Servers",
        "icon": "linux",
        "services": [
            "open_ports",
            "closed_ports",
            "check_hd"
        ],
        "open_ports" : [
            22
        ],
        "class": "health"
    }

    # Create Host - what are the implications for the group and subnet?
    a = unwrap(serve.create_edit_host)(sample_host)
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["hosts"].find({})
    c = [x for x in b]
    print("Hosts: ", c)
    assert len(c) == 1

    for key in sample_host.keys():
        assert sample_host[key] == c[0][key]


    b = serve.mongo_client["labyrinth"]["subnets"].find({})
    c = [x for x in b]
    assert len(c) == 1

    assert c[0]["subnet"] == "192.168.0"

    # Edit Host - what are the implications for the group and subnet?
    sample_host["ip"] = "192.168.10.176"
    sample_host["group"] = "Windows Servers"
    sample_host["subnet"] = "192.168.10"

    a = unwrap(serve.create_edit_host)(sample_host)
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["hosts"].find({})
    c = [x for x in b]
    assert len(c) == 1

    for key in sample_host.keys():
        assert sample_host[key] == c[0][key]


    b = serve.mongo_client["labyrinth"]["subnets"].find({})
    c = [x for x in b]
    assert len(c) == 2

    assert c[1]["subnet"] == "192.168.10"


def test_create_edit_link(setup):
    """Creates/Edits a link between two subnets"""
    test_create_edit_subnet(setup)
    data = {
        "ref": "start_76",
        "ip": ".178",
        "icon": "Router",
        "color": "orange"
    }
    a = unwrap(serve.create_edit_link)(link=data, subnet="192.168.0")

    b = serve.mongo_client["labyrinth"]["subnets"].find({})
    c = [x for x in b]
    assert len(c) == 1

    print(c[0])

    assert c[0]["links"] == data


def test_delete_subnet(setup):
    """Deletes a subnet"""
    test_create_edit_subnet(setup)
    b = serve.mongo_client["labyrinth"]["subnets"].find({})
    c = [x for x in b]
    assert len(c) == 1

    a = unwrap(serve.delete_subnet)("192.168.0")
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["subnets"].find({})
    c = [x for x in b]
    assert len(c) == 0

    a = unwrap(serve.delete_subnet)("192.168.0")
    assert a[1] == 407

def test_delete_host(setup):
    """
    Deletes a Host
    """
    test_create_edit_host(setup)
    b = serve.mongo_client["labyrinth"]["hosts"].find({})
    c = [x for x in b]
    assert len(c) == 1

    a = unwrap(serve.delete_host)("00-00-00-00-01")
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["hosts"].find({})
    c = [x for x in b]
    assert len(c) == 0

    a = unwrap(serve.delete_host)("00-00-00-00-01")
    assert a[1] == 407

def test_read_service(setup):
    """Reads a given service"""
    port_service = {
        "name": "port_ssh",
        "type": "port",
        "port": 22,
        "state": "open"
    }


    # Create Service
    a = unwrap(serve.create_edit_service)(port_service)
    assert a[1] == 200

    # Read service
    a = unwrap(serve.read_service)("port_ssh")
    assert a[1] == 200

    b = json.loads(a[0])[0]
    for item in [x for x in port_service.keys() if x != "_id"]:
        assert b[item] == port_service[item]


def test_read_services(setup):
    """Lists all available services"""
    port_service = {
        "name": "port_ssh",
        "type": "port",
        "port": 22,
        "state": "open"
    }
    check_service = {
        "name": "check_hd",
        "type": "check",
        "metric": "diskio",
        "field": "read_time",
        "comparison": "greater",
        "value": 1000

    }

    # Create Service
    a = unwrap(serve.create_edit_service)(port_service)
    assert a[1] == 200

    a = unwrap(serve.create_edit_service)(check_service)
    assert a[1] == 200

    a = unwrap(serve.list_services)()
    assert a[1] == 200
    b = json.loads(a[0])

    assert b == ["port_ssh", "check_hd"]
def test_create_service(setup):
    """
    Services are definitions of how to interpret the received metrics
        - For example, a service could be reading the metric of "mem" for a 
        host and seeing if "free" was greater than 1000

    Creating services is difficult.  
        - Need to have the JSON definiton
        - Type: service can be a port scan, a telegraf input, or data to be pulled
        - Need to have the boolean comparison operations - and, not, or, contains, etc.
        - THESE INVOLVE SNIPPETS
    """
    port_service = {
        "name": "port_ssh",
        "type": "port",
        "port": 22,
        "state": "open"
    }
    check_service = {
        "name": "check_hd",
        "type": "check",
        "metric": "diskio",
        "field": "read_time",
        "comparison": "greater",
        "value": 1000

    }

    # Create Service
    a = unwrap(serve.create_edit_service)(port_service)
    assert a[1] == 200

    a = unwrap(serve.create_edit_service)(check_service)
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["services"].find({})
    c = [x for x in b]
    assert len(c) == 2

    for item in port_service.keys():
        assert c[0][item] == port_service[item]

    for item in check_service.keys():
        assert c[1][item] == check_service[item]

    # Edit Service
    port_service["port"] = 23
    check_service["value"] = 300

    a = unwrap(serve.create_edit_service)(port_service)
    assert a[1] == 200

    a = unwrap(serve.create_edit_service)(check_service)
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["services"].find({})
    c = [x for x in b]
    assert len(c) == 2

    for item in port_service.keys():
        assert c[0][item] == port_service[item]

    for item in check_service.keys():
        assert c[1][item] == check_service[item]


def test_delete_service(setup):
    """
    Deletes a Service
        - THIS NOW HAS IMPLICATIONS FOR SNIPPETS
        - Implications for hosts that have this service enabled
    """
    test_create_edit_host(setup)
    test_create_service(setup)

    # Create snippet if not exists
    filename = "/src/snippets/check_hd"
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write(".")

    assert os.path.exists(filename)

    b = serve.mongo_client["labyrinth"]["hosts"].find({})
    c = [x for x in b]
    assert len(c) == 1
    assert c[0]["services"] == [
        "open_ports",
        "closed_ports",
        "check_hd"
    ]

    b = serve.mongo_client["labyrinth"]["services"].find({})
    c = [x for x in b]
    assert len(c) == 2

    a = unwrap(serve.delete_service)("open_ports")
    assert a[1] == 200

    a = unwrap(serve.delete_service)("check_hd")
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["services"].find({})
    c = [x for x in b]
    assert len(c) == 1

    # Check that snippet is gone
    assert not os.path.exists(filename)

    # Check that all hosts have the service deleted
    b = serve.mongo_client["labyrinth"]["hosts"].find({})
    c = [x for x in b]
    assert len(c) == 1
    assert c[0]["services"] == ["closed_ports"]

def test_update_mac_address(setup):
    """
    There may be an odd case where a hardware failure (or VMWare reconfiguration)
    causes a MAC change.

    In that case, we would need to update the other entries in the database
    with the new MAC
    """
    test_create_edit_host(setup)
    b = serve.mongo_client["labyrinth"]["hosts"].find({})
    c = [x for x in b]
    print("Hosts: ", c)
    assert len(c) == 1

    a = unwrap(serve.update_mac)(old_mac=c[0]["mac"], new_mac="000000")
    assert a[1] == 200
    b = serve.mongo_client["labyrinth"]["hosts"].find({})
    c = [x for x in b]
    print("Hosts: ", c)
    assert len(c) == 1

    assert c[0]["mac"] == "000000"


def test_update_ip_address(setup):
    """Updates an IP address for the given MAC address"""
    test_create_edit_host(setup)
    b = serve.mongo_client["labyrinth"]["hosts"].find({})
    c = [x for x in b]
    print("Hosts: ", c)
    assert len(c) == 1

    a = unwrap(serve.update_ip)(mac=c[0]["mac"], new_ip="000000")
    assert a[1] == 200
    b = serve.mongo_client["labyrinth"]["hosts"].find({})
    c = [x for x in b]
    print("Hosts: ", c)
    assert len(c) == 1

    assert c[0]["ip"] == "000000"

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
    expected = [
        {
            "subnet": "192.168.0",
            "origin": {
                "ip": "127.0.0.1",
                "icon": "VMWare"
            },
            "groups": [
                {
                    "name": "Linux Servers",
                    "hosts": [
                        {
                            "ip": "192.168.0.172",
                            "subnet": "192.168.0",
                            "mac": "00-00-00-00-01",
                            "group": "Linux Servers",
                            "icon": "linux",
                            "services": [
                                {
                                    "name" : "open_ports",
                                    "state" : True
                                },
                                {
                                    "name" : "closed_ports",
                                    "state" :True 
                                },
                                {
                                    "name" : "check_hd",
                                    "state" : True
                                },

                            ],
                            "class": "health"
                        }
                    ]
                }
            ],
            "links": {
                "ref": "start_1",
                "ip": ".175",
                "icon": "Router",
                "color": "orange"
            }
        }
    ]

    a = unwrap(serve.dashboard)()
    assert a[1] == 200

    b = json.loads(a[0])
    assert b == expected