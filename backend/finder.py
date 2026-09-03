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
from threading import Event, Thread

import redis

from pid import PidFile
from typing import Dict, List
from nmap import PortScannerYield as ps


from common.test import unwrap
from serve import list_subnet, list_subnets, create_edit_host, list_host, insert_metric


def _int_from_env(name, default):
    """Reads an integer setting from the environment, falling back to `default`"""
    try:
        return int(os.environ.get(name) or default)
    except (TypeError, ValueError):
        print("Invalid value for {} - using {}".format(name, default))
        return default


# Removed vulners, since security scanning will be done externally.
# `--host-timeout`/`--max-retries` matter a great deal here: without them a single
# firewalled host can hold a connect scan of 2500 ports open for hours, which is
# what turns a scan cycle that should take minutes into one that takes a day.
PORT_SCAN_ARGUMENTS = (
    os.environ.get("FINDER_NMAP_ARGUMENTS")
    or "-sT -PU0 -Pn --top-ports 2500 -T4 --max-retries 2 --host-timeout 15m"
)

# How long the ping sweep is allowed to take before we give up on the subnet
PING_TIMEOUT_SECONDS = _int_from_env("FINDER_PING_TIMEOUT_SECONDS", 900)

# Minimum spacing between two scans of the same subnet
RESCAN_DELAY_SECONDS = _int_from_env("FINDER_RESCAN_DELAY_SECONDS", 900)

# Hard cap on the lifetime of the finder process.  Cron restarts it every minute,
# so exiting here is how a wedged scan heals itself.  Set to 0 to disable.
MAX_RUNTIME_SECONDS = _int_from_env("FINDER_MAX_RUNTIME_SECONDS", 21600)

SCAN_THREADS = _int_from_env("FINDER_THREADS", 4)

# The per-subnet scan log in Redis is display-only - cap it and let it expire
OUTPUT_MAX_BYTES = _int_from_env("FINDER_OUTPUT_MAX_BYTES", 250000)
OUTPUT_TTL_SECONDS = _int_from_env("FINDER_OUTPUT_TTL_SECONDS", 86400)

# Grace period given to in-flight scans when the process is shutting down
SHUTDOWN_GRACE_SECONDS = _int_from_env("FINDER_SHUTDOWN_GRACE_SECONDS", 30)


def parse_ping_results(ping_output) -> List[str]:
    """
    Pulls the addresses of the live hosts out of an nmap ping sweep.

    Returns an empty list when nothing answered - nmap omits the `host` key
    entirely in that case, and asking it to scan an empty target list is an error.
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
    callback_fn(search + "\n\n" + f"Hosts Count:{len(arr)}")

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


def record_results(results: List, update_redis) -> None:  # pragma: no cover
    """
    Writes the hosts found by a scan back to the database

    Each host is handled independently - one bad host must not cost us the rest
    of the subnet's results.
    """
    for result in results:
        host = [x for x in (result or {}).get("scan", {}).values()]
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


def main(loop=True):  # pragma: no cover
    """
    Runs scan and updates database

    With `loop` set the process stays alive and continually rescans every subnet;
    that is how the cron job runs it.  `loop=False` makes a single pass and
    returns, which is what the `/scan/` endpoint needs so it doesn't permanently
    occupy a worker in the backend's thread pool.
    """

    rclient = redis.Redis(host=(os.environ.get("REDIS_HOST") or "redis"))

    def update_redis(msg, subnet):
        """
        Appends to the subnet's scan log.

        This is called from deep inside the scan, so it must never raise - a
        failure here used to kill the worker thread and strand the subnet.
        """
        key = "output-{}".format(subnet)
        try:
            if rclient.strlen(key) > OUTPUT_MAX_BYTES:
                rclient.set(key, "...[truncated]...\n")
            rclient.append(key, str(msg))
            rclient.expire(key, OUTPUT_TTL_SECONDS)
        except Exception as exc:
            print("Unable to write scan output for {}: {}".format(subnet, exc))

    def reset_redis(subnet):
        try:
            rclient.delete("output-{}".format(subnet))
        except Exception as exc:
            print("Unable to reset scan output for {}: {}".format(subnet, exc))

    with PidFile("labyrinth-finder") as p:
        # List each subnet
        subnets = json.loads(unwrap(list_subnets)()[0])

        if not subnets:
            print("No subnets configured - nothing to scan.")
            return

        def scan_subnet(subnet):
            """
            Scans a subnet
            """
            reset_redis(subnet)
            update_redis("\nStarting {}".format(subnet), subnet)
            results = scan(subnet, lambda x: update_redis(x, subnet))

            # For each host, if it doesn't exist, create it.
            update_redis("\nHosts Check...", subnet)
            record_results(results, lambda msg: update_redis(msg, subnet))

            update_redis("Finished.\n", subnet)

        # Set up a queue for subnets
        subnet_queue = queue.Queue()
        stop_event = Event()

        # Add all subnets to the queue initially
        for subnet in subnets:
            subnet_queue.put(subnet)

        def worker():
            """Worker thread that scans subnets and continually rescans them."""
            while not stop_event.is_set():
                try:
                    subnet = subnet_queue.get(timeout=1)
                except queue.Empty:
                    if loop:
                        continue
                    return

                started = time.time()
                try:
                    scan_subnet(subnet)
                except Exception as exc:
                    # A worker that dies takes its subnet with it - the subnet is
                    # never requeued, and once every subnet has been lost this way
                    # the remaining workers block on an empty queue forever while
                    # still holding the pid file, so cron can never restart us.
                    print("Scan of {} failed: {}".format(subnet, exc))
                    update_redis("\nScan failed: {}\n".format(exc), subnet)
                finally:
                    subnet_queue.task_done()
                    if loop and not stop_event.is_set():
                        # Space rescans out, then hand the subnet back for the next pass
                        remaining = RESCAN_DELAY_SECONDS - (time.time() - started)
                        if remaining > 0:
                            stop_event.wait(remaining)
                        subnet_queue.put(subnet)

        # Start a thread pool to process subnets concurrently
        num_threads = max(1, min(SCAN_THREADS, len(subnets)))
        threads = []
        for _ in range(num_threads):
            t = Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        deadline = None
        if loop and MAX_RUNTIME_SECONDS > 0:
            deadline = time.time() + MAX_RUNTIME_SECONDS

        try:
            while any(t.is_alive() for t in threads):
                if deadline and time.time() >= deadline:
                    print("Finder reached its maximum runtime - exiting for a restart.")
                    break
                time.sleep(1)
        finally:
            stop_event.set()
            for t in threads:
                t.join(timeout=SHUTDOWN_GRACE_SECONDS)


if __name__ == "__main__":
    main()
