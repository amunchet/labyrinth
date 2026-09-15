#!/usr/bin/env python3
"""
Auto discovery finder
"""
import collections
import time
import json
import os
import signal
import subprocess
import threading
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

# Cap on how many subnets are scanned at the same time.  Every subnet gets
# its own worker, but only this many may be inside nmap at once; the rest
# queue for a slot in the order they asked.  0 removes the cap.
SCAN_THREADS = _int_from_env("FINDER_THREADS", 4)

# Pause between one scan of a subnet finishing and the next one starting.
# The floor cron used to impose between passes; it stops an empty subnet
# spinning its ping sweep back to back.
RESCAN_DELAY_SECONDS = _int_from_env("FINDER_RESCAN_DELAY_SECONDS", 60)

# Pause before retrying a subnet that was skipped (do_not_scan, or another
# finder instance had it locked).
RETRY_DELAY_SECONDS = _int_from_env("FINDER_RETRY_DELAY_SECONDS", 60)

# How often the resident finder re-reads the subnet list, so subnets added
# or removed in the UI start/stop scanning without a restart.
SUBNET_REFRESH_SECONDS = _int_from_env("FINDER_SUBNET_REFRESH_SECONDS", 60)

# The resident finder recycles itself after this long: it hands the global
# lock back so the next cron tick starts a fresh process, then lets its
# in-flight scans finish.  Bounds how long a wedged worker can hold a subnet
# and how long a python-nmap process gets to accumulate state.  0 disables.
MAX_RUNTIME_SECONDS = _int_from_env("FINDER_MAX_RUNTIME_SECONDS", 21600)

# How long a recycling/stopping finder waits for in-flight scans before
# exiting anyway.  Longer than any legitimate scan (the dashboard marks port
# data stale after ~2.8h), so only a genuinely hung worker gets cut off.
SHUTDOWN_GRACE_SECONDS = _int_from_env("FINDER_SHUTDOWN_GRACE_SECONDS", 7200)

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


class ScanSlots:
    """
    FIFO-fair bound on how many subnets scan at once.

    A plain Semaphore would do the bounding, but not the fairness: with more
    subnets than slots, the worker that just finished re-asks immediately and
    could keep winning the race against subnets that have been waiting.  Slots
    are handed out in the order they were requested, so a fast subnet cycles
    through while a slow one holds its slot, and nobody starves.

    `limit <= 0` means unlimited.
    """

    def __init__(self, limit):
        self._unlimited = limit <= 0
        self._free = limit
        self._cond = threading.Condition()
        self._waiting = collections.deque()

    def acquire(self, stop_event):
        """Blocks until a slot is ours.  Returns False if `stop_event` fired first."""
        if self._unlimited:
            return True
        ticket = object()
        with self._cond:
            self._waiting.append(ticket)
            while True:
                # Checked before a free slot is taken, not only while waiting
                # for one: a stop that lands as the slot frees must still win.
                if stop_event.is_set():
                    self._waiting.remove(ticket)
                    self._cond.notify_all()
                    return False
                if self._free > 0 and self._waiting[0] is ticket:
                    break
                self._cond.wait(1.0)
            self._waiting.popleft()
            self._free -= 1
            self._cond.notify_all()
            return True

    def release(self):
        if self._unlimited:
            return
        with self._cond:
            self._free += 1
            self._cond.notify_all()


