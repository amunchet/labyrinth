"""
Shared thin wrapper around existing backend functions using unwrap.

Extracted so both the standalone MCP server (mcp/server.py, its own Docker
service) and the in-process chat agent (backend/ai/agent_tools.py, which runs
inside the same process as serve.py) can reuse the same host/service/metric
tool implementations instead of maintaining two copies.
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make backend modules importable when running from backend/ai/mcp
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))

from common.test import unwrap  # type: ignore
import serve  # type: ignore


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
