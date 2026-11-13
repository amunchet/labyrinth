#!/usr/bin/env python3
"""
UniFi integration: device status, switch-port topology and Protect cameras

Cron runs this module every minute (cron/unifi_refresh.sh):
    - Each configured controller (a UniFi OS console, or a self-hosted Network
      application) is asked for every monitored site's devices (`stat/device`:
      state, uplink, port table) and connected clients (`stat/sta`: the switch
      port of each wired client).  These come from the Network application's
      own API: its official Integration API names a client's switch but never
      the port, so it cannot say what is plugged in where
    - Protect cameras come from the official Protect API with an API key, else
      from Protect's own API with the login session
    - Snapshots are cached in Redis (`unifi:<controller id>`).  A controller
      that fails to answer keeps its last snapshot, flagged stale, and wired
      clients that drop off are remembered at their last switch port for
      UNIFI_CLIENT_MEMORY_DAYS, so a powered-off server still shows where it
      is cabled
    - UniFi devices and cameras not yet in Labyrinth become hosts (unless the
      controller's `add_devices` is off), and offline ones are alerted with
      notification backoff (watcher.py)

serve.py reads the snapshots through link(), which ties them to hosts.
"""
import json
import os
import re
import time
import traceback
import urllib.parse

import redis
import requests
import urllib3

import watcher
from common.hostnames import same_subnet

# Consoles mostly have self-signed certificates; verification is per controller
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CACHE_KEY = "unifi:{}"
SESSION_KEY = "unifi-session:{}"
LOGIN_WAIT_KEY = "unifi-login-wait:{}"
# The cron refresh rewrites snapshots every minute; the TTL only bounds how
# long a controller that stays unreachable keeps showing its last results
CACHE_SECONDS = 7 * 24 * 3600
SESSION_SECONDS = 24 * 3600
LOGIN_WAIT_SECONDS = 300
TIMEOUT = 15
CLIENT_MEMORY_SECONDS = float(os.environ.get("UNIFI_CLIENT_MEMORY_DAYS") or 30) * 86400

# UniFi device `type` -> Labyrinth device type (serve.DEVICE_TYPES)
DEVICE_TYPES = {
    "usw": "switch",
    "uap": "ap",
    "ugw": "router",
    "udm": "router",
    "uxg": "router",
    "ubb": "bridge",
}
# stat/device `state` codes
STATES = {
    0: "disconnected",
    1: "connected",
    2: "pending adoption",
    3: "firmware mismatch",
    4: "upgrading",
    5: "provisioning",
    6: "heartbeat missed",
    7: "adopting",
    8: "deleting",
    9: "inform error",
    10: "adoption failed",
    11: "isolated",
}
# The states in which a device is cut off from its controller; the others are
# passing (upgrading, provisioning, a missed heartbeat ...)
OFFLINE = {"disconnected", "inform error", "adoption failed", "isolated"}

MAC_PATTERN = re.compile(r"^[0-9a-f]{2}([:-]?)(?:[0-9a-f]{2}\1){4}[0-9a-f]{2}$", re.I)


def mac(value):
    """`value` as a MAC in Labyrinth's key format (AA:BB:CC:DD:EE:FF), else "" """
    value = str(value or "").strip()
    if not MAC_PATTERN.match(value):
        return ""
    digits = re.sub("[:-]", "", value).upper()
    return ":".join(digits[i : i + 2] for i in range(0, 12, 2))


class UnifiError(Exception):
    """A controller did not answer as expected; the message is safe to show"""


