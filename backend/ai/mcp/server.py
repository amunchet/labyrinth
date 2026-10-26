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
    from mcp.server.fastmcp import FastMCP as _FastMCP, Image as MCPImage
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

# Every client call blocks on Postgres/Redis.  Awaited inline, one slow call
# (an unindexed metrics read ran for minutes) froze the event loop and every
# other request with it.  Run them on threads, capped at the per-process DB
# pool size: ThreadedConnectionPool raises rather than waits when exhausted.
_db_slots = asyncio.Semaphore(int(os.environ.get("POSTGRES_POOL_MAX") or 2))


async def _blocking(fn, *args, **kwargs):
    """Run a blocking client call off the event loop."""
    async with _db_slots:
        return await asyncio.to_thread(fn, *args, **kwargs)


@app.tool()
async def mcp_list_hosts() -> List[Dict[str, Any]]:
    """List all hosts in Labyrinth."""
    return await _blocking(client.list_hosts)


@app.tool()
async def mcp_get_host(host_key: str) -> Dict[str, Any]:
    """Fetch a single host by MAC or IP."""
    host = await _blocking(client.get_host, host_key)
    if not host:
        raise ValueError("Host not found")
    return host


@app.tool()
async def mcp_create_or_update_host(host_json: str) -> str:
    """
    Create or update a host/device (replaces the whole record; use
    mcp_set_device_inventory to change only location/rack/type fields).
    Provide a JSON object string. `mac` is the key: omit it to update the
    device currently at that IP, or to generate a key for a new device (keys
    are never IPs, since DHCP moves them between devices).
    Optional inventory fields: device_type, location, rack, rack_unit,
    rack_height, vendor, model, serial, uplink (another device's key),
    link_type, proxmox_node, proxmox_vmid.
    """
    host = json.loads(host_json)
    return await _blocking(client.create_or_update_host, host)


@app.tool()
async def mcp_delete_host(host_key: str) -> str:
    """Delete a host/device by key/MAC or IP; uplinks to it and its map placements are dropped."""
    return await _blocking(client.delete_host, host_key)


@app.tool()
async def mcp_list_tags() -> List[str]:
    """List every tag in use across hosts."""
    return await _blocking(client.list_tags)


@app.tool()
async def mcp_list_hosts_by_tag(tag: str) -> List[Dict[str, Any]]:
    """Hosts carrying a tag, or a service of that name (case-insensitive)."""
    return await _blocking(client.list_hosts_by_tag, tag)


@app.tool()
async def mcp_set_host_tags(host_key: str, tags: str) -> Dict[str, Any]:
    """Replace a host's tags with a comma-separated list (blank clears them)."""
    return await _blocking(client.set_host_tags, host_key, tags)


@app.tool()
async def mcp_set_service_level(
    host_key: str, service: str, level: str = ""
) -> Dict[str, Any]:
    """
    Override how a failing service on one host is reported: "warning" or
    "error"; blank clears the override.
    """
    return await _blocking(client.set_service_level, host_key, service, level)


@app.tool()
async def mcp_add_service_to_host(host_key: str, service_name: str) -> Dict[str, Any]:
    """Attach a service (display_name) to a host."""
    return await _blocking(client.add_service_to_host, host_key, service_name)


@app.tool()
async def mcp_remove_service_from_host(
    host_key: str, service_name: str
) -> Dict[str, Any]:
    """Remove a service from a host."""
    return await _blocking(client.remove_service_from_host, host_key, service_name)


@app.tool()
async def mcp_replace_host_services(
    host_key: str, services_json: str
) -> Dict[str, Any]:
    """Replace the full services list for a host. Provide a JSON array string."""
    services = json.loads(services_json)
    if not isinstance(services, list):
        raise ValueError("services_json must decode to a list")
    return await _blocking(client.update_host_services, host_key, services)


@app.tool()
async def mcp_list_services(include_full: bool = False) -> List[Any]:
    """List services. Set include_full=true for full records."""
    return await _blocking(client.list_services, include_full=include_full)


@app.tool()
async def mcp_create_or_update_service(service_json: str) -> str:
    """Create or update a service definition. Provide a JSON object string."""
    service = json.loads(service_json)
    return await _blocking(client.create_or_update_service, service)


@app.tool()
async def mcp_get_service(name: str) -> Dict[str, Any]:
    """Full definition of one service by display name."""
    return await _blocking(client.get_service, name)


@app.tool()
async def mcp_get_metric_counts(host_key: str) -> Dict[str, Any]:
    """Telegraf ingest counters for a host: requests and metrics sent, plus the last hour per minute."""
    return await _blocking(client.get_metric_counts, host_key)


@app.tool()
async def mcp_list_subnets() -> List[str]:
    """List subnet prefixes (e.g. 192.168.1)."""
    return await _blocking(client.list_subnets)


