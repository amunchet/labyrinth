#!/usr/bin/env python3
"""Hosts are identified by hostname first, so DHCP hosts keep their record when their IP changes"""
import json
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

import alive
import finder
import serve
from common.hostnames import hostnames_match, same_subnet
from common.test import unwrap


def scanned(ip, name="", mac=""):
    """An nmap result for one host"""
    addresses = {"ipv4": ip}
    if mac:
        addresses["mac"] = mac
    return {
        "addresses": addresses,
        "hostnames": [{"name": name, "type": "PTR"}] if name else [],
    }


def record(ip, name="", **extra):
    """A host record as the finder keys it - by IP when nmap saw no MAC"""
    host = {
        "mac": ip,
        "ip": ip,
        "host": name,
        "subnet": ".".join(ip.split(".")[:3]),
        "monitor": False,
        "services": ["open_ports", "closed_ports"],
    }
    host.update(extra)
    return host


def reconcile(scan, hosts, boards=()):
    database = {"hosts": MagicMock(), "dashboards": MagicMock()}
    database["dashboards"].find.return_value = list(boards)
    created = []
    log = finder.reconcile_hosts(scan, hosts, database, created.append)
    return database["hosts"], created, log


def test_hostnames_match():
    assert hostnames_match("desktop-x.north.example.com", "DESKTOP-X")
    assert hostnames_match(
        "desktop-x.north.example.com.", "desktop-x.north.example.com"
    )
    assert not hostnames_match("pollux.north.example.com", "pollux.south.example.com")
    assert not hostnames_match("", "")
    assert not hostnames_match("desktop-x", None)


def test_same_subnet():
    assert same_subnet("192.168.10.5", "192.168.10.200")
    assert not same_subnet("192.168.10.5", "192.168.11.5")
    assert not same_subnet("", "192.168.10.5")


def test_moved_host_keeps_its_record():
    """The most common case: a DHCP client comes back on a new lease"""
    hosts = [record("192.168.10.11", "laptop.north.example.com", monitor=True)]
    collection, created, _ = reconcile(
        [scanned("192.168.10.98", "laptop.north.example.com")], hosts
    )
    assert created == []
    collection.update_one.assert_called_once_with(
        {"mac": "192.168.10.11"}, {"$set": {"ip": "192.168.10.98"}}
    )
    assert hosts[0]["ip"] == "192.168.10.98"


def test_hand_named_host_follows_its_dns_name():
    """People type short names; reverse DNS gives the FQDN"""
    hosts = [record("192.168.0.16", "uap-ac-m")]
    collection, created, _ = reconcile(
        [scanned("192.168.0.40", "UAP-AC-M.south.example.com")], hosts
    )
    assert created == []
    assert hosts[0]["ip"] == "192.168.0.40"
    assert hosts[0]["host"] == "uap-ac-m"


def test_new_device_on_a_moved_hosts_old_ip_gets_its_own_key():
    """The old IP is still the moved host's key - creating by IP must not replace it"""
    hosts = [record("192.168.10.11", "laptop")]
    _, created, _ = reconcile(
        [scanned("192.168.10.98", "laptop"), scanned("192.168.10.11", "phone")], hosts
    )
    assert len(created) == 1
    assert created[0]["ip"] == "192.168.10.11"
    assert created[0]["host"] == "phone"
    assert created[0]["mac"].startswith("device-")


def test_name_is_not_matched_across_subnets():
    """Same-named hosts on different subnets are different machines (or NICs)"""
    hosts = [record("192.168.10.243", "balexandria")]
    collection, created, _ = reconcile([scanned("192.168.0.216", "balexandria")], hosts)
    assert hosts[0]["ip"] == "192.168.10.243"
    assert created[0]["ip"] == "192.168.0.216"
    collection.update_one.assert_not_called()


