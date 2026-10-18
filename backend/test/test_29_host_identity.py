#!/usr/bin/env python3
"""
Host identity across DHCP address changes
    - Hostname normalisation and matching rules
    - The finder's reconcile step: MAC, then reverse-DNS hostname, then IP
    - Hosts saved without a MAC never get an address as their key
"""
import json
import time

import pytest

import finder
import host_identity
import serve

from common.test import unwrap


class _Labyrinth:
    """Looks collections up per use: test_27 closes the shared client's pool"""

    def __getitem__(self, name):
        return serve.db["labyrinth"][name]


db = _Labyrinth()


def tearDown():
    for collection in ["hosts", "subnets", "dashboards", "metrics"]:
        db[collection].delete_many({})


@pytest.fixture
def setup():
    tearDown()
    yield "Setting up"
    tearDown()


def scan_result(ip, name="", mac=""):
    """One host as nmap's scanner reports it"""
    result = {"addresses": {"ipv4": ip}, "hostnames": [], "tcp": {22: {}}}
    if mac:
        result["addresses"]["mac"] = mac
    if name:
        result["hostnames"] = [{"name": name, "type": "PTR"}]
    return result


def reconcile_all(*results):
    """Runs one subnet scan's worth of results through the finder's reconcile"""
    known = list(db["hosts"].find({}))
    ambiguous = host_identity.ambiguous_hostnames(results)
    return [
        host_identity.reconcile(
            serve.db,
            known,
            result,
            finder.convert_host,
            unwrap(serve.create_edit_host),
            ambiguous,
        )
        for result in results
    ]


def all_hosts():
    return list(db["hosts"].find({}))


def test_normalize_hostname():
    assert host_identity.normalize_hostname("NAS.lan.", "10.0.0.5") == "nas.lan"
    assert host_identity.normalize_hostname("", "10.0.0.5") == ""
    assert host_identity.normalize_hostname("Main NAS", "10.0.0.5") == ""
    # Names made from the address move with the address, not the device
    for name in [
        "10-0-0-5.lan",
        "ip-10-0-0-5.ec2.internal",
        "5.0.0.10.in-addr.arpa",
        "host10.0.0.5",
    ]:
        assert host_identity.normalize_hostname(name, "10.0.0.5") == "", name
    assert host_identity.normalize_hostname("printer5", "10.0.0.5") == "printer5"
    assert host_identity.normalize_hostname("10-0-0-5.lan", "") == "10-0-0-5.lan"


def test_same_hostname():
    assert host_identity.same_hostname("nas", "nas.lan")
    assert host_identity.same_hostname("nas.lan", "nas")
    assert host_identity.same_hostname("nas.lan", "nas.lan")
    assert not host_identity.same_hostname("nas.north.lan", "nas.south.lan")
    assert not host_identity.same_hostname("nas", "")
    assert not host_identity.same_hostname("nas", "nas2")


def test_is_real_mac():
    assert host_identity.is_real_mac("02:42:C0:A8:00:02")
    assert host_identity.is_real_mac("02-42-c0-a8-00-02")
    assert not host_identity.is_real_mac("10.0.0.5")
    assert not host_identity.is_real_mac("device-1a2b3c")
    assert not host_identity.is_real_mac("")
    assert not host_identity.is_real_mac(None)


def test_ambiguous_hostnames():
    results = [
        scan_result("10.0.0.5", "android"),
        scan_result("10.0.0.6", "Android."),
        scan_result("10.0.0.7", "nas"),
        scan_result("10.0.0.8"),
    ]
    assert host_identity.ambiguous_hostnames(results) == {"android"}


def test_new_device_without_mac_is_not_keyed_by_ip(setup):
    notes = reconcile_all(scan_result("10.0.0.5", "nas.lan"))
    hosts = all_hosts()
    assert len(hosts) == 1
    assert hosts[0]["mac"].startswith("device-")
    assert hosts[0]["ip"] == "10.0.0.5"
    assert hosts[0]["subnet"] == "10.0.0"
    assert hosts[0]["host"] == "nas.lan"
    assert hosts[0]["resolved_hostname"] == "nas.lan"
    assert hosts[0]["last_seen"]
    assert "Creating new host" in notes[0]

    # Seen again at the same address: the same host, nothing new
    assert reconcile_all(scan_result("10.0.0.5", "nas.lan")) == [""]
    assert len(all_hosts()) == 1


def test_new_device_with_mac_is_keyed_by_mac(setup):
    reconcile_all(scan_result("10.0.0.5", mac="02:42:C0:A8:00:02"))
    assert all_hosts()[0]["mac"] == "02:42:C0:A8:00:02"