@app.tool()
async def mcp_get_subnet(subnet: str) -> Dict[str, Any]:
    """One subnet's settings (origin, links, location, colors, ...)."""
    return await _blocking(client.get_subnet, subnet)


@app.tool()
async def mcp_save_subnet(subnet_json: str) -> Dict[str, Any]:
    """
    Create or update a subnet. JSON with "subnet" (prefix, e.g. 192.168.1) plus
    any fields to set, e.g. "location"; fields left out keep their values.
    """
    return await _blocking(client.save_subnet, json.loads(subnet_json))


@app.tool()
async def mcp_delete_subnet(subnet: str) -> str:
    """Delete a subnet record. Its hosts are not deleted."""
    return await _blocking(client.delete_subnet, subnet)


@app.tool()
async def mcp_list_groups(subnet: str) -> List[Dict[str, Any]]:
    """A subnet's host groups, each with its members' IPs."""
    return await _blocking(client.list_groups, subnet)


@app.tool()
async def mcp_update_group(
    subnet: str,
    group: str,
    new_name: str = "",
    monitor: Optional[bool] = None,
    icon: str = "",
    add_service: str = "",
    remove_service: str = "",
) -> Dict[str, Any]:
    """
    Change every host in a subnet's group at once: rename the group, turn
    monitoring on/off, set the icon, or add/remove a service.
    """
    return await _blocking(
        client.update_group,
        subnet,
        group,
        new_name,
        monitor,
        icon,
        add_service,
        remove_service,
    )


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
    return await _blocking(client.get_metrics, host_key, service, count)


@app.tool()
async def mcp_list_locations() -> List[Dict[str, Any]]:
    """List locations (sites/buildings), each with its racks."""
    return await _blocking(client.list_locations)


@app.tool()
async def mcp_save_location(location_json: str) -> Dict[str, Any]:
    """
    Create or update a location. JSON: {"name", "address", "notes",
    "racks": [{"name", "units"}]}. To update or rename, include its "_id"
    (from mcp_list_locations) and send the full rack list; a rack sent with
    "previous_name" was renamed and keeps its devices, and devices in racks
    left out are un-racked.
    """
    return await _blocking(client.save_location, json.loads(location_json))


@app.tool()
async def mcp_delete_location(name: str) -> str:
    """Delete a location by name. Its devices, subnets and maps become unassigned, not deleted."""
    return await _blocking(client.delete_location, name)


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
    return await _blocking(client.get_inventory, location, device_type, status)


@app.tool()
async def mcp_set_device_inventory(host_key: str, fields_json: str) -> Dict[str, Any]:
    """
    Update only the inventory fields of a device (by key/MAC or IP), e.g.
    {"location": "Plant", "rack": "Rack A", "rack_unit": 10, "rack_height": 2,
    "device_type": "server", "uplink": "<switch key>", "link_type": "fiber"}.
    Blank values clear a field; the location, rack and uplink must exist.
    """
    return await _blocking(
        client.set_device_inventory, host_key, json.loads(fields_json)
    )


@app.tool()
async def mcp_check_device(host_key: str) -> Dict[str, Any]:
    """Ping (or TCP-check, if the device has a check port) a device now and record the result."""
    return await _blocking(client.check_device, host_key)


@app.tool()
async def mcp_list_maps(location: str = "") -> List[Dict[str, Any]]:
    """
    List location maps (floor plans with placed devices), optionally for one
    location. "legacy" maps come from the old editor and have no placements yet.
    """
    return await _blocking(client.list_maps, location)


@app.tool()
async def mcp_get_map(name: str) -> Dict[str, Any]:
    """
    One map with its placements: {key, x, y, device}, x/y being percent of
    the image's width/height from its top-left corner.
    """
    return await _blocking(client.get_map, name)


@app.tool()
async def mcp_save_map(map_json: str) -> Dict[str, Any]:
    """
    Create or update a map. JSON: {"name", "location", "background_image"
    (from mcp_list_map_images), "default" (show on Home; only one map is),
    "placements": [{"key", "x", "y"}]}. Fields left out of an update keep
    their values; placements given replace them all (use mcp_place_devices to
    change a few). Include "previous_name" to rename.
    """
    return await _blocking(client.save_map, json.loads(map_json))


@app.tool()
async def mcp_place_devices(
    map_name: str, placements_json: str = "[]", remove: str = ""
) -> Dict[str, Any]:
    """
    Place or move devices on a map without touching the others.
    placements_json: [{"key": "<device key, MAC or IP>", "x": 0-100,
    "y": 0-100}], percent of the image from its top-left corner.  remove:
    comma-separated device keys/IPs to take off the map.
    """
    return await _blocking(
        client.place_devices,
        map_name,
        json.loads(placements_json),
        [x.strip() for x in remove.split(",") if x.strip()],
    )


