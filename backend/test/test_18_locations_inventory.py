#!/usr/bin/env python3
"""
Locations, device inventory and live reachability
    - Locations (sites/buildings) with racks, referenced by name from hosts/subnets/maps
    - Hosts as devices: inventory fields, IP-less "label" devices, partial inventory updates
    - Alive checks recorded in Redis, and the rolled-up `/inventory/` view
"""
import json
import os
import time

import pytest
import redis

import alive
import proxmox_helper
import serve

from common.test import unwrap

rc = redis.Redis(host=os.environ.get("REDIS_HOST"))
db = serve.db["labyrinth"]


def tearDown():
    for collection in [
        "hosts",
        "subnets",
        "locations",
        "dashboards",
        "proxmox_clusters",
        "services",
    ]:
        db[collection].delete_many({})
    rc.delete(alive.ALIVE_KEY)
    for key in rc.keys("proxmox-disk:*"):
        rc.delete(key)


@pytest.fixture
def setup():
    tearDown()
    yield "Setting up"
    tearDown()


def make_location(name="Main Office", racks=None):
    """Creates a location and returns its id"""
    a = unwrap(serve.create_edit_location)(
        {"name": name, "address": "1 Main St", "racks": racks or []}
    )
    assert a[1] == 200
    return json.loads(a[0])["_id"]


def make_host(**fields):
    """Saves a host through the normal host save path and returns its stored doc"""
    host = {"ip": "", "mac": "", "subnet": "", "host": "", "services": []}
    host.update(fields)
    a = unwrap(serve.create_edit_host)(host)
    assert a[1] == 200, a
    return host


def get_host(key):
    return db["hosts"].find_one({"mac": key})


def get_inventory():
    a = unwrap(serve.inventory)()
    assert a[1] == 200
    data = json.loads(a[0])
    return data, {x["_live"]["key"]: x for x in data["devices"]}


def fake_dashboard(monkeypatch, hosts):
    """Stands in for the judged main dashboard (one subnet, one group)"""

    def judged():  # pragma: no cover
        pass

    judged.__wrapped__ = lambda: (
        json.dumps([{"subnet": "10.0.0", "groups": [{"name": "", "hosts": hosts}]}]),
        200,
    )
    monkeypatch.setattr(serve, "dashboard", judged)


# Locations


def test_location_create_list_and_unique_names(setup):
    """Locations are listed by name, and names are unique regardless of case"""
    make_location("Warehouse")
    make_location("Main Office", racks=[{"name": "Rack A", "units": 42}])

    locations = json.loads(unwrap(serve.list_locations)()[0])
    assert [x["name"] for x in locations] == ["Main Office", "Warehouse"]
    assert locations[0]["racks"] == [{"name": "Rack A", "units": 42}]

    a = unwrap(serve.create_edit_location)({"name": "main office"})
    assert a[1] == 409

    assert unwrap(serve.create_edit_location)({"name": " "})[1] == 407
    assert unwrap(serve.create_edit_location)({"name": "A/B"})[1] == 407


def test_location_rack_validation(setup):
    """Racks need unique names and a sane height"""
    bad_racks = [
        ([{"name": "", "units": 42}], 407),
        ([{"name": "Rack A", "units": 0.5}], 407),
        ([{"name": "Rack A", "units": 61}], 407),
        ([{"name": "Rack A", "units": "tall"}], 407),
        (["Rack A"], 407),
        ([{"name": "Rack A"}, {"name": "Rack A"}], 409),
    ]
    for racks, code in bad_racks:
        a = unwrap(serve.create_edit_location)({"name": "Office", "racks": racks})
        assert a[1] == code, racks

    # Units default to a full-height 42U rack
    make_location("Office", racks=[{"name": "Rack A"}])
    assert db["locations"].find_one({"name": "Office"})["racks"][0]["units"] == 42


def test_location_rename_carries_over(setup):
    """Renaming a location keeps everything that pointed at the old name"""
    location_id = make_location("Plant", racks=[{"name": "Rack A", "units": 42}])
    make_host(ip="10.0.0.5", mac="AA", location="Plant", rack="Rack A", rack_unit=4)
    db["subnets"].update_one({"subnet": "10.0.0"}, {"$set": {"location": "Plant"}})
    db["dashboards"].insert_one({"name": "Floor 1", "location": "Plant"})

    a = unwrap(serve.create_edit_location)(
        {
            "_id": location_id,
            "name": "Plant 1",
            "racks": [{"name": "Rack 1", "previous_name": "Rack A", "units": 42}],
        }
    )
    assert a[1] == 200

    host = get_host("AA")
    assert (host["location"], host["rack"], host["rack_unit"]) == (
        "Plant 1",
        "Rack 1",
        4,
    )
    assert db["subnets"].find_one({"subnet": "10.0.0"})["location"] == "Plant 1"
    assert db["dashboards"].find_one({"name": "Floor 1"})["location"] == "Plant 1"
    assert db["locations"].count_documents({}) == 1


