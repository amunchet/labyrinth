#!/usr/bin/env python3
"""
Auto discovery finder
"""
import time
import json

import redis

from common.test import unwrap

from pid import PidFile
from typing import Dict, List
from nmap import PortScannerYield as ps

from common.test import unwrap
from serve import list_subnet, list_subnets, create_edit_host, list_host, insert_metric

def scan(subnet: str, callback_fn) -> List: 
    """Scans a given subnet"""
    search = subnet
    if len(subnet.split(".")) == 3:
        search += ".0/24"

    scanner = ps()
    results = []
    for line in scanner.scan(hosts=search, arguments="-sV -O -A --script vulners"):
        if line[1]["nmap"]["scanstats"]["uphosts"] != '0':
            callback_fn("\n" + str(line[0]) + ": " + str(line[1]["nmap"]["scanstats"]) + "\n")
            results.append(line[1])
        else:
            callback_fn(".")
    return results

def convert_host(input: Dict) -> Dict:
    """
    Converts host information to Database format
    """
    output = {
        "ip" : "",
        "subnet" : "",
        "mac" : "",
        "group" : "",
        "icon" : "",
        "services" : ["open_ports", "closed_ports"],
        "open_ports": [],
        "class" : ""
    }
    output["ip"] = input["addresses"]["ipv4"]
    output["mac"] = input["addresses"]["mac"]
    output["subnet"] = ".".join(output["ip"].split(".")[:3])
    print(input["osmatch"])
    if input["osmatch"]:
        output["icon"] = input["osmatch"][0]["name"].split(" ")[0].lower()

    if "tcp" in input:
        output["open_ports"] = [int(x) for x in input["tcp"].keys()]

    return output

def process_scan(input: Dict) -> Dict:
    """
    Handles a new scan
    """
    output = {
        "fields": {
            "ports": [],
            "ip" : ""
        },
        "name" : "open_ports",
        "tags" : {
            "host" : "",
        },
        "timestamp" : 0
    }
    output["fields"]["ip"] = input["addresses"]["ipv4"]
    output["tags"]["host"] = input["addresses"]["mac"]

    if "tcp" in input:
        output["fields"]["ports"] = [int(x) for x in input["tcp"].keys()]
    output["timestamp"] = time.time()
    return output

def main():
    """Runs scan and updates database"""

    rclient = redis.Redis(host="redis")
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
        update_redis("\nStarting check of hosts...")
        for result in results:
            host = [x for x in result["scan"].values()]
            if not host:
                continue
            host = host[0]
            
            try:
                mac = host["addresses"]["mac"]
                update_redis("\n" + str(mac) )
                output = unwrap(list_host)(mac)[0]
                if output == "null":
                    update_redis("\nCreating new host: {}".format(mac))
                    unwrap(create_edit_host)(convert_host(host))

                update_redis("\nInserting metrics...")
                metric = unwrap(insert_metric)({"metrics" : [process_scan(host)]})
                update_redis("\n" + str(metric))
            except Exception as exc:
                update_redis("\nException occurred: " + str(exc))
        
        update_redis("Finished.\n")

if __name__ == "__main__":
    main()