class UnifiClient:
    """One controller's Network (and Protect) API, by API key or local account"""

    def __init__(self, controller, rc):
        self.controller = controller
        self.rc = rc
        self.http = requests.Session()
        self.http.verify = bool(controller.get("verify_ssl"))
        self.api_key = (
            controller.get("api_key") if controller.get("auth") == "api_key" else ""
        )
        if self.api_key:
            # Only UniFi OS has API keys
            self.http.headers["X-API-KEY"] = self.api_key
            self.unifi_os = True
            return
        saved = rc.get(SESSION_KEY.format(controller["_id"]))
        if saved:
            saved = json.loads(saved)
            self.unifi_os = saved["unifi_os"]
            self.http.cookies.update(saved["cookies"])
        else:
            self.login()

    def request(self, method, path, **kwargs):
        """One HTTP call to the controller, with connection failures as UnifiError"""
        try:
            return self.http.request(
                method, self.controller["url"] + path, timeout=TIMEOUT, **kwargs
            )
        except requests.exceptions.SSLError:
            raise UnifiError(
                "Its TLS certificate is not trusted: turn off certificate "
                "verification, or give the console a trusted certificate"
            )
        except requests.exceptions.Timeout:
            raise UnifiError("Timed out")
        except requests.exceptions.RequestException:
            raise UnifiError("Could not connect")

    def login(self):
        """
        Logs in with the local account and keeps the session for later runs
            - Logging in every minute trips UniFi OS's login rate limit, which
              each refused attempt extends, so after a refusal no login is
              tried for LOGIN_WAIT_SECONDS
        """
        wait_key = LOGIN_WAIT_KEY.format(self.controller["_id"])
        if self.rc.get(wait_key):
            raise UnifiError(
                "Login refused; trying again a few minutes after the last attempt"
            )
        # An expired session's cookies would otherwise go out beside the new ones
        self.http.cookies.clear()
        # UniFi OS answers / itself; the self-hosted Network application
        # redirects to, or serves a page based at, /manage/
        res = self.request("GET", "/", allow_redirects=False)
        self.unifi_os = res.status_code == 200 and not re.search(
            r"<base\s+href=[\"']/manage/[\"']", res.text, re.I
        )
        res = self.request(
            "POST",
            "/api/auth/login" if self.unifi_os else "/api/login",
            json={
                "username": self.controller.get("username"),
                "password": self.controller.get("password"),
            },
        )
        if res.status_code != 200:
            self.rc.set(wait_key, 1, ex=LOGIN_WAIT_SECONDS)
            raise UnifiError("Login refused (HTTP {})".format(res.status_code))
        self.rc.set(
            SESSION_KEY.format(self.controller["_id"]),
            json.dumps(
                {"unifi_os": self.unifi_os, "cookies": self.http.cookies.get_dict()}
            ),
            ex=SESSION_SECONDS,
        )

    def get(self, path):
        """
        GETs a Network application path (/api/..., under /proxy/network on
        UniFi OS) and returns its `data`, or any other path's JSON as it is
        """
        network = path.startswith("/api/")
        full = ("/proxy/network" if network and self.unifi_os else "") + path
        res = self.request("GET", full)
        if res.status_code == 401 and not self.api_key:
            self.login()  # the saved session expired
            res = self.request("GET", full)
        if res.status_code != 200:
            raise UnifiError("HTTP {} from {}".format(res.status_code, path))
        try:
            body = res.json()
            return body["data"] if network else body
        except (ValueError, KeyError, TypeError):
            raise UnifiError("Unexpected answer from {}".format(path))


