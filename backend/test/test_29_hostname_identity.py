#!/usr/bin/env python3
"""Hosts are identified by hostname first, so DHCP hosts keep their record when their IP changes"""
from unittest.mock import MagicMock, patch

import alive
import finder
from common.hostnames import hostnames_match, same_subnet


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


def reconcile(scan, hosts):
    collection = MagicMock()
    created = []
    log = finder.reconcile_hosts(scan, hosts, collection, created.append)
    return collection, created, log


def test_hostnames_match():
    assert hostnames_match("desktop-x.north.example.com", "DESKTOP-X")
    assert hostnames_match("desktop-x.north.example.com.", "desktop-x.north.example.com")
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
    collection, created, _ = reconcile(
        [scanned("192.168.0.216", "balexandria")], hosts
    )
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
        collection,
        lambda h: None,
    )
    assert "Exception occurred for 192.168.10.8: db down" in log
    assert any("192.168.10.9" in line for line in log)


@patch("alive.ping", return_value=True)
@patch("socket.gethostbyname", return_value="192.168.10.98")
def test_alive_checks_the_resolved_address(mock_dns, mock_ping):
    result = alive.check_host(record("192.168.10.11", "laptop"))
    mock_dns.assert_called_once_with("laptop")
    mock_ping.assert_called_once_with("192.168.10.98")
    assert result["up"] and result["address"] == "192.168.10.98"


@patch("alive.ping", return_value=False)
@patch("socket.gethostbyname", return_value="172.18.0.4")
def test_alive_ignores_resolutions_outside_the_subnet(mock_dns, mock_ping):
    """e.g. a host named like a docker service resolving to the container"""
    result = alive.check_host(record("192.168.10.244", "labyrinth"))
    mock_ping.assert_called_once_with("192.168.10.244")
    assert result["address"] == "192.168.10.244"


@patch("alive.check_port", return_value=True)
@patch("socket.gethostbyname", side_effect=OSError("not found"))
def test_alive_falls_back_to_the_ip_when_dns_fails(mock_dns, mock_port):
    alive.check_host(record("192.168.10.11", "laptop", check_alive_port="22"))
    mock_port.assert_called_once_with("192.168.10.11", 22)


@patch("alive.ping", return_value=True)
@patch("socket.gethostbyname")
def test_alive_skips_dns_for_names_that_are_not_hostnames(mock_dns, mock_ping):
    alive.check_host(record("10.8.0.75", "Engraving Mailserver Larger"))
    mock_dns.assert_not_called()
    mock_ping.assert_called_once_with("10.8.0.75")