def test_hostname_follows_a_dhcp_move(setup):
    """A legacy IP-keyed host keeps its record, uplinks and placements"""
    db["hosts"].insert_one(
        {
            "mac": "10.0.0.5",
            "ip": "10.0.0.5",
            "subnet": "10.0.0",
            "host": "nas.lan",
            "monitor": True,
        }
    )
    db["hosts"].insert_one({"mac": "device-switch", "ip": "", "uplink": "10.0.0.5"})
    db["dashboards"].insert_one(
        {"name": "Floor", "placements": [{"key": "10.0.0.5", "x": 1, "y": 2}]}
    )
    db["dashboards"].insert_one({"name": "Other", "placements": []})

    notes = reconcile_all(scan_result("10.0.0.9", "nas.lan"))

    hosts = all_hosts()
    assert len(hosts) == 2
    nas = db["hosts"].find_one({"host": "nas.lan"})
    assert nas["ip"] == "10.0.0.9"
    assert nas["previous_ip"] == "10.0.0.5"
    assert nas["monitor"] is True
    # The old address must not stay its key: another device will get it
    assert nas["mac"].startswith("device-")
    assert db["hosts"].find_one({"mac": "device-switch"})["uplink"] == nas["mac"]
    floor = db["dashboards"].find_one({"name": "Floor"})
    assert floor["placements"] == [{"key": nas["mac"], "x": 1, "y": 2}]
    assert "moved 10.0.0.5 -> 10.0.0.9" in notes[0]


def test_reassigned_address_displaces_the_old_host(setup):
    db["hosts"].insert_one(
        {
            "mac": "device-printer",
            "ip": "10.0.0.5",
            "subnet": "10.0.0",
            "host": "Front printer",
            "resolved_hostname": "printer.lan",
        }
    )

    notes = reconcile_all(scan_result("10.0.0.5", "laptop.lan"))

    printer = db["hosts"].find_one({"mac": "device-printer"})
    assert printer["ip"] == ""
    assert printer["subnet"] == ""
    assert printer["previous_ip"] == "10.0.0.5"
    assert printer["displaced_at"]
    laptop = db["hosts"].find_one({"resolved_hostname": "laptop.lan"})
    assert laptop["ip"] == "10.0.0.5"
    assert laptop["mac"].startswith("device-")
    assert "no longer at 10.0.0.5" in notes[0]

    # The printer turns up again elsewhere and is no longer displaced
    reconcile_all(scan_result("10.0.0.12", "printer.lan"))
    printer = db["hosts"].find_one({"mac": "device-printer"})
    assert printer["ip"] == "10.0.0.12"
    assert printer["subnet"] == "10.0.0"
    assert printer["previous_ip"] == "10.0.0.5"
    assert "displaced_at" not in printer
    assert printer["host"] == "Front printer"


def test_displaced_ip_keyed_host_is_rekeyed(setup):
    db["hosts"].insert_one(
        {
            "mac": "10.0.0.5",
            "ip": "10.0.0.5",
            "subnet": "10.0.0",
            "host": "printer.lan",
        }
    )
    reconcile_all(scan_result("10.0.0.5", "laptop"))
    assert not db["hosts"].find_one({"mac": "10.0.0.5"})
    printer = db["hosts"].find_one({"host": "printer.lan"})
    assert printer["mac"].startswith("device-")
    assert printer["previous_ip"] == "10.0.0.5"


def test_display_name_is_not_identity(setup):
    """Renaming a host never makes the finder think it is another device"""
    db["hosts"].insert_one(
        {"mac": "device-nas", "ip": "10.0.0.5", "subnet": "10.0.0", "host": "Main NAS"}
    )
    reconcile_all(scan_result("10.0.0.5", "nas.lan"))
    hosts = all_hosts()
    assert len(hosts) == 1
    assert hosts[0]["host"] == "Main NAS"
    assert hosts[0]["resolved_hostname"] == "nas.lan"

    db["hosts"].update_one({"mac": "device-nas"}, {"$set": {"host": "nas2"}})
    reconcile_all(scan_result("10.0.0.5", "nas.lan"))
    assert len(all_hosts()) == 1


def test_nameless_scan_falls_back_to_ip(setup):
    db["hosts"].insert_one(
        {"mac": "10.0.0.5", "ip": "10.0.0.5", "subnet": "10.0.0", "host": "nas"}
    )
    # Reverse DNS can fail on one scan; that is no reason to doubt the host
    assert reconcile_all(scan_result("10.0.0.5")) == [""]
    hosts = all_hosts()
    assert len(hosts) == 1
    assert hosts[0]["mac"] == "10.0.0.5"