def fetch(controller, rc):
    """
    A live snapshot of a controller: its sites, the devices and clients of the
    monitored ones, and its Protect cameras
        - Raises UnifiError if the Network application fails; a Protect
          failure is only recorded
    """
    api = UnifiClient(controller, rc)
    now = time.time()
    skipped = {
        x["site"] for x in controller.get("sites") or [] if x.get("monitor") is False
    }
    snapshot = {
        "fetched_at": now,
        "error": "",
        "stale": False,
        "sites": [],
        "protect": None,
    }
    for site in api.get("/api/self/sites"):
        entry = {
            "site": site["name"],
            "name": site.get("desc") or site["name"],
            "monitored": site["name"] not in skipped,
            "devices": [],
            "clients": [],
        }
        snapshot["sites"].append(entry)
        if not entry["monitored"]:
            continue
        path = "/api/s/{}/".format(urllib.parse.quote(site["name"], safe=""))

        for d in api.get(path + "stat/device"):
            if d.get("adopted") is False or not mac(d.get("mac")):
                continue
            # A disconnected device keeps its last uplink in last_uplink
            uplink = d.get("uplink") or {}
            last = d.get("last_uplink") or {}
            parent = mac(uplink.get("uplink_mac") or last.get("uplink_mac"))
            entry["devices"].append(
                {
                    "mac": mac(d["mac"]),
                    "name": d.get("name") or d.get("model") or mac(d["mac"]),
                    "type": DEVICE_TYPES.get(d.get("type"), "other"),
                    "model": d.get("model") or "",
                    "serial": d.get("serial") or "",
                    "version": d.get("displayable_version") or d.get("version") or "",
                    "ip": d.get("ip") or "",
                    "state": STATES.get(d.get("state"), "unknown"),
                    "disabled": bool(d.get("disabled")),
                    "last_seen": d.get("last_seen"),
                    "uptime": d.get("uptime"),
                    "uplink": (
                        {
                            "mac": parent,
                            "port": uplink.get("uplink_remote_port")
                            or last.get("uplink_remote_port"),
                            "local_port": uplink.get("port_idx"),
                            "wireless": uplink.get("type") == "wireless",
                            "media": uplink.get("media") or "",
                            "speed": uplink.get("speed") or None,
                        }
                        if parent
                        else None
                    ),
                    "ports": [
                        {
                            "idx": p["port_idx"],
                            "name": p.get("name") or "Port {}".format(p["port_idx"]),
                            "up": bool(p.get("up")),
                            "enabled": p.get("enable") is not False,
                            "speed": p.get("speed") if p.get("up") else None,
                            "media": p.get("media") or "",
                            "poe": float(p.get("poe_power") or 0) or None,
                            "uplink": bool(p.get("is_uplink")),
                        }
                        for p in d.get("port_table") or []
                        if p.get("port_idx") is not None
                    ],
                }
            )

        for c in api.get(path + "stat/sta"):
            if not mac(c.get("mac")):
                continue
            wired = bool(c.get("is_wired"))
            if wired:
                uplink = {"mac": mac(c.get("sw_mac")), "port": c.get("sw_port")}
            else:
                uplink = {"mac": mac(c.get("ap_mac")), "port": None}
            entry["clients"].append(
                {
                    "mac": mac(c["mac"]),
                    "name": c.get("name") or c.get("hostname") or "",
                    "ip": c.get("ip") or "",
                    "network": c.get("network") or "",
                    "last_seen": c.get("last_seen") or now,
                    "active": True,
                    "uplink": (
                        dict(uplink, wireless=not wired) if uplink["mac"] else None
                    ),
                }
            )

    if controller.get("protect"):
        try:
            if not api.unifi_os:
                raise UnifiError("Protect runs only on UniFi OS consoles")
            cameras = api.get(
                "/proxy/protect/integration/v1/cameras"
                if api.api_key
                else "/proxy/protect/api/cameras"
            )
            snapshot["protect"] = {
                "error": "",
                "stale": False,
                "cameras": [
                    {
                        "id": cam.get("id"),
                        "mac": mac(cam.get("mac")),
                        "name": cam.get("name")
                        or cam.get("marketName")
                        or cam.get("type")
                        or "",
                        "model": cam.get("marketName") or cam.get("type") or "",
                        "state": str(cam.get("state") or "unknown").lower(),
                        "ip": cam.get("host") or "",
                        "last_seen": (
                            cam["lastSeen"] / 1000 if cam.get("lastSeen") else None
                        ),
                    }
                    for cam in cameras
                    if cam.get("isAdopted") is not False
                ],
            }
        except UnifiError as exc:
            snapshot["protect"] = {"error": str(exc), "stale": False, "cameras": []}
    return snapshot


def refresh(controller, rc):
    """
    Fetches a controller and caches its snapshot
        - On failure the last snapshot is kept, flagged stale, with the error
        - Wired clients that dropped off stay at their last switch port,
          inactive, for CLIENT_MEMORY_SECONDS.  Wireless ones say nothing about
          cabling, and on guest Wi-Fi would pile up.  Cameras are kept while
          Protect fails
    Returns the snapshot
    """
    key = CACHE_KEY.format(controller["_id"])
    previous = json.loads(rc.get(key) or "null")
    now = time.time()
    try:
        snapshot = fetch(controller, rc)
    except Exception as exc:
        if not isinstance(exc, UnifiError):
            traceback.print_exc()
            exc = "Unexpected answer from the controller (see the cron log)"
        snapshot = previous or {"fetched_at": None, "sites": [], "protect": None}
        snapshot.update(
            error=str(exc),
            stale=bool(snapshot["fetched_at"]),
            last_attempt_at=now,
        )
    else:
        old_sites = {x["site"]: x for x in (previous or {}).get("sites", [])}
        active = {c["mac"] for x in snapshot["sites"] for c in x["clients"]}
        for site in snapshot["sites"]:
            if not site["monitored"]:
                continue
            for c in old_sites.get(site["site"], {}).get("clients", []):
                if (
                    c["uplink"]
                    and not c["uplink"]["wireless"]
                    and c["mac"] not in active
                    and now - c["last_seen"] < CLIENT_MEMORY_SECONDS
                ):
                    site["clients"].append(dict(c, active=False))
        old_protect = (previous or {}).get("protect")
        protect = snapshot["protect"]
        if protect and protect["error"] and old_protect and old_protect["cameras"]:
            protect.update(cameras=old_protect["cameras"], stale=True)
    rc.set(key, json.dumps(snapshot), ex=CACHE_SECONDS)
    return snapshot


