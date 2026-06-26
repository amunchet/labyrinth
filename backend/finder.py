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


from common.test import unwrap
from serve import list_subnet, list_subnets, create_edit_host, list_host, insert_metric


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

    arguments = "-sT -PU0 -Pn -p-"  # Scan all ports; removed --top-ports limit to catch non-common ports (e.g. 27017)
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


def main():  # pragma: no cover
    """Runs scan and updates database"""

    rclient = redis.Redis(host=(os.environ.get("REDIS_HOST") or "redis"))

    def update_redis(msg, subnet):
        output = rclient.get("output-{}".format(subnet)).decode("utf-8")
        rclient.set("output-{}".format(subnet), output + str(msg))

    # Use Redis-based distributed lock instead of a file-based PidFile so that
    # multiple containers sharing the same Redis instance cannot start duplicate
    # scanners.  The key expires after 1 hour as a safety net; a background
    # thread refreshes it while the scanner is running.
    global_lock_key = "labyrinth-finder-lock"
    global_lock_expiry = 3600  # seconds

    if not rclient.set(global_lock_key, "1", nx=True, ex=global_lock_expiry):
        print("Finder already running (Redis lock held), skipping")
        return

    def _refresh_global_lock():
        """Refreshes the global Redis lock so it does not expire while running."""
        while True:
            time.sleep(global_lock_expiry // 2)
            rclient.expire(global_lock_key, global_lock_expiry)

    refresh_thread = Thread(target=_refresh_global_lock, daemon=True)
    refresh_thread.start()

    # List each subnet
    subnets = json.loads(unwrap(list_subnets)()[0])

    def scan_subnet(subnet):
        """
        Scans a subnet
        """
        rclient.set("output-{}".format(subnet), "")

        # Check if this subnet has the "do not scan" flag set
        try:
            subnet_result = unwrap(list_subnet)(subnet)
            if subnet_result[1] == 200:
                subnet_info = json.loads(subnet_result[0])
                if subnet_info.get("no_scan", False):
                    update_redis(
                        "\nSubnet {} has 'do not scan' flag set, skipping".format(subnet),
                        subnet,
                    )
                    return
        except Exception as exc:
            update_redis("\nCould not check no_scan flag: " + str(exc), subnet)

        # Per-subnet Redis lock prevents two scanner threads (or two containers)
        # from scanning the same subnet concurrently.
        subnet_lock_key = "scanning-lock-{}".format(subnet)
        if not rclient.set(subnet_lock_key, "1", nx=True, ex=7200):
            update_redis(
                "\nSubnet {} scan already in progress, skipping".format(subnet),
                subnet,
            )
            return

        try:
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
                    metric = unwrap(insert_metric)({"metrics": [process_scan(host)]})
                    update_redis("\n" + str(metric), subnet)
                except Exception as exc:
                    update_redis("\nException occurred: " + str(exc), subnet)

            update_redis("Finished.\n", subnet)
        finally:
            rclient.delete(subnet_lock_key)

    # Set up a queue for subnets
    subnet_queue = queue.Queue()

    # Add all subnets to the queue initially
    for subnet in subnets:
        subnet_queue.put(subnet)

    def worker():
        """Worker thread that scans subnets and continually rescans them."""
        while True:
            # Get a subnet from the queue
            subnet = subnet_queue.get()
            scan_subnet(subnet)
            subnet_queue.task_done()  # Mark this subnet as done
            # Put the subnet back into the queue to scan again
            subnet_queue.put(subnet)

    # Start a thread pool to process subnets concurrently
    num_threads = 4  # You can adjust the number of concurrent threads
    threads = []
    for _ in range(num_threads):
        t = Thread(target=worker)
        t.start()
        threads.append(t)

    # Keep the main thread alive indefinitely
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