def test_mac_follows_a_move_and_beats_hostname(setup):
    db["hosts"].insert_one(
        {"mac": "02:42:C0:A8:00:02", "ip": "10.0.0.5", "subnet": "10.0.0"}
    )
    reconcile_all(scan_result("10.1.0.9", "nas", mac="02:42:c0:a8:00:02"))
    hosts = all_hosts()
    assert len(hosts) == 1
    assert hosts[0]["mac"] == "02:42:C0:A8:00:02"
    assert hosts[0]["ip"] == "10.1.0.9"
    assert hosts[0]["subnet"] == "10.1.0"


def test_different_mac_at_address_is_another_device(setup):
    db["hosts"].insert_one(
        {"mac": "02:42:C0:A8:00:02", "ip": "10.0.0.5", "subnet": "10.0.0"}
    )
    reconcile_all(scan_result("10.0.0.5", mac="02:42:C0:A8:00:03"))
    assert db["hosts"].find_one({"mac": "02:42:C0:A8:00:02"})["ip"] == ""
    assert db["hosts"].find_one({"mac": "02:42:C0:A8:00:03"})["ip"] == "10.0.0.5"


def test_shared_default_names_are_not_identity(setup):
    db["hosts"].insert_one(
        {"mac": "device-a", "ip": "10.0.0.5", "subnet": "10.0.0", "host": "android"}
    )
    db["hosts"].insert_one(
        {"mac": "device-b", "ip": "10.0.0.6", "subnet": "10.0.0", "host": "android"}
    )
    # Both answered as "android": nobody moves, each keeps its own address
    reconcile_all(
        scan_result("10.0.0.6", "android"), scan_result("10.0.0.5", "android")
    )
    assert db["hosts"].find_one({"mac": "device-a"})["ip"] == "10.0.0.5"
    assert db["hosts"].find_one({"mac": "device-b"})["ip"] == "10.0.0.6"
    assert len(all_hosts()) == 2


def test_duplicate_records_follow_the_most_recently_seen(setup):
    db["hosts"].insert_one(
        {"mac": "device-old", "ip": "10.0.0.5", "host": "nas", "last_seen": 1}
    )
    db["hosts"].insert_one(
        {"mac": "device-new", "ip": "10.0.0.6", "host": "nas", "last_seen": 2}
    )
    reconcile_all(scan_result("10.0.0.9", "nas"))
    assert db["hosts"].find_one({"mac": "device-new"})["ip"] == "10.0.0.9"
    assert db["hosts"].find_one({"mac": "device-old"})["ip"] == "10.0.0.5"


def test_blank_mac_save_never_mints_an_ip_key(setup):
    unwrap(serve.create_edit_host)({"ip": "10.0.0.5", "mac": "", "host": "a"})
    host = db["hosts"].find_one({"ip": "10.0.0.5"})
    assert host["mac"].startswith("device-")

    # A real-MAC host at the same address is not overwritten by a blank save
    db["hosts"].insert_one({"mac": "02:42:C0:A8:00:02", "ip": "10.0.0.6"})
    unwrap(serve.create_edit_host)({"ip": "10.0.0.6", "mac": "", "host": "b"})
    assert db["hosts"].find_one({"mac": "02:42:C0:A8:00:02"})
    assert db["hosts"].count_documents({"ip": "10.0.0.6"}) == 2


def test_metrics_by_generated_key_use_the_current_ip(setup):
    db["hosts"].insert_one({"mac": "device-nas", "ip": "10.0.0.9", "subnet": "10.0.0"})
    db["metrics"].insert_one(
        {
            "name": "cpu",
            "tags": {"ip": "10.0.0.9", "host": "nas"},
            "fields": {},
            "timestamp": time.time(),
        }
    )
    a = unwrap(serve.read_metrics)("device-nas")
    assert a[1] == 200
    assert len(json.loads(a[0])) == 1


def test_legacy_blank_key_is_given_one(setup):
    db["hosts"].insert_one({"mac": "", "ip": "10.0.0.5", "subnet": "10.0.0"})
    notes = reconcile_all(scan_result("10.0.0.5"))
    hosts = all_hosts()
    assert len(hosts) == 1
    assert hosts[0]["mac"].startswith("device-")
    assert "re-keyed blank key" in notes[0]


def test_legacy_single_word_name_is_not_a_conflict(setup):
    """Hand-typed names on hosts the finder has not named yet never displace"""
    db["hosts"].insert_one(
        {"mac": "10.0.0.5", "ip": "10.0.0.5", "subnet": "10.0.0", "host": "proxmox1"}
    )
    reconcile_all(scan_result("10.0.0.5", "pve1.lan"))
    hosts = all_hosts()
    assert len(hosts) == 1
    assert hosts[0]["host"] == "proxmox1"
    assert hosts[0]["resolved_hostname"] == "pve1.lan"
