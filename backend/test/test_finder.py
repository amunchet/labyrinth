#!/usr/bin/env python3
"""
Tests for auto-scanner (nmap)
"""
import finder

def test_scan():
    """
    Tests running a scan

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
        }
    }]
    """


def test_create_initial():
    """
    Testing for initial creation of the host
        - Only the initial run will create service hosts
    """

    # We want to actually modify this, 
    # so it comes up with an error for the next test

def test_after_initial():
    """
    Tests after initial run - if different ports exist, need to flag
    """
