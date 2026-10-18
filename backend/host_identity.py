#!/usr/bin/env python3
"""
Works out which known host a scanned device is, without trusting its IP.

Most addresses on a network are handed out by DHCP, so an IP says where a
device is right now, not which device it is.  A MAC would say that, but nmap
only sees MACs on its own layer-2 segment - from inside a Docker bridge
network it sees none at all - so most hosts were keyed by IP, and every lease
change either created a second record for the same device or left the old
record describing whatever device took the address next.

A scanned device is matched to a known host by, strongest first:
    1. a real MAC address, when nmap saw one;
    2. its reverse-DNS hostname, which DHCP servers that register leases in
       DNS keep with the device as its address changes;
    3. its IP, but only when that host is not known to be another device.

When a host is found at a new address, its IP and subnet follow it.  A host
still holding an address that has been seen to belong to a different device
is "displaced": its IP is cleared (kept as `previous_ip`) rather than left
pointing at the wrong device, so IP-based metric matching, reachability
checks and alerts stop attributing the other device to it.  Nothing is
deleted.

The finder records the scanned name in `resolved_hostname`, separate from the
user-editable display name `host`, so renaming a host never changes how it is
recognised.
"""
import re
import time
import uuid

MAC_PATTERN = re.compile(r"^[0-9a-f]{2}([:-][0-9a-f]{2}){5}$", re.IGNORECASE)
IP_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
DNS_NAME_PATTERN = re.compile(r"^[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?(\.[a-z0-9_-]+)*$")


def is_real_mac(value):
    """True for an actual hardware address, not an IP or generated stand-in key"""
    return bool(MAC_PATTERN.match(str(value or "")))


def new_device_key():
    """A key for a host without a known MAC; never derived from its address"""
    return "device-" + uuid.uuid4().hex[:12]


def normalize_hostname(name, ip=""):
    """
    The hostname as an identity, or "" when it cannot serve as one.

    Names built from the address itself (`192-168-0-5.lan`,
    `ip-10-0-0-5.ec2.internal`, `5.0.168.192.in-addr.arpa`) move with the
    address rather than the device, so they are no identity at all.
    """
    name = str(name or "").strip().lower().rstrip(".")
    if not DNS_NAME_PATTERN.match(name):
        return ""
    octets = str(ip or "").split(".")
    if len(octets) == 4:
        digits = re.findall(r"\d+", name)
        joined = "." + ".".join(digits) + "."
        for order in (octets, octets[::-1]):
            if "." + ".".join(order) + "." in joined:
                return ""
    return name


def same_hostname(a, b):
    """
    Two normalised names are the same device.  A bare name (`nas`) matches any
    FQDN it starts (`nas.lan`), as one resolver may append the search domain
    and another not; two FQDNs must match in full.
    """
    if not a or not b:
        return False
    if a == b:
        return True
    if "." in a and "." in b:
        return False
    return a.split(".")[0] == b.split(".")[0]


def known_hostname(host):
    """
    The name a stored host is recognised by.  `resolved_hostname` is written
    only by the finder; hosts saved before it existed fall back to `host` when
    that looks like a DNS name, since the finder used to fill it from nmap.
    """
    if host.get("resolved_hostname"):
        return normalize_hostname(host["resolved_hostname"], host.get("ip"))
    return normalize_hostname(host.get("host"), host.get("ip"))


def scanned_identity(scan_result):
    """(mac, ip, hostname) from one nmap host result"""
    addresses = scan_result.get("addresses", {})
    ip = addresses.get("ipv4", "")
    mac = addresses.get("mac", "")
    hostnames = scan_result.get("hostnames") or []
    name = hostnames[0].get("name", "") if hostnames else ""
    return (mac if is_real_mac(mac) else ""), ip, name


def ambiguous_hostnames(scan_results):
    """
    Names that more than one address answered to in a single scan.  Devices
    that ship with the same default name (`android`, `espressif`) would
    otherwise all be treated as one device bouncing between addresses.
    """
    seen = {}
    for result in scan_results:
        _, ip, name = scanned_identity(result)
        name = normalize_hostname(name, ip)
        if name:
            seen.setdefault(name, set()).add(ip)
    return {name for name, ips in seen.items() if len(ips) > 1}


def resolve(hosts, mac, ip, hostname):
    """
    Picks the known host a scanned device is.

    Returns (match, displaced): the matching host doc or None for a new
    device, and the hosts holding `ip` that turn out to be other devices.
    `hostname` must already be normalised ("" when it is no identity).
    """
    at_ip = [h for h in hosts if h.get("ip") == ip]

    match = None
    if mac:
        match = next(
            (h for h in hosts if str(h.get("mac", "")).lower() == mac.lower()), None
        )

    if match is None and hostname:
        named = [
            h
            for h in hosts
            if same_hostname(known_hostname(h), hostname) and _could_be(h, mac, "")
        ]
        here = [h for h in named if h.get("ip") == ip]
        if here:
            match = here[0]
        elif named:
            # The name has more than one stale record; follow the one seen last
            match = max(named, key=lambda h: h.get("last_seen") or 0)

    if match is None:
        match = next((h for h in at_ip if _could_be(h, mac, hostname)), None)

    displaced = [h for h in at_ip if h is not match and not _could_be(h, mac, hostname)]
    return match, displaced


