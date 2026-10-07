# Changelog: Inventory Management

- Armada session: `Inventory Management`
- Branch: `armada/Inventory-Management-1dccc1`
- Base branch: `master`
- Started: 2026-10-07 17:56 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-07 14:12 CDT (19:12 UTC)
Fixed custom dashboards being unusable. Listing dashboards returned a 404 when
none existed yet, so the UI errored on first use; it now returns an empty list
(a named dashboard that does not exist still 404s). Image uploads (dashboard
map graphics and icons) silently failed because `apiPost` set a
`multipart/form-data` header by hand, which drops the multipart boundary since
the switch from axios to fetch; the browser now sets the header itself.

## 2026-10-07 14:41 CDT (19:41 UTC)
Backend for physical inventory: locations (sites/buildings with racks), hosts
as devices, and live reachability.
- New `locations` collection with CRUD (`/locations/`, `/location/`). Names are
  unique; renames carry over to hosts, subnets and maps, rack renames keep
  their hosts, and deleting a location unassigns rather than deletes.
- Hosts accept optional inventory fields (type, location, rack/U, vendor,
  model, serial, uplink + link type, Proxmox node/vmid), validated and coerced
  on save. `POST /host/<key>/inventory` updates only those fields.
- IP-less "label" devices (e.g. unmanaged switches) are supported: a blank MAC
  is keyed by IP like the finder does, or gets a generated key. Previously two
  hosts saved with a blank MAC overwrote each other.
- `alive.py` now checks every host with an IP in parallel each minute and
  records results in Redis, so anything pingable shows live status; alerts are
  still only for monitored hosts. Fixed port checks always failing (the UI
  stores the port as text) and an always-true port-check condition.
- `GET /inventory/` rolls each host's reachability and service health into one
  status, resolves its location (explicit, else its Proxmox node's, else its
  subnet's) and returns the cached Proxmox node -> VM/LXC tree matched to hosts.

## 2026-10-07 14:58 CDT (19:58 UTC)
MCP tools so an AI agent can manage the inventory: list/save/delete locations,
read the inventory with live status (filter by location, device type or
status), update a device's location/rack/type/uplink without touching its
monitoring setup, and run an on-demand reachability check. Creating a host
over MCP no longer requires a MAC (IP-keyed or generated), but refuses to
shadow a host already known by MAC. The MCP image now installs `ping`, which
the on-demand check needs. TCP reachability checks now time out after 2s; a
dead host previously held a check open for the OS connect timeout (~2 min).

## 2026-10-07 15:24 CDT (20:24 UTC)
New Locations page (nav: Locations) for buildings/sites, replacing the old
Settings > Custom Dashboards editor:
- Map tab: floor plans (uploaded images) with every device as a live status
  marker (up / unreachable / failing / warning / unchecked / no IP), placed by
  drag and drop at percentage positions so maps scale to any screen; uplinks
  between placed devices are drawn (fiber and wireless prominent, routine
  ethernet subtle); servers flag problems on their VMs/LXCs. A location with no
  floor plan yet automatically shows a board of all its devices. Maps saved by
  the old editor are converted when opened.
- Racks tab: rack elevations with drag-and-drop U placement, overlap warnings,
  and the Proxmox VMs/LXCs on a selected server with their host status.
- Devices tab: filterable list; the Unassigned view assigns devices to a
  location. Subnets can also be given a location (subnet editor) so all their
  hosts land there.
- The host editor gained an Inventory & Location section (type, location,
  rack/U, vendor/model/serial, uplink + link type, Proxmox node/VM ID), accepts
  devices without an IP, edits a copy (Cancel no longer leaks edits), and
  checks reachability right after saving.
- Home shows the default map (or a location board) with live status and now
  also on mobile.
Verified in headless Chromium against the real backend (auth bypassed in a
local-only harness): every view and the drag/drop, upload, create and assign
flows, with no console errors.

## 2026-10-07 15:31 CDT (20:31 UTC)
Documented locations, maps, racks and live reachability in the README (for
users) and CLAUDE.md (data model, `/inventory/` semantics, alive cron, MCP
tools).

## 2026-10-07 15:46 CDT (20:46 UTC)
Merged master (45 commits, including the move to PostgreSQL/TimescaleDB behind
the `backend/db/` adapter) into this branch and ported the inventory work onto
it: all new code goes through `serve.db`, avoids operators the Postgres adapter
does not support (`$nin`, `find_one_and_delete`, `replace_one`, dotted array
filters), compares `_id`s as text (Postgres ids are strings, so a location
update would otherwise have been rejected as a duplicate name), registers the
`locations` table with the Postgres schema bootstrap and copies it in
`migrate_to_postgres.py`. The new MCP tools moved to master's
`backend/ai/mcp/client.py`/`server.py` split. Conflicts in the host and subnet
editors, nav, routes and Settings keep both sides (Clone, ingest counters,
Do-not-scan, Problems page, AI Alerts). Backend suite passes on Postgres (the
inventory tests also on the Mongo fallback); frontend lint/tests/build pass.

## 2026-10-07 16:21 CDT (21:21 UTC)
Found in self-review: a device saved without an IP but with a subnet (e.g. an
IP cleared on an existing host, or an MCP call) would have crashed the whole
dashboard - and with it `/inventory/` and alerting - because the dashboard
orders a subnet's hosts by last octet. IP-less devices are now always stored
with no subnet, and every saved host has an `ip` key. Deploy-by-tag
(`/tags/<tag>`) also skips IP-less devices instead of returning "" (or
raising on hosts saved without an `ip` key) as a deploy target. Regression
tests cover both.
