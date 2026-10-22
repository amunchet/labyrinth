#!/usr/bin/env python3
"""
Checks hosts alive

Every host with an IP is pinged (or TCP-connected to when it has a
`check_alive_port`) at the address its hostname resolves to, falling back to
its last known IP, and the result is recorded in the Redis `alive` hash
(IP -> JSON) so maps and the inventory can show live reachability for anything
IP-reachable, not only hosts with Telegraf metrics.  Monitored hosts that are
down are also sent to Alertmanager.
"""
import json
import os
import platform
import subprocess
import socket
import time

import redis

import watcher

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

from common.hostnames import same_subnet

ALIVE_KEY = "alive"


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
            # Without a timeout a dead host blocks for the OS connect timeout (~2 min)
            sock.settimeout(2)
            if sock.connect_ex((host, port)) == 0:
                return True
            else:
                return False
    except Exception:
        return False


def check_host(host):
    """
    Checks one host and returns its alive record
        - The hostname is checked first, so a DHCP host that moved is found at its new IP.
          A resolved address outside the host's /24 (a search-domain or container-name
          collision) is ignored in favour of the last known IP
        - A `check_alive_port` (stored as text by the UI) means a TCP check instead of ping
        - An unusable port marks only this host down, with the reason, instead of failing every check
    """
    address = host["ip"]
    name = str(host.get("host") or "").strip().rstrip(".")
    if name and " " not in name:
        try:
            resolved = socket.gethostbyname(name)
        except (OSError, UnicodeError):
            resolved = ""
        if same_subnet(resolved, address):
            address = resolved

    port = str(host.get("check_alive_port") or "").strip()
    result = {
        "method": "port" if port else "ping",
        "port": port,
        "address": address,
        "error": "",
    }
    if not port:
        result["up"] = ping(address)
    elif port.isdigit():
        result["up"] = check_port(address, int(port))
    else:
        result["up"] = False
        result["error"] = "Invalid check port: {}".format(port)
    result["checked"] = time.time()
    return result


def check_all_hosts():  # pragma: no cover
    """
    Checks every host with an IP in parallel, records the results and alerts
    for monitored hosts that are down
    """
    # Imported here so serve can import this module for on-demand checks
    from pid import PidFile
    from common.test import unwrap
    from serve import list_hosts

    with PidFile("labyrinth-alive"):
        hosts = [x for x in json.loads(unwrap(list_hosts)()[0]) if x.get("ip")]

        with ThreadPoolExecutor(32) as pool:
            results = list(pool.map(check_host, hosts))

        # Replace the whole hash atomically so removed hosts drop out
        rc = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
        pipe = rc.pipeline()
        pipe.delete(ALIVE_KEY)
        if hosts:
            pipe.hset(
                ALIVE_KEY,
                mapping={h["ip"]: json.dumps(r) for h, r in zip(hosts, results)},
            )
        pipe.execute()

        for host, result in zip(hosts, results):
            if str(host.get("monitor")).lower() == "true" and not result["up"]:
                alive_type = (
                    "Port Check" if result["method"] == "port" else "Ping Check"
                )
                name = host.get("host") or host["ip"]
                watcher.send_alert(
                    "Check Alive",
                    alive_type,
                    name,
                    summary="{} ({}) did not respond to {}.".format(
                        name, result["address"], alive_type
                    ),
                    severity="warning",
                )


if __name__ == "__main__":  # pragma: no cover
    check_all_hosts()
