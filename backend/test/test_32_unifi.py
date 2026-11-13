#!/usr/bin/env python3
"""
UniFi integration (unifi_helper.py and the /unifi/ routes)
    - Polling a controller (UniFi OS by API key or local login, or a
      self-hosted Network application) into a cached snapshot
    - Tying snapshots to hosts: switch ports, uplinks, inventory status
    - Outages: stale snapshots, remembered clients, one alert per outage
    - Adding UniFi devices and cameras to the inventory
"""
import json
import os
import re
import time

import pytest
import redis
import requests

import alive
import serve
import unifi_helper
import watcher

from common.test import unwrap

rc = redis.Redis(host=os.environ.get("REDIS_HOST"))

GW, CORE, AP, EDGE, LEAF, MESH = ["f4:e2:c6:00:00:0{}".format(i) for i in range(1, 7)]
PRINTER, PVE, VM1, VM2, LAPTOP = ["aa:00:00:00:00:0{}".format(i) for i in range(1, 6)]
FRONT, BACK = "cc:cc:cc:00:00:01", "cc:cc:cc:00:00:02"


def key(value):
    """A MAC as Labyrinth keys it (the finder's upper case)"""
    return value.upper()


def device(mac, name, kind, ip, ports=(), state=1, **fields):
    """A stat/device entry; ports are (idx, up, media, poe, is_uplink)"""
    return dict(
        {
            "mac": mac,
            "name": name,
            "type": kind,
            "model": {"udm": "UDMPRO", "usw": "US48PRO", "uap": "U6PRO"}[kind],
            "serial": mac.replace(":", "").upper(),
            "ip": ip,
            "state": state,
            "adopted": True,
            "displayable_version": "7.1.26",
            "last_seen": 1700000000,
            "uptime": 1000,
            "port_table": [
                {
                    "port_idx": idx,
                    "name": "Port {}".format(idx),
                    "up": up,
                    "enable": True,
                    "speed": 1000 if up else 0,
                    "media": media,
                    "poe_power": poe,
                    "is_uplink": is_uplink,
                }
                for idx, up, media, poe, is_uplink in ports
            ],
        },
        **fields,
    )


def wired(mac, name, ip, switch, port):
    return {
        "mac": mac,
        "hostname": name,
        "ip": ip,
        "is_wired": True,
        "sw_mac": switch,
        "sw_port": port,
    }


