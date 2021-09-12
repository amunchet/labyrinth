#!/usr/bin/env python3
"""
Auto discovery finder
"""
import time
import json
import os

import redis

from pid import PidFile
from typing import Dict, List
from nmap import PortScannerYield as ps

from common.test import unwrap
from serve import list_subnet, list_subnets, create_edit_host, list_host, insert_metric


def scan(subnet: str, callback_fn, verbose=False) -> List:  # pragma: no cover
    """Scans a given subnet"""
    search = subnet
    if len(subnet.split(".")) == 3:
        search += ".0/24"

    scanner = ps()
    results = []
    for line in scanner.scan(hosts=search, arguments="-sV -O -A --script vulners"):
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
        "monitor" : False,
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
    print(input["osmatch"])
    if input["osmatch"]:
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
        "tags": {
            "host": "",
            "mac": "",
            "ip": "",
        },
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

    def update_redis(msg):
        output = rclient.get("output").decode("utf-8")
        rclient.set("output", output + str(msg))

    with PidFile("labyrinth-finder") as p:
        rclient.set("output", "")

        # List each subnet
        subnets = json.loads(unwrap(list_subnets)()[0])

        for subnet in subnets:
            update_redis("\nStarting {}".format(subnet))
            results = scan(subnet, update_redis)

            # For each host, if it doesn't exist, create it.
            update_redis("\nHosts Check...")
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
                    update_redis("\n" + str(mac))
                    output = unwrap(list_host)(mac)[0]
                    if output == "null":
                        update_redis("\nCreating new host: {}".format(mac))
                        unwrap(create_edit_host)(convert_host(host))

                    update_redis("\nInserting metrics...")
                    metric = unwrap(insert_metric)({"metrics": [process_scan(host)]})
                    update_redis("\n" + str(metric))
                except Exception as exc:
                    update_redis("\nException occurred: " + str(exc))

        update_redis("Finished.\n")


if __name__ == "__main__":
    main()
