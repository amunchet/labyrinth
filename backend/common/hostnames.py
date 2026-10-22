"""
Hostname identity helpers

Hosts on DHCP change IP, so the hostname is the first thing a host is matched
on, falling back to the MAC/IP key.  Names come both from reverse DNS
(`desktop-x.north.example.com`) and from people (`desktop-x`), so a bare name
matches the first label of a fully-qualified one.
"""


def hostnames_match(a, b):
    """True when two hostnames name the same device"""
    a = (a or "").strip().rstrip(".").lower()
    b = (b or "").strip().rstrip(".").lower()
    if not a or not b:
        return False
    if "." in a and "." in b:
        return a == b
    return a.split(".")[0] == b.split(".")[0]


def same_subnet(ip_a, ip_b):
    """True when two IPv4 addresses share a /24 - the scope a DHCP host moves within"""
    return bool(ip_a and ip_b) and ip_a.split(".")[:3] == ip_b.split(".")[:3]