def _could_be(host, mac, hostname):
    """
    Whether a host at the scanned address may be the scanned device: it is
    not, when both sides have a real MAC or a hostname and they differ.
    """
    if mac and is_real_mac(host.get("mac")) and host["mac"].lower() != mac.lower():
        return False
    known = known_hostname(host)
    # A legacy display name only counts against a match when it looks like the
    # FQDN the finder used to write there, not a single word someone typed
    if not host.get("resolved_hostname") and "." not in known:
        known = ""
    if hostname and known and not same_hostname(known, hostname):
        return False
    return True


def reconcile(db, hosts, scan_result, convert_host, create_host, ambiguous=()):
    """
    Records one scanned device against the hosts collection.

    `hosts` is a list of host docs loaded once per scan and kept current here,
    so later devices in the same scan see earlier moves.  `convert_host` turns
    a scan result into a new host doc and `create_host` saves one.  Returns a
    short description of what happened, for the scan log.
    """
    collection = db["labyrinth"]["hosts"]
    mac, ip, raw_name = scanned_identity(scan_result)
    hostname = normalize_hostname(raw_name, ip)
    if hostname in ambiguous:
        hostname = ""

    match, displaced = resolve(hosts, mac, ip, hostname)
    now = time.time()
    notes = []

    for host in displaced:
        changes = {"ip": "", "subnet": "", "previous_ip": ip, "displaced_at": now}
        collection.update_one(_selector(host), {"$set": changes})
        host.update(changes)
        notes.append("{} no longer at {}".format(host.get("mac") or ip, ip))
        _rekey_if_address(db, host, "", notes)

    if match is None:
        doc = convert_host(scan_result)
        if not doc.get("mac"):
            doc["mac"] = new_device_key()
        if hostname:
            doc["resolved_hostname"] = hostname
        doc["last_seen"] = now
        create_host(doc)
        hosts.append(doc)
        notes.append("Creating new host: {}".format(doc["mac"]))
        return "; ".join(notes)

    changes = {"last_seen": now}
    if hostname and match.get("resolved_hostname") != hostname:
        changes["resolved_hostname"] = hostname
    if hostname and not match.get("host"):
        changes["host"] = raw_name
    if match.get("ip") != ip:
        notes.append(
            "{} moved {} -> {}".format(match.get("mac"), match.get("ip") or "?", ip)
        )
        changes.update(ip=ip, subnet=".".join(ip.split(".")[:3]))
        changes["previous_ip"] = match.get("ip") or match.get("previous_ip", "")
    collection.update_one(_selector(match), {"$set": changes})
    match.update(changes)
    if match.get("displaced_at"):
        collection.update_one(_selector(match), {"$unset": {"displaced_at": ""}})
        del match["displaced_at"]

    _rekey_if_address(db, match, ip, notes)
    return "; ".join(notes)


def _rekey_if_address(db, host, ip, notes):
    """
    Gives a host keyed by an address other than its own `ip` a generated key.
    A key that is an old address would name the wrong device to every
    `{"$or": [{"mac": key}, {"ip": key}]}` lookup once another device has it.
    """
    key = str(host.get("mac") or "")
    if key and not (IP_PATTERN.match(key) and key != ip):
        return
    new_key = new_device_key()
    rekey_host(db, host, new_key)
    notes.append("re-keyed {} as {}".format(key or "blank key", new_key))


def _selector(host):
    """Selects exactly this host doc; legacy hosts may share a blank key"""
    return {"_id": host["_id"]} if host.get("_id") else {"mac": host["mac"]}


def rekey_host(db, host, new_key):
    """Changes a host's key, carrying uplinks and map placements with it"""
    labyrinth = db["labyrinth"]
    old_key = host.get("mac") or ""
    labyrinth["hosts"].update_one(_selector(host), {"$set": {"mac": new_key}})
    host["mac"] = new_key
    if not old_key:
        return
    labyrinth["hosts"].update_many({"uplink": old_key}, {"$set": {"uplink": new_key}})
    for dashboard in labyrinth["dashboards"].find({"placements": {"$exists": True}}):
        if not any(p.get("key") == old_key for p in dashboard["placements"] or []):
            continue
        placements = [
            dict(p, key=new_key) if p.get("key") == old_key else p
            for p in dashboard.get("placements") or []
        ]
        labyrinth["dashboards"].update_one(
            {"_id": dashboard["_id"]}, {"$set": {"placements": placements}}
        )
