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
