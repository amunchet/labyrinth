# Labyrinth MCP Server

A Python MCP server that wraps existing backend endpoints (via `unwrap`) to manage hosts and services without exposing extra HTTP APIs.

## Architecture

The MCP server:
- Runs in its own Docker container alongside the backend
- Uses `unwrap()` to call Flask handlers directly, bypassing the Auth0 decorators
- Requires an `MCP_KEY` pre-shared secret on every request instead (see
  [Authentication](#authentication))
- Shares the same database (see `../../db/README.md` and the root
  `MONGO_MIGRATION.md` - `DB_BACKEND=postgres` by default, `mongo` fallback)
  and Redis instance as the backend
- Exposes tools for managing hosts, services, and reading metrics
- Speaks MCP streamable HTTP at `/mcp`, proxied from outside by Caddy

## Prerequisites
- Python 3.11+
- Access to the same database/Redis the backend uses (`DB_BACKEND`,
  `POSTGRES_*` or `MONGO_*`, `REDIS_HOST` envs)
- Dependency: `mcp<2` plus backend requirements (this directory's own
  `requirements.txt` is a separate copy - keep its `pymongo`/`psycopg2` pins in
  sync with `backend/requirements.txt`). The SDK renamed `FastMCP` to
  `MCPServer` in 2.x and removed `mcp.server.fastmcp`, so the major version is
  pinned.

## Run locally
```bash
export PYTHONPATH=$(pwd)/backend
export MCP_KEY=some-long-random-secret
pip install -r backend/ai/mcp/requirements.txt
python backend/ai/mcp/server.py
```

Environment variables:
- `MCP_KEY` (**required** - see [Authentication](#authentication); the server
  refuses to start without it)
- `MCP_PORT` (default 8765)
- `MCP_HOST` (default 0.0.0.0) - uvicorn's bind address
- `MCP_ALLOWED_HOSTS`, `MCP_ALLOWED_ORIGINS` (both optional - see
  [Host header checking](#host-header-checking))
- `DB_BACKEND` (default `postgres`)
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` (when `DB_BACKEND=postgres`)
- `MONGO_HOST`, `MONGO_USERNAME`, `MONGO_PASSWORD` (when `DB_BACKEND=mongo`)
- `REDIS_HOST`
- `LABYRINTH_URL` - public base URL of the Labyrinth UI (e.g. `https://labyrinth.example.com`), used to build Deploy page deep links; without it links are relative (`/deploy?request=...`)
- The container mounts `backend/uploads` read-only at `/src/uploads` so it can read playbooks and become files

`server.py` loads `backend/.env` explicitly before importing `serve`, so in
production `MCP_KEY` and the Mongo credentials can live there alongside
`TELEGRAF_KEY` rather than being passed through compose.

## Authentication

Every tool call goes through `unwrap()`, which strips the Auth0 decorators off
the Flask handlers. Nothing else stands between a request and a write to the
`hosts` or `services` collections, so the server requires a pre-shared secret on
every HTTP request and refuses to start if `MCP_KEY` is unset or blank.

Present the secret one of three ways:

```
X-MCP-Key: <MCP_KEY>
Authorization: Bearer <MCP_KEY>
Authorization: <MCP_KEY>          # bare form, matching serve.py's TELEGRAF_KEY
```

Anything else gets `401 {"error": "unauthorized"}`. The check is applied as ASGI
middleware wrapping the whole app, so a newly added tool cannot end up outside
it. Comparison is constant-time.

Generate a key with `openssl rand -hex 32`. The development compose file hard-codes
`MCP_KEY: development`, which is fine for a local stack and must not be used
anywhere reachable.

## Host header checking

If a client gets `421 Invalid Host header`, this is the setting behind it.

The MCP SDK has DNS-rebinding protection that it enables automatically whenever
FastMCP's own `settings.host` is a loopback address - and it is, because
`MCP_HOST` is uvicorn's bind address, which FastMCP never sees, so its host
stays at the `127.0.0.1` default. Left alone, that rejects every request whose
`Host` header is not `127.0.0.1` or `localhost`, which is every request that
arrives through Caddy under a real domain.

`server.py` therefore passes the policy explicitly instead of inheriting it, so
it no longer depends on what `MCP_HOST` happens to be. The check is **off by
default**: it is there to protect unauthenticated servers bound to loopback
from malicious pages in a browser, whereas this server is deliberately
reachable and guarded by `MCP_KEY`.

To turn it back on, pin the hosts you serve:

```
MCP_ALLOWED_HOSTS=labyrinth.example.com
MCP_ALLOWED_HOSTS=labyrinth.example.com,localhost:*   # comma-separated; host:* allows any port
```

`MCP_ALLOWED_HOSTS` is what enables the check. `MCP_ALLOWED_ORIGINS` only
narrows it further and does nothing on its own; when the check is on and that
list is empty, a request carrying any `Origin` header is refused with `403`,
which matters for browser-based clients but not for typical agents.

## Accessing it from an external system

The container publishes no ports; it is reachable at `mcp:8765` on the
`labyrinth` Docker network. External access goes through Caddy, which already
proxies `/mcp*` to it (`caddy/Caddyfile.sample`), so the endpoint is:

```
https://<your-domain>/mcp
```

Development uses the same path on the Caddy dev port: `https://localhost:7210/mcp`
(accept the internal dev CA first).

The transport is MCP streamable HTTP. Registering it with Claude Code:

```bash
claude mcp add --transport http labyrinth https://<your-domain>/mcp \
  --header "X-MCP-Key: <MCP_KEY>"
```

Or in an MCP client config file:

```json
{
  "mcpServers": {
    "labyrinth": {
      "type": "http",
      "url": "https://<your-domain>/mcp",
      "headers": { "X-MCP-Key": "<MCP_KEY>" }
    }
  }
}
```

Quick check that the secret is being enforced - the first should 401, the
second should not:

```bash
curl -i https://<your-domain>/mcp
curl -i -H "X-MCP-Key: $MCP_KEY" \
     -H "Accept: application/json, text/event-stream" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
     https://<your-domain>/mcp
```

Publishing port 8765 directly instead is possible but serves plaintext HTTP on
every interface; routing through Caddy keeps TLS and one ingress point.

## Docker (included in docker-compose)

The MCP server is automatically started with the rest of Labyrinth:

```bash
# Development
docker-compose -f docker-compose-development.yml up -d

# Production
docker-compose -f docker-compose-production.yml up -d
```

The service runs on port 8765 internally and is accessible to other containers on the `labyrinth` network.

## Manual Docker build/run
```bash
docker build -f backend/ai/mcp/Dockerfile -t labyrinth-mcp .
docker run --rm -p 8765:8765 \
  -v "$(pwd)/backend:/app/backend" \
  -e MCP_KEY=some-long-random-secret \
  -e MONGO_HOST=... -e MONGO_USERNAME=... -e MONGO_PASSWORD=... \
  -e REDIS_HOST=redis \
  labyrinth-mcp
```

`.env` files are excluded from the build context (root `.dockerignore`) so
secrets are not baked into an image layer, which is why the bind mount is
needed - it is how the compose services get `backend/.env` too. Without it,
pass everything `backend/.env` would have supplied (`AUTH0DOMAIN` included,
which `common/auth.py` requires at import) as `-e` flags.

## Tools exposed

### Host Management
- `mcp_list_hosts` - List all hosts
- `mcp_get_host(host_key)` - Get a single host by MAC or IP
- `mcp_create_or_update_host(host_json)` - Create/update a host (JSON string)
- `mcp_add_service_to_host(host_key, service_name)` - Add a service to a host
- `mcp_remove_service_from_host(host_key, service_name)` - Remove a service from a host
- `mcp_replace_host_services(host_key, services_json)` - Replace entire services list (JSON array string)
- `mcp_delete_host(host_key)` - Delete a host; uplinks to it and its map placements are dropped
- `mcp_list_tags` / `mcp_list_hosts_by_tag(tag)` / `mcp_set_host_tags(host_key, tags)` - Tags (comma-separated)
- `mcp_set_service_level(host_key, service, level)` - Report one host's failing service as `warning`/`error`; blank clears

### Service Management
- `mcp_list_services(include_full)` - List services (names only or full records)
- `mcp_create_or_update_service(service_json)` - Create/update a service definition (JSON string)
- `mcp_get_service(name)` - One service's full definition

### Metrics
- `mcp_read_metrics(host_key, service, count)` - Read latest metrics for a host
- `mcp_get_metric_counts(host_key)` - Telegraf ingest counters for a host

### Subnets and Groups
- `mcp_list_subnets` / `mcp_get_subnet(subnet)` - Subnet prefixes / one subnet's settings
- `mcp_save_subnet(subnet_json)` - Create or update a subnet; fields left out keep their values
- `mcp_delete_subnet(subnet)` - Delete a subnet record (its hosts stay)
- `mcp_list_groups(subnet)` - A subnet's host groups with member IPs
- `mcp_update_group(subnet, group, new_name, monitor, icon, add_service, remove_service)` - Group-wide changes

### Locations and Inventory
Hosts double as the device inventory (servers, VMs/LXCs, PCs, switches, bridges, PLCs, ...), including IP-less "label" devices such as unmanaged switches.
- `mcp_list_locations` - List locations (sites/buildings) with their racks
- `mcp_save_location(location_json)` - Create a location, or update/rename one by including its `_id`
- `mcp_delete_location(name)` - Delete a location; its devices, subnets and maps become unassigned (not deleted)
- `mcp_get_inventory(location, device_type, status)` - Devices with live status (optionally filtered), plus locations and the Proxmox node -> VM/LXC tree
- `mcp_set_device_inventory(host_key, fields_json)` - Change only a device's inventory fields (location, rack, type, uplink, ...); blank values clear a field
- `mcp_check_device(host_key)` - Ping (or TCP-check) a device right now and record the result

### Location Maps
A map is a floor plan image with devices placed on it. Positions are percentages (0-100) of the image's width and height from its top-left corner, so they don't depend on the image's resolution.
- `mcp_list_maps(location)` - Maps, optionally for one location (`legacy` = old-editor map without placements)
- `mcp_get_map(name)` - One map with its placements and each placed device's name/IP/type
- `mcp_list_map_images` / `mcp_get_map_image(name, max_size)` - Uploaded floor plans; the image comes back as JPEG content the agent can look at
- `mcp_save_map(map_json)` - Create/update a map (`name`, `location`, `background_image`, `default`, `placements`); `previous_name` renames; only one map is the Home default
- `mcp_place_devices(map_name, placements_json, remove)` - Place/move some devices (by key, MAC or IP) or take them off, leaving the rest
- `mcp_delete_map(name)` - Delete a map (devices and image file stay)

Images are uploaded and deleted in the UI; the MCP container mounts uploads read-only.

### Alerts and Monitoring Reports
- `mcp_list_alerts` / `mcp_resolve_alert(fingerprint)` - Active Alertmanager alerts / resolve one
- `mcp_get_proxmox_disk_space(refresh)` - Proxmox storage/VM/LXC usage (cached unless `refresh`)
- `mcp_get_proxmox_telegraf_check(stale_minutes)` / `mcp_get_proxmox_graylog_check` - Guests not reporting Telegraf metrics / not forwarding to Graylog
- `mcp_list_proxmox_clusters` - Configured clusters, without token secrets
- `mcp_get_ec2_instances` - EC2 instances across AWS accounts with host matches

Deliberately not exposed: credentials and secrets (settings, Telegraf key, Alertmanager config, Proxmox/AWS account create/update, AI settings), service deletion (it removes snippet files, which the MCP container can't write), network scans (nmap runs in the cron container), and running Ansible directly (a human launches runs from the Deploy page).

### Ansible Deployments and Conversations
- `mcp_list_playbooks` / `mcp_get_playbook(name)` - List / read saved playbooks
- `mcp_list_become_files` - List vault-encrypted become files a deployment can use
- `mcp_start_conversation(title, message, needs_response)` - Open a conversation with the human, optionally with a first message or question
- `mcp_send_message(conversation_id, text, needs_response)` - Post a message; `needs_response=true` makes it a question that flags and alerts the human
- `mcp_prepare_deployment(hosts, playbook, become_file, playbook_content, ssh_key, notes, conversation_id)` - Stage a deployment into a conversation (a new one when `conversation_id` is blank) and get a `deploy_url` deep link; a blank `become_file` lets the human pick
- `mcp_wait_for_response(conversation_id, since, timeout_seconds)` - Wait for the human's turn: a reply, a declined deployment, a finished run, or closing the conversation
- `mcp_get_conversation(conversation_id)` / `mcp_list_conversations(waiting_only)` - Full history / recent conversations
- `mcp_close_conversation(conversation_id, summary)` - Close a finished conversation
- `mcp_get_deployment_request(request_id)` - A staged deployment plus the runs launched from it
- `mcp_list_deployments(limit)` - Recent runs, newest first (no logs)
- `mcp_get_deployment(job_id, log_tail)` - One run's status, outcome, per-host stats, failed tasks and log tail

The MCP server never runs playbooks itself: the agent stages and asks, and a human holding the vault password decides. That work happens in a **conversation**, a recorded thread the human sees under Conversations in the UI:

1. The agent opens one with `mcp_start_conversation` (or lets `mcp_prepare_deployment` open it), checks `mcp_list_become_files`, writes a playbook, and stages it with `mcp_prepare_deployment`: target hosts (IPs or MACs), a playbook name, a become file (or blank for the human to choose), notes on what and why, and optionally the generated `playbook_content`. Generated content must pass `ansible_helper.validate_ai_playbook`: `hosts: all`/`clients` only, no `vars_files`, no cleartext passwords, no target hosts embedded in the YAML. It may replace an earlier *generated* playbook of the same name, never one a human wrote.
2. Staging a deployment, or sending a message with `needs_response=true`, marks the conversation as waiting on the human: the Conversations nav item shows a badge, and an `Agent needs a response` alert goes to Alertmanager (labels `service` = conversation title, `instance` = `<conversation id>/<message id>` so every ask is its own alert; its `generatorURL` is the deploy link or the conversation page; when it is delivered follows your Alertmanager route's grouping). If Alertmanager can't be reached the result says `notified: false` and the badge still shows.
3. The human opens `deploy_url`. The Deploy page shows a "Prepared Deployment" card with the hosts, notes and the playbook for review, a become file picker (preset to the agent's choice), and asks only for the vault password. On Deploy, the backend saves the staged content (become file attached to `vars_files`, checked with `ansible-playbook --check`) and starts the run, so what runs is exactly what was staged. From the conversation page they can instead decline it, reply, or close the conversation.
4. The agent calls `mcp_wait_for_response`. It returns as soon as the human or Ansible takes a turn after the agent's last message - a reply, a decline, a closed conversation, or a `run` message carrying the outcome, per-host stats and failed tasks - or after `timeout_seconds` (default 300, max 1800) with `answered: false`, in which case it calls again. A human merely launching the run does not end the wait; `runs_in_progress` lists runs still going. Logs come from `mcp_get_deployment(job_id)`. The wait only holds a database connection while it checks (every 5 seconds), so it never starves other tools.

Conversations live in the `conversations` collection/table: `title`, `status` (`open`/`closed`), `messages` (each with `author` agent/human/system and a `kind`: `message`, `question`, `deploy`, `reply`, `launched`, `declined`, `run`, `closed`), and `pending` (open questions and unlaunched deployments the human still owes, changed only by atomic `$push`/`$pull` so concurrent posts cannot undo each other). `needs_human` (open, with anything pending) is derived when read. Every run (Deploy page or MCP-staged) is recorded in `ansible_runs`: `status` (`queued`/`running`/`completed`/`error`), `outcome` (`success` only when the play recap shows no failed or unreachable hosts), `stats`, `failures`, and the log tail (capped at ~1MB). Staged deployments live in `ansible_requests`. Runs and staged deployments carry the `conversation_id` they belong to. Vault passwords are never stored.

Deploy deep links also work without staging: `/deploy?ips=10.0.0.5,10.0.0.6&playbook=<name>&become=<file>[&ssh=<key>]`. The Deploy page has a "Copy deploy link" button that builds one from the current selection.

## Host Schema

When creating/updating hosts, use this structure:
```json
{
  "ip": "192.168.1.100",
  "mac": "00:11:22:33:44:55",
  "subnet": "192.168.1",
  "host": "server1.local",
  "group": "Linux Servers",
  "icon": "linux",
  "services": ["open_ports", "closed_ports", "check_cpu"],
  "open_ports": [22, 80, 443],
  "class": "health",
  "monitor": true
}
```

`mac` is the host key. Omit it to key a device by its IP (or, for an IP-less device, to generate a key); `subnet` is derived from the IP when omitted.

Optional inventory fields:
```json
{
  "device_type": "server | vm | lxc | pc | laptop | switch | router | firewall | ap | bridge | plc | iot | camera | printer | phone | ups | storage | patch-panel | other",
  "location": "Main Office",
  "rack": "Rack A",
  "rack_unit": 10,
  "rack_height": 2,
  "vendor": "Ubiquiti",
  "model": "USW-Pro-24",
  "serial": "...",
  "uplink": "<key of the device it connects up to>",
  "link_type": "ethernet | fiber | wireless | vpn",
  "proxmox_node": "pve1",
  "proxmox_vmid": 105
}
```

## Inventory Status

`mcp_get_inventory` rolls each device into one `status`:
- `up` / `down` - reachability from the minute-by-minute ping (or TCP check when `check_alive_port` is set). A host that drops pings but reports healthy metrics counts as `up`.
- `error` / `warning` - reachable, but services are failing (warning-level or stale services are `warning`)
- `unknown` - has an IP but no recent check yet
- `none` - no IP; a labelled device that is not monitored

A device's `location` is its own, else that of the Proxmox node it runs on (VMs/LXCs), else that of its subnet (`location_source` says which).

## Service Schema

Port service example:
```json
{
  "name": "port_ssh",
  "display_name": "SSH Port Check",
  "type": "port",
  "port": 22,
  "state": "open"
}
```

Check service example:
```json
{
  "name": "check_cpu",
  "display_name": "CPU Check",
  "type": "check",
  "metric": "cpu",
  "field": "usage_user",
  "comparison": "greater",
  "value": 80,
  "tag_name": "cpu",
  "tag_value": "cpu-total"
}
```

## Notes

- Uses `unwrap()` to call Flask handlers directly, bypassing Auth0 - which is why
  the `MCP_KEY` pre-shared secret is mandatory
- Host/service operations persist via the shared database client in `backend/serve.py` (`serve.db`, see `../../db/README.md`)
- Services attached to hosts use the `display_name` field
- No deployment automation - all changes prepare services/metrics for manual deployment