def test_location_removed_rack_unracks_hosts(setup):
    """Hosts in a deleted rack stay at the location but lose their rack slot"""
    location_id = make_location("Plant", racks=[{"name": "Rack A"}, {"name": "Rack B"}])
    make_host(ip="10.0.0.5", mac="AA", location="Plant", rack="Rack A", rack_unit=4)
    make_host(ip="10.0.0.6", mac="BB", location="Plant", rack="Rack B", rack_unit=1)

    a = unwrap(serve.create_edit_location)(
        {"_id": location_id, "name": "Plant", "racks": [{"name": "Rack B"}]}
    )
    assert a[1] == 200

    host = get_host("AA")
    assert host["location"] == "Plant"
    assert "rack" not in host and "rack_unit" not in host
    assert get_host("BB")["rack"] == "Rack B"


def test_location_update_errors(setup):
    """Updates must target an existing location and not take another's name"""
    make_location("Plant")
    office_id = make_location("Office")

    a = unwrap(serve.create_edit_location)({"_id": office_id, "name": "PLANT"})
    assert a[1] == 409
    a = unwrap(serve.create_edit_location)({"_id": "not-an-id", "name": "X"})
    assert a[1] == 400
    a = unwrap(serve.create_edit_location)(
        {"_id": "5f0000000000000000000000", "name": "X"}
    )
    assert a[1] == 404

    # Keeping its own name (in another case) is fine
    a = unwrap(serve.create_edit_location)({"_id": office_id, "name": "OFFICE"})
    assert a[1] == 200


def test_location_delete_unassigns(setup):
    """Deleting a location leaves its devices, subnets and maps in place, unassigned"""
    location_id = make_location("Plant", racks=[{"name": "Rack A"}])
    make_host(ip="10.0.0.5", mac="AA", location="Plant", rack="Rack A", rack_unit=4)
    db["subnets"].update_one({"subnet": "10.0.0"}, {"$set": {"location": "Plant"}})
    db["dashboards"].insert_one({"name": "Floor 1", "location": "Plant"})

    assert unwrap(serve.delete_location)("not-an-id")[1] == 400
    assert unwrap(serve.delete_location)(location_id)[1] == 200
    assert unwrap(serve.delete_location)(location_id)[1] == 404

    host = get_host("AA")
    assert host["ip"] == "10.0.0.5"
    assert not {"location", "rack", "rack_unit"} & set(host)
    assert "location" not in db["subnets"].find_one({"subnet": "10.0.0"})
    assert db["dashboards"].find_one({"name": "Floor 1"})["location"] == ""


# Hosts as devices


def test_ip_less_devices_get_unique_keys(setup):
    """Label-only devices (no IP/MAC) never overwrite each other or create subnets"""
    make_host(host="Unmanaged switch 1", device_type="switch")
    make_host(host="Unmanaged switch 2", device_type="switch")

    devices = list(db["hosts"].find({}))
    assert len(devices) == 2
    assert all(x["mac"].startswith("device-") for x in devices)
    assert devices[0]["mac"] != devices[1]["mac"]
    assert db["subnets"].count_documents({}) == 0


def test_blank_mac_is_keyed_by_ip(setup):
    """Hosts without a known MAC are keyed by IP (as the finder does), subnet derived"""
    make_host(ip="10.1.2.3", host="plc-gate")
    host = get_host("10.1.2.3")
    assert host["subnet"] == "10.1.2"
    assert db["subnets"].find_one({"subnet": "10.1.2"})

    # Saving again updates in place
    make_host(ip="10.1.2.3", host="plc-gate-renamed", _live={"status": "up"})
    assert db["hosts"].count_documents({}) == 1
    host = get_host("10.1.2.3")
    assert host["host"] == "plc-gate-renamed"
    # A device read from /inventory/ and saved back does not persist its live block
    assert "_live" not in host


def test_legacy_blank_mac_host_is_rekeyed(setup):
    """A host saved before keys were enforced (MAC "") is re-keyed, not duplicated"""
    db["hosts"].insert_one({"ip": "10.1.2.3", "mac": "", "subnet": "10.1.2"})
    make_host(ip="10.1.2.3", subnet="10.1.2", host="edited")

    hosts = list(db["hosts"].find({}))
    assert len(hosts) == 1
    assert hosts[0]["mac"] == "10.1.2.3"


