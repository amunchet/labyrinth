#!/usr/bin/env python3

"""Sample tests"""
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
DATA = [{"subnet": "192.168.0", "origin": {"ip": "127.0.0.1", "icon": "VMWare"}, "groups": [{"name": "Linux Servers", "hosts": [{"ip": "176", "icon": "Linux"}, {"ip": "176", "icon": "Linux"}, {"ip": "176", "icon": "Linux"}, {"ip": "176", "icon": "Linux"}]}, {"name": "Windows Servers", "hosts": [{"ip": "176", "icon": "Windows"}, {"ip": "176", "icon": "Windows"}, {"ip": "176", "icon": "Windows"}, {"ip": "176", "icon": "Windows"}]}], "links": {"ref": "start_1", "ip": ".175", "icon": "Router", "color": "orange"}}, {
    "subnet": "192.168.1", "color": "orange", "origin": {"ref": "end_1", "icon": "Cloud", "ip": "10.8.0.6"}, "groups": [{"name": "Linux Servers", "hosts": [{"ip": "176", "icon": "Phone"}, {"ip": "176", "icon": "Phone"}, {"ip": "176", "icon": "Phone"}, {"ip": "176", "icon": "Phone"}]}, {"name": "Windows Servers", "hosts": [{"ip": "176", "icon": "Tower"}, {"ip": "176", "icon": "Tower"}, {"ip": "176", "icon": "Tower"}, {"ip": "176", "icon": "Tower"}]}], "links": {"ref": "start_2", "ip": ".176", "icon": "Wireless", "color": "blue"}}]




def test_create_edit_subnet():
    """Creates/Edits a subnet in the database"""


def test_create_edit_host():
    """Creates/Edits a host for the given subnet"""


def test_create_edit_service():
    """Creates/Edits a service for the given host"""


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
