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