class FakeController:
    """
    A UniFi console (or, with unifi_os=False, a self-hosted Network
    application) answering Session.request.  Its network:
        GW (gateway) port 11 -SFP+-> CORE port 25
        CORE port 1: PVE, 2: VM1 + VM2, 3: AP, 4: EDGE (off), 5: camera FRONT
        GW port 1: PRINTER; AP: LAPTOP (wireless) and MESH (wireless uplink)
        EDGE port 1: LEAF (off)
    """

    def __init__(self, unifi_os=True):
        self.unifi_os = unifi_os
        self.up = True
        self.protect_up = True
        self.logins = 0
        self.tokens = set()
        self.requests = []
        self.devices = [
            device(
                GW,
                "UDM Pro",
                "udm",
                "10.0.0.1",
                [(1, True, "GE", "0", False), (11, True, "SFP+", "0", False)],
            ),
            device(
                CORE,
                "USW-Pro-48",
                "usw",
                "10.0.0.2",
                [
                    (1, True, "GE", "0.00", False),
                    (2, True, "GE", "0.00", False),
                    (3, True, "GE", "6.50", False),
                    (4, False, "GE", "0.00", False),
                    (5, True, "GE", "4.20", False),
                    (25, True, "SFP+", "0.00", True),
                ],
                uplink={
                    "uplink_mac": GW,
                    "uplink_remote_port": 11,
                    "port_idx": 25,
                    "type": "wire",
                    "media": "SFP+",
                    "speed": 10000,
                },
            ),
            device(
                AP,
                "U6-Pro",
                "uap",
                "10.0.0.3",
                uplink={
                    "uplink_mac": CORE,
                    "uplink_remote_port": 3,
                    "port_idx": 1,
                    "type": "wire",
                    "media": "GE",
                },
            ),
            device(
                EDGE,
                "USW-Lite-8",
                "usw",
                "10.0.0.4",
                [(1, False, "GE", "0", False)],
                state=0,
                last_uplink={"uplink_mac": CORE, "uplink_remote_port": 4},
            ),
            device(
                LEAF,
                "USW-Flex-Mini",
                "usw",
                "10.0.0.5",
                state=0,
                last_uplink={"uplink_mac": EDGE, "uplink_remote_port": 1},
            ),
            device(
                MESH,
                "U6-Mesh",
                "uap",
                "10.0.0.6",
                uplink={"uplink_mac": AP, "type": "wireless"},
            ),
            # Not adopted yet: not part of the network
            device(
                "f4:e2:c6:00:00:99",
                "New AP",
                "uap",
                "10.0.0.99",
                adopted=False,
                state=2,
            ),
        ]
        self.clients = [
            wired(PRINTER, "printer", "10.0.0.20", GW, 1),
            wired(PVE, "pve1", "10.0.0.10", CORE, 1),
            wired(VM1, "vm1", "10.0.0.11", CORE, 2),
            wired(VM2, "vm2", "10.0.0.12", CORE, 2),
            wired(FRONT, "front-door", "10.0.0.50", CORE, 5),
            {
                "mac": LAPTOP,
                "hostname": "laptop",
                "ip": "10.0.0.30",
                "is_wired": False,
                "ap_mac": AP,
            },
        ]
        self.cameras = [
            {
                "id": "cam1",
                "mac": "CCCCCC000001",
                "name": "Front Door",
                "type": "G4 Bullet",
                "state": "CONNECTED",
            },
            {
                "id": "cam2",
                "mac": "CCCCCC000002",
                "name": "Back Lot",
                "type": "G5 Flex",
                "state": "DISCONNECTED",
            },
        ]

    def handle(self, session, method, url, **kwargs):
        path = url.split("unifi.test", 1)[1]
        self.requests.append((method, path))
        if not self.up:
            raise requests.exceptions.ConnectionError("down")
        if method == "GET" and path == "/":
            if self.unifi_os:
                return response(200, text="<html>UniFi OS</html>")
            return response(302)
        if method == "POST" and path == (
            "/api/auth/login" if self.unifi_os else "/api/login"
        ):
            self.logins += 1
            if kwargs["json"] != {"username": "viewer", "password": "secret"}:
                return response(403)
            token = "token-{}".format(self.logins)
            self.tokens.add(token)
            session.cookies.set("TOKEN", token)
            return response(200, {"username": "viewer"})

        if (
            session.headers.get("X-API-KEY") != "KEY"
            and session.cookies.get("TOKEN") not in self.tokens
        ):
            return response(401)
        prefix = "/proxy/network" if self.unifi_os else ""
        if path == prefix + "/api/self/sites":
            return ok(
                [{"name": "default", "desc": "Default"}, {"name": "lab", "desc": "Lab"}]
            )
        found = re.fullmatch(
            re.escape(prefix) + r"/api/s/(\w+)/stat/(device|sta)", path
        )
        if found and found.group(1) != "default":
            return ok([])
        if found:
            return ok(self.devices if found.group(2) == "device" else self.clients)
        if path in (
            "/proxy/protect/integration/v1/cameras",
            "/proxy/protect/api/cameras",
        ):
            return response(200, self.cameras) if self.protect_up else response(502)
        return response(404)


def response(status, body=None, text=""):
    res = requests.models.Response()
    res.status_code = status
    res._content = (json.dumps(body) if body is not None else text).encode()
    return res


def ok(data):
    return response(200, {"meta": {"rc": "ok"}, "data": data})


CONTROLLER = {
    "_id": "6566a1b2c3d4e5f6a7b8c9d0",
    "name": "HQ console",
    "url": "https://unifi.test",
    "auth": "api_key",
    "api_key": "KEY",
    "protect": True,
    "add_devices": True,
    "sites": [{"site": "default", "location": "HQ"}, {"site": "lab", "monitor": False}],
}


def tearDown():
    for collection in ["hosts", "subnets", "locations", "unifi_controllers"]:
        serve.db["labyrinth"][collection].delete_many({})
    for pattern in ["unifi:*", "unifi-session:*", "unifi-login-wait:*"]:
        for found in rc.keys(pattern):
            rc.delete(found)
    rc.delete(alive.ALIVE_KEY, watcher.BACKOFF_KEY.format("unifi"))


@pytest.fixture
def setup():
    tearDown()
    yield "Setting up"
    tearDown()


@pytest.fixture
def fake(monkeypatch):
    controller = FakeController()
    monkeypatch.setattr(
        requests.Session,
        "request",
        lambda session, method, url, **kwargs: controller.handle(
            session, method, url, **kwargs
        ),
    )
    return controller