def test_name_at_several_ips_falls_back_to_ip():
    """Stale PTR records or multi-homed hosts must not flap a record between IPs"""
    hosts = [record("192.168.10.11", "desktop"), record("192.168.10.142")]
    collection, created, _ = reconcile(
        [scanned("192.168.10.11", "desktop"), scanned("192.168.10.142", "desktop")],
        hosts,
    )
    assert created == []
    collection.update_one.assert_not_called()
    collection.delete_one.assert_not_called()
    assert [h["ip"] for h in hosts] == ["192.168.10.11", "192.168.10.142"]
    assert hosts[1]["host"] == ""


def test_real_mac_is_matched_after_hostname():
    hosts = [record("192.168.10.5", mac="AA:BB:CC:DD:EE:FF")]
    collection, created, _ = reconcile(
        [scanned("192.168.11.9", mac="AA:BB:CC:DD:EE:FF")], hosts
    )
    assert created == []
    collection.update_one.assert_called_once_with(
        {"mac": "AA:BB:CC:DD:EE:FF"},
        {"$set": {"ip": "192.168.11.9", "subnet": "192.168.11"}},
    )


def test_unnamed_host_learns_its_name():
    """So it can be followed by name once its lease changes"""
    hosts = [record("192.168.10.7")]
    collection, created, _ = reconcile([scanned("192.168.10.7", "printer")], hosts)
    assert created == []
    collection.update_one.assert_called_once_with(
        {"mac": "192.168.10.7"}, {"$set": {"host": "printer"}}
    )


def test_unchanged_host_is_left_alone():
    hosts = [record("192.168.10.7", "printer")]
    collection, created, log = reconcile([scanned("192.168.10.7", "printer")], hosts)
    assert created == [] and log == []
    collection.update_one.assert_not_called()


def test_duplicates_merge_into_the_monitored_record():
    hosts = [
        record("192.168.10.11", "desktop"),
        record("192.168.10.142", "desktop.north.example.com", notes="Front desk"),
        record(
            "192.168.10.98",
            "desktop",
            monitor=True,
            services=["open_ports", "closed_ports", "cpu"],
        ),
        # left behind before DNS knew the name
        record("192.168.10.157", services=["open_ports", "new_host"]),
        record("192.168.10.157", "", monitor=True, mac="192.168.10.157-kept"),
        record("192.168.10.60", "west-bay-switch"),
    ]
    hosts[0]["services"].append("disk")
    collection, created, log = reconcile(
        [scanned("192.168.10.157", "desktop.north.example.com")], hosts
    )

    deleted = sorted(c.args[0]["mac"] for c in collection.delete_one.call_args_list)
    assert deleted == ["192.168.10.11", "192.168.10.142", "192.168.10.157"]
    assert [h["mac"] for h in hosts] == [
        "192.168.10.98",
        "192.168.10.157-kept",
        "192.168.10.60",
    ]

    kept = hosts[0]
    assert kept["ip"] == "192.168.10.157"
    assert kept["monitor"] is True
    assert kept["notes"] == "Front desk"
    assert kept["services"] == ["open_ports", "closed_ports", "cpu", "disk"]
    filter_, update = collection.update_one.call_args_list[0].args
    assert filter_ == {"mac": "192.168.10.98"}
    assert update["$set"]["notes"] == "Front desk"
    assert created == []
    assert log[0].startswith("Merged")


def test_scanner_copy_of_a_moved_monitored_host_is_folded_in():
    """
    Production's pattern: a monitored host was moved to a new IP by hand and the
    scanner then created an unreviewed record there under the PTR name
    """
    hosts = [
        record("192.168.10.244", "labyrinth", monitor=True, mac="192.168.10.74"),
        record(
            "192.168.10.244",
            "network.north.example.com",
            services=["open_ports", "closed_ports", "new_host"],
        ),
        record("192.168.10.50", "printer"),
    ]
    collection, created, _ = reconcile(
        [
            scanned("192.168.10.244", "network.north.example.com"),
            scanned("192.168.10.50", "scanner"),
        ],
        hosts,
    )
    collection.delete_one.assert_called_once_with({"mac": "192.168.10.244"})
    assert [h["mac"] for h in hosts] == ["192.168.10.74", "192.168.10.50"]
    assert hosts[0]["host"] == "labyrinth"
    assert "new_host" not in hosts[0]["services"]
    assert hosts[1]["host"] == "printer"  # configured, so never renamed or merged
    assert created == []


