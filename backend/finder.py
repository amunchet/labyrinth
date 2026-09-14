#!/usr/bin/env python3
"""
Auto discovery finder
"""
import time
import json
import os
import queue
import subprocess
import xmltodict
from threading import Thread

import redis

from typing import Dict, List
from nmap import PortScannerYield as ps


from common.single_run import RedisSingleRunLock, LockNotAcquired
from common.test import unwrap
from serve import list_subnet, list_subnets, create_edit_host, list_host, insert_metric


def _int_from_env(name, default):
    """Reads an integer setting from the environment, falling back to `default`"""
    try:
        return int(os.environ.get(name) or default)
    except (TypeError, ValueError):
        print("Invalid value for {} - using {}".format(name, default))
        return default


# Cross-container "only one finder at a time" lock.  RedisSingleRunLock
# heartbeats the TTL for as long as this process is alive, so the TTL only has
# to outlive a crash rather than a full scan.  A plain `ex=` TTL could not:
# it expired out from under a still-running finder, and the next cron tick
# then started a second one on top of it.  Every hour, forever.
GLOBAL_LOCK_KEY = "labyrinth_finder_lock"
GLOBAL_LOCK_TTL_SECONDS = 120
# The subnet lock prevents concurrent scans of the same subnet across instances.
# It is heartbeat-extended like the global lock, so - as above - the TTL only
# has to outlive a crash.  A plain `ex=` TTL had to be guessed longer than the
# slowest imaginable scan, and a scan that outran the guess both lost its lock
# mid-scan and then deleted the *next* scan's lock on its way out.
SUBNET_LOCK_TTL_SECONDS = 120

# Worker threads sharing the subnet queue for a single pass.
SCAN_THREADS = _int_from_env("FINDER_THREADS", 4)

# Scan every port, to catch non-standard services (e.g. MongoDB on 27017).
#
# The bounds are not optional at that width.  A `-p-` connect scan against a
# host that silently drops packets spends the full retry budget on each of
# 65535 ports; without `-T4 --max-retries 2 --host-timeout` a single firewalled
# host holds the pass open for hours, and since cron only starts the next pass
# once this one finishes, the scan interval degrades to a day or worse.
PORT_SCAN_ARGUMENTS = os.environ.get(
    "FINDER_NMAP_ARGUMENTS"
) or "-sT -PU0 -Pn -p- -T4 --max-retries 2 --host-timeout {}".format(
    os.environ.get("FINDER_HOST_TIMEOUT") or "20m"
)

# How long the ping sweep is allowed to take before we give up on the subnet
PING_TIMEOUT_SECONDS = _int_from_env("FINDER_PING_TIMEOUT_SECONDS", 900)

# The per-subnet scan log in Redis is display-only - cap it and let it expire
OUTPUT_MAX_BYTES = _int_from_env("FINDER_OUTPUT_MAX_BYTES", 250000)
OUTPUT_TTL_SECONDS = _int_from_env("FINDER_OUTPUT_TTL_SECONDS", 86400)


def parse_ping_results(ping_output) -> List[str]:
    """
    Pulls the addresses of the live hosts out of an nmap ping sweep.

    Returns an empty list when nothing answered.  nmap omits the `host` key
    entirely in that case, which used to raise `KeyError: 'host'` and cost the
    subnet its whole pass - an empty or fully firewalled subnet is a normal
    result, not an error.
    """
    parsed = xmltodict.parse(ping_output)

    hosts = (parsed.get("nmaprun") or {}).get("host") or []

    ## Exactly one alive host will break the process
    if isinstance(hosts, dict):
        hosts = [hosts]

    arr = []
    for x in hosts:
        address = x.get("address")
        if isinstance(address, dict):
            if "@addr" in address:
                arr.append(address["@addr"])
        elif isinstance(address, list):
            found = [
                item["@addr"]
                for item in address
                if (
                    "@addr" in item
                    and "." in item["@addr"]
                    and ":" not in item["@addr"]
                )
            ]
            if found:
                arr.append(found[0])

    return arr