def link(controllers, hosts, rc):
    """
    Ties each controller's cached snapshot to Labyrinth hosts
        - A UniFi device, client or camera is the host keyed by its MAC, else
          the host at its IP that is not keyed by a MAC, so a reused DHCP
          address never lends one device another's record.  Devices claim a
          host before clients, and connected clients before remembered ones
        - Uplinks gain the upstream device's name, host key and link type, and
          every switch port lists what is plugged into it (remembered clients
          too, and on a device's own uplink port the device upstream)
        - Devices gain `offline` (cut off from the controller, and not
          disabled), `clients` (connected straight to it), `downstream`
          (everything that connects through it) and `behind_offline` (a
          device upstream is offline as well)
        - Cameras gain the site, IP and switch port of their client entry
    Returns (snapshots, by_host): the annotated snapshots, one per controller,
    and the UniFi entry of each matched host, by host key
    """
    by_mac, by_ip = {}, {}
    for host in hosts:
        if mac(host["mac"]):
            by_mac[mac(host["mac"])] = host["mac"]
        elif host.get("ip"):
            by_ip.setdefault(host["ip"], host["mac"])
    claimed = {}

    def host_key(item):
        if item["mac"] in by_mac:
            return by_mac[item["mac"]]
        key = by_ip.get(item.get("ip") or "", "")
        if key and claimed.setdefault(key, item["mac"]) == item["mac"]:
            return key
        return ""

    snapshots = []
    for controller in controllers:
        snapshot = json.loads(
            rc.get(CACHE_KEY.format(controller["_id"])) or "null"
        ) or {
            "fetched_at": None,
            "error": "",
            "stale": False,
            "sites": [],
            "protect": None,
        }
        snapshot.update(
            _id=str(controller["_id"]),
            name=controller["name"],
            add_devices=controller.get("add_devices", True),
        )
        locations = {
            x["site"]: x.get("location") or "" for x in controller.get("sites") or []
        }
        for site in snapshot["sites"]:
            site["location"] = locations.get(site["site"], "")
        snapshots.append(snapshot)

    sites = [(snapshot, site) for snapshot in snapshots for site in snapshot["sites"]]
    for _, site in sites:
        for d in site["devices"]:
            d["key"] = host_key(d)
    clients = sorted(
        ((snapshot, site, c) for snapshot, site in sites for c in site["clients"]),
        key=lambda x: (not x[2]["active"], -x[2]["last_seen"]),
    )
    for _, _, c in clients:
        c["key"] = host_key(c)

    for snapshot, site in sites:
        devices = {d["mac"]: d for d in site["devices"]}
        ports = {}
        for d in site["devices"]:
            d["offline"] = d["state"] in OFFLINE and not d["disabled"]
            d["clients"] = 0
            for p in d["ports"]:
                p["connected"] = []
                ports[(d["mac"], p["idx"])] = p
        children = {}
        for item in site["devices"] + site["clients"]:
            up = item["uplink"]
            if not up:
                continue
            parent = devices.get(up["mac"])
            port = ports.get((up["mac"], up["port"]))
            media = (up.get("media") or (port or {}).get("media") or "").upper()
            if up["wireless"]:
                link_type = "wireless"
            elif "SFP" in media:
                link_type = "fiber"
            else:
                link_type = "ethernet"
            up.update(
                name=parent["name"] if parent else "",
                key=parent["key"] if parent else "",
                link_type=link_type,
            )
            children.setdefault(up["mac"], []).append(item)
            is_device = item["mac"] in devices
            if parent and not is_device and item["active"]:
                parent["clients"] += 1
            if port is not None:
                port["connected"].append(
                    {
                        "mac": item["mac"],
                        "name": item["name"],
                        "ip": item["ip"],
                        "key": item["key"],
                        "device": is_device,
                        "active": item.get("active", not item.get("offline")),
                    }
                )
            own = ports.get((item["mac"], up.get("local_port")))
            if parent and own is not None:
                own["connected"].append(
                    {
                        "mac": parent["mac"],
                        "name": parent["name"],
                        "ip": parent["ip"],
                        "key": parent["key"],
                        "device": True,
                        "active": not parent["offline"],
                        "upstream": True,
                    }
                )

        def below(device_mac, seen):
            """How many devices and clients connect through `device_mac`"""
            total = 0
            for child in children.get(device_mac, []):
                if child["mac"] not in seen:
                    seen.add(child["mac"])
                    total += 1 + below(child["mac"], seen)
            return total

        for d in site["devices"]:
            d["downstream"] = below(d["mac"], {d["mac"]})
            d["behind_offline"] = False
            seen, up = {d["mac"]}, d["uplink"]
            while up and up["mac"] in devices and up["mac"] not in seen:
                parent = devices[up["mac"]]
                if parent["offline"]:
                    d["behind_offline"] = True
                    break
                seen.add(parent["mac"])
                up = parent["uplink"]

    by_host = {}
    for snapshot, site in sites:
        context = {
            "controller": snapshot["name"],
            "site": site["name"],
            "location": site["location"],
            "stale": bool(snapshot["error"]),
        }
        for d in site["devices"]:
            if d["key"]:
                by_host.setdefault(
                    d["key"],
                    dict(
                        d,
                        kind="device",
                        online=not snapshot["error"] and d["state"] == "connected",
                        offline=not snapshot["error"] and d["offline"],
                        **context,
                    ),
                )

    for snapshot in snapshots:
        protect = snapshot["protect"] or {}
        own = {}
        for s, site, c in clients:
            if s is snapshot:
                own.setdefault(c["mac"], (site, c))
        for cam in protect.get("cameras", []):
            site, c = own.get(cam["mac"], (None, None))
            cam.update(
                site=site["name"] if site else "",
                location=site["location"] if site else "",
                ip=cam["ip"] or (c["ip"] if c else ""),
                uplink=c["uplink"] if c else None,
            )
            cam["key"] = host_key(cam) or (c["key"] if c else "")
            stale = bool(snapshot["error"] or protect["error"])
            if cam["key"]:
                by_host.setdefault(
                    cam["key"],
                    dict(
                        cam,
                        kind="camera",
                        controller=snapshot["name"],
                        stale=stale,
                        online=not stale and cam["state"] == "connected",
                        offline=not stale and cam["state"] == "disconnected",
                    ),
                )

    for snapshot, site, c in clients:
        if c["key"]:
            by_host.setdefault(
                c["key"],
                dict(
                    c,
                    kind="client",
                    controller=snapshot["name"],
                    site=site["name"],
                    location=site["location"],
                    stale=bool(snapshot["error"]),
                    online=not snapshot["error"] and c["active"],
                    offline=False,
                ),
            )
    return snapshots, by_host