@app.tool()
async def mcp_delete_map(name: str) -> str:
    """Delete a map. Its devices and image file are not affected."""
    return await _blocking(client.delete_map, name)


@app.tool()
async def mcp_list_map_images() -> List[str]:
    """List uploaded map/floor plan image files."""
    return await _blocking(client.list_map_images)


@app.tool()
async def mcp_get_map_image(name: str, max_size: int = 1600) -> MCPImage:
    """
    View an uploaded map image (JPEG, scaled to fit max_size pixels). Read it
    to work out where rooms and areas are before placing devices.
    """
    return MCPImage(
        data=await _blocking(client.get_map_image, name, max_size), format="jpeg"
    )


@app.tool()
async def mcp_list_alerts() -> List[Dict[str, Any]]:
    """Active Alertmanager alerts (labels, annotations, fingerprint, times)."""
    return await _blocking(client.list_alerts)


@app.tool()
async def mcp_resolve_alert(fingerprint: str) -> str:
    """Resolve an active alert by its fingerprint (from mcp_list_alerts)."""
    return await _blocking(client.resolve_alert, fingerprint)


@app.tool()
async def mcp_get_proxmox_disk_space(refresh: bool = False) -> Dict[str, Any]:
    """
    Disk, VM and LXC usage for every Proxmox cluster, from the cache unless
    refresh=true (a live query, which can take a while).
    """
    return await _blocking(client.get_proxmox_disk_space, refresh)


@app.tool()
async def mcp_get_proxmox_telegraf_check(stale_minutes: int = 15) -> Dict[str, Any]:
    """Which Proxmox VMs/LXCs map to a Labyrinth host that is reporting Telegraf metrics."""
    return await _blocking(client.get_proxmox_telegraf_check, stale_minutes)


@app.tool()
async def mcp_get_proxmox_graylog_check() -> Dict[str, Any]:
    """Which Proxmox VMs/LXCs are forwarding logs to Graylog (check_graylog)."""
    return await _blocking(client.get_proxmox_graylog_check)


@app.tool()
async def mcp_list_proxmox_clusters() -> List[Dict[str, Any]]:
    """Configured Proxmox clusters (without token secrets)."""
    return await _blocking(client.list_proxmox_clusters)


@app.tool()
async def mcp_get_ec2_instances() -> Dict[str, Any]:
    """EC2 instances across configured AWS accounts, with Labyrinth host matches."""
    return await _blocking(client.get_ec2_instances)


@app.tool()
async def mcp_list_playbooks() -> List[str]:
    """List saved Ansible playbooks (filenames) available on the Deploy page."""
    return await _blocking(client.list_files, "ansible")


@app.tool()
async def mcp_get_playbook(name: str) -> str:
    """Read the YAML contents of a saved Ansible playbook."""
    return await _blocking(client.get_playbook, name)


@app.tool()
async def mcp_list_become_files() -> List[str]:
    """List the vault-encrypted become/credential files a deployment can use."""
    return await _blocking(client.list_files, "become")


@app.tool()
async def mcp_prepare_deployment(
    hosts: str,
    playbook: str,
    become_file: str,
    playbook_content: str = "",
    ssh_key: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    """
    Stage an Ansible deployment and return a deep link to the Deploy page.

    hosts: comma-separated IPs or MACs.  playbook: playbook name (without .yml).
    become_file: one of mcp_list_become_files.  playbook_content: optional new
    playbook YAML, saved under `playbook` only when the human deploys.  It must
    use `hosts: all` (targets come from `hosts`, never the YAML), must not set
    vars_files or any password, and may not reuse the name of a playbook a
    human wrote (an earlier generated one is fine).  Nothing runs until a human
    opens deploy_url and enters the vault password.  Read results back with
    mcp_get_deployment_request / mcp_get_deployment.
    """
    return await _blocking(
        client.prepare_deployment,
        {
            "hosts": [x.strip() for x in hosts.split(",") if x.strip()],
            "playbook": playbook,
            "become_file": become_file,
            "playbook_content": playbook_content,
            "ssh_key": ssh_key,
            "notes": notes,
        },
    )


@app.tool()
async def mcp_get_deployment_request(request_id: str) -> Dict[str, Any]:
    """A staged deployment plus summaries (status, outcome, stats, failures) of runs launched from it."""
    return await _blocking(client.get_deployment_request, request_id)


@app.tool()
async def mcp_list_deployments(limit: int = 25) -> List[Dict[str, Any]]:
    """Recent Ansible runs, newest first, without logs."""
    return await _blocking(client.list_deployments, limit)


@app.tool()
async def mcp_get_deployment(job_id: str, log_tail: int = 200) -> Dict[str, Any]:
    """
    Full result of one Ansible run: status, outcome, per-host stats, failed tasks,
    and the last `log_tail` log lines (0 for all).  Running jobs include live logs.
    """
    return await _blocking(client.get_deployment, job_id, log_tail)


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