def scan(subnet: str, callback_fn, verbose=False) -> List:  # pragma: no cover
    """Scans a given subnet"""
    search = subnet
    if len(subnet.split(".")) == 3:
        search += ".0/24"

    # Ping version
    try:
        ping_output = subprocess.check_output(
            ["nmap", "-PE", "-sn", "-T5", "-oX", "-", search],
            timeout=PING_TIMEOUT_SECONDS,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        callback_fn("\nPing sweep failed for {}: {}\n".format(subnet, exc))
        return []

    arr = parse_ping_results(ping_output)

    print(arr)
    callback_fn(" ".join(arr) + "\n\n" + f"Hosts Count:{len(arr)}")

    # nmap errors out when handed an empty target list, and there is nothing to do
    if not arr:
        callback_fn("\nNo live hosts found.\n")
        return []

    scanner = ps()
    results = []

    for line in scanner.scan(hosts=" ".join(arr), arguments=PORT_SCAN_ARGUMENTS):
        if verbose:
            callback_fn(str(line))

        scanstats = ((line[1] or {}).get("nmap") or {}).get("scanstats") or {}
        if scanstats.get("uphosts", "0") != "0":
            callback_fn("\n" + str(line[0]) + ": " + str(scanstats) + "\n")
            callback_fn("*")
            results.append(line[1])
        else:
            callback_fn("*")
    return results


def convert_host(input: Dict) -> Dict:
    """
    Converts host information to Database format
    """
    output = {
        "ip": "",
        "subnet": "",
        "mac": "",
        "group": "",
        "icon": "",
        "monitor": False,
        "services": ["open_ports", "closed_ports", "new_host"],
        "open_ports": [],
        "class": "",
        "host": "",
    }
    if "hostnames" in input and input["hostnames"] and "name" in input["hostnames"][0]:
        output["host"] = input["hostnames"][0]["name"]
    output["ip"] = input["addresses"]["ipv4"]
    if "mac" in input["addresses"]:
        output["mac"] = input["addresses"]["mac"]
    else:
        output["mac"] = input["addresses"]["ipv4"]
    output["subnet"] = ".".join(output["ip"].split(".")[:3])
    if "osmatch" in input and input["osmatch"]:
        print(input["osmatch"])
        output["icon"] = input["osmatch"][0]["name"].split(" ")[0].lower()

    output["group"] = output["icon"]

    if "tcp" in input:
        output["open_ports"] = [int(x) for x in input["tcp"].keys()]

    return output


def process_scan(input: Dict) -> Dict:
    """
    Handles a new scan
    """
    output = {
        "fields": {"ports": [], "ip": ""},
        "name": "open_ports",
        "tags": {"host": "", "mac": "", "ip": "", "name": "open_ports"},
        "timestamp": 0,
    }
    output["fields"]["ip"] = input["addresses"]["ipv4"]
    output["tags"]["ip"] = input["addresses"]["ipv4"]

    if "mac" in input["addresses"]:
        output["tags"]["mac"] = input["addresses"]["mac"]

    if "hostnames" in input and input["hostnames"] and "name" in input["hostnames"][0]:
        output["tags"]["host"] = input["hostnames"][0]["name"]

    if "tcp" in input:
        output["fields"]["ports"] = [int(x) for x in input["tcp"].keys()]
        output["fields"]["vulners"] = {}
        # Vulners
        for port in input["tcp"].keys():
            current_port = input["tcp"][port]
            if "script" in current_port and "vulners" in current_port["script"]:
                output["fields"]["vulners"][str(port)] = (
                    current_port["script"]["vulners"].split("\t")[0].strip()
                )

    output["timestamp"] = time.time()
    return output


def scan_all_subnets(subnets, scan_subnet, num_threads=SCAN_THREADS):
    """Scan every subnet exactly once across a pool of worker threads.

    Returns once the queue is drained.  Deliberately *not* a resident loop:
    cron re-fires finder every minute, so a worker that re-queued its own
    subnet turned each tick into a permanently running process holding a
    database connection pool.  Cron is the scan cadence; this is one pass.
    """
    subnet_queue = queue.Queue()
    for subnet in subnets:
        subnet_queue.put(subnet)

    def worker():
        while True:
            try:
                subnet = subnet_queue.get_nowait()
            except queue.Empty:
                return
            try:
                scan_subnet(subnet)
            except Exception as exc:
                # One unscannable subnet must not strand the rest of the pass.
                print("Error scanning {}: {}".format(subnet, exc))
            finally:
                subnet_queue.task_done()

    threads = [Thread(target=worker) for _ in range(max(1, num_threads))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def main():  # pragma: no cover
    """Runs scan and updates database"""

    rclient = redis.Redis(host=(os.environ.get("REDIS_HOST") or "redis"))

    def update_redis(msg, subnet):
        """
        Appends to the subnet's scan log.

        Called from deep inside the scan, so it must never raise - a blip here
        used to abort the subnet's whole pass.  APPEND also avoids re-writing
        the entire log on every progress tick, and the TTL stops abandoned
        subnets' logs living in Redis forever.
        """
        key = "output-{}".format(subnet)
        try:
            if rclient.strlen(key) > OUTPUT_MAX_BYTES:
                rclient.set(key, "...[truncated]...\n")
            rclient.append(key, str(msg))
            rclient.expire(key, OUTPUT_TTL_SECONDS)
        except Exception as exc:
            print("Unable to write scan output for {}: {}".format(subnet, exc))

    # Redis-based global lock so multiple containers don't duplicate work.
    # wait=0 aborts on contention - the next cron tick retries a minute later,
    # which is cheaper than parking a blocked process on a database pool.
    lock = RedisSingleRunLock(
        rclient,
        GLOBAL_LOCK_KEY,
        ttl=GLOBAL_LOCK_TTL_SECONDS,
        wait=0,
    )
    try:
        lock.acquire()
    except LockNotAcquired:
        print("Another finder instance is already running. Exiting.")
        return

    try:
        # List each subnet
        subnets = json.loads(unwrap(list_subnets)()[0])

        def scan_subnet(subnet):
            """
            Scans a subnet
            """
            # Check do_not_scan flag on the subnet document
            try:
                subnet_data = json.loads(unwrap(list_subnet)(subnet)[0])
                if isinstance(subnet_data, dict) and subnet_data.get(
                    "do_not_scan", False
                ):
                    print(f"Skipping {subnet}: do_not_scan flag is set")
                    return
            except Exception as exc:
                print(f"Could not read subnet data for {subnet}: {exc}")

            # Acquire per-subnet Redis lock to prevent concurrent scans of the
            # same subnet.  wait=0: another instance already has this subnet in
            # hand, so move on to the next one rather than block a worker.
            subnet_lock = RedisSingleRunLock(
                rclient,
                "scan_lock_{}".format(subnet),
                ttl=SUBNET_LOCK_TTL_SECONDS,
                wait=0,
            )
            try:
                subnet_lock.acquire()
            except LockNotAcquired:
                print(f"Subnet {subnet} is already being scanned. Skipping.")
                return

            try:
                rclient.delete("output-{}".format(subnet))
                update_redis("\nStarting {}".format(subnet), subnet)
                results = scan(subnet, lambda x: update_redis(x, subnet))

                # For each host, if it doesn't exist, create it.
                update_redis("\nHosts Check...", subnet)
                for result in results:
                    host = [x for x in result["scan"].values()]
                    if not host:
                        continue
                    host = host[0]

                    try:
                        if "mac" in host["addresses"]:
                            mac = host["addresses"]["mac"]
                        else:
                            mac = host["addresses"]["ipv4"]
                        update_redis("\n" + str(mac), subnet)
                        output = unwrap(list_host)(mac)[0]
                        if output == "null":
                            update_redis("\nCreating new host: {}".format(mac), subnet)
                            unwrap(create_edit_host)(convert_host(host))

                        update_redis("\nInserting metrics...", subnet)
                        metric = unwrap(insert_metric)(
                            {"metrics": [process_scan(host)]}
                        )
                        update_redis("\n" + str(metric), subnet)
                    except Exception as exc:
                        update_redis("\nException occurred: " + str(exc), subnet)

                update_redis("Finished.\n", subnet)
            finally:
                subnet_lock.release()

        scan_all_subnets(subnets, scan_subnet)

    finally:
        # Reachable now.  The old `t.join()`-forever loop meant this cleanup
        # never ran, so the lock was only ever released by TTL expiry.
        lock.release()


if __name__ == "__main__":
    main()
