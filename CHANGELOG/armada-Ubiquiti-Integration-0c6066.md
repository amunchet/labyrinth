# Changelog: Ubiquiti Integration

- Armada session: `Ubiquiti Integration`
- Branch: `armada/Ubiquiti-Integration-0c6066`
- Base branch: `master`
- Started: 2026-11-13 20:20 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-11-13 15:16 CST
UniFi integration, alongside Proxmox and AWS: a **UniFi** page (Network, Cameras, Settings) and a once-a-minute cron job (`cron/unifi_refresh.sh` -> `backend/unifi_helper.py`).
- Controllers (UniFi OS consoles or self-hosted Network applications) are stored in a new `unifi_controllers` collection/table, signed in by API key or a local account; secrets are never returned. Each UniFi site maps to a Labyrinth location, and sites can be left unmonitored.
- Switch ports come from the Network application's own API (`stat/device`, `stat/sta`): Ubiquiti's official Integration API (checked against its v11 spec) names a client's switch but never the port. Login sessions are kept in Redis and a refused login pauses retries for 5 minutes, since UniFi OS rate-limits logins.
- Snapshots are cached in Redis; an unreachable controller keeps its last data (flagged stale), and clients that disconnect stay at their last port for `UNIFI_CLIENT_MEMORY_DAYS` (30) so powered-off servers keep their place.
- Inventory: UniFi devices and Protect cameras are added as (unmonitored) hosts; hosts seen at a site inherit its location; device cards show the switch and port a device is plugged into, and a switch's ports with what is on each; UniFi's offline/connected state decides reachability; maps draw UniFi uplinks.
- Racks: devices plugged into a racked switch are suggested for that rack at the nearest free U (one click or "Place all"), skipping shared ports (VMs, desk switches) and devices that live elsewhere by type.
- Alerts with notification backoff: one "UniFi Device Offline" per outage (devices behind it are counted, not alerted separately), "UniFi Camera Offline" (light Protect monitoring), and controller/Protect unreachable.
- MCP: `mcp_get_unifi`, and `mcp_get_inventory` now includes each device's UniFi details.
