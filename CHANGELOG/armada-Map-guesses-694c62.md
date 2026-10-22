# Changelog: Map guesses

- Armada session: `Map guesses`
- Branch: `armada/Map-guesses-694c62`
- Base branch: `master`
- Started: 2026-10-22 08:16 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-22 13:16 CDT
Brought the MCP server up to what the UI can do, so an agent can manage location maps end to end.
New map tools list, read, save, rename and delete maps, place/move/remove devices by key or IP
(positions are image percentages, validated 0-100 against existing devices, locations and images),
and return an uploaded floor plan as a scaled JPEG the agent can look at. Also added: host delete,
tags and per-host service levels, subnet and group management, service and ingest-counter reads,
Alertmanager alert list/resolve (the MCP container now mounts `alertmanager/` read-only for the
password), Proxmox disk/Telegraf/Graylog reports and clusters, and EC2 instances. Secrets, service
deletion, scans and direct Ansible runs remain UI-only. Tested on both Mongo and Postgres.

## 2026-10-22 13:35 CDT
Fixed the new MCP tool tests erroring in the full suite on Postgres ("connection pool is closed"):
they cached a database handle at import, which `test_27_db_connections` invalidates when it closes
the shared client. They now go through the lazy `serve.db` on every use, like the other tests.

## 2026-10-22 15:33 CDT
Data-only change in the live Labyrinth through the new MCP map tools; no code changed. Named all 36
UniFi switches/APs from the UniFi controller lists, set their type (switch/ap), location, vendor,
model and the uplinks UniFi reports (switch ports; mesh APs as wireless), and placed them on the
North and South ("Plant Map") maps. Floor plan orientation was derived from the OpenStreetMap
footprints of both addresses: North's plan is rotated 180 degrees (top = south), South's is rotated
90 degrees (top = east, Church Street side). Positions within each area are estimates for a human
to fine-tune in the map editor.
