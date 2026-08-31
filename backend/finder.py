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

# Cross-container "only one finder at a time" lock.  RedisSingleRunLock
# heartbeats the TTL for as long as this process is alive, so the TTL only has
# to outlive a crash rather than a full scan.  A plain `ex=` TTL could not:
# it expired out from under a still-running finder, and the next cron tick
# then started a second one on top of it.  Every hour, forever.
GLOBAL_LOCK_KEY = "labyrinth_finder_lock"
GLOBAL_LOCK_TTL_SECONDS = 120
# The subnet lock prevents concurrent scans of the same subnet across instances.
# Set longer than a typical full-port scan to handle slow hosts.
SUBNET_LOCK_TIMEOUT_SECONDS = 7200

# Worker threads sharing the subnet queue for a single pass.
SCAN_THREADS = 4


def scan(subnet: str, callback_fn, verbose=False) -> List:  # pragma: no cover
    """Scans a given subnet"""
    search = subnet
    if len(subnet.split(".")) == 3:
        search += ".0/24"

    # Ping version
    ping_output = subprocess.check_output(
        ["nmap", "-PE", "-sn", "-T5", "-oX", "-", search]
    )
    parsed = xmltodict.parse(ping_output)

    ## Exactly one alive host will break the process
    if type(parsed["nmaprun"]["host"]) == type({}):
        parsed["nmaprun"]["host"] = [parsed["nmaprun"]["host"]]

    arr = []
    for x in parsed["nmaprun"]["host"]:
        if "address" in x and "@addr" in x["address"]:
            arr.append(x["address"]["@addr"])
        elif type(x["address"]) is list:
            found = [
                item["@addr"]
                for item in x["address"]
                if (
                    "@addr" in item
                    and "." in item["@addr"]
                    and ":" not in item["@addr"]
                )
            ]
            if found:
                arr.append(found[0])

    print(arr)
    search = " ".join(arr)

    scanner = ps()
    results = []

    arguments = "-sT -PU0 -Pn -p-"  # Scan all ports to catch non-standard services (e.g. MongoDB on 27017)
    callback_fn(search + "\n\n" + f"Hosts Count:{len(arr)}")

    for line in scanner.scan(hosts=search, arguments=arguments):
        if verbose:
            callback_fn(str(line))
        if line[1]["nmap"]["scanstats"]["uphosts"] != "0":
            callback_fn(
                "\n" + str(line[0]) + ": " + str(line[1]["nmap"]["scanstats"]) + "\n"
            )
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
        output = rclient.get("output-{}".format(subnet)).decode("utf-8")
        rclient.set("output-{}".format(subnet), output + str(msg))

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

            # Acquire per-subnet Redis lock to prevent concurrent scans of the same subnet
            subnet_lock_key = "scan_lock_{}".format(subnet)
            subnet_lock = rclient.set(
                subnet_lock_key, "1", nx=True, ex=SUBNET_LOCK_TIMEOUT_SECONDS
            )
            if not subnet_lock:
                print(f"Subnet {subnet} is already being scanned. Skipping.")
                return

            try:
                rclient.set("output-{}".format(subnet), "")
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
                rclient.delete(subnet_lock_key)

        scan_all_subnets(subnets, scan_subnet)

    finally:
        # Reachable now.  The old `t.join()`-forever loop meant this cleanup
        # never ran, so the lock was only ever released by TTL expiry.
        lock.release()


if __name__ == "__main__":
    main()
