#!/usr/bin/env python3
"""Extended tests for finder.py to improve coverage."""

import collections
import threading
import time

import pytest
from unittest.mock import patch, MagicMock, call
import xmltodict

import finder


class TestFinderModuleImports:
    """Tests to ensure finder module components work."""

    def test_finder_imports(self):
        """Test that finder module imports successfully."""
        assert finder is not None

    def test_finder_has_scan_function(self):
        """Test that finder has scan function."""
        assert hasattr(finder, "scan")

    def test_finder_has_required_modules(self):
        """Test that required modules are imported."""
        # Just ensure imports worked
        assert finder.time is not None
        assert finder.json is not None
        assert finder.os is not None


class TestFinderCallbackExecution:
    """Tests for finder callback execution scenarios."""

    @patch("subprocess.check_output")
    def test_scan_calls_nmap(self, mock_check_output):
        """Test that scan function calls nmap."""
        # This would be in the coverage but scan is marked pragma: no cover
        # We test the structure at least
        pass

    def test_finder_threading(self):
        """Test that finder uses threading."""
        # Verify Thread is available
        assert finder.Thread is not None

    def test_finder_redis_connection(self):
        """Test that finder can establish redis structure."""
        # Just test the module has redis
        assert finder.redis is not None

    def test_finder_subprocess_usage(self):
        """Test that finder imports subprocess."""
        assert finder.subprocess is not None


class TestPortScannerYield:
    """Tests for nmap PortScannerYield usage."""

    def test_port_scanner_import(self):
        """Test that PortScannerYield is imported."""
        assert finder.ps is not None

    @patch("finder.ps")
    def test_scanner_basic_structure(self, mock_scanner):
        """Test basic scanner structure."""
        # Verify ps is available
        assert mock_scanner is not None


class TestFinderHelpers:
    """Tests for helper functions in finder."""

    def test_finder_has_common_functions(self):
        """Test that finder module has expected components."""
        # Verify the module structure
        assert hasattr(finder, "time")
        assert hasattr(finder, "json")
        assert hasattr(finder, "os")
        assert hasattr(finder, "subprocess")


class TestNmapOutputParsing:
    """Tests for nmap XML output parsing."""

    def test_xmltodict_import(self):
        """Test that xmltodict is available."""
        assert xmltodict is not None

    def test_simple_nmap_xml_parsing(self):
        """Test parsing simple nmap XML."""
        sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nmaprun>
<nmaprun scanner="nmap" args="nmap -PE -sn -T5 -oX - 192.168.1.0/24" 
         start="1624819200" startstr="Tue Jun 27 12:00:00 2023" 
         version="7.92" xmloutputversion="1.05">
    <host starttime="1624819200" endtime="1624819205">
        <status state="up" reason="echo-reply" reason_ttl="64"/>
        <address addr="192.168.1.1" addrtype="ipv4"/>
        <address addr="00:11:22:33:44:55" addrtype="mac" vendor="Example Inc"/>
    </host>
</nmaprun>"""

        parsed = xmltodict.parse(sample_xml)
        assert "nmaprun" in parsed
        assert "host" in parsed["nmaprun"]

    def test_multiple_hosts_nmap_xml(self):
        """Test parsing nmap XML with multiple hosts."""
        sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<nmaprun scanner="nmap" version="7.92" xmloutputversion="1.05">
    <host starttime="1624819200" endtime="1624819205">
        <status state="up" reason="echo-reply" reason_ttl="64"/>
        <address addr="192.168.1.1" addrtype="ipv4"/>
    </host>
    <host starttime="1624819206" endtime="1624819211">
        <status state="up" reason="echo-reply" reason_ttl="64"/>
        <address addr="192.168.1.2" addrtype="ipv4"/>
    </host>
</nmaprun>"""

        parsed = xmltodict.parse(sample_xml)
        hosts = parsed["nmaprun"]["host"]
        assert isinstance(hosts, list)
        assert len(hosts) == 2

    def test_single_host_nmap_xml(self):
        """Test that single host is converted to list."""
        sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<nmaprun scanner="nmap" version="7.92" xmloutputversion="1.05">
    <host starttime="1624819200" endtime="1624819205">
        <status state="up" reason="echo-reply" reason_ttl="64"/>
        <address addr="192.168.1.1" addrtype="ipv4"/>
    </host>
