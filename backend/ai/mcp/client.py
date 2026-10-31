"""
Thin wrapper around existing backend functions using unwrap, backing the
host/service/metric tools of the standalone MCP server (mcp/server.py).
"""

import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

# Make backend modules importable when running from backend/ai/mcp
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from common.test import unwrap  # type: ignore
import serve  # type: ignore

IMAGES_DIR = "/src/uploads/images"


def call(fn, *args, decode=True, **request_kwargs):
    """
    Call a route handler, raising on a non-2xx status, and decode its JSON
    (decode=False for handlers that answer plain text such as "Success").
        - request_kwargs (query_string, ...) build a request context for
          handlers that read Flask's request object
    """
    if request_kwargs:
        with serve.app.test_request_context(**request_kwargs):
            raw, status = unwrap(fn)(*args)
    else:
        raw, status = unwrap(fn)(*args)
    if not 200 <= status < 300:
        raise RuntimeError(f"{fn.__name__} failed ({status}): {raw}")
    return json.loads(raw) if decode else raw


class LabyrinthClient:
    """Thin wrapper around existing backend functions using unwrap."""

    def list_hosts(self) -> List[Dict[str, Any]]:
        raw, status = unwrap(serve.list_hosts)()
        if status != 200:
            raise RuntimeError(f"list_hosts failed with status {status}")
        return json.loads(raw)

    def get_host(self, host_key: str) -> Optional[Dict[str, Any]]:
        # Try MAC/IP lookup directly for flexibility
        found = serve.db["labyrinth"]["hosts"].find_one(
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
            existing = serve.db["labyrinth"]["hosts"].find_one({"ip": host["ip"]})
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
    ) -> List[Dict[str, Any]]:
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

    def list_files(self, file_type: str) -> List[str]:
        raw, status = unwrap(serve.list_directory)(file_type)
        if status != 200:
            raise RuntimeError(f"list_directory failed with status {status}")
        return json.loads(raw)

    def get_playbook(self, name: str) -> str:
        raw, _ = unwrap(serve.get_ansible_file)(name)
        return raw

    def prepare_deployment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Hosts may be given as MACs; the deploy page and inventory want IPs
        hosts = []
        for key in data["hosts"]:
            host = self.get_host(key)
            hosts.append(host["ip"] if host and host.get("ip") else key)
        data["hosts"] = hosts

        raw, status = unwrap(serve.create_ansible_request)(json.dumps(data))
        if status != 200:
            raise RuntimeError(f"create_ansible_request failed ({status}): {raw}")
        return {
            **raw,
            "hosts": hosts,
            "deploy_url": serve.labyrinth_url(raw["path"]),
            "conversation_url": serve.labyrinth_url(
                "/conversations/" + raw["conversation_id"]
            ),
        }

    def start_conversation(
        self, title: str, text: str = "", needs_response: bool = False
    ) -> Dict[str, Any]:
        conversation_id = serve.start_conversation(title)["conversation_id"]
        result = {
            "conversation_id": conversation_id,
            "url": serve.labyrinth_url("/conversations/" + conversation_id),
        }
        if text:
            result.update(self.send_message(conversation_id, text, needs_response))
        return result

    def send_message(
        self, conversation_id: str, text: str, needs_response: bool = False
    ) -> Dict[str, Any]:
        if not text.strip():
            raise ValueError("text is required")
        message = serve.post_conversation_message(
            conversation_id,
            "agent",
            "question" if needs_response else "message",
            text.strip(),
        )
        if not message:
            raise ValueError("Conversation not found")
        return {"message_id": message["id"], "notified": message.get("notified", False)}

    def list_conversations(self, waiting_only: bool = False) -> List[Dict[str, Any]]:
        return call(serve.list_conversations, "waiting" if waiting_only else "")

    def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        return call(serve.get_conversation, conversation_id)

    def close_conversation(self, conversation_id: str, summary: str = "") -> str:
        if not serve.post_conversation_message(
            conversation_id, "agent", "closed", summary.strip()
        ):
            raise ValueError("Conversation not found")
        return "Closed"

    def check_response(self, conversation_id: str, since: int = -1) -> Dict[str, Any]:
        """
        Where a conversation stands for an agent waiting on it.  It has been
        answered once the human or Ansible spoke after message `since` (by
        default, after the agent's own last message): a reply, a declined
        deployment, a finished run, or closing it.  A launch alone only means
        a run is under way.
        """
        conversation = self.get_conversation(conversation_id)
        messages = conversation["messages"]
        if since < 0:
            since = max(
                (i + 1 for i, m in enumerate(messages) if m["author"] == "agent"),
                default=0,
            )
        new = messages[since:]
        return {
            "conversation_id": conversation_id,
            "answered": any(
                m["author"] != "agent" and m["kind"] != "launched" for m in new
            ),
            "status": conversation["status"],
            "waiting_on_human": conversation["pending"],
            "runs_in_progress": [
                run["job_id"]
                for staged in conversation["requests"].values()
                for run in staged["runs"]
                if run["status"] in ("queued", "running")
            ],
            "new_messages": new,
            "message_count": len(messages),
        }

    def get_deployment_request(self, request_id: str) -> Dict[str, Any]:
        raw, status = unwrap(serve.get_ansible_request)(request_id)
        if status != 200:
            raise ValueError("Deployment request not found")
        return json.loads(raw)

    def list_deployments(self, limit: int = 25) -> List[Dict[str, Any]]:
        raw, _ = unwrap(serve.list_ansible_runs)(limit)
        return json.loads(raw)

    def get_deployment(self, job_id: str, log_tail: int = 200) -> Dict[str, Any]:
        raw, status = unwrap(serve.get_ansible_run)(job_id)
        if status != 200:
            raise ValueError("Deployment run not found")
        run = json.loads(raw)
        if log_tail > 0:
            run["logs"] = run.get("logs", [])[-log_tail:]
        return run

    def delete_host(self, host_key: str) -> str:
        _, status = unwrap(serve.delete_host)(host_key)
        if status != 200:
            raise ValueError("Host not found")
        return "Success"

    def list_tags(self) -> List[str]:
        return call(serve.list_tags)

    def list_hosts_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        hosts = call(serve.list_hosts_by_tag, tag)
        for host in hosts:
            host.pop("_id", None)
        return hosts

    def set_host_tags(self, host_key: str, tags: str) -> Dict[str, Any]:
        host = self.get_host(host_key)
        if not host:
            raise ValueError("Host not found")
        if host.get("ip"):
            call(serve.update_host_tags, host["ip"], tags, decode=False)
        else:
            host["tags"] = tags
            self.create_or_update_host(host)
        return self.get_host(host["mac"])

    def set_service_level(
        self, host_key: str, service: str, level: str
    ) -> Dict[str, Any]:
        if level not in ("warning", "error", ""):
            raise ValueError("level must be warning, error or blank to clear")
        host = self.get_host(host_key)
        if not host or not host.get("ip"):
            raise ValueError("No host with an IP found for that key")
        call(serve.update_host_service_level, host["ip"], service, level, decode=False)
        return self.get_host(host["mac"])

    def get_service(self, name: str) -> Dict[str, Any]:
        found = call(serve.read_service, name)
        if not found:
            raise ValueError(f"No service named {name}")
        found[0].pop("_id", None)
        return found[0]

    def get_metric_counts(self, host_key: str) -> Dict[str, Any]:
        return call(serve.read_metric_counts, host_key)

    # Subnets and their host groups

    def list_subnets(self) -> List[str]:
        return call(serve.list_subnets)

    def get_subnet(self, subnet: str) -> Dict[str, Any]:
        raw, status = unwrap(serve.list_subnet)(subnet)
        if status != 200:
            raise ValueError(f"No subnet {subnet}")
        found = json.loads(raw)
        found.pop("_id", None)
        return found

    def save_subnet(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a subnet; fields left out of an update keep their values"""
        if not data.get("subnet"):
            raise ValueError("A subnet needs its `subnet` prefix, e.g. 192.168.1")
        merged = serve.db["labyrinth"]["subnets"].find_one({"subnet": data["subnet"]})
        merged = {**(merged or {"origin": {}, "links": {}}), **data}
        merged.pop("_id", None)
        call(serve.create_edit_subnet, merged, decode=False)
        return self.get_subnet(data["subnet"])

    def delete_subnet(self, subnet: str) -> str:
        _, status = unwrap(serve.delete_subnet)(subnet)
        if status != 200:
            raise ValueError(f"No subnet {subnet}")
        return "Success"

    def list_groups(self, subnet: str) -> List[Dict[str, Any]]:
        return [
            {
                "group": group,
                "members": call(serve.list_subnets_group_members, subnet, group),
            }
            for group in sorted(call(serve.list_subnets_groups, subnet))
        ]

    def update_group(
        self,
        subnet: str,
        group: str,
        new_name: str = "",
        monitor: Optional[bool] = None,
        icon: str = "",
        add_service: str = "",
        remove_service: str = "",
    ) -> Dict[str, Any]:
        """Apply group-wide changes to every host in a subnet's group"""
        if not call(serve.list_subnets_group_members, subnet, group):
            raise ValueError(f"No group {group} in subnet {subnet}")
        if monitor is not None:
            call(serve.group_monitor, subnet, group, str(monitor), decode=False)
        if icon:
            call(serve.group_icon, subnet, group, icon, decode=False)
        if add_service:
            call(serve.group_add_service, subnet, group, add_service, decode=False)
        if remove_service:
            call(
                serve.group_delete_service, subnet, group, remove_service, decode=False
            )
        if new_name and new_name != group:
            call(serve.group_rename, subnet, group, new_name, decode=False)
            group = new_name
        return {
            "subnet": subnet,
            "group": group,
            "members": call(serve.list_subnets_group_members, subnet, group),
        }

    # Location maps: a floor plan image with devices placed at percentage
    # positions (0-100 from the image's left/top).  Stored as custom dashboards.

    def list_maps(self, location: str = "") -> List[Dict[str, Any]]:
        retval = []
        for found in call(serve.list_custom_dashboards):
            if location and (found.get("location") or "").casefold() != (
                location.casefold()
            ):
                continue
            retval.append(
                {
                    "name": found["name"],
                    "location": found.get("location", ""),
                    "background_image": found.get("background_image", ""),
                    "default": bool(found.get("default")),
                    "placed": len(found.get("placements") or []),
                    # The old dashboard editor stored IPs at pixel offsets
                    "legacy": "placements" not in found and "components" in found,
                }
            )
        return retval

    def get_map(self, name: str) -> Dict[str, Any]:
        """A map with each placement's device (None if it no longer exists)"""
        raw, status = unwrap(serve.list_custom_dashboards)(name)
        if status != 200:
            raise ValueError(f"No map named {name}")
        found = json.loads(raw)[0]
        found.pop("_id", None)
        placements = found.get("placements") or []
        hosts = {}
        if placements:
            hosts = {
                x["mac"]: x
                for x in serve.db["labyrinth"]["hosts"].find(
                    {"mac": {"$in": [x["key"] for x in placements]}}
                )
            }
        for placement in placements:
            host = hosts.get(placement["key"])
            placement["device"] = host and {
                "name": host.get("host", ""),
                "ip": host.get("ip", ""),
                "device_type": host.get("device_type", ""),
            }
        return found

    def device_key(self, key_or_ip: str) -> str:
        """The host key for a device given by key/MAC or IP"""
        host = serve.db["labyrinth"]["hosts"].find_one(
            {"$or": [{"mac": key_or_ip}, {"ip": key_or_ip}]}
        )
        if not host:
            raise ValueError(f"No device with key or IP {key_or_ip}")
        return host["mac"]

    def clean_placements(self, placements: Any) -> List[Dict[str, Any]]:
        """Validated placements keyed by host key, one per device (last wins)"""
        if not isinstance(placements, list):
            raise ValueError("placements must be a list of {key, x, y}")
        cleaned = {}
        for item in placements:
            key = self.device_key(str(item.get("key") or ""))
            try:
                x, y = float(item["x"]), float(item["y"])
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"Placement for {key} needs numeric x and y")
            if not (0 <= x <= 100 and 0 <= y <= 100):
                raise ValueError(f"Placement for {key} must be within 0-100")
            cleaned[key] = {"key": key, "x": round(x, 2), "y": round(y, 2)}
        return list(cleaned.values())

    def save_map(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create or update a map; fields left out of an update keep their
        values, and "previous_name" renames.  Only one map is the Home default.
        """
        data = dict(data)
        data.pop("_id", None)
        previous = str(data.pop("previous_name", "") or "").strip()
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("A map needs a name")
        maps = {x["name"]: x for x in call(serve.list_custom_dashboards)}
        if previous and previous != name and name in maps:
            raise ValueError(f"A map named {name} already exists")
        current = maps.get(previous or name)
        if previous and not current:
            raise ValueError(f"No map named {previous}")

        merged = current or {
            "location": "",
            "background_image": "",
            "default": False,
            "placements": [],
        }
        merged = {**merged, **data, "name": name}
        merged.pop("_id", None)

        if merged.get("location"):
            match = [
                x["name"]
                for x in self.list_locations()
                if x["name"].casefold() == merged["location"].strip().casefold()
            ]
            if not match:
                raise ValueError(f"No location named {merged['location']}")
            merged["location"] = match[0]
        if (
            merged.get("background_image")
            and merged["background_image"] not in self.list_map_images()
        ):
            raise ValueError(f"No uploaded image {merged['background_image']}")
        if "placements" in merged:
            merged["placements"] = self.clean_placements(merged["placements"])

        if merged.get("default"):
            for other in maps.values():
                if other.get("default") and other["name"] not in (name, previous):
                    other = {**other, "default": False}
                    other.pop("_id", None)
                    call(
                        serve.create_edit_custom_dashboard,
                        other["name"],
                        other,
                        decode=False,
                    )
        call(serve.create_edit_custom_dashboard, name, merged, decode=False)
        if previous and previous != name:
            call(serve.delete_custom_dashboard, previous, decode=False)
        return self.get_map(name)

    def place_devices(
        self, map_name: str, placements: Any, remove: List[str]
    ) -> Dict[str, Any]:
        """Place or move devices on a map, and take others off it"""
        current = self.get_map(map_name)
        new = self.clean_placements(placements)
        dropped = {x["key"] for x in new}
        for key in remove:
            host = serve.db["labyrinth"]["hosts"].find_one(
                {"$or": [{"mac": key}, {"ip": key}]}
            )
            # A deleted device can still be named by its old key
            dropped.add(host["mac"] if host else key)
        kept = [
            {"key": x["key"], "x": x["x"], "y": x["y"]}
            for x in current.get("placements") or []
            if x["key"] not in dropped
        ]
        return self.save_map({"name": map_name, "placements": kept + new})

    def delete_map(self, name: str) -> str:
        if not any(x["name"] == name for x in self.list_maps()):
            raise ValueError(f"No map named {name}")
        call(serve.delete_custom_dashboard, name, decode=False)
        return "Success"

    def list_map_images(self) -> List[str]:
        return call(serve.custom_dashboard_list_images)

    def get_map_image(self, name: str, max_size: int = 1600) -> bytes:
        """An uploaded map image as JPEG, scaled to fit within max_size pixels"""
        if name not in self.list_map_images():
            raise ValueError(f"No uploaded image {name}")
        with Image.open(os.path.join(IMAGES_DIR, name)) as img:
            img = img.convert("RGBA")
            img.thumbnail((max_size, max_size))
            # Transparent areas of a floor plan read as paper, not black
            flat = Image.new("RGB", img.size, "white")
            flat.paste(img, mask=img.getchannel("A"))
        out = io.BytesIO()
        flat.save(out, "JPEG", quality=85)
        return out.getvalue()

    # Alerts and monitoring reports

    def list_alerts(self) -> List[Dict[str, Any]]:
        return call(serve.list_alerts)

    def resolve_alert(self, fingerprint: str) -> str:
        found = [x for x in self.list_alerts() if x.get("fingerprint") == fingerprint]
        if not found:
            raise ValueError(f"No active alert with fingerprint {fingerprint}")
        call(serve.resolve_alert, found[0], decode=False)
        return "Success"

    def get_proxmox_disk_space(self, refresh: bool = False) -> Dict[str, Any]:
        if refresh:
            return call(serve.refresh_proxmox_disk_space)
        return call(serve.get_proxmox_disk_space)

    def get_proxmox_telegraf_check(self, stale_minutes: int = 15) -> Dict[str, Any]:
        return call(
            serve.get_proxmox_telegraf_check,
            query_string={"stale_minutes": stale_minutes},
        )

    def get_proxmox_graylog_check(self) -> Dict[str, Any]:
        return call(serve.get_proxmox_graylog_check)

    def list_proxmox_clusters(self) -> List[Dict[str, Any]]:
        # The route already drops token_secret
        return call(serve.list_proxmox_clusters)

    def get_ec2_instances(self) -> Dict[str, Any]:
        return call(serve.get_aws_ec2_instances)
