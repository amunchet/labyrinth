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