def scan_subnets(
    list_subnets_fn,
    scan_subnet,
    loop=True,
    stop_event=None,
    num_threads=SCAN_THREADS,
    rescan_delay=RESCAN_DELAY_SECONDS,
    retry_delay=RETRY_DELAY_SECONDS,
    refresh_interval=SUBNET_REFRESH_SECONDS,
    max_runtime=MAX_RUNTIME_SECONDS,
    shutdown_grace=SHUTDOWN_GRACE_SECONDS,
    on_recycle=None,
):
    """
    Scans every subnet on its own worker thread.

    With `loop` set (the cron job) each worker rescans its subnet as soon as
    the previous scan finishes, so a subnet's rescan interval is however long
    *its own* scan takes - a five-minute subnet no longer waits for a
    two-hour subnet before it gets another look.  `list_subnets_fn` is re-read
    every `refresh_interval` seconds: new subnets get a worker, removed ones
    retire after their current scan.  After `max_runtime` seconds (or when
    `stop_event` is set) `on_recycle` is called - main() uses it to hand the
    global lock back so the next cron tick can start a fresh finder straight
    away - and in-flight scans are given `shutdown_grace` seconds to finish.

    With `loop` unset (the `/scan/` endpoint) each subnet is scanned exactly
    once and the call returns when the last one finishes, so it doesn't park
    forever in the backend's thread pool.

    `scan_subnet` returns True if it scanned and False if it skipped (the
    subnet is flagged do_not_scan, or another instance had it locked); a skip
    is retried after `retry_delay` rather than `rescan_delay`.  A raising
    `scan_subnet` only costs that subnet that one scan.
    """
    stop_event = stop_event or threading.Event()
    slots = ScanSlots(num_threads)
    workers = {}

    def worker(subnet, retired):
        while not stop_event.is_set() and not retired.is_set():
            if not slots.acquire(stop_event):
                return
            try:
                scanned = scan_subnet(subnet)
            except Exception as exc:
                # One unscannable subnet must not kill its own worker, let
                # alone anybody else's.
                print("Error scanning {}: {}".format(subnet, exc))
                scanned = False
            finally:
                slots.release()
            if not loop:
                return
            stop_event.wait(rescan_delay if scanned else retry_delay)

    def refresh():
        try:
            wanted = list(list_subnets_fn())
        except Exception as exc:
            print("Could not list subnets: {}".format(exc))
            return
        for subnet in list(workers):
            if subnet not in wanted:
                print("Subnet {} removed - retiring its worker".format(subnet))
                workers.pop(subnet)[1].set()
        for subnet in wanted:
            if subnet in workers:
                continue
            retired = threading.Event()
            # Daemon: a hung worker must not keep a recycled finder alive
            # forever - the whole point of recycling is that it can't.
            thread = Thread(
                target=worker,
                args=(subnet, retired),
                name="finder-{}".format(subnet),
                daemon=True,
            )
            workers[subnet] = (thread, retired)
            thread.start()

    refresh()

    if not loop:
        for thread, _ in list(workers.values()):
            thread.join()
        return

    deadline = time.monotonic() + max_runtime if max_runtime > 0 else None
    while not stop_event.is_set():
        if deadline is not None and time.monotonic() >= deadline:
            print("Finder has run for {}s - recycling".format(max_runtime))
            stop_event.set()
            break
        stop_event.wait(refresh_interval)
        if not stop_event.is_set():
            refresh()

    if on_recycle is not None:
        on_recycle()

    grace_until = time.monotonic() + shutdown_grace
    for thread, _ in list(workers.values()):
        thread.join(max(0.0, grace_until - time.monotonic()))
    stragglers = [name for name, (t, _) in workers.items() if t.is_alive()]
    if stragglers:
        print("Giving up on unfinished scans: {}".format(", ".join(stragglers)))


def main(loop=True, stop_event=None):  # pragma: no cover
    """
    Runs scan and updates database

    With `loop` set the process stays resident and every subnet rescans as
    soon as its previous scan finishes; that is how the cron job runs it, and
    the global lock makes every later cron tick a no-op until this process
    recycles.  `loop=False` scans each subnet once and returns - what the
    `/scan/` endpoint needs so it doesn't permanently occupy a worker in the
    backend's thread pool.
    """

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

        def current_subnets():
            return json.loads(unwrap(list_subnets)()[0])

        def scan_subnet(subnet):
            """
            Scans a subnet.  Returns True if it did, False if it was skipped.
            """
            # Check do_not_scan flag on the subnet document
            try:
                subnet_data = json.loads(unwrap(list_subnet)(subnet)[0])
                if isinstance(subnet_data, dict) and subnet_data.get(
                    "do_not_scan", False
                ):
                    print(f"Skipping {subnet}: do_not_scan flag is set")
                    return False
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
                return False

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
                return True
            finally:
                subnet_lock.release()

        scan_subnets(
            current_subnets,
            scan_subnet,
            loop=loop,
            stop_event=stop_event,
            # Hand the lock back *before* draining: the next cron tick then
            # starts a fresh finder immediately and picks up every subnet
            # this one isn't still inside (the per-subnet locks keep the two
            # apart), so recycling never pauses scanning.
            on_recycle=lock.release,
        )

    finally:
        lock.release()


if __name__ == "__main__":
    stop = threading.Event()
    # A container stop should let in-flight scans finish rather than orphan
    # half-written results; only the main thread may install handlers.
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    main(stop_event=stop)
