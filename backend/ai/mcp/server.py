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

from dotenv import dotenv_values

# Make backend modules importable when running from backend/ai/mcp
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

# common/auth.py's bare load_dotenv() reads the working directory, which is
# /app in this container rather than /app/backend, so backend/.env never gets
# loaded here.  Pull it in explicitly, before anything downstream reads the
# environment.  A plain load_dotenv() would not be enough: it leaves any
# variable that is already set, and compose substitutes an unset ${MCP_KEY} as
# an empty string rather than omitting it, so blank is treated as absent.
for _name, _value in (dotenv_values(BACKEND_ROOT / ".env") or {}).items():
    if _value and not (os.environ.get(_name) or "").strip():
        os.environ[_name] = _value

from ai.mcp.client import LabyrinthClient  # type: ignore

from ai.mcp.auth import (  # type: ignore
    PreSharedKeyMiddleware,
    get_host_allowlists,
    get_mcp_key,
)

try:
    from mcp.server.fastmcp import FastMCP as _FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Unable to import FastMCP from `mcp.server.fastmcp` "
        f"({exc}). Install the official SDK with `pip install 'mcp<2'` - "
        "mcp 2.x renamed FastMCP to MCPServer and moved the module."
    ) from exc


def transport_security():
    """
    Decide the SDK's DNS-rebinding policy instead of inheriting its default.

    FastMCP turns that protection on by itself whenever its own settings.host
    is a loopback address, and ours is: the bind address in MCP_HOST goes to
    uvicorn, which FastMCP knows nothing about, so its host stays at the
    "127.0.0.1" default.  Left alone it answers 421 "Invalid Host header" to
    every request whose Host is not 127.0.0.1 or localhost - which is every
    request arriving through Caddy under a real domain.

    That check guards unauthenticated servers bound to loopback against
    malicious pages in the user's browser.  This one is reachable on purpose
    and guarded by MCP_KEY, so the check is off unless an operator pins an
    allowlist through MCP_ALLOWED_HOSTS (entries may use `host:*` for any
    port).  Passing settings explicitly also suppresses the auto-enable, so
    the policy no longer depends on what MCP_HOST happens to be.
    """
    hosts, origins = get_host_allowlists()
    if not hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


client = LabyrinthClient()
app = _FastMCP("labyrinth-mcp", transport_security=transport_security())


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
    """
    Create or update a host/device (replaces the whole record; use
    mcp_set_device_inventory to change only location/rack/type fields).
    Provide a JSON object string. `mac` is the key: omit it to key the device
    by IP, or for IP-less devices (e.g. an unmanaged switch) to generate one.
    Optional inventory fields: device_type, location, rack, rack_unit,
    rack_height, vendor, model, serial, uplink (another device's key),
    link_type, proxmox_node, proxmox_vmid.
    """
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
) -> List[Dict[str, Any]]:
    """
    Read latest metrics for a host (optionally filtered by service).

    serve.read_metrics returns a JSON array, and FastMCP builds this tool's
    output schema from the return annotation and validates against it - so
    declaring a dict here failed every call, empty result included, with
    "Input should be a valid dictionary".
    """
    return client.get_metrics(host_key, service, count)


@app.tool()
async def mcp_list_locations() -> List[Dict[str, Any]]:
    """List locations (sites/buildings), each with its racks."""
    return client.list_locations()


@app.tool()
async def mcp_save_location(location_json: str) -> Dict[str, Any]:
    """
    Create or update a location. JSON: {"name", "address", "notes",
    "racks": [{"name", "units"}]}. To update or rename, include its "_id"
    (from mcp_list_locations) and send the full rack list; a rack sent with
    "previous_name" was renamed and keeps its devices, and devices in racks
    left out are un-racked.
    """
    return client.save_location(json.loads(location_json))


@app.tool()
async def mcp_delete_location(name: str) -> str:
    """Delete a location by name. Its devices, subnets and maps become unassigned, not deleted."""
    return client.delete_location(name)


@app.tool()
async def mcp_get_inventory(
    location: str = "", device_type: str = "", status: str = ""
) -> Dict[str, Any]:
    """
    Devices with live status, plus locations and the Proxmox node -> VM/LXC tree.
    Filters (optional): location (effective location name), device_type (server,
    vm, lxc, pc, laptop, switch, router, firewall, ap, bridge, plc, iot, camera,
    printer, phone, ups, storage, patch-panel, other) and status (up, down,
    error, warning, unknown, none = no IP/label only). A device's location is
    explicit, else inherited from its Proxmox node, else from its subnet.
    """
    return client.get_inventory(location, device_type, status)


@app.tool()
async def mcp_set_device_inventory(host_key: str, fields_json: str) -> Dict[str, Any]:
    """
    Update only the inventory fields of a device (by key/MAC or IP), e.g.
    {"location": "Plant", "rack": "Rack A", "rack_unit": 10, "rack_height": 2,
    "device_type": "server", "uplink": "<switch key>", "link_type": "fiber"}.
    Blank values clear a field; the location, rack and uplink must exist.
    """
    return client.set_device_inventory(host_key, json.loads(fields_json))


@app.tool()
async def mcp_check_device(host_key: str) -> Dict[str, Any]:
    """Ping (or TCP-check, if the device has a check port) a device now and record the result."""
    return client.check_device(host_key)


def create_http_app():
    """
    Build the ASGI application uvicorn serves.

    FastMCP is not itself an ASGI app - it has no __call__ - so the streamable
    HTTP transport has to be materialised with streamable_http_app(), which
    mounts the MCP endpoint at /mcp.  Everything is then wrapped in the
    pre-shared secret check, so no tool can be reached without the key.
    """
    return PreSharedKeyMiddleware(app.streamable_http_app(), get_mcp_key())


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    port = int(os.environ.get("MCP_PORT", "8765"))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    print(f"Starting Labyrinth MCP server on {host}:{port}/mcp")
    uvicorn.run(create_http_app(), host=host, port=port, log_level="info")