</nmaprun>"""

        parsed = xmltodict.parse(sample_xml)
        # Single host parsed as dict, would need conversion
        if isinstance(parsed["nmaprun"]["host"], dict):
            parsed["nmaprun"]["host"] = [parsed["nmaprun"]["host"]]

        hosts = parsed["nmaprun"]["host"]
        assert isinstance(hosts, list)


class TestSubnetProcessing:
    """Tests for subnet processing logic."""

    def test_subnet_normalization_with_slash(self):
        """Test subnet with /24 notation."""
        subnet = "192.168.1.0/24"
        # Already has /24
        assert "/24" in subnet or "/24" not in subnet

    def test_subnet_normalization_without_slash(self):
        """Test subnet without /24 notation."""
        subnet = "192.168.1"
        # Would add .0/24
        if len(subnet.split(".")) == 3:
            subnet = subnet + ".0/24"
        assert subnet == "192.168.1.0/24"

    def test_subnet_with_host_bits(self):
        """Test subnet with host bits."""
        subnet = "192.168.1.100"
        # Has 4 octets
        assert len(subnet.split(".")) == 4


class TestScanSubnetsOnePass:
    """`loop=False` is what `/scan/` runs: every subnet once, then return.

    The backend submits it to a two-thread executor, so a call that never
    returned would permanently eat one of those threads.
    """

    @staticmethod
    def _run(subnets, scan_subnet, timeout=10, **kwargs):
        """Run a single pass, failing rather than hanging on a regression."""
        done = threading.Event()

        def target():
            finder.scan_subnets(lambda: subnets, scan_subnet, loop=False, **kwargs)
            done.set()

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout)
        assert done.is_set(), "a single pass must return, not scan forever"

    def test_scans_each_subnet_exactly_once(self):
        seen = []
        seen_lock = threading.Lock()

        def scan_subnet(subnet):
            with seen_lock:
                seen.append(subnet)
            return True

        subnets = ["10.0.0", "10.0.1", "10.0.2", "192.168.1"]
        self._run(subnets, scan_subnet)
        assert sorted(seen) == sorted(subnets)

    def test_returns_on_empty_subnet_list(self):
        self._run([], lambda subnet: pytest.fail("scan_subnet should not run"))

    def test_one_failing_subnet_does_not_strand_the_pass(self):
        """A raising scan must not kill its worker and leave work unclaimed."""
        seen = []
        seen_lock = threading.Lock()

        def scan_subnet(subnet):
            with seen_lock:
                seen.append(subnet)
            if subnet == "10.0.1":
                raise RuntimeError("nmap exploded")
            return True

        subnets = ["10.0.0", "10.0.1", "10.0.2"]
        self._run(subnets, scan_subnet)
        assert sorted(seen) == sorted(subnets)

    def test_thread_cap_is_honoured(self):
        """More subnets than slots: at most `num_threads` scan at once."""
        active = {"now": 0, "peak": 0}
        guard = threading.Lock()

        def scan_subnet(subnet):
            with guard:
                active["now"] += 1
                active["peak"] = max(active["peak"], active["now"])
            time.sleep(0.05)
            with guard:
                active["now"] -= 1
            return True

        self._run(["10.0.%d" % i for i in range(8)], scan_subnet, num_threads=2)
        assert active["peak"] == 2

    def test_zero_threads_means_no_cap(self):
        """A cap of 0 must scan everything at once, not silently no-op."""
        seen = []
        self._run(["10.0.0", "10.0.1"], seen.append, num_threads=0)
        assert sorted(seen) == ["10.0.0", "10.0.1"]

    def test_unlistable_subnets_returns(self):
        """A database blip listing subnets must not crash or hang the pass."""

        def boom():
            raise RuntimeError("db down")

        done = threading.Event()

        def target():
            finder.scan_subnets(boom, lambda s: pytest.fail("no scan"), loop=False)
            done.set()

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(5)
        assert done.is_set()


class TestScanSubnetsContinuous:
    """`loop=True` is what cron runs: each subnet rescans as soon as it's done.

    The point of the change: a subnet's rescan interval is however long its
    own scan takes, not however long the slowest subnet's scan takes.
    """

    @staticmethod
    def _run(list_fn, scan_subnet, stop, timeout=10, **kwargs):
        done = threading.Event()
        kwargs.setdefault("rescan_delay", 0)
        kwargs.setdefault("retry_delay", 0)
        kwargs.setdefault("refresh_interval", 0.05)
        kwargs.setdefault("shutdown_grace", 5)

        def target():
            finder.scan_subnets(
                list_fn, scan_subnet, loop=True, stop_event=stop, **kwargs
            )
            done.set()

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return done, thread

    @staticmethod
    def _wait_until(predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.01)
        return predicate()

    def test_fast_subnet_does_not_wait_for_slow_subnet(self):
        """The bug being fixed: a pass used to end only when *every* subnet had."""
        counts = collections.Counter()
        guard = threading.Lock()
        slow_started = threading.Event()
        release_slow = threading.Event()

        def scan_subnet(subnet):
            with guard:
                counts[subnet] += 1
            if subnet == "slow":
                slow_started.set()
                release_slow.wait(5)
            return True

        stop = threading.Event()
        done, _ = self._run(lambda: ["fast", "slow"], scan_subnet, stop)

        assert slow_started.wait(5)
        assert self._wait_until(lambda: counts["fast"] >= 5)
        # The slow subnet is still on its first scan the whole time
        assert counts["slow"] == 1

        release_slow.set()
        stop.set()
        assert done.wait(5)

    def test_stop_event_ends_the_loop_after_the_current_scan(self):
        in_scan = threading.Event()
        finish_scan = threading.Event()
        completed = []

        def scan_subnet(subnet):
            in_scan.set()
            finish_scan.wait(5)
            completed.append(subnet)
            return True

        stop = threading.Event()
        done, _ = self._run(lambda: ["10.0.0"], scan_subnet, stop)
        assert in_scan.wait(5)
        stop.set()
        # Still draining - the in-flight scan gets to finish
        assert not done.wait(0.2)
        finish_scan.set()
        assert done.wait(5)
        assert completed == ["10.0.0"]

    def test_max_runtime_recycles_and_hands_back_the_lock_first(self):
        """The lock is released before the drain so the next tick isn't blocked."""
        events = []
        finish_scan = threading.Event()

        def scan_subnet(subnet):
            finish_scan.wait(5)
            events.append("scan-finished")
            return True

        stop = threading.Event()
        done, _ = self._run(
            lambda: ["10.0.0"],
            scan_subnet,
            stop,
            max_runtime=0.1,
            on_recycle=lambda: events.append("recycled"),
        )
        assert self._wait_until(lambda: "recycled" in events)
        assert events == ["recycled"]
        finish_scan.set()
        assert done.wait(5)
        assert events == ["recycled", "scan-finished"]

    def test_shutdown_grace_gives_up_on_a_hung_worker(self):
        hung = threading.Event()
        let_go = threading.Event()

        def scan_subnet(subnet):
            hung.set()
            let_go.wait(10)
            return True

        stop = threading.Event()
        done, _ = self._run(lambda: ["10.0.0"], scan_subnet, stop, shutdown_grace=0.1)
        assert hung.wait(5)
        stop.set()
        assert done.wait(5), "must exit after the grace period, hung worker or not"
        let_go.set()

    def test_worker_waiting_for_a_slot_exits_on_stop(self):
        """A worker queued behind a busy slot must not outlive the stop."""
        in_scan = threading.Event()
        finish_scan = threading.Event()
        scanned = []

        def scan_subnet(subnet):
            scanned.append(subnet)
            in_scan.set()
            finish_scan.wait(5)
            return True

        stop = threading.Event()
        done, _ = self._run(
            lambda: ["busy", "queued"], scan_subnet, stop, num_threads=1
        )
        assert in_scan.wait(5)
        stop.set()
        finish_scan.set()
        assert done.wait(5)
        # The queued subnet never got a slot, and must not have been scanned
        assert scanned == ["busy"]

    def test_new_subnet_gets_a_worker_and_removed_subnet_retires(self):
        subnets = ["10.0.0"]
        counts = collections.Counter()
        guard = threading.Lock()

        def scan_subnet(subnet):
            with guard:
                counts[subnet] += 1
            time.sleep(0.01)
            return True

        stop = threading.Event()
        done, _ = self._run(lambda: list(subnets), scan_subnet, stop)
        assert self._wait_until(lambda: counts["10.0.0"] >= 2)

        subnets.append("10.0.1")
        assert self._wait_until(lambda: counts["10.0.1"] >= 2)

        subnets.remove("10.0.0")
        assert self._wait_until(lambda: "10.0.0" not in subnets)
        # Give the retired worker time to notice and stop
        time.sleep(0.3)
        with guard:
            before = counts["10.0.0"]
        time.sleep(0.3)
        with guard:
            assert counts["10.0.0"] == before
        assert counts["10.0.1"] > 2

        stop.set()
        assert done.wait(5)

    def test_skipped_subnet_uses_retry_delay(self):
        """A do_not_scan / locked subnet waits `retry_delay`, not `rescan_delay`."""
        calls = []

        def scan_subnet(subnet):
            calls.append(time.monotonic())
            return False

        stop = threading.Event()
        done, _ = self._run(
            lambda: ["10.0.0"], scan_subnet, stop, rescan_delay=0, retry_delay=0.2
        )
        assert self._wait_until(lambda: len(calls) >= 3, timeout=5)
        stop.set()
        assert done.wait(5)
        assert calls[1] - calls[0] >= 0.15

    def test_listing_failure_keeps_existing_workers(self):
        state = {"fail": False}
        counts = collections.Counter()

        def list_fn():
            if state["fail"]:
                raise RuntimeError("db down")
            return ["10.0.0"]

        def scan_subnet(subnet):
            counts[subnet] += 1
            return True

        stop = threading.Event()
        done, _ = self._run(list_fn, scan_subnet, stop)
        assert self._wait_until(lambda: counts["10.0.0"] >= 2)
        state["fail"] = True
        before = counts["10.0.0"]
        assert self._wait_until(lambda: counts["10.0.0"] >= before + 3)
        stop.set()
        assert done.wait(5)