def test_one_bad_host_does_not_stop_the_rest():
    hosts = [record("192.168.10.7", "printer")]
    collection = MagicMock()
    collection.update_one.side_effect = [RuntimeError("db down"), None]
    log = finder.reconcile_hosts(
        [scanned("192.168.10.8", "printer"), scanned("192.168.10.9", "scanner")],
        hosts,
        {"hosts": collection, "dashboards": MagicMock()},
        lambda h: None,
    )
    assert "Exception occurred for 192.168.10.8: db down" in log
    assert any("192.168.10.9" in line for line in log)


def test_merge_moves_uplinks_and_map_placements_to_the_kept_record():
    hosts = [
        record("192.168.10.98", "desktop", monitor=True),
        record("192.168.10.11", "desktop", uplink="192.168.10.98"),
        record("192.168.10.60", "switch", uplink="192.168.10.11", link_type="copper"),
    ]
    boards = [
        {"_id": "a", "placements": [{"key": "192.168.10.11", "x": 10, "y": 20}]},
        # both copies placed: the merged-away one's spot is dropped
        {
            "_id": "b",
            "placements": [
                {"key": "192.168.10.98", "x": 1, "y": 1},
                {"key": "192.168.10.11", "x": 2, "y": 2},
            ],
        },
        {"_id": "c", "placements": [{"key": "192.168.10.60", "x": 5, "y": 5}]},
    ]
    database = {"hosts": MagicMock(), "dashboards": MagicMock()}
    database["dashboards"].find.return_value = boards
    finder.reconcile_hosts(
        [scanned("192.168.10.98", "desktop")], hosts, database, lambda h: None
    )

    kept_update = database["hosts"].update_one.call_args_list[0].args
    assert kept_update[0] == {"mac": "192.168.10.98"}
    assert kept_update[1]["$unset"] == {"uplink": "", "link_type": ""}
    assert "uplink" not in kept_update[1]["$set"]
    database["hosts"].update_one.assert_any_call(
        {"mac": "192.168.10.60"}, {"$set": {"uplink": "192.168.10.98"}}
    )
    assert hosts[1]["uplink"] == "192.168.10.98"
    assert database["dashboards"].update_one.call_args_list == [
        (
            (
                {"_id": "a"},
                {"$set": {"placements": [{"key": "192.168.10.98", "x": 10, "y": 20}]}},
            ),
        ),
        (
            (
                {"_id": "b"},
                {"$set": {"placements": [{"key": "192.168.10.98", "x": 1, "y": 1}]}},
            ),
        ),
    ]


@pytest.fixture
def labyrinth_db():
    db = serve.db["labyrinth"]
    tearDown = lambda: [
        db[c].delete_many({})
        for c in ("hosts", "subnets", "services", "metrics-latest")
    ]
    tearDown()
    yield db
    tearDown()


def test_moved_agent_metrics_stay_with_their_record(labyrinth_db, monkeypatch):
    """
    A Telegraf agent's config bakes in the IP it had then.  After its host moves,
    a new device at the old IP must not be judged on the moved host's metrics
    """
    monkeypatch.setattr(serve.mc, "judge", lambda metric, service: True)
    labyrinth_db["services"].insert_one(
        {"name": "cpu", "display_name": "cpu", "type": "check"}
    )
    for mac, ip in (("10.0.0.5", "10.0.0.9"), ("device-new", "10.0.0.5")):
        assert (
            unwrap(serve.create_edit_host)(
                {
                    "mac": mac,
                    "ip": ip,
                    "subnet": "10.0.0",
                    "group": "servers",
                    "host": "",
                    "services": ["cpu"],
                }
            )[1]
            == 200
        )
    labyrinth_db["metrics-latest"].insert_one(
        {
            "name": "cpu",
            "tags": {"mac": "10.0.0.5", "ip": "10.0.0.5", "name": "cpu"},
            "fields": {"usage_idle": 90},
            "timestamp": time.time(),
        }
    )

    [subnet] = json.loads(unwrap(serve.dashboard)()[0])
    found = {
        h["mac"]: h["services"][0]["latest_metric"]
        for g in subnet["groups"]
        for h in g["hosts"]
    }
    assert found["10.0.0.5"]["tags"]["mac"] == "10.0.0.5"
    assert found["device-new"] is None


