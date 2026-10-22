# Changelog: Fix Labyrinth issues

- Armada session: `Fix Labyrinth issues`
- Branch: `armada/Fix-Labyrinth-issues-36cfaa`
- Base branch: `master`
- Started: 2026-10-22 03:54 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-22 00:47 CDT
Audited all 114 monitored Labyrinth hosts against nmap scan history, Graylog (north/south) and GitHub repos, then corrected live Labyrinth data (no code change). Each change was confirmed by two independent verifiers and is recorded in the host's notes as "2026-10-22 (auto-audit)". The changes:
- Turned off monitoring on 34 obsolete or IP-reassigned records. Examples: old switch/AP IPs that now answer as iPhones, duplicate records for guacamole and balexandria, ESXI-Hypervisor, cubietruck, tina, template-clients, metabase.north.
- Updated expected open_ports on 7 hosts whose stable port set is explained by the service they run: pve1/pve4/proxmox 8006, the unifi controllers, graylog, and security.north 8000 for the rorshark callback.
Not changed: most of the remaining port noise is "No metric received". Port checks treat scans older than 10000s as stale, but finder.py rescans each subnet only every 4-8h (north) or every few days (south). This needs a decision on the stale window or the scan cadence.

## 2026-10-22 01:18 CDT
Made the stale window for open/closed port checks configurable via a new `port_stale_hours` setting (Settings > Monitoring tab), defaulting to 12 hours instead of the hard-coded 10000s (~2.8h). finder.py rescans each subnet only every 4-8h in the north and less often in the south, so healthy hosts were constantly alerting "No metric received". Both the dashboard/alerting path and the latest-value `/metrics/<host>/open_ports/latest` judgement use the setting (history rows are still never judged stale). Unparseable or non-positive values fall back to 12h.