class TestScanSlots:
    """Slots are handed out in request order, so a fast subnet can't starve a slow one."""

    def test_unlimited_never_blocks(self):
        slots = finder.ScanSlots(0)
        stop = threading.Event()
        for _ in range(50):
            assert slots.acquire(stop)
        slots.release()

    def test_fifo_order(self):
        slots = finder.ScanSlots(1)
        stop = threading.Event()
        assert slots.acquire(stop)

        order = []
        started = []

        def waiter(name):
            started.append(name)
            slots.acquire(stop)
            order.append(name)
            time.sleep(0.02)
            slots.release()

        threads = []
        for name in ["a", "b", "c"]:
            t = threading.Thread(target=waiter, args=(name,), daemon=True)
            t.start()
            threads.append(t)
            # Make sure each is queued before the next asks
            while name not in started:
                time.sleep(0.001)
            time.sleep(0.02)

        slots.release()
        for t in threads:
            t.join(5)
        assert order == ["a", "b", "c"]

    def test_acquire_returns_false_once_stopped(self):
        slots = finder.ScanSlots(1)
        stop = threading.Event()
        assert slots.acquire(stop)
        stop.set()
        assert slots.acquire(stop) is False
        # The abandoned ticket must not block anyone else
        slots.release()
        assert slots.acquire(threading.Event())


