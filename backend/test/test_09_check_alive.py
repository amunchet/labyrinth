"""
Check Alive tests
    - TODO: Look at Nagios and see what options/configurations are done there
        - command
        - max check attempts
        - notification options (won't be used here)

This is probably going to be parallelized in Go at some point
"""

import alive

def test_alive_ping():
    """
    Detects alive from ping
        - sampleclient
    """
    assert alive.ping("sampleclient")


def test_alive_port():
    """
    Detects Alive from a port connection
        - sampleclient, 22
    """
    assert alive.check_port("sampleclient", 22)

def test_alive_cron():
    """
    Runs check alive for everyone and alerts for any not alive that should be
        - Alerts will run from within the loop
    """
    alive.check_all_hosts()