def problems(snapshots):
    """
    The alerts for watcher.report_problems(): controllers or Protect that do
    not answer, offline devices and offline cameras
        - One alert per outage: a device behind another offline device is
          counted in that one's alert rather than raising its own
    Returns (alerts, held): held are the device and camera alerts of stale
    snapshots, which are left as they were, neither raised nor resolved
    """
    alerts, held = [], []
    for snapshot in snapshots:
        if snapshot["error"]:
            alerts.append(
                {
                    "alert_name": "UniFi Controller Unreachable",
                    "service": "UniFi",
                    "instance": snapshot["name"],
                    "severity": "error",
                    "summary": "UniFi controller {} is not answering: {}".format(
                        snapshot["name"], snapshot["error"]
                    ),
                }
            )
        for site in snapshot["sites"]:
            where = site["location"] or site["name"]
            for d in site["devices"]:
                if not d["offline"] or d["behind_offline"]:
                    continue
                (held if snapshot["error"] else alerts).append(
                    {
                        "alert_name": "UniFi Device Offline",
                        "service": "UniFi " + where,
                        "instance": d["name"],
                        "severity": "error",
                        "summary": "UniFi reports {} ({}{}) at {} as {}{}.".format(
                            d["name"],
                            d["type"],
                            ", " + d["ip"] if d["ip"] else "",
                            where,
                            d["state"],
                            (
                                "; {} device(s) connect through it".format(
                                    d["downstream"]
                                )
                                if d["downstream"]
                                else ""
                            ),
                        ),
                    }
                )

        protect = snapshot["protect"]
        if not protect:
            continue
        if protect["error"] and not snapshot["error"]:
            alerts.append(
                {
                    "alert_name": "UniFi Protect Unreachable",
                    "service": "Protect",
                    "instance": snapshot["name"],
                    "severity": "warning",
                    "summary": "UniFi Protect on {} is not answering: {}".format(
                        snapshot["name"], protect["error"]
                    ),
                }
            )
        for cam in protect["cameras"]:
            if cam["state"] != "disconnected":
                continue
            (held if snapshot["error"] or protect["error"] else alerts).append(
                {
                    "alert_name": "UniFi Camera Offline",
                    "service": "Protect " + snapshot["name"],
                    "instance": cam["name"],
                    "severity": "warning",
                    "summary": "Camera {}{} is disconnected from UniFi Protect.".format(
                        cam["name"],
                        " ({})".format(cam["location"]) if cam.get("location") else "",
                    ),
                }
            )
    return alerts, held