def test_alive_checks_the_resolved_address():
    with patch("alive.ping", return_value=True) as mock_ping:
        result = alive.check_host(record("192.168.10.11", "laptop"), "192.168.10.98")
    mock_ping.assert_called_once_with("192.168.10.98")
    assert result["up"] and result["address"] == "192.168.10.98"


@patch("alive.ping", return_value=False)
def test_alive_ignores_resolutions_outside_the_subnet(mock_ping):
    """e.g. a host named like a docker service resolving to the container"""
    result = alive.check_host(record("192.168.10.244", "labyrinth"), "172.18.0.4")
    mock_ping.assert_called_once_with("192.168.10.244")
    assert result["address"] == "192.168.10.244"


@patch("alive.check_port", return_value=True)
def test_alive_falls_back_to_the_ip_when_dns_fails(mock_port):
    alive.check_host(record("192.168.10.11", "laptop", check_alive_port="22"), "")
    mock_port.assert_called_once_with("192.168.10.11", 22)


class FakeRedis:
    def __init__(self, cached=None):
        self.data = dict(cached or {})
        self.ttl = {}

    def mget(self, keys):
        return [self.data[k].encode() if k in self.data else None for k in keys]

    def pipeline(self):
        return self

    def set(self, key, value, ex=None):
        self.data[key] = value
        self.ttl[key] = ex

    def execute(self):
        pass


def test_resolve_names_looks_each_name_up_once_and_caches_it():
    hosts = [
        record("192.168.10.11", "laptop"),
        record("192.168.10.12", "LAPTOP."),
        record("192.168.10.13", "gone"),
        record("10.8.0.75", "Engraving Mailserver Larger"),
        record("192.168.10.14"),
    ]
    rc = FakeRedis()
    answers = {"laptop": "192.168.10.98"}

    def lookup(name):
        if name not in answers:
            raise OSError("not found")
        return answers[name]

    with patch("socket.gethostbyname", side_effect=lookup) as mock_dns:
        assert alive.resolve_names(hosts, rc) == [
            "192.168.10.98",
            "192.168.10.98",
            "",
            "",
            "",
        ]
    assert sorted(c.args[0] for c in mock_dns.call_args_list) == ["gone", "laptop"]
    # "not found" is cached too, so a dead name isn't asked about every minute
    assert rc.data == {"alive-dns:laptop": "192.168.10.98", "alive-dns:gone": ""}
    assert set(rc.ttl.values()) == {alive.DNS_CACHE_SECONDS}

    with patch("socket.gethostbyname") as mock_dns:
        assert alive.resolve_names(hosts, rc)[0] == "192.168.10.98"
    mock_dns.assert_not_called()


def test_resolve_names_bounds_concurrency_and_time(monkeypatch):
    """A slow resolver costs one bounded wait, not a thread per host or a stuck run"""
    monkeypatch.setattr(alive, "DNS_WORKERS", 2)
    monkeypatch.setattr(alive, "DNS_TIMEOUT_SECONDS", 0.3)
    active, peak, release = [0], [0], threading.Event()
    lock = threading.Lock()

    def slow(name):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        if name == "stuck":
            release.wait(5)
        else:
            time.sleep(0.05)
        with lock:
            active[0] -= 1
        return "192.168.10.50"

    hosts = [record("192.168.10.{}".format(i), "host{}".format(i)) for i in range(6)]
    hosts.append(record("192.168.10.99", "stuck"))
    rc = FakeRedis()
    started = time.monotonic()
    with patch("socket.gethostbyname", side_effect=slow):
        result = alive.resolve_names(hosts, rc)
    release.set()

    assert time.monotonic() - started < 1
    assert peak[0] <= 2
    assert result[-1] == ""
    assert "alive-dns:stuck" not in rc.data  # retried next run, not cached as missing