def test_host_save_coerces_inventory_fields(setup):
    """Rack positions are stored as numbers; blanks are dropped; bad values rejected"""
    make_host(ip="10.0.0.5", mac="AA", rack_unit="12", rack_height=" 2 ", vendor=" ")
    host = get_host("AA")
    assert host["rack_unit"] == 12 and host["rack_height"] == 2
    assert "vendor" not in host

    for bad in [
        {"device_type": "toaster"},
        {"link_type": "carrier pigeon"},
        {"rack_unit": "top"},
        {"rack_height": 0},
    ]:
        host = {"ip": "10.0.0.6", "mac": "BB", "subnet": "10.0.0"}
        host.update(bad)
        assert unwrap(serve.create_edit_host)(host)[1] == 407, bad


def test_update_host_inventory(setup):
    """Partial inventory updates validate references and leave monitoring alone"""
    make_location("Plant", racks=[{"name": "Rack A"}])
    make_location("Office")
    make_host(
        ip="10.0.0.5",
        mac="AA",
        services=["open_ports", "cpu"],
        monitor=True,
        check_alive_port="22",
    )
    make_host(ip="10.0.0.1", mac="CORE", device_type="switch")

    a = unwrap(serve.update_host_inventory)(
        "10.0.0.5",
        {
            "location": "Plant",
            "rack": "Rack A",
            "rack_unit": "10",
            "rack_height": 2,
            "device_type": "server",
            "uplink": "CORE",
            "link_type": "fiber",
        },
    )
    assert a[1] == 200
    host = get_host("AA")
    assert host["rack_unit"] == 10 and host["uplink"] == "CORE"
    assert host["services"] == ["open_ports", "cpu"]
    assert host["monitor"] is True and host["check_alive_port"] == "22"
    assert json.loads(a[0])["rack"] == "Rack A"

    errors = [
        ({"colour": "red"}, 407),
        ({"location": "Mars"}, 404),
        ({"rack": "Rack Z"}, 404),
        ({"location": "", "rack": "Rack A"}, 407),
        ({"uplink": "AA"}, 407),
        ({"uplink": "NOPE"}, 404),
        ({"rack_unit": "high"}, 407),
    ]
    for data, code in errors:
        assert unwrap(serve.update_host_inventory)("AA", data)[1] == code, data
    assert unwrap(serve.update_host_inventory)("ZZ", {})[1] == 404
    assert unwrap(serve.update_host_inventory)("AA", {})[1] == 200

    # Moving buildings without naming a rack takes it out of the old rack
    assert unwrap(serve.update_host_inventory)("AA", {"location": "Office"})[1] == 200
    host = get_host("AA")
    assert host["location"] == "Office"
    assert "rack" not in host and "rack_unit" not in host
    assert host["rack_height"] == 2

    # Blank values clear fields
    a = unwrap(serve.update_host_inventory)("AA", {"location": "", "uplink": None})
    assert a[1] == 200
    assert not {"location", "uplink"} & set(get_host("AA"))


def test_delete_host_cleans_references(setup):
    """Deleting a device drops uplinks and map placements that pointed at it"""
    make_host(ip="10.0.0.1", mac="CORE", device_type="switch")
    make_host(ip="10.0.0.5", mac="AA", uplink="CORE", link_type="fiber")
    db["dashboards"].insert_one(
        {"name": "Floor 1", "placements": [{"key": "CORE", "x": 1, "y": 2}]}
    )
    db["dashboards"].insert_one({"name": "Legacy", "components": []})

    assert unwrap(serve.delete_host)("10.0.0.1")[1] == 200
    assert not {"uplink", "link_type"} & set(get_host("AA"))
    assert db["dashboards"].find_one({"name": "Floor 1"})["placements"] == []
    # Maps from the old editor are left exactly as they were
    assert "placements" not in db["dashboards"].find_one({"name": "Legacy"})
    assert unwrap(serve.delete_host)("10.0.0.1")[1] == 407


# Alive checks


