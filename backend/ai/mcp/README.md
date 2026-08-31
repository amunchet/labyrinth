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

### Service Management
- `mcp_list_services(include_full)` - List services (names only or full records)
- `mcp_create_or_update_service(service_json)` - Create/update a service definition (JSON string)

### Metrics
- `mcp_read_metrics(host_key, service, count)` - Read latest metrics for a host

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

- Uses `unwrap()` to call Flask handlers directly, bypassing Auth0 - which is why
  the `MCP_KEY` pre-shared secret is mandatory
- Host/service operations persist via the shared database client in `backend/serve.py` (`serve.db`, see `../../db/README.md`)
- Services attached to hosts use the `display_name` field
- No deployment automation - all changes prepare services/metrics for manual deployment
