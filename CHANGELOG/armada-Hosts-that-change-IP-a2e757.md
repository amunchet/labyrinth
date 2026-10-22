# Changelog: Hosts that change IP

- Armada session: `Hosts that change IP`
- Branch: `armada/Hosts-that-change-IP-a2e757`
- Base branch: `master`
- Started: 2026-10-22 02:34 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-21 21:36 CT
Fast-forwarded the session branch to current `master` (it was 55 commits behind, including the Postgres migration and inventory work) before starting the hostname-as-identity design. Replaced the Armada policy text that another session had committed into `CLAUDE.md` with the Flagship-managed pointer to `CLAUDE.local.md`. No application code changed.

## 2026-10-21 23:04 CT
Hostnames are now the first thing a host is identified by, so DHCP devices (clients, APs, some routers) can be monitored without reserved IPs.
- `finder.py` `reconcile_hosts`: scanned hosts match on hostname first (within the /24, and only when the name answers at one IP in that scan), then real MAC, then IP. A host that moved keeps its record and key, and only its `ip` changes, so Telegraf metrics tagged with the key keep matching. Unnamed records pick up their DNS name. A new device on a moved host's old IP gets a generated `device-` key instead of overwriting the moved host.
- Duplicates are merged on scan. Same-name records in a /24 merge into the best configured one, and unreviewed scanner copies (unmonitored, unnamed or still flagged `new_host`) at the same IP fold into the configured host there. A configured host is never deleted just for sharing an IP, and `new_host` is never carried onto the survivor. A dry run on the production snapshot merges 875 records down to 860, covering the 9 hand-moved monitored hosts and their scanner copies plus the `DESKTOP-D27UII6`/`KasongosiPhone8`/`client-virtual-machine` DHCP duplicates.
- `alive.py`: hosts are checked at the address their hostname resolves to, falling back to the stored IP when DNS fails or answers outside the host's /24 (search-domain and Docker service-name collisions). Alerts are labeled with the hostname.
- MCP `mcp_get_host` also accepts an unambiguous hostname.
