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
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make backend modules importable when running from backend/ai/mcp
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from common.test import unwrap  # type: ignore
import serve  # type: ignore

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


class LabyrinthClient:
    """Thin wrapper around existing backend functions using unwrap."""

    def list_hosts(self) -> List[Dict[str, Any]]:
        raw, status = unwrap(serve.list_hosts)()
        if status != 200:
            raise RuntimeError(f"list_hosts failed with status {status}")
        return json.loads(raw)

    def get_host(self, host_key: str) -> Optional[Dict[str, Any]]:
        # Try MAC/IP lookup directly for flexibility
        found = serve.mongo_client["labyrinth"]["hosts"].find_one(
            {"$or": [{"mac": host_key}, {"ip": host_key}]}
        )
        if found:
            found.pop("_id", None)
            return found
        # Fallback to API that only accepts MAC
        raw, status = unwrap(serve.list_host)(host_key)
        if status != 200:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                data.pop("_id", None)
                return data
        except Exception:
            return None
        return None

    def create_or_update_host(self, host: Dict[str, Any]) -> str:
        if "mac" not in host:
            raise ValueError("Host requires mac field")
        _, status = unwrap(serve.create_edit_host)(host)
        if status != 200:
            raise RuntimeError(f"create_edit_host failed with status {status}")
        return "Success"

    def update_host_services(
        self, host_key: str, services: List[str]
    ) -> Dict[str, Any]:
        host = self.get_host(host_key)
        if not host:
            raise ValueError("Host not found")
        host["services"] = services
        self.create_or_update_host(host)
        return host

    def add_service_to_host(self, host_key: str, service: str) -> Dict[str, Any]:
        host = self.get_host(host_key)
        if not host:
            raise ValueError("Host not found")
        if service not in host.get("services", []):
            host_services = host.get("services", [])
            host_services.append(service)
            host["services"] = host_services
            self.create_or_update_host(host)
        return host

    def remove_service_from_host(self, host_key: str, service: str) -> Dict[str, Any]:
        host = self.get_host(host_key)
        if not host:
            raise ValueError("Host not found")
        host["services"] = [s for s in host.get("services", []) if s != service]
        self.create_or_update_host(host)
        return host

    def list_services(self, include_full: bool = False) -> List[Dict[str, Any]]:
        arg = "all" if include_full else ""
        raw, status = unwrap(serve.list_services)(arg)
        if status != 200:
            raise RuntimeError(f"list_services failed with status {status}")
        data = json.loads(raw)
        if include_full:
            for entry in data:
                entry.pop("_id", None)
        return data

    def create_or_update_service(self, service: Dict[str, Any]) -> str:
        if "name" not in service:
            raise ValueError("Service requires name field")
        _, status = unwrap(serve.create_edit_service)(service)
        if status != 200:
            raise RuntimeError(f"create_edit_service failed with status {status}")
        return "Success"

    def get_metrics(
        self, host_key: str, service: str = "", count: int = 50
    ) -> Dict[str, Any]:
        raw, status = unwrap(serve.read_metrics)(host_key, service, count)
        if status != 200:
            raise RuntimeError(f"read_metrics failed with status {status}")
        return json.loads(raw)


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


def main() -> None:  # pragma: no cover
    port = int(os.environ.get("MCP_PORT", "8765"))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    print(f"Starting Labyrinth MCP server on {host}:{port}")
    app.run(host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    main()