def test_check_host_methods(monkeypatch):
    """Ping by default, TCP when a check port is set; a bad port is reported, not raised"""
    monkeypatch.setattr(alive, "ping", lambda ip: ip == "10.0.0.5")
    calls = []

    def fake_check_port(ip, port):
        calls.append((ip, port))
        return True

    monkeypatch.setattr(alive, "check_port", fake_check_port)

    result = alive.check_host({"ip": "10.0.0.5"})
    assert result["up"] is True and result["method"] == "ping"
    assert time.time() - result["checked"] < 5
    assert alive.check_host({"ip": "10.0.0.6", "check_alive_port": ""})["up"] is False

    # The UI stores the port as text; it must reach the socket as a number
    result = alive.check_host({"ip": "10.0.0.7", "check_alive_port": " 502 "})
    assert result["up"] is True and result["method"] == "port"
    assert calls == [("10.0.0.7", 502)]

    result = alive.check_host({"ip": "10.0.0.8", "check_alive_port": "http"})
    assert result["up"] is False
    assert "Invalid check port" in result["error"]


def test_check_port_times_out(monkeypatch):
    """A dead host must not hold a TCP check open for the OS connect timeout"""
    sockets = []

    class FakeSocket:
        def __init__(self, *args):
            self.timeout = None
            sockets.append(self)

        def settimeout(self, seconds):
            self.timeout = seconds

        def connect_ex(self, address):
            return 0 if self.timeout else 110

        def close(self):
            pass

    monkeypatch.setattr(alive.socket, "socket", FakeSocket)
    assert alive.check_port("10.0.0.9", 80) is True
    assert sockets[0].timeout == 2


def test_alive_check_endpoint_records(setup, monkeypatch):
    """An on-demand check is stored where the inventory reads it"""
    monkeypatch.setattr(alive, "ping", lambda ip: True)
    make_host(ip="10.0.0.5", mac="AA")
    make_host(host="Unmanaged switch")

    a = unwrap(serve.alive_check)("AA")
    assert a[1] == 200 and json.loads(a[0])["up"] is True
    assert json.loads(rc.hget(alive.ALIVE_KEY, "10.0.0.5"))["up"] is True

    assert unwrap(serve.alive_check)("missing")[1] == 404
    ip_less = db["hosts"].find_one({"host": "Unmanaged switch"})
    assert unwrap(serve.alive_check)(ip_less["mac"])[1] == 404


# Inventory


def set_alive(ip, up, age=0):
    rc.hset(
        alive.ALIVE_KEY,
        ip,
        json.dumps({"up": up, "method": "ping", "checked": time.time() - age}),
    )


def judged_host(mac, states, **fields):
    host = {"mac": mac, "services": [{"name": n, "state": s} for n, s in states]}
    host.update(fields)
    return host


def test_inventory_status_rollup(setup, monkeypatch):
    """Each device rolls reachability and service health into one status"""
    for mac, ip in [
        ("UP", "10.0.0.1"),
        ("DOWN", "10.0.0.2"),
        ("NOPING", "10.0.0.3"),
        ("FAILING", "10.0.0.4"),
        ("WARN", "10.0.0.5"),
        ("NEVER", "10.0.0.6"),
        ("STALE", "10.0.0.7"),
        ("LEVEL", "10.0.0.8"),
    ]:
        make_host(ip=ip, mac=mac)
    make_host(host="Patch panel", device_type="patch-panel")

    set_alive("10.0.0.1", True)
    set_alive("10.0.0.2", False)
    set_alive("10.0.0.3", False)
    set_alive("10.0.0.4", True)
    set_alive("10.0.0.7", True, age=3600)
    fake_dashboard(
        monkeypatch,
        [
            judged_host("NOPING", [("cpu", True)]),
            judged_host("FAILING", [("cpu", True), ("disk", False)]),
            judged_host("WARN", [("cpu", True), ("apt", -1)]),
            judged_host(
                "LEVEL",
                [("cpu", False), ("apt", False)],
                service_levels=[{"service": "apt", "level": "warning"}],
            ),
        ],
    )

    _, devices = get_inventory()
    status = {k: v["_live"]["status"] for k, v in devices.items()}
    assert status["UP"] == "up"
    assert status["DOWN"] == "down"
    # Drops pings (e.g. Windows firewall) but reports healthy metrics
    assert status["NOPING"] == "up"
    assert status["FAILING"] == "error"
    assert status["WARN"] == "warning"
    assert status["NEVER"] == "unknown"
    assert status["STALE"] == "unknown"
    assert devices["STALE"]["_live"]["alive"] is None
    assert status["LEVEL"] == "error"
    patch_panel = [v for v in devices.values() if not v["ip"]][0]
    assert patch_panel["_live"]["status"] == "none"
    assert patch_panel["_live"]["type"] == "patch-panel"

    services = devices["LEVEL"]["_live"]["services"]
    assert (services["failed"], services["warning"]) == (1, 1)
    assert services["failing"] == ["cpu", "apt"]


