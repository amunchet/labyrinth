#!/usr/bin/env python3
"""
Checks hosts alive

This will be very similar to `finder.py`
"""
import json
import platform
import subprocess
import socket

import watcher

from pid import PidFile
from contextlib import closing

from common.test import unwrap
from serve import list_hosts


def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
    """

    # Option for the number of packets as a function of
    param = "-n" if platform.system().lower() == "windows" else "-c"

    # Building the command. Ex: "ping -c 1 google.com"
    command = ["ping", param, "1", "-W", "1", host]

    return subprocess.call(command) == 0


def check_port(host, port):
    """
    Checks if TCP port is open
    """
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            if sock.connect_ex((host, port)) == 0:
                return True
            else:
                return False
    except Exception:
        return False


def check_all_hosts():
    """
    Pulls in all hosts and checks them all
    """
    # Pid check
    with PidFile("labyrinth-alive") as p:
        # Load list of all hosts
        # List each subnet
        hosts = json.loads(unwrap(list_hosts)()[0])

        for host in hosts:
            # Alert if alerting is set on the host and it's down
            if "ip" not in host:
                continue

            host_name = host["ip"]

            alive_type = "Ping Check"
            if "check_alive_port" in host and "check_alive_port" != "":
                alive_type = "Port Check"

            if "monitor" in host and host["monitor"]:
                if alive_type == "Ping Check":
                    result = ping(host_name)
                else:
                    result = check_port(host_name, host["check_alive_port"])

                summary = "{} did not respond to {}.".format(host_name, alive_type)

                if not result:
                    watcher.send_alert(
                        "Check Alive", alive_type, host_name, summary=summary
                    )


if __name__ == "__main__":
    check_all_hosts()
