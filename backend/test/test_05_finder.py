#!/usr/bin/env python3
"""
Tests for auto-scanner (nmap)
"""
import os
import json
import time

import pytest
import finder

sample_input = {
    "hostnames": [
        {"name": "labyrinth_sampleclient_1.labyrinth_labyrinth", "type": "PTR"}
    ],
    "addresses": {"ipv4": "192.168.0.2", "mac": "02:42:C0:A8:00:02"},
    "vendor": {},
    "status": {"state": "up", "reason": "arp-response"},
    "uptime": {"seconds": "729514", "lastboot": "Thu Jul  1 06:36:08 2021"},
    "tcp": {
        22: {
            "state": "open",
            "reason": "syn-ack",
            "name": "ssh",
            "product": "OpenSSH",
            "version": "7.9p1 Debian 10+deb10u2",
            "extrainfo": "protocol 2.0",
            "conf": "10",
            "cpe": "cpe:/o:linux:linux_kernel",
        }
    },
    "portused": [
        {"state": "open", "proto": "tcp", "portid": "22"},
        {"state": "closed", "proto": "tcp", "portid": "1"},
        {"state": "closed", "proto": "udp", "portid": "41065"},
    ],
    "osmatch": [
        {
            "name": "Linux 2.6.32",
            "accuracy": "96",
            "line": "55173",
            "osclass": [
                {
                    "type": "general purpose",
                    "vendor": "Linux",
                    "osfamily": "Linux",
                    "osgen": "2.6.X",
                    "accuracy": "96",
                    "cpe": ["cpe:/o:linux:linux_kernel:2.6.32"],
                }
            ],
        },
        {
            "name": "Linux 3.2 - 4.9",
            "accuracy": "96",
            "line": "65105",
            "osclass": [
                {
                    "type": "general purpose",
                    "vendor": "Linux",
                    "osfamily": "Linux",
                    "osgen": "3.X",
                    "accuracy": "96",
                    "cpe": ["cpe:/o:linux:linux_kernel:3"],
                },
                {
                    "type": "general purpose",
                    "vendor": "Linux",
                    "osfamily": "Linux",
                    "osgen": "4.X",
                    "accuracy": "96",
                    "cpe": ["cpe:/o:linux:linux_kernel:4"],
                },
            ],
        },
        {
            "name": "Linux 2.6.32 - 3.10",
            "accuracy": "96",
            "line": "56381",
            "osclass": [
                {
                    "type": "general purpose",
                    "vendor": "Linux",
                    "osfamily": "Linux",
                    "osgen": "2.6.X",
                    "accuracy": "96",
                    "cpe": ["cpe:/o:linux:linux_kernel:2.6"],
                },
                {
                    "type": "general purpose",
                    "vendor": "Linux",
                    "osfamily": "Linux",
                    "osgen": "3.X",
                    "accuracy": "96",
                    "cpe": ["cpe:/o:linux:linux_kernel:3"],
                },
            ],
        },
        {
            "name": "Linux 3.4 - 3.10",
            "accuracy": "95",
            "line": "65366",
            "osclass": [
                {
                    "type": "general purpose",
                    "vendor": "Linux",
                    "osfamily": "Linux",
                    "osgen": "3.X",
                    "accuracy": "95",
                    "cpe": ["cpe:/o:linux:linux_kernel:3"],
                }
            ],
        },
        {
            "name": "Linux 3.1",
            "accuracy": "95",
            "line": "62708",
            "osclass": [
                {
                    "type": "general purpose",
                    "vendor": "Linux",
                    "osfamily": "Linux",
                    "osgen": "3.X",
                    "accuracy": "95",
                    "cpe": ["cpe:/o:linux:linux_kernel:3.1"],
                }
            ],
        },
        {
            "name": "Linux 3.2",
            "accuracy": "95",
            "line": "64455",
            "osclass": [
                {
                    "type": "general purpose",
                    "vendor": "Linux",
                    "osfamily": "Linux",
                    "osgen": "3.X",
                    "accuracy": "95",
                    "cpe": ["cpe:/o:linux:linux_kernel:3.2"],
                }
            ],
        },
        {
            "name": "AXIS 210A or 211 Network Camera (Linux 2.6.17)",
            "accuracy": "94",
            "line": "61606",
            "osclass": [
                {
                    "type": "webcam",
                    "vendor": "Linux",
                    "osfamily": "Linux",
                    "osgen": "2.6.X",
                    "accuracy": "94",
                    "cpe": ["cpe:/o:linux:linux_kernel:2.6.17"],
                },
                {
                    "type": "webcam",
                    "vendor": "AXIS",
                    "osfamily": "embedded",
                    "osgen": None,
                    "accuracy": "94",
                    "cpe": [
                        "cpe:/h:axis:210a_network_camera",
                        "cpe:/h:axis:211_network_camera",
                    ],
                },
            ],
        },
        {
            "name": "Synology DiskStation Manager 5.2-5644",
            "accuracy": "94",
            "line": "101159",
            "osclass": [
                {
                    "type": "storage-misc",
                    "vendor": "Synology",
                    "osfamily": "DiskStation Manager",
                    "osgen": "5.X",
                    "accuracy": "94",
                    "cpe": ["cpe:/a:synology:diskstation_manager:5.2"],
                }
            ],
        },
        {
            "name": "Netgear RAIDiator 4.2.28",
            "accuracy": "94",
            "line": "88023",
            "osclass": [
                {
                    "type": "storage-misc",
                    "vendor": "Netgear",
                    "osfamily": "RAIDiator",
                    "osgen": "4.X",
                    "accuracy": "94",
                    "cpe": ["cpe:/o:netgear:raidiator:4.2.28"],
                }
            ],
        },
        {
            "name": "Linux 2.6.32 - 2.6.35",
            "accuracy": "94",
            "line": "56153",
            "osclass": [
                {
                    "type": "general purpose",
                    "vendor": "Linux",
                    "osfamily": "Linux",
                    "osgen": "2.6.X",
                    "accuracy": "94",
                    "cpe": ["cpe:/o:linux:linux_kernel:2.6"],
                }
            ],
        },
    ],
}