def test_inventory_locations_and_proxmox(setup, monkeypatch):
    """Devices are placed explicitly, by subnet, or by the Proxmox node they run on"""
    fake_dashboard(monkeypatch, [])
    make_location("Main Office", racks=[{"name": "Rack A"}])
    make_location("Warehouse")

    # pve1 is matched to its Proxmox node by hostname and racked explicitly
    make_host(
        ip="10.0.0.10",
        mac="PVE1",
        host="pve1.corp.local",
        location="Main Office",
        rack="Rack A",
        rack_unit=10,
    )
    # web01 is a VM matched by hostname; dns is an LXC linked explicitly by vmid
    make_host(ip="10.0.5.20", mac="WEB", host="WEB01")
    make_host(ip="10.0.5.21", mac="DNS", host="resolver", proxmox_vmid=201)
    # A PC in the warehouse subnet, and a device with an explicit location override
    make_host(ip="10.0.9.50", mac="PC")
    make_host(ip="10.0.9.51", mac="KIOSK", location="Main Office")
    db["subnets"].update_one({"subnet": "10.0.9"}, {"$set": {"location": "Warehouse"}})
    # A host linked to another cluster's vmid 201 must not be claimed here
    make_host(ip="10.0.5.22", mac="OTHER", proxmox_vmid=201, proxmox_cluster="lab")
    make_host(ip="10.0.5.30", mac="FILES", host="files")

    cluster = {"name": "prod", "host": "10.0.0.10"}
    cluster["_id"] = db["proxmox_clusters"].insert_one(dict(cluster)).inserted_id
    proxmox_helper.set_cached_proxmox_disk_data(
        cluster,
        {
            "nodes": [
                {
                    "name": "pve1",
                    "status": "online",
                    "vms": [
                        {"id": 101, "name": "web01", "status": "running"},
                        {"id": 102, "name": "orphan", "status": "stopped"},
                    ],
                    "containers": [{"id": 201, "name": "dns", "status": "running"}],
                },
                # A node nobody registered as a host; its VM still is one
                {
                    "name": "pve2",
                    "status": "online",
                    "vms": [{"id": 301, "name": "files", "status": "running"}],
                    "containers": [],
                },
            ]
        },
        redis_client=rc,
    )

    data, devices = get_inventory()
    assert [x["name"] for x in data["locations"]] == ["Main Office", "Warehouse"]

    live = {k: v["_live"] for k, v in devices.items()}
    assert (live["PVE1"]["type"], live["PVE1"]["location_source"]) == (
        "server",
        "explicit",
    )
    assert live["WEB"]["type"] == "vm"
    assert live["WEB"]["parent"] == "PVE1"
    assert (live["WEB"]["location"], live["WEB"]["location_source"]) == (
        "Main Office",
        "proxmox",
    )
    assert live["DNS"]["type"] == "lxc"
    assert live["DNS"]["proxmox"]["vmid"] == 201
    assert live["OTHER"]["proxmox"] is None
    assert (live["PC"]["location"], live["PC"]["location_source"]) == (
        "Warehouse",
        "subnet",
    )
    assert live["KIOSK"]["location_source"] == "explicit"

    [cluster_tree] = data["proxmox"]
    assert cluster_tree["cluster"] == "prod" and cluster_tree["error"] is None
    assert (live["FILES"]["type"], live["FILES"]["parent"]) == ("vm", "")
    assert live["FILES"]["location"] == ""

    node, unregistered_node = cluster_tree["nodes"]
    assert unregistered_node["host_key"] == ""
    assert unregistered_node["guests"][0]["host_key"] == "FILES"
    assert node["host_key"] == "PVE1"
    guests = {x["name"]: x for x in node["guests"]}
    assert guests["web01"]["host_key"] == "WEB"
    assert guests["dns"]["host_key"] == "DNS" and guests["dns"]["kind"] == "lxc"
    assert guests["orphan"]["host_key"] == ""


def test_inventory_proxmox_cache_miss(setup, monkeypatch):
    """Without cached Proxmox data the inventory says so instead of querying live"""
    fake_dashboard(monkeypatch, [])
    db["proxmox_clusters"].insert_one({"name": "prod", "host": "10.0.0.10"})
    monkeypatch.setattr(
        proxmox_helper,
        "get_proxmox_disk_data",
        lambda *args, **kwargs: pytest.fail("inventory must not query Proxmox live"),
    )

    data, _ = get_inventory()
    assert data["proxmox"] == [
        {"cluster": "prod", "error": "No cached Proxmox data yet", "nodes": []}
    ]
