# Changelog: Updating Layouts

- Armada session: `Updating Layouts`
- Branch: `armada/Updating-Layouts-bdcf75`
- Base branch: `master`
- Started: 2026-10-17 07:14 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-17 03:17 CDT
Data-only change in the live Labyrinth instance through the MCP server; no code changed.
Added a North location (116 Neal Drive Rantoul IL 61866), then assigned a curated set of
hosts by IP: 192.168.9.x / 192.168.10.x to North (80 hosts) and 192.168.0.x to South
(48 hosts). Hosts were triaged by Telegraf services, user-assigned group, monitor/display
flags, Proxmox membership, and the latest nmap sighting: its timestamp, ports and reverse
DNS name. Phones, tablets, PCs, generic IoT, duplicate records and anything not seen in 30
days were left unassigned. Locations are set per host, not per subnet, so that DHCP noise
does not inherit a location. Also cleared nine stale South assignments on unnamed
scan-artifact records (192.168.0.100, .101, .111, .119, .125, .130, .133, .136, .177).

## 2026-10-18 03:24 CDT
Stop treating a host's IP as its identity. Most addresses are DHCP and nmap sees no
MACs from inside Docker, so nearly every host was keyed by IP: a lease change created a
second record, and the old one went on describing whichever device got the address next.
New `backend/host_identity.py`, used by the finder, matches each scanned device by real
MAC, then reverse-DNS hostname (stored separately as `resolved_hostname`, so renaming a
host never changes how it is recognised), then IP. Hosts found at a new address move
there; IP-shaped keys are replaced by generated `device-` keys, carrying uplinks and map
placements along. A host left on an address that now belongs to another device is
displaced (IP cleared, `previous_ip` kept) instead of collecting that device's metrics,
pings and alerts; nothing is deleted. Address-derived and shared default names are
ignored as identity. Saving a host without a MAC no longer mints an IP key, reading
metrics by a generated key falls back to the host's current IP, and the device card
shows a displaced device's last IP.