def add_hosts(collection, snapshots, hosts):
    """
    Keeps hosts in step with each controller's own devices and cameras, from
    fresh snapshots of controllers with `add_devices` on
        - One with no host yet becomes one, unmonitored (the UniFi alerts
          cover it); its location comes from its site through link()
        - A host keyed by its MAC follows its IP when that changes
    `snapshots` are link()'s.  Returns a log line per change
    """
    log = []
    by_key = {h["mac"]: h for h in hosts}
    for snapshot in snapshots:
        if snapshot["error"] or not snapshot["add_devices"]:
            continue
        items = [d for site in snapshot["sites"] for d in site["devices"]]
        protect = snapshot["protect"]
        if protect and not protect["error"]:
            items += [dict(cam, type="camera") for cam in protect["cameras"]]
        for item in items:
            if not item["mac"]:
                continue
            host = by_key.get(item["key"] or item["mac"])
            if not host:
                host = {
                    "mac": item["mac"],
                    "ip": item["ip"],
                    "host": item["name"],
                    "subnet": ".".join(item["ip"].split(".")[:3]) if item["ip"] else "",
                    "group": "",
                    "icon": "",
                    "class": "",
                    "tags": "",
                    "services": [],
                    "monitor": False,
                    "device_type": item["type"],
                    "vendor": "Ubiquiti",
                }
                for field in ("model", "serial"):
                    if item.get(field):
                        host[field] = item[field]
                collection.insert_one(host)
                by_key[host["mac"]] = host
                log.append("Added {} ({})".format(item["name"], item["mac"]))
            elif (
                mac(host["mac"]) == item["mac"]
                and item["ip"]
                and host.get("ip") != item["ip"]
            ):
                changes = {"ip": item["ip"]}
                if not same_subnet(host.get("ip"), item["ip"]):
                    changes["subnet"] = ".".join(item["ip"].split(".")[:3])
                collection.update_one({"mac": host["mac"]}, {"$set": changes})
                host.update(changes)
                log.append(
                    "Updated {} ({}): {}".format(item["name"], host["mac"], changes)
                )
    return log


def main():
    """Cron entry: refresh every controller, add new devices as hosts, and alert"""
    from pid import PidFile
    from db import shared_db

    with PidFile("labyrinth-unifi"):
        db = shared_db()
        rc = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
        controllers = list(db["labyrinth"]["unifi_controllers"].find({}))
        for controller in controllers:
            refresh(controller, rc)
        hosts = list(db["labyrinth"]["hosts"].find({}))
        snapshots, _ = link(controllers, hosts, rc)
        for line in add_hosts(db["labyrinth"]["hosts"], snapshots, hosts):
            print(line)
        alerts, held = problems(snapshots)
        # Runs every minute, so a 5 minute hold rides out a skipped run
        watcher.report_problems(
            rc, "unifi", alerts, watcher.backoff_settings(db), hold=300, held=held
        )
        print(json.dumps({"controllers": len(controllers), "problems": len(alerts)}))


if __name__ == "__main__":  # pragma: no cover
    main()
