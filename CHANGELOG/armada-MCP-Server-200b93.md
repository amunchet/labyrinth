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

`server.py` now calls `load_dotenv(BACKEND_ROOT / ".env")` before importing `serve`.
The bare `load_dotenv()` in `common/auth.py` reads the working directory, which is
`/app` in this container rather than `/app/backend`, so in production the Mongo
credentials were never loaded and `serve.py` would have built a
`mongodb+srv://None:None@None` URI. `MCP_KEY` can live in `backend/.env` alongside
them; the dev compose file sets it inline instead.

The middleware is covered by `backend/test/test_18_mcp_auth.py` (23 tests). It is
deliberately stdlib-only - no Starlette, no `mcp` - so the backend suite can exercise
it without the MCP runtime installed.
