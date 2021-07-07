#!/usr/bin/env python3

import requests


def test_insecure():
    """Try to access open resource (success) and protected (fail)"""

    a = requests.get("http://localhost:7000/insecure")
    assert a.status_code == 200


def test_secure():
    """Checks access to a protected resource"""

    a = requests.get("http://localhost:7000/secure")
    assert a.status_code == 500  # Production would be 401


# Labyrinth main functions




def test_create_edit_subnet():
    """Creates/Edits a subnet in the database"""


def test_create_edit_host():
    """Creates/Edits a host for the given subnet"""



def test_create_edit_link():
    """Creates/Edits a link between two subnets"""
    
def test_list_dashboard():
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

def test_create_service():
    """
    Creating services is difficult.  
        - Need to have the JSON definiton
        - Type: service can be a port scan, a telegraf input, or data to be pulled
        - Need to have the boolean comparison operations - and, not, or, contains, etc.
    """

def test_read_services():
    """Returns the services for a given host"""
