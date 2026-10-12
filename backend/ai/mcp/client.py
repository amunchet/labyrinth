"""
Thin wrapper around existing backend functions using unwrap, backing the
host/service/metric tools of the standalone MCP server (mcp/server.py).
"""

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
    ) -> List[Dict[str, Any]]:
        raw, status = unwrap(serve.read_metrics)(host_key, service, count)
        if status != 200:
            raise RuntimeError(f"read_metrics failed with status {status}")
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
        base = os.environ.get("LABYRINTH_URL", "").rstrip("/")
        return {**raw, "hosts": hosts, "deploy_url": base + raw["path"]}

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
