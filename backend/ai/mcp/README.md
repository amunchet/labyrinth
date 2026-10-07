# Labyrinth MCP Server

A Python MCP server that wraps existing backend endpoints (via `unwrap`) to manage hosts and services without exposing extra HTTP APIs.

## Architecture

The MCP server:
- Runs in its own Docker container alongside the backend
- Uses `unwrap()` to call Flask handlers directly, bypassing auth decorators
- Shares the same MongoDB and Redis instances as the backend
- Exposes tools for managing hosts, services, and reading metrics

## Prerequisites
- Python 3.11+
- Access to the same MongoDB/Redis the backend uses (`MONGO_*`, `REDIS_HOST` envs)
- Dependency: `modelcontextprotocol` plus backend requirements

## Run locally
```bash
export PYTHONPATH=$(pwd)/backend
pip install -r backend/ai/mcp/requirements.txt
python backend/ai/mcp/server.py
```

Environment variables:
- `MCP_PORT` (default 8765)
- `MCP_HOST` (default 0.0.0.0)
- `MONGO_HOST`, `MONGO_USERNAME`, `MONGO_PASSWORD`
- `REDIS_HOST`

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
  -e MONGO_HOST=... -e MONGO_USERNAME=... -e MONGO_PASSWORD=... \
  -e REDIS_HOST=redis \
  labyrinth-mcp
```

## Tools exposed

### Host Management
- `mcp_list_hosts` - List all hosts
- `mcp_get_host(host_key)` - Get a single host by MAC or IP
- `mcp_create_or_update_host(host_json)` - Create/update a host (JSON string)
- `mcp_add_service_to_host(host_key, service_name)` - Add a service to a host
- `mcp_remove_service_from_host(host_key, service_name)` - Remove a service from a host
- `mcp_replace_host_services(host_key, services_json)` - Replace entire services list (JSON array string)

### Service Management
- `mcp_list_services(include_full)` - List services (names only or full records)
- `mcp_create_or_update_service(service_json)` - Create/update a service definition (JSON string)

### Metrics
- `mcp_read_metrics(host_key, service, count)` - Read latest metrics for a host

### Locations and Inventory
Hosts double as the device inventory (servers, VMs/LXCs, PCs, switches, bridges, PLCs, ...), including IP-less "label" devices such as unmanaged switches.
- `mcp_list_locations` - List locations (sites/buildings) with their racks
- `mcp_save_location(location_json)` - Create a location, or update/rename one by including its `_id`
- `mcp_delete_location(name)` - Delete a location; its devices, subnets and maps become unassigned (not deleted)
- `mcp_get_inventory(location, device_type, status)` - Devices with live status (optionally filtered), plus locations and the Proxmox node -> VM/LXC tree
- `mcp_set_device_inventory(host_key, fields_json)` - Change only a device's inventory fields (location, rack, type, uplink, ...); blank values clear a field
- `mcp_check_device(host_key)` - Ping (or TCP-check) a device right now and record the result

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

- Uses `unwrap()` to call Flask handlers directly - no HTTP auth required when running inside trusted network
- Host/service operations persist via existing Mongo client in `backend/serve.py`
- Services attached to hosts use the `display_name` field
- No deployment automation - all changes prepare services/metrics for manual deployment
