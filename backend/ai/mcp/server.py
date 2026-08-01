"""
Labyrinth MCP server

Exposes tools to manage hosts and services via the existing Flask backend
functions (accessed through unwrap to bypass auth decorators for internal use).
Intended to run as a separate process/container alongside the backend.
"""

import asyncio
import json
import os
import sys
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make backend modules importable when running from backend/ai/mcp
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from ai.mcp.client import LabyrinthClient  # type: ignore

try:
    # Newer MCP versions
    from mcp.server.fastmcp import FastMCP as _FastMCP
except ImportError:
    try:
        # Older MCP versions
        from mcp.server.fastmcp import FastMCPServer as _FastMCP
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Unable to import MCP server runtime from `mcp.server.fastmcp` "
            f"({exc}). Ensure `modelcontextprotocol` is installed with a compatible version."
        ) from exc


client = LabyrinthClient()
app = _FastMCP("labyrinth-mcp")


@app.tool()
async def mcp_list_hosts() -> List[Dict[str, Any]]:
    """List all hosts in Labyrinth."""
    return client.list_hosts()


@app.tool()
async def mcp_get_host(host_key: str) -> Dict[str, Any]:
    """Fetch a single host by MAC or IP."""
    host = client.get_host(host_key)
    if not host:
        raise ValueError("Host not found")
    return host


@app.tool()
async def mcp_create_or_update_host(host_json: str) -> str:
    """Create or update a host. Provide a JSON object string."""
    host = json.loads(host_json)
    return client.create_or_update_host(host)


@app.tool()
async def mcp_add_service_to_host(host_key: str, service_name: str) -> Dict[str, Any]:
    """Attach a service (display_name) to a host."""
    return client.add_service_to_host(host_key, service_name)


@app.tool()
async def mcp_remove_service_from_host(
    host_key: str, service_name: str
) -> Dict[str, Any]:
    """Remove a service from a host."""
    return client.remove_service_from_host(host_key, service_name)


@app.tool()
async def mcp_replace_host_services(
    host_key: str, services_json: str
) -> Dict[str, Any]:
    """Replace the full services list for a host. Provide a JSON array string."""
    services = json.loads(services_json)
    if not isinstance(services, list):
        raise ValueError("services_json must decode to a list")
    return client.update_host_services(host_key, services)


@app.tool()
async def mcp_list_services(include_full: bool = False) -> List[Any]:
    """List services. Set include_full=true for full records."""
    return client.list_services(include_full=include_full)


@app.tool()
async def mcp_create_or_update_service(service_json: str) -> str:
    """Create or update a service definition. Provide a JSON object string."""
    service = json.loads(service_json)
    return client.create_or_update_service(service)


@app.tool()
async def mcp_read_metrics(
    host_key: str, service: str = "", count: int = 50
) -> Dict[str, Any]:
    """Read latest metrics for a host (optionally filtered by service)."""
    return client.get_metrics(host_key, service, count)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    port = int(os.environ.get("MCP_PORT", "8765"))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    print(f"Starting Labyrinth MCP server on {host}:{port}")
    # FastMCP is a Starlette app; serve via uvicorn for proper long-running operation
    uvicorn.run(app, host=host, port=port, log_level="info")