def test_create_initial():
    """
    Testing for initial creation of the host
        - Only the initial run will create service hosts
    """

    sample_host = {
        "ip": "192.168.0.2",
        "subnet": "192.168.0",
        "mac": "02:42:C0:A8:00:02",
        "group": "linux",
        "icon": "linux",
        "services": ["open_ports", "closed_ports", "new_host"],
        "open_ports": [22],
        "class": "",
        "monitor": False,
        "host": "labyrinth_sampleclient_1.labyrinth_labyrinth",
    }
    a = finder.convert_host(sample_input)
    assert a == sample_host


def test_after_initial():
    """
    Tests after initial run - if different ports exist, need to flag
        - This will actually enter a metrics item
        - Setup will need to change expected ports
    """

    b = json.loads(json.dumps(sample_input))

    b["tcp"][23] = {
        "state": "open",
        "reason": "syn-ack",
        "name": "ssh",
        "product": "OpenSSH",
        "version": "7.9p1 Debian 10+deb10u2",
        "extrainfo": "protocol 2.0",
        "conf": "10",
        "cpe": "cpe:/o:linux:linux_kernel",
    }

    # Interesting here is an IP update for the host - really only matching on mac
    b["addresses"]["ipv4"] = "192.168.0.6"

    a = finder.process_scan(b)
    expected = {
        "fields": {"ports": [22, 23], "vulners": {}, "ip": "192.168.0.6"},
        "name": "open_ports",
        "tags": {
            "mac": "02:42:C0:A8:00:02",
            "host": "labyrinth_sampleclient_1.labyrinth_labyrinth",
            "name": "open_ports",
        },
        "timestamp": time.time(),
    }

    assert expected["fields"] == a["fields"]
    assert expected["name"] == a["name"]

    del a["tags"]["ip"]  # This is dynamically assigned

    assert expected["tags"] == a["tags"]
    assert expected["timestamp"] - a["timestamp"] < 10


def test_vuln_scanner():
    """[FUTURE] Tests vuln scanner integration"""


def scan_test():  # pragma: no cover
    """
    [DEPRECATED] Tests running a scan
        - This was removed from unit tests, because it's basically just testing integration of the NMap package

    ```
    >>> [n[x]['tcp'].keys() for x in n.all_hosts() if 'tcp' in n[x]]
    [dict_keys([111, 7200, 8082, 8100, 8181]), dict_keys([22]), dict_keys([7000]), dict_keys([8000, 8080]), dict_keys([8081])]
    ```
    """
    expected = """
    [{
        'hostnames': [{
            'name': 'sampleclient',
            'type': 'user'
        }, {
            'name': 'labyrinth_sampleclient_1.labyrinth_labyrinth',
            'type': 'PTR'
        }],
        'addresses': {
            'ipv4': '192.168.0.2',
            'mac': '02:42:C0:A8:00:02'
        },
        'vendor': {},
        'status': {
            'state': 'up',
            'reason': 'arp-response'
        },
        'tcp': {
            22: {
                'state': 'open',
                'reason': 'syn-ack',
                'name': 'ssh',
                'product': 'OpenSSH',
                'version': '7.9p1 Debian 10+deb10u2',
                'extrainfo': 'protocol 2.0',
                'conf': '10',
                'cpe': 'cpe:/o:linux:linux_kernel'
            }
        },
        'osmatch' : [
            {
                'name' : "Linux ...",
                "osclass" : [
                    {   
                        "osfamily" : "Linux"
                    }
                ]
            }
        ]
    }]
    """
    os.system("hostname -i > /tmp/hostname")
    subnet = ""
    with open("/tmp/hostname") as f:
        subnet = f.read()
    subnet = ".".join(subnet.split(".")[0:3])
    print("Subnet: ", subnet)
    a = finder.scan(subnet, print)

    idx = ""
    for i in range(0, len(a)):
        print(a[i]["hostnames"])
        if "sampleclient" in a[i]["hostnames"][0]["name"]:
            idx = i

    assert idx != ""

    assert "sampleclient" in a[idx]["hostnames"][0]["name"]
    assert a[idx]["status"]["state"] == "up"
    assert list(a[idx]["tcp"].keys()) == [22]
