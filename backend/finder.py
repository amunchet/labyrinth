#!/usr/bin/env python3
"""
Auto discovery finder
"""
import time
from typing import Dict, List
from nmap import PortScanner as ps

from common.test import unwrap
from serve import list_subnet, list_subnets, create_edit_host 

def scan(subnet: str) -> List: 
    """Scans a given subnet"""
    search = subnet
    if len(subnet.split(".")) == 3:
        search += ".0/24"

    scanner = ps()
    scanner.scan(search)
    return[scanner[host] for host in scanner.all_hosts()]

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
    if input["osmatch"]:
        output["icon"] = input["osmatch"][0]["name"].split(" ")[0].lower()

    if input["tcp"]:
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

    if input["tcp"]:
        output["fields"]["ports"] = [int(x) for x in input["tcp"].keys()]
    output["timestamp"] = time.time()
    return output

def main():
    """Runs scan and updates database"""

    # List each subnet

    # Lists hosts in database with subnet

    # Scan

    # For each host, if it doesn't exist, create
    
    # Insert metric 

if __name__ == "__main__":
    # Main run loop
    pass