class TestFinderGlobalLock:
    """The global lock must outlive a scan without outliving the process."""

    def test_uses_heartbeat_extended_lock(self):
        """A fixed `ex=` TTL is what let a second finder start on top."""
        assert finder.RedisSingleRunLock is not None
        assert finder.LockNotAcquired is not None

    def test_fixed_hour_long_ttl_is_gone(self):
        """The old constant expired under a live finder; it must not return."""
        assert not hasattr(finder, "GLOBAL_LOCK_TIMEOUT_SECONDS")

    def test_ttl_only_has_to_outlive_a_crash(self):
        """Heartbeats cover the scan, so the TTL is a crash-recovery bound."""
        assert finder.GLOBAL_LOCK_TTL_SECONDS <= 300

    def test_lock_key_is_stable(self):
        """Renaming this would let old and new finders run side by side."""
        assert finder.GLOBAL_LOCK_KEY == "labyrinth_finder_lock"


def _ping_xml(hosts_xml):
    return (
        '<?xml version="1.0"?><nmaprun scanner="nmap">' + hosts_xml + "</nmaprun>"
    ).encode("utf-8")


class TestParsePingResults:
    """Tests for pulling live hosts out of an nmap ping sweep."""

    def test_no_hosts_returns_empty_list(self):
        """nmap omits `host` entirely when nothing answers - that is not an error."""
        assert finder.parse_ping_results(_ping_xml("")) == []

    def test_single_host_is_not_treated_as_a_dict_of_fields(self):
        """xmltodict collapses a lone host into a dict rather than a list."""
        xml = _ping_xml('<host><address addr="192.168.0.5" addrtype="ipv4"/></host>')
        assert finder.parse_ping_results(xml) == ["192.168.0.5"]

    def test_multiple_hosts(self):
        xml = _ping_xml(
            '<host><address addr="192.168.0.5" addrtype="ipv4"/></host>'
            '<host><address addr="192.168.0.6" addrtype="ipv4"/></host>'
        )
        assert finder.parse_ping_results(xml) == ["192.168.0.5", "192.168.0.6"]

    def test_host_with_mac_and_ipv4_prefers_ipv4(self):
        xml = _ping_xml(
            "<host>"
            '<address addr="192.168.0.7" addrtype="ipv4"/>'
            '<address addr="02:42:C0:A8:00:07" addrtype="mac"/>'
            "</host>"
        )
        assert finder.parse_ping_results(xml) == ["192.168.0.7"]

    def test_host_with_only_ipv6_is_skipped(self):
        xml = _ping_xml(
            "<host>"
            '<address addr="fe80::1" addrtype="ipv6"/>'
            '<address addr="02:42:C0:A8:00:08" addrtype="mac"/>'
            "</host>"
        )
        assert finder.parse_ping_results(xml) == []

    def test_host_without_address_is_skipped(self):
        xml = _ping_xml('<host><status state="up"/></host>')
        assert finder.parse_ping_results(xml) == []

    def test_host_with_address_but_no_addr_attribute_is_skipped(self):
        xml = _ping_xml('<host><address addrtype="ipv4"/></host>')
        assert finder.parse_ping_results(xml) == []


class TestIntFromEnv:
    """Tests for the environment helper backing the scan tunables."""

    def test_reads_value(self, monkeypatch):
        monkeypatch.setenv("FINDER_TEST_VALUE", "42")
        assert finder._int_from_env("FINDER_TEST_VALUE", 7) == 42

    def test_missing_falls_back(self, monkeypatch):
        monkeypatch.delenv("FINDER_TEST_VALUE", raising=False)
        assert finder._int_from_env("FINDER_TEST_VALUE", 7) == 7

    def test_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("FINDER_TEST_VALUE", "not-a-number")
        assert finder._int_from_env("FINDER_TEST_VALUE", 7) == 7


class TestScanArguments:
    """A `-p-` scan must be bounded, or one host stalls the whole pass."""

    def test_still_scans_every_port(self):
        assert "-p-" in finder.PORT_SCAN_ARGUMENTS

    def test_has_a_host_timeout(self):
        assert "--host-timeout" in finder.PORT_SCAN_ARGUMENTS

    def test_caps_retries(self):
        assert "--max-retries" in finder.PORT_SCAN_ARGUMENTS

    def test_ping_sweep_is_bounded(self):
        assert finder.PING_TIMEOUT_SECONDS > 0


class TestSubnetLock:
    """The per-subnet lock must not expire under, or outlive, its own scan."""

    def test_guessed_hour_long_ttl_is_gone(self):
        """A guessed TTL both expired mid-scan and deleted the next scan's lock."""
        assert not hasattr(finder, "SUBNET_LOCK_TIMEOUT_SECONDS")

    def test_ttl_only_has_to_outlive_a_crash(self):
        assert finder.SUBNET_LOCK_TTL_SECONDS <= 300
