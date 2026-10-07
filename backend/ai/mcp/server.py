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
        # Without a mac the backend keys the host by IP (or generates a key for
        # IP-less devices), so refuse to shadow a host already known by MAC.
        if not host.get("mac") and host.get("ip"):
            existing = serve.mongo_client["labyrinth"]["hosts"].find_one(
                {"ip": host["ip"]}
            )
            if existing and existing.get("mac") != host["ip"]:
                raise ValueError(
                    f"A host with IP {host['ip']} already exists (key "
                    f"{existing['mac']}); include that mac to update it"
                )
        msg, status = unwrap(serve.create_edit_host)(host)
        if status != 200:
            raise RuntimeError(f"create_edit_host failed with status {status}: {msg}")
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

    def list_locations(self) -> List[Dict[str, Any]]:
        raw, _ = unwrap(serve.list_locations)()
        return json.loads(raw)

    def save_location(self, location: Dict[str, Any]) -> Dict[str, Any]:
        raw, status = unwrap(serve.create_edit_location)(location)
        if status != 200:
            raise RuntimeError(f"Saving the location failed ({status}): {raw}")
        return json.loads(raw)

    def delete_location(self, name: str) -> str:
        found = [
            x
            for x in self.list_locations()
            if x["name"].casefold() == name.strip().casefold()
        ]
        if not found:
            raise ValueError(f"No location named {name}")
        msg, status = unwrap(serve.delete_location)(str(found[0]["_id"]))
        if status != 200:
            raise RuntimeError(f"Deleting the location failed ({status}): {msg}")
        return "Success"

    def get_inventory(
        self, location: str = "", device_type: str = "", status: str = ""
    ) -> Dict[str, Any]:
        """Inventory with devices slimmed to what an agent needs, optionally filtered."""
        data = json.loads(unwrap(serve.inventory)()[0])
        devices = []
        for device in data["devices"]:
            live = device["_live"]
            if location and live["location"].casefold() != location.casefold():
                continue
            if device_type and live["type"] != device_type:
                continue
            if status and live["status"] != status:
                continue
            slim = {
                "key": live["key"],
                "name": device.get("host", ""),
                "ip": device.get("ip", ""),
                "mac": device.get("mac", ""),
                "type": live["type"],
                "location": live["location"],
                "location_source": live["location_source"],
                "status": live["status"],
                "alive": live["alive"],
                "services": live["services"],
                "proxmox": live["proxmox"],
                "parent": live["parent"],
            }
            for field in list(serve.INVENTORY_FIELDS) + [
                "group",
                "subnet",
                "tags",
                "notes",
                "monitor",
                "check_alive_port",
            ]:
                if field in device and field not in ("device_type", "location"):
                    slim[field] = device[field]
            devices.append(slim)

        locations = data["locations"]
        if location:
            locations = [
                x for x in locations if x["name"].casefold() == location.casefold()
            ]
        return {"locations": locations, "devices": devices, "proxmox": data["proxmox"]}

    def set_device_inventory(
        self, host_key: str, fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        raw, status = unwrap(serve.update_host_inventory)(host_key, fields)
        if status != 200:
            raise RuntimeError(f"Updating the device failed ({status}): {raw}")
        device = json.loads(raw)
        device.pop("_id", None)
        return device

    def check_device(self, host_key: str) -> Dict[str, Any]:
        raw, status = unwrap(serve.alive_check)(host_key)
        if status != 200:
            raise RuntimeError(f"Checking the device failed ({status}): {raw}")
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
) -> Dict[str, Any]:
    """Read latest metrics for a host (optionally filtered by service)."""
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


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    port = int(os.environ.get("MCP_PORT", "8765"))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    print(f"Starting Labyrinth MCP server on {host}:{port}")
    # FastMCP is a Starlette app; serve via uvicorn for proper long-running operation
    uvicorn.run(app, host=host, port=port, log_level="info")