def linked(hosts=(), controller=CONTROLLER):
    snapshots, by_host = unifi_helper.link([controller], list(hosts), rc)
    site = snapshots[0]["sites"][0]
    return snapshots, by_host, {d["mac"]: d for d in site["devices"]}


def ports_of(d):
    return {p["idx"]: [x["name"] for x in p["connected"]] for p in d["ports"]}


def test_mac_normalization():
    """Any MAC spelling becomes Labyrinth's key format; IPs and generated keys are not MACs"""
    assert unifi_helper.mac("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"
    assert unifi_helper.mac("24A43C3DFEB9") == "24:A4:3C:3D:FE:B9"
    for value in ["10.0.0.5", "192.168.100.200", "device-a1b2c3d4e5f6", "", None]:
        assert unifi_helper.mac(value) == ""


def test_refresh_reads_sites_devices_clients_and_cameras(setup, fake):
    """An API key snapshot of a UniFi OS console, skipping unmonitored sites"""
    snapshot = unifi_helper.refresh(CONTROLLER, rc)
    assert snapshot["error"] == "" and not snapshot["stale"]
    assert [(s["site"], s["monitored"]) for s in snapshot["sites"]] == [
        ("default", True),
        ("lab", False),
    ]

    devices = {d["mac"]: d for d in snapshot["sites"][0]["devices"]}
    assert set(devices) == {key(x) for x in [GW, CORE, AP, EDGE, LEAF, MESH]}
    core = devices[key(CORE)]
    assert (core["type"], core["state"], core["model"], core["version"]) == (
        "switch",
        "connected",
        "US48PRO",
        "7.1.26",
    )
    assert core["uplink"]["mac"] == key(GW) and core["uplink"]["port"] == 11
    assert [p["poe"] for p in core["ports"]][2:5] == [6.5, None, 4.2]
    # A disconnected device keeps its last uplink
    assert devices[key(EDGE)]["state"] == "disconnected"
    assert devices[key(EDGE)]["uplink"]["mac"] == key(CORE)
    assert devices[key(GW)]["type"] == "router" and devices[key(GW)]["uplink"] is None

    clients = {c["mac"]: c for c in snapshot["sites"][0]["clients"]}
    assert clients[key(PVE)]["uplink"] == {
        "mac": key(CORE),
        "port": 1,
        "wireless": False,
    }
    assert clients[key(LAPTOP)]["uplink"] == {
        "mac": key(AP),
        "port": None,
        "wireless": True,
    }

    cameras = {c["name"]: c for c in snapshot["protect"]["cameras"]}
    assert cameras["Front Door"]["mac"] == key(FRONT)
    assert (cameras["Back Lot"]["state"], cameras["Back Lot"]["model"]) == (
        "disconnected",
        "G5 Flex",
    )
    assert ("GET", "/proxy/protect/integration/v1/cameras") in fake.requests
    assert not [path for _, path in fake.requests if "/api/s/lab/" in path]
    assert fake.logins == 0

    assert (
        json.loads(rc.get(unifi_helper.CACHE_KEY.format(CONTROLLER["_id"]))) == snapshot
    )


def test_link_ports_uplinks_and_hosts(setup, fake):
    """
    Each switch port lists what is plugged into it, and UniFi entries are tied
    to hosts by MAC, or by IP only for hosts not keyed by a MAC
    """
    unifi_helper.refresh(CONTROLLER, rc)
    hosts = [
        {"mac": key(CORE), "ip": "10.0.0.2"},
        {"mac": "10.0.0.10", "ip": "10.0.0.10"},  # routed subnet: keyed by IP
        {
            "mac": "BB:00:00:00:00:99",
            "ip": "10.0.0.11",
        },  # another device on VM1's old IP
        {"mac": PRINTER, "ip": "10.0.0.20"},  # an older lower-case key
    ]
    snapshots, by_host, devices = linked(hosts)
    core, gw = devices[key(CORE)], devices[key(GW)]

    assert ports_of(core) == {
        1: ["pve1"],
        2: ["vm1", "vm2"],
        3: ["U6-Pro"],
        4: ["USW-Lite-8"],
        5: ["front-door"],
        25: ["UDM Pro"],
    }
    assert core["ports"][-1]["connected"][0]["upstream"]
    # The offline EDGE switch is listed on its port, as not connected now
    assert core["ports"][3]["connected"][0]["active"] is False
    assert core["ports"][0]["connected"][0]["active"] is True
    assert ports_of(gw) == {1: ["printer"], 11: ["USW-Pro-48"]}

    assert (
        core["uplink"]["name"] == "UDM Pro" and core["uplink"]["link_type"] == "fiber"
    )
    assert devices[key(AP)]["uplink"]["link_type"] == "ethernet"
    assert devices[key(MESH)]["uplink"]["link_type"] == "wireless"
    assert core["clients"] == 4
    # AP + MESH + laptop, EDGE + LEAF, and four wired clients
    assert core["downstream"] == 9
    assert gw["downstream"] == 11
    assert (
        devices[key(LEAF)]["behind_offline"]
        and not devices[key(EDGE)]["behind_offline"]
    )

    assert core["key"] == key(CORE)
    assert by_host[key(CORE)]["kind"] == "device" and by_host[key(CORE)]["online"]
    pve = by_host["10.0.0.10"]
    assert (
        pve["kind"],
        pve["location"],
        pve["uplink"]["key"],
        pve["uplink"]["port"],
    ) == ("client", "HQ", key(CORE), 1)
    assert "BB:00:00:00:00:99" not in by_host
    assert by_host[PRINTER]["uplink"]["name"] == "UDM Pro"


def test_cameras_join_their_switch_port(setup, fake):
    """A Protect camera takes the site, IP and switch port of its client entry"""
    unifi_helper.refresh(CONTROLLER, rc)
    snapshots, by_host, _ = linked([{"mac": "10.0.0.50", "ip": "10.0.0.50"}])
    front, back = snapshots[0]["protect"]["cameras"]
    assert (front["ip"], front["location"], front["uplink"]["port"]) == (
        "10.0.0.50",
        "HQ",
        5,
    )
    entry = by_host["10.0.0.50"]
    assert (entry["kind"], entry["state"], entry["online"]) == (
        "camera",
        "connected",
        True,
    )
    assert back["key"] == "" and back["uplink"] is None


def test_login_session_is_kept_between_runs(setup, fake):
    """
    A local account logs in once and its session is reused by later runs,
    logging in again only once it has expired; a refused login pauses retries
    """
    controller = dict(
        CONTROLLER, auth="login", username="viewer", password="secret", api_key=""
    )
    assert unifi_helper.refresh(controller, rc)["error"] == ""
    assert unifi_helper.refresh(controller, rc)["error"] == ""
    assert fake.logins == 1
    assert ("GET", "/proxy/protect/api/cameras") in fake.requests

    fake.tokens.clear()  # the session expired
    assert unifi_helper.refresh(controller, rc)["error"] == ""
    assert fake.logins == 2

    rc.delete(unifi_helper.SESSION_KEY.format(controller["_id"]))
    wrong = dict(controller, password="wrong")
    snapshot = unifi_helper.refresh(wrong, rc)
    assert snapshot["error"] == "Login refused (HTTP 403)" and snapshot["stale"]
    snapshot = unifi_helper.refresh(wrong, rc)
    assert snapshot["error"].startswith("Login refused; trying again")
    assert fake.logins == 3


def test_self_hosted_controller(setup, fake):
    """A self-hosted Network application: /api/login, no /proxy/network, no Protect"""
    fake.unifi_os = False
    controller = dict(
        CONTROLLER, auth="login", username="viewer", password="secret", api_key=""
    )
    snapshot = unifi_helper.refresh(controller, rc)
    assert snapshot["error"] == ""
    assert len(snapshot["sites"][0]["devices"]) == 6
    assert ("POST", "/api/login") in fake.requests
    assert snapshot["protect"]["error"] == "Protect runs only on UniFi OS consoles"


def test_outage_keeps_last_snapshot_and_remembers_clients(setup, fake, monkeypatch):
    """
    Clients that drop off stay at their last port for a while, and a
    controller that stops answering keeps its last snapshot, flagged stale
    """
    unifi_helper.refresh(CONTROLLER, rc)
    fake.clients = [x for x in fake.clients if x["mac"] not in (PVE, LAPTOP)]
    snapshot = unifi_helper.refresh(CONTROLLER, rc)
    clients = {c["mac"]: c for c in snapshot["sites"][0]["clients"]}
    assert clients[key(PVE)]["active"] is False
    assert clients[key(PVE)]["uplink"]["port"] == 1
    # Wireless clients say nothing about cabling, so they are not remembered
    assert key(LAPTOP) not in clients

    _, by_host, devices = linked([{"mac": "10.0.0.10", "ip": "10.0.0.10"}])
    assert ports_of(devices[key(CORE)])[1] == ["pve1"]
    assert by_host["10.0.0.10"]["online"] is False

    # Forgotten once remembered for longer than UNIFI_CLIENT_MEMORY_DAYS
    now = time.time
    later = now() + unifi_helper.CLIENT_MEMORY_SECONDS + 60
    monkeypatch.setattr(unifi_helper.time, "time", lambda: later)
    snapshot = unifi_helper.refresh(CONTROLLER, rc)
    monkeypatch.setattr(unifi_helper.time, "time", now)
    assert key(PVE) not in [c["mac"] for c in snapshot["sites"][0]["clients"]]

    fake.protect_up = False
    snapshot = unifi_helper.refresh(CONTROLLER, rc)
    assert (
        snapshot["protect"]["error"]
        == "HTTP 502 from /proxy/protect/integration/v1/cameras"
    )
    assert snapshot["protect"]["stale"] and len(snapshot["protect"]["cameras"]) == 2

    fake.up = False
    snapshot = unifi_helper.refresh(CONTROLLER, rc)
    assert (snapshot["error"], snapshot["stale"]) == ("Could not connect", True)
    assert len(snapshot["sites"][0]["devices"]) == 6

    # An answer it cannot read is logged, and shown without its exception text
    fake.up = True
    fake.devices[1]["port_table"][0]["poe_power"] = "n/a"
    snapshot = unifi_helper.refresh(CONTROLLER, rc)
    assert (
        snapshot["error"] == "Unexpected answer from the controller (see the cron log)"
    )
    assert snapshot["stale"] and len(snapshot["sites"][0]["devices"]) == 6

    # Never reached at all: nothing to show, not stale
    rc.delete(unifi_helper.CACHE_KEY.format(CONTROLLER["_id"]))
    snapshot = unifi_helper.refresh(CONTROLLER, rc)
    assert (snapshot["fetched_at"], snapshot["stale"], snapshot["sites"]) == (
        None,
        False,
        [],
    )


def test_problems_raise_one_alert_per_outage(setup, fake):
    """
    The topmost offline device carries the outage (with how much is behind
    it); disabled devices are not alerted; a stale snapshot holds its alerts
    """
    fake.devices.append(
        device("f4:e2:c6:00:00:42", "Spare", "usw", "10.0.0.42", state=0, disabled=True)
    )
    unifi_helper.refresh(CONTROLLER, rc)
    alerts, held = unifi_helper.problems(linked()[0])
    assert held == []
    assert [(a["alert_name"], a["instance"], a["severity"]) for a in alerts] == [
        ("UniFi Device Offline", "USW-Lite-8", "error"),
        ("UniFi Camera Offline", "Back Lot", "warning"),
    ]
    assert alerts[0]["service"] == "UniFi HQ"
    assert alerts[0]["summary"] == (
        "UniFi reports USW-Lite-8 (switch, 10.0.0.4) at HQ as disconnected; "
        "1 device(s) connect through it."
    )
    assert set(alerts[0]) == {
        "alert_name",
        "service",
        "instance",
        "severity",
        "summary",
    }

    fake.protect_up = False
    unifi_helper.refresh(CONTROLLER, rc)
    alerts, held = unifi_helper.problems(linked()[0])
    assert [a["alert_name"] for a in alerts] == [
        "UniFi Device Offline",
        "UniFi Protect Unreachable",
    ]
    assert [a["instance"] for a in held] == ["Back Lot"]

    fake.up = False
    unifi_helper.refresh(CONTROLLER, rc)
    alerts, held = unifi_helper.problems(linked()[0])
    assert [a["alert_name"] for a in alerts] == ["UniFi Controller Unreachable"]
    assert (
        alerts[0]["summary"]
        == "UniFi controller HQ console is not answering: Could not connect"
    )
    assert [a["instance"] for a in held] == ["USW-Lite-8", "Back Lot"]


def test_add_hosts(setup, fake):
    """
    UniFi devices and cameras without a host become (unmonitored) hosts, hosts
    keyed by their MAC follow their IP, and nothing is added from stale data
    or when the controller's add_devices is off
    """
    unifi_helper.refresh(CONTROLLER, rc)
    serve.db["labyrinth"]["hosts"].insert_one(
        {"mac": "10.0.0.3", "ip": "10.0.0.3", "host": "ap"}
    )
    serve.db["labyrinth"]["hosts"].insert_one(
        {"mac": key(CORE), "ip": "10.0.9.2", "subnet": "10.0.9", "host": "core"}
    )
    hosts = list(serve.db["labyrinth"]["hosts"].find({}))
    snapshots, _, _ = linked(hosts)

    log = unifi_helper.add_hosts(serve.db["labyrinth"]["hosts"], snapshots, hosts)
    assert len(log) == 7
    added = {h["mac"]: h for h in serve.db["labyrinth"]["hosts"].find({})}
    assert set(added) == {key(x) for x in [GW, CORE, EDGE, LEAF, MESH, FRONT, BACK]} | {
        "10.0.0.3"
    }
    gw = added[key(GW)]
    assert (
        gw["host"],
        gw["ip"],
        gw["subnet"],
        gw["device_type"],
        gw["vendor"],
        gw["model"],
    ) == ("UDM Pro", "10.0.0.1", "10.0.0", "router", "Ubiquiti", "UDMPRO")
    assert gw["monitor"] is False and gw["services"] == []
    assert added[key(FRONT)]["device_type"] == "camera"
    assert added[key(BACK)]["ip"] == "" and added[key(BACK)]["subnet"] == ""
    assert (added[key(CORE)]["ip"], added[key(CORE)]["subnet"]) == (
        "10.0.0.2",
        "10.0.0",
    )

    # Nothing new the second time round
    hosts = list(serve.db["labyrinth"]["hosts"].find({}))
    assert (
        unifi_helper.add_hosts(serve.db["labyrinth"]["hosts"], linked(hosts)[0], hosts)
        == []
    )

    serve.db["labyrinth"]["hosts"].delete_many({})
    for snapshot in [
        dict(linked()[0][0], add_devices=False),
        dict(linked()[0][0], error="Timed out"),
    ]:
        assert (
            unifi_helper.add_hosts(serve.db["labyrinth"]["hosts"], [snapshot], []) == []
        )
    assert serve.db["labyrinth"]["hosts"].count_documents({}) == 0


def test_main_cron_run(setup, fake, monkeypatch):
    """The cron run refreshes, adds hosts and reports the problems with backoff"""
    unwrap(serve.create_edit_location)({"name": "HQ"})
    controller = {k: v for k, v in CONTROLLER.items() if k != "_id"}
    a = unwrap(serve.create_edit_unifi_controller)(controller)
    assert a[1] == 200

    reported = []
    monkeypatch.setattr(
        watcher,
        "report_problems",
        lambda rc_, source, alerts, cfg, hold, held: reported.append(
            (source, alerts, held, hold)
        ),
    )
    unifi_helper.main()
    assert serve.db["labyrinth"]["hosts"].count_documents({}) == 8
    [(source, alerts, held, hold)] = reported
    assert (source, hold, held) == ("unifi", 300, [])
    assert [a["instance"] for a in alerts] == ["USW-Lite-8", "Back Lot"]


def make_controller(**fields):
    data = {
        "name": "HQ console",
        "url": "https://unifi.test/",
        "auth": "api_key",
        "api_key": "KEY",
    }
    data.update(fields)
    return unwrap(serve.create_edit_unifi_controller)(data)


def test_controller_routes(setup):
    """Controllers are validated, never echo or return secrets, and drop stale state on change"""
    unwrap(serve.create_edit_location)({"name": "HQ"})
    evil = "<script>x</script>"
    for fields, code in [
        ({"name": " "}, 407),
        ({"url": "ftp://unifi.test"}, 407),
        ({"url": "https://unifi.test/manage/site/default"}, 407),
        ({"url": evil}, 407),
        ({"api_key": ""}, 407),
        ({"auth": "login", "username": "viewer"}, 407),
        ({"auth": evil}, 407),
        ({"sites": [{"location": "HQ"}]}, 407),
        ({"sites": [{"site": "default", "location": evil}]}, 404),
    ]:
        body, status = make_controller(**fields)
        assert status == code, fields
        assert evil not in body

    body, status = make_controller(sites=[{"site": "default", "location": "HQ"}])
    assert status == 200
    controller_id = json.loads(body)["_id"]
    assert make_controller(name="hq CONSOLE")[1] == 409

    [listed] = json.loads(unwrap(serve.list_unifi_controllers)()[0])
    assert listed["url"] == "https://unifi.test"
    assert (listed["has_api_key"], listed["has_password"]) == (True, False)
    assert "api_key" not in listed and "password" not in listed
    assert (listed["verify_ssl"], listed["protect"], listed["add_devices"]) == (
        False,
        False,
        True,
    )
    assert listed["sites"] == [{"site": "default", "location": "HQ", "monitor": True}]

    # A blank secret keeps the saved one; changing credentials drops the session
    for name in ("SESSION_KEY", "LOGIN_WAIT_KEY", "CACHE_KEY"):
        rc.set(getattr(unifi_helper, name).format(controller_id), "x")
    a = unwrap(serve.create_edit_unifi_controller)(
        {"_id": controller_id, "api_key": "", "protect": True}
    )
    assert a[1] == 200
    saved = serve.db["labyrinth"]["unifi_controllers"].find_one(
        {"name_key": "hq console"}
    )
    assert (saved["api_key"], saved["protect"]) == ("KEY", True)
    assert rc.exists(unifi_helper.SESSION_KEY.format(controller_id))

    a = unwrap(serve.create_edit_unifi_controller)(
        {
            "_id": controller_id,
            "auth": "login",
            "username": "viewer",
            "password": "secret",
        }
    )
    assert a[1] == 200
    assert not rc.exists(unifi_helper.SESSION_KEY.format(controller_id))
    assert not rc.exists(unifi_helper.LOGIN_WAIT_KEY.format(controller_id))
    assert rc.exists(unifi_helper.CACHE_KEY.format(controller_id))

    # Saved secrets are never sent to a new address unseen
    body, status = unwrap(serve.create_edit_unifi_controller)(
        {"_id": controller_id, "url": "https://other.test"}
    )
    assert (body, status) == (
        "Enter the local account's username and password again for the new URL",
        407,
    )
    assert rc.exists(unifi_helper.CACHE_KEY.format(controller_id))
    a = unwrap(serve.create_edit_unifi_controller)(
        {"_id": controller_id, "url": "https://other.test", "password": "new"}
    )
    assert a[1] == 200
    saved = serve.db["labyrinth"]["unifi_controllers"].find_one(
        {"name_key": "hq console"}
    )
    assert (saved["url"], saved["username"], saved["password"]) == (
        "https://other.test",
        "viewer",
        "new",
    )
    assert not rc.exists(unifi_helper.CACHE_KEY.format(controller_id))

    assert unwrap(serve.create_edit_unifi_controller)({"_id": "nope"})[1] == 400
    assert (
        unwrap(serve.create_edit_unifi_controller)({"_id": "6566a1b2c3d4e5f6a7b8c9d1"})[
            1
        ]
        == 404
    )

    rc.set(unifi_helper.CACHE_KEY.format(controller_id), "x")
    assert unwrap(serve.delete_unifi_controller)(controller_id)[1] == 200
    assert not rc.exists(unifi_helper.CACHE_KEY.format(controller_id))
    assert unwrap(serve.delete_unifi_controller)(controller_id)[1] == 404
    assert unwrap(serve.delete_unifi_controller)("nope")[1] == 400


def test_location_rename_and_delete_carry_over_to_sites(setup):
    """UniFi site mappings follow a location's rename, and are unmapped when it is deleted"""
    hq = json.loads(unwrap(serve.create_edit_location)({"name": "HQ"})[0])["_id"]
    unwrap(serve.create_edit_location)({"name": "Lab"})
    body, status = make_controller(
        sites=[
            {"site": "default", "location": "HQ"},
            {"site": "lab", "location": "Lab"},
            {"site": "spare", "location": "HQ", "monitor": False},
        ]
    )
    assert status == 200, body

    def sites():
        controller = serve.db["labyrinth"]["unifi_controllers"].find_one({})
        return [(x["site"], x["location"], x["monitor"]) for x in controller["sites"]]

    assert (
        unwrap(serve.create_edit_location)({"_id": hq, "name": "Head Office"})[1] == 200
    )
    assert sites() == [
        ("default", "Head Office", True),
        ("lab", "Lab", True),
        ("spare", "Head Office", False),
    ]

    assert unwrap(serve.delete_location)(hq)[1] == 200
    assert sites() == [
        ("default", "", True),
        ("lab", "Lab", True),
        ("spare", "", False),
    ]


def test_status_and_refresh_routes(setup, fake):
    """The status lists devices and problems but only counts clients; refresh polls now"""
    unwrap(serve.create_edit_location)({"name": "HQ"})
    controller_id = json.loads(
        make_controller(protect=True, sites=[{"site": "default", "location": "HQ"}])[0]
    )["_id"]
    status = json.loads(unwrap(serve.unifi_status)()[0])
    assert status["controllers"][0]["fetched_at"] is None and status["problems"] == []

    status = json.loads(unwrap(serve.refresh_unifi)()[0])
    [controller] = status["controllers"]
    assert controller["_id"] == controller_id
    site = controller["sites"][0]
    assert site["client_count"] == 6 and "clients" not in site
    assert site["location"] == "HQ"
    assert [p["instance"] for p in status["problems"]] == ["USW-Lite-8", "Back Lot"]

    fake.up = False
    status = json.loads(unwrap(serve.refresh_unifi)()[0])
    assert [(p["instance"], p.get("stale", False)) for p in status["problems"]] == [
        ("HQ console", False),
        ("USW-Lite-8", True),
        ("Back Lot", True),
    ]


def test_inventory_uses_unifi(setup, fake, monkeypatch):
    """
    Hosts take their location, type, uplink and reachability from UniFi
    unless they say otherwise themselves
    """
    unwrap(serve.create_edit_location)({"name": "HQ"})
    unwrap(serve.create_edit_location)({"name": "Plant"})
    make_controller(protect=True, sites=[{"site": "default", "location": "HQ"}])
    unwrap(serve.refresh_unifi)()
    for host in [
        {"mac": key(CORE), "ip": "10.0.0.2"},
        {"mac": key(EDGE), "ip": "10.0.0.4"},
        {"mac": "10.0.0.10", "ip": "10.0.0.10"},
        {
            "mac": key(VM1),
            "ip": "10.0.0.11",
            "location": "Plant",
            "uplink": key(EDGE),
            "device_type": "vm",
        },
        {"mac": "10.0.0.50", "ip": "10.0.0.50"},
    ]:
        assert (
            unwrap(serve.create_edit_host)(dict(host, subnet="", services=[]))[1] == 200
        )
    # pve1 ignores pings, but UniFi sees it connected
    rc.hset(
        alive.ALIVE_KEY, "10.0.0.10", json.dumps({"up": False, "checked": time.time()})
    )

    judged = lambda: None  # noqa: E731
    judged.__wrapped__ = lambda: (json.dumps([]), 200)
    monkeypatch.setattr(serve, "dashboard", judged)
    devices = {
        x["mac"]: x["_live"]
        for x in json.loads(unwrap(serve.inventory)()[0])["devices"]
    }

    core, edge, pve, vm, cam = (
        devices[k] for k in [key(CORE), key(EDGE), "10.0.0.10", key(VM1), "10.0.0.50"]
    )
    assert (
        core["type"],
        core["location"],
        core["location_source"],
        core["status"],
    ) == ("switch", "HQ", "unifi", "up")
    assert (
        core["uplink"] == ""
        and core["unifi"]["ports"][0]["connected"][0]["key"] == "10.0.0.10"
    )
    assert (edge["status"], edge["unifi"]["state"]) == ("down", "disconnected")
    assert (pve["status"], pve["location"], pve["uplink"], pve["link_type"]) == (
        "up",
        "HQ",
        key(CORE),
        "ethernet",
    )
    assert (pve["unifi"]["kind"], pve["unifi"]["uplink"]["port"]) == ("client", 1)
    # Its own location, type and uplink win over UniFi's
    assert (vm["location"], vm["type"], vm["uplink"]) == ("Plant", "vm", key(EDGE))
    assert (cam["type"], cam["status"], cam["unifi"]["kind"]) == (
        "camera",
        "up",
        "camera",
    )


def test_mcp_tool(setup, fake, monkeypatch):
    """The MCP tool reports UniFi status, leaving out switch ports unless asked"""
    from ai.mcp.client import LabyrinthClient

    unwrap(serve.create_edit_location)({"name": "HQ"})
    make_controller(sites=[{"site": "default", "location": "HQ"}])
    client = LabyrinthClient()

    data = client.get_unifi(refresh=True)
    devices = data["controllers"][0]["sites"][0]["devices"]
    assert len(devices) == 6 and "ports" not in devices[0]
    assert [p["instance"] for p in data["problems"]] == ["USW-Lite-8"]
    assert (
        "ports"
        in client.get_unifi(include_ports=True)["controllers"][0]["sites"][0][
            "devices"
        ][0]
    )

    unwrap(serve.create_edit_host)(
        {"mac": "10.0.0.10", "ip": "10.0.0.10", "subnet": "", "services": []}
    )
    judged = lambda: None  # noqa: E731
    judged.__wrapped__ = lambda: (json.dumps([]), 200)
    monkeypatch.setattr(serve, "dashboard", judged)
    [pve] = client.get_inventory()["devices"]
    assert pve["unifi"]["uplink"]["port"] == 1 and pve["location"] == "HQ"
    assert pve["effective_uplink"] == ""  # its switch is not a host
