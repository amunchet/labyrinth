# Changelog: MCP Server

- Armada session: `MCP Server`
- Branch: `armada/MCP-Server-200b93`
- Base branch: `master`
- Started: 2026-08-31 19:29 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-08-31 19:45 UTC
Made the MCP server actually reachable from outside the Docker network, behind a
pre-shared secret.

The service was unreachable and, as configured, could not have served HTTP at all:

- `backend/ai/mcp/requirements.txt` pinned `modelcontextprotocol`, a third-party
  scaffolding CLI rather than the official SDK. It pulled `mcp` in transitively and
  unpinned, so a fresh build resolved to mcp 2.x, where `mcp.server.fastmcp` is gone
  (`FastMCP` became `MCPServer`) - both `except ImportError` branches in `server.py`
  fired and the process exited. Now pinned to `mcp>=1.2,<2`.
- The Dockerfile served `server:app`, but `FastMCP` is not an ASGI application. Added
  `create_http_app()`, which materialises the streamable HTTP transport via
  `streamable_http_app()` (endpoint at `/mcp`), and switched the CMD to
  `uvicorn ai.mcp.server:create_http_app --factory`, honouring `MCP_HOST`/`MCP_PORT`.
- Neither compose file published a port and Caddy had no route, so nothing outside the
  `labyrinth` network could reach it. Added a `handle /mcp*` reverse proxy to both
  Caddyfiles - `handle`, not `handle_path`, so the prefix FastMCP mounts on survives.
  Ingress stays on Caddy, so the port is still not published.

Every tool reaches the backend through `unwrap()`, which strips the Auth0 decorators
off handlers that include host and service writes. Exposing that unauthenticated was
not an option, so `backend/ai/mcp/auth.py` adds a pre-shared secret (`MCP_KEY`) checked
as ASGI middleware around the whole app - a new tool cannot be added outside the check.
It accepts `X-MCP-Key`, `Authorization: Bearer <key>`, and the bare `Authorization:
<key>` form `serve.py` already uses for `TELEGRAF_KEY`; comparison is constant-time,
and the server refuses to start if the key is unset or blank rather than falling back
to open access. Lifespan messages pass through unchecked, or the session manager never
starts.

`server.py` now loads `backend/.env` itself on startup. The bare `load_dotenv()` in
`common/auth.py` reads the working directory, which is `/app` in this container rather
than `/app/backend`, so that file was never picked up here at all. A plain
`load_dotenv()` would not have been enough either: it leaves variables that are already
set, and compose substitutes an unset `${MCP_KEY}` as an empty string rather than
omitting it, so blank is treated as absent. `MCP_KEY` can therefore live in the root
`.env` (wired through prod compose, matching how `POSTGRES_PASSWORD` is handled) or in
`backend/.env`; the dev compose file sets it inline.

The middleware is covered by `backend/test/test_18_mcp_auth.py` (23 tests). It is
deliberately stdlib-only - no Starlette, no `mcp` - so the backend suite can exercise
it without the MCP runtime installed.

## 2026-08-31 20:35 UTC
Merged `origin/master` (Mongo -> Postgres migration, the AI agent work, and the
`LabyrinthClient` extraction into `ai/mcp/client.py`) into the branch and resolved the
conflicts it created in `server.py`, both env samples, `docker-compose-production.yml`,
`CLAUDE.md`, and the MCP README.

The three startup and reachability problems were untouched on master, so all of the
above still applies: `requirements.txt` still pinned `modelcontextprotocol`, the
Dockerfile still served the non-ASGI `server:app`, and neither Caddyfile had an MCP
route. `server.py` now takes master's `from ai.mcp.client import LabyrinthClient` in
place of the inline client, and the dotenv load runs ahead of it since that import is
what pulls in `serve`.

Master already passes `POSTGRES_*` through to the `mcp` service and made the database
handle lazy, so the credential gap that motivated the dotenv load is narrower now - it
still matters for `MCP_KEY` and anything else kept in `backend/.env`.

## 2026-08-31 21:40 UTC
Fixed `421 Invalid Host header`, which made the server unreachable through Caddy - the
exact thing the previous commits set out to enable.

The MCP SDK enables DNS-rebinding protection by itself whenever FastMCP's own
`settings.host` is a loopback address, and ours was: `MCP_HOST` is uvicorn's bind
address, which FastMCP never sees, so its host stayed at the `127.0.0.1` default. The
resulting allowlist is `127.0.0.1:*`/`localhost:*`/`[::1]:*`, so every request whose
`Host` is a real domain - which is every request through Caddy - got a 421.

`server.py` now passes `transport_security` explicitly rather than inheriting the
auto-enable, so the policy no longer depends on what `MCP_HOST` happens to be. The
check is off by default: it guards unauthenticated loopback servers against malicious
pages in a browser, while this server is deliberately reachable and guarded by
`MCP_KEY`. `MCP_ALLOWED_HOSTS` turns it back on scoped to named hosts (comma-separated,
`host:*` wildcards); `MCP_ALLOWED_ORIGINS` narrows it further and does nothing alone.
The parsing lives in `auth.py` with the rest of the stdlib-only, testable config.

Worth recording why this got through: the earlier end-to-end checks all ran from inside
the container against `http://127.0.0.1:8765/mcp`, so the Host header was the one value
the allowlist accepted. They confirmed the auth matrix and the tool list while being
blind to the only thing that mattered for external access. The verification now sends
an explicit non-loopback Host header.

## 2026-08-31 21:36 UTC
Fixed `mcp_read_metrics` failing every call with a response-schema validation error.

`serve.read_metrics` ends in `json.dumps(retval, default=str)` where `retval` is a list
comprehension over a Mongo cursor, so `client.get_metrics` hands back a list. Both it
and the tool were annotated `-> Dict[str, Any]`. FastMCP builds each tool's output
schema from the return annotation and validates the result against it, so the tool
answered:

```
Error executing tool mcp_read_metrics: 1 validation error for mcp_read_metricsOutput
result
  Input should be a valid dictionary [type=dict_type, input_value=[], input_type=list]
```

Note `input_value=[]` - this failed even with no metrics to return, so the tool was
unusable rather than intermittently wrong.

Both annotations are now `List[Dict[str, Any]]`. The other eight tools were audited
through the live protocol; `mcp_list_hosts` and both `mcp_list_services` variants were
already correct, so this was the only instance.

It survived earlier testing because `ai/agent_tools.py` wraps the same client call as
`{"metrics": client.get_metrics(...)}`, so the in-process chat agent receives a dict
and works; only the MCP tool returns it raw.

Covered by `backend/test/test_18_mcp_metrics_schema.py`. Because `server.py` cannot be
imported without the `mcp` package, the tool's annotation is pinned by reading the
source with `ast` - the annotation generates the wire schema, so it is load-bearing
rather than decoration. Reverting both annotations makes 3 of the 7 tests fail, which
is the check that they actually cover the bug.
