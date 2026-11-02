#!/usr/bin/env python3
"""
Checks hosts alive

Every host with an IP is pinged (or TCP-connected to when it has a
`check_alive_port`) at the address its hostname resolves to, falling back to
its last known IP (lookups are cached and rate-limited, see `resolve_names`),
and the result is recorded in the Redis `alive` hash (IP -> JSON) so maps and
the inventory can show live reachability for anything IP-reachable, not only
hosts with Telegraf metrics.  Monitored hosts that are
down are also sent to Alertmanager, with notification backoff (see watcher.py).
"""
import json
import os
import platform
import queue
import subprocess
import socket
import threading
import time

import redis

import watcher

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

from common.hostnames import same_subnet

ALIVE_KEY = "alive"
DNS_KEY = "alive-dns:"
DNS_CACHE_SECONDS = int(os.environ.get("ALIVE_DNS_CACHE_SECONDS") or 300)
DNS_TIMEOUT_SECONDS = float(os.environ.get("ALIVE_DNS_TIMEOUT_SECONDS") or 10)
DNS_WORKERS = int(os.environ.get("ALIVE_DNS_WORKERS") or 4)


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


def resolve_names(hosts, rc):
    """
    Resolves each host's name to an address, without flooding the resolver
        - Answers, "not found" included, are cached in Redis for DNS_CACHE_SECONDS, so a
          name is looked up a few times an hour instead of every minute
        - Uncached names are looked up once each, DNS_WORKERS at a time, and the whole
          batch gets DNS_TIMEOUT_SECONDS; a name still pending then is checked at its IP
    Returns one address per host, "" where there is none
    """
    names = [str(h.get("host") or "").strip().rstrip(".").lower() for h in hosts]
    wanted = sorted({n for n in names if n and " " not in n})
    if not wanted:
        return [""] * len(hosts)

    found = {
        n: a.decode()
        for n, a in zip(wanted, rc.mget([DNS_KEY + n for n in wanted]))
        if a is not None
    }
    pending = queue.Queue()
    for n in wanted:
        if n not in found:
            pending.put(n)
    resolved = {}

    def work():
        while True:
            try:
                name = pending.get_nowait()
            except queue.Empty:
                return
            try:
                resolved[name] = socket.gethostbyname(name)
            except (OSError, UnicodeError):
                resolved[name] = ""

    # gethostbyname can't be cancelled, so a lookup that outlives the deadline is
    # left to finish in a daemon thread rather than holding the run open
    workers = [
        threading.Thread(target=work, daemon=True)
        for _ in range(min(DNS_WORKERS, pending.qsize()))
    ]
    for t in workers:
        t.start()
    deadline = time.monotonic() + DNS_TIMEOUT_SECONDS
    for t in workers:
        t.join(max(0, deadline - time.monotonic()))

    done = dict(resolved)
    if done:
        pipe = rc.pipeline()
        for n, a in done.items():
            pipe.set(DNS_KEY + n, a, ex=DNS_CACHE_SECONDS)
        pipe.execute()
    found.update(done)
    return [found.get(n, "") for n in names]


def check_host(host, resolved=""):
    """
    Checks one host and returns its alive record
        - `resolved` is the address its hostname resolves to (`resolve_names`), so a DHCP
          host that moved is found at its new IP.  One outside the host's /24 (a
          search-domain or container-name collision) is ignored in favour of the last known IP
        - A `check_alive_port` (stored as text by the UI) means a TCP check instead of ping
        - An unusable port marks only this host down, with the reason, instead of failing every check
    """
    address = resolved if same_subnet(resolved, host["ip"]) else host["ip"]

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
    from serve import list_hosts, db

    with PidFile("labyrinth-alive"):
        hosts = [x for x in json.loads(unwrap(list_hosts)()[0]) if x.get("ip")]

        rc = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
        with ThreadPoolExecutor(32) as pool:
            results = list(pool.map(check_host, hosts, resolve_names(hosts, rc)))

        # Replace the whole hash atomically so removed hosts drop out
        pipe = rc.pipeline()
        pipe.delete(ALIVE_KEY)
        if hosts:
            pipe.hset(
                ALIVE_KEY,
                mapping={h["ip"]: json.dumps(r) for h, r in zip(hosts, results)},
            )
        pipe.execute()

        alerts = []
        for host, result in zip(hosts, results):
            if str(host.get("monitor")).lower() == "true" and not result["up"]:
                alive_type = (
                    "Port Check" if result["method"] == "port" else "Ping Check"
                )
                # Keyed by name so a host that changes IP keeps its backoff state
                name = host.get("host") or host["ip"]
                alerts.append(
                    {
                        "alert_name": "Check Alive",
                        "service": alive_type,
                        "instance": name,
                        "summary": "{} ({}) did not respond to {}.".format(
                            name, result["address"], alive_type
                        ),
                        "severity": "warning",
                    }
                )
        # Runs every minute, so a 5 minute hold rides out a skipped run
        watcher.report_problems(
            rc, "alive", alerts, watcher.backoff_settings(db), hold=300
        )


if __name__ == "__main__":  # pragma: no cover
    check_all_hosts()
