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
- `LABYRINTH_URL` - public base URL of the Labyrinth UI (e.g. `https://labyrinth.example.com`), used to build Deploy page deep links; without it links are relative (`/deploy?request=...`)
- The container mounts `backend/uploads` read-only at `/src/uploads` so it can read playbooks and become files

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

### Ansible Deployments
- `mcp_list_playbooks` / `mcp_get_playbook(name)` - List / read saved playbooks
- `mcp_list_become_files` - List vault-encrypted become files a deployment can use
- `mcp_prepare_deployment(hosts, playbook, become_file, playbook_content, ssh_key, notes)` - Stage a deployment and get a `deploy_url` deep link
- `mcp_get_deployment_request(request_id)` - A staged deployment plus the runs launched from it
- `mcp_list_deployments(limit)` - Recent runs, newest first (no logs)
- `mcp_get_deployment(job_id, log_tail)` - One run's status, outcome, per-host stats, failed tasks and log tail

The MCP server never runs playbooks itself. The intended hand-off is:

1. The agent writes a playbook and calls `mcp_prepare_deployment` with the target hosts (IPs or MACs), a playbook name, a become file, and optionally the generated `playbook_content`.
2. A human opens the returned `deploy_url`. The Deploy page arrives pre-filled, shows the generated playbook for review, and only needs the vault password. If content was staged, it's saved (validated, with the become file injected into `vars_files`) right before the run. **A staged playbook overwrites any existing playbook of the same name.**
3. The agent polls `mcp_get_deployment_request(request_id)` until a run shows `status` `completed`/`error`, then reads `mcp_get_deployment(job_id)` for failures and logs.

Every run, MCP-staged or not, is recorded in the Mongo `ansible_runs` collection: `status` (`queued`/`running`/`completed`/`error`), `outcome` (`success` only when the play recap shows no failed or unreachable hosts), `stats`, `failures`, and the log tail (capped at ~1MB). Staged deployments live in `ansible_requests`.

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

Required fields: `mac`, `subnet`

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
