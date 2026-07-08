#!/usr/bin/env python3
"""
Proxmox API integration for disk space monitoring
"""

import os
import requests
import json
import ssl
from typing import Dict, List, Optional, Tuple
import redis

# Suppress SSL warnings for self-signed certificates
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass


PROXMOX_CACHE_PREFIX = "proxmox-disk"
PROXMOX_CACHE_TTL_SECONDS = int(os.environ.get("PROXMOX_CACHE_TTL_SECONDS", "90"))


def get_redis_client():
    """Return the shared Redis client used for cached Proxmox payloads."""
    return redis.Redis(host=(os.environ.get("REDIS_HOST") or "redis"))


def get_proxmox_cache_key(cluster_or_identifier) -> str:
    """Build the Redis cache key for a Proxmox cluster."""
    identifier = cluster_or_identifier

    if isinstance(cluster_or_identifier, dict):
        identifier = (
            cluster_or_identifier.get("_id")
            or cluster_or_identifier.get("name")
            or cluster_or_identifier.get("host")
        )

    if identifier is None:
        raise ValueError("Proxmox cluster identifier is required for cache key generation")

    return f"{PROXMOX_CACHE_PREFIX}:{identifier}"


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def enrich_qemu_flags(payload: Dict) -> Dict:
    """Ensure QEMU warning flags are present on VM payloads."""
    for node in payload.get("nodes", []):
        for vm in node.get("vms", []):
            is_running = str(vm.get("status") or "").lower() == "running"
            inferred_warning = vm.get("qemu_guest_agent_warning_inferred")

            if inferred_warning is None:
                inferred_warning = (
                    is_running
                    and _to_int(vm.get("maxdisk")) > 0
                    and _to_int(vm.get("disk")) == 0
                )
                vm["qemu_guest_agent_warning_inferred"] = inferred_warning

            if "qemu_guest_agent_installed" not in vm:
                vm["qemu_guest_agent_installed"] = not inferred_warning

            if inferred_warning and not vm.get("qemu_guest_agent_error"):
                vm["qemu_guest_agent_error"] = (
                    "Guest disk reported as zero for a running VM; "
                    "QEMU guest agent may not be installed or available"
                )

    return payload


def format_proxmox_cluster_payload(cluster: Dict, data: Optional[Dict]) -> Dict:
    """Normalize cluster payload shape and attach cluster metadata."""
    payload = dict(data or {})
    payload = enrich_qemu_flags(payload)
    payload["cluster_name"] = cluster.get("name")
    payload["host"] = cluster.get("host")

    if cluster.get("_id") is not None:
        payload["_id"] = str(cluster.get("_id"))

    return payload


def get_cached_proxmox_disk_data(cluster: Dict, redis_client=None) -> Optional[Dict]:
    """Read cached Proxmox payload for a cluster from Redis."""
    redis_client = redis_client or get_redis_client()

    try:
        cached = redis_client.get(get_proxmox_cache_key(cluster))
    except Exception:
        return None

    if not cached:
        return None

    if isinstance(cached, bytes):
        cached = cached.decode("utf-8")

    try:
        payload = json.loads(cached)
    except Exception:
        return None

    return format_proxmox_cluster_payload(cluster, payload)


def set_cached_proxmox_disk_data(cluster: Dict, payload: Dict, redis_client=None) -> Dict:
    """Store Proxmox payload for a cluster in Redis with TTL."""
    redis_client = redis_client or get_redis_client()
    normalized_payload = format_proxmox_cluster_payload(cluster, payload)

    try:
        redis_client.setex(
            get_proxmox_cache_key(cluster),
            PROXMOX_CACHE_TTL_SECONDS,
            json.dumps(normalized_payload, default=str),
        )
    except Exception:
        pass

    return normalized_payload


def delete_cached_proxmox_disk_data(cluster_or_identifier, redis_client=None) -> None:
    """Delete cached Proxmox payload for a cluster."""
    redis_client = redis_client or get_redis_client()

    try:
        redis_client.delete(get_proxmox_cache_key(cluster_or_identifier))
    except Exception:
        pass


def fetch_and_cache_proxmox_disk_data(cluster: Dict, redis_client=None) -> Dict:
    """Fetch live Proxmox data for a cluster and cache the normalized payload."""
    payload = get_proxmox_disk_data(cluster.get("host"), cluster)
    return set_cached_proxmox_disk_data(cluster, payload, redis_client=redis_client)


def get_proxmox_disk_data_cached(cluster: Dict, redis_client=None) -> Dict:
    """Return cached Proxmox data when available, otherwise fetch live data."""
    cached_payload = get_cached_proxmox_disk_data(cluster, redis_client=redis_client)
    if cached_payload is not None:
        return cached_payload

    return fetch_and_cache_proxmox_disk_data(cluster, redis_client=redis_client)


def refresh_proxmox_cluster_cache(clusters: List[Dict], redis_client=None) -> List[Dict]:
    """Refresh Redis cache entries for all configured Proxmox clusters."""
    redis_client = redis_client or get_redis_client()
    results = []

    for cluster in clusters or []:
        results.append(fetch_and_cache_proxmox_disk_data(cluster, redis_client=redis_client))

    return results


class ProxmoxClient:
    """Client for interacting with Proxmox API"""

    def __init__(self, host: str, user: str, token_id: str, token_secret: str, verify_ssl: bool = False):
        """
        Initialize Proxmox client
        
        :param host: Proxmox host IP or hostname
        :param user: Proxmox user (e.g., root@pam)
        :param token_id: API token ID
        :param token_secret: API token secret
        :param verify_ssl: Whether to verify SSL certificates
        """
        self.host = host
        self.user = user
        self.token_id = token_id
        self.token_secret = token_secret
        self.verify_ssl = verify_ssl
        self.base_url = f"https://{host}:8006/api2/json"
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.headers.update({
            "Authorization": f"PVEAPIToken={user}!{token_id}={token_secret}"
        })

    def get_nodes(self) -> List[Dict]:
        """Get list of all nodes in cluster"""
        try:
            response = self.session.get(f"{self.base_url}/nodes", timeout=10)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            print(f"Error getting nodes: {e}")
            return []

    def get_storage(self, node: str) -> List[Dict]:
        """Get storage information for a node"""
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/storage",
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            print(f"Error getting storage for {node}: {e}")
            return []

    def get_vms_and_containers(self, node: str) -> Tuple[List[Dict], List[Dict]]:
        """Get VMs and containers (LXCs) on a node"""
        vms = []
        containers = []
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/qemu",
                timeout=10
            )
            response.raise_for_status()
            vms = response.json().get("data", [])
        except Exception as e:
            print(f"Error getting VMs for {node}: {e}")

        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/lxc",
                timeout=10
            )
            response.raise_for_status()
            containers = response.json().get("data", [])
        except Exception as e:
            print(f"Error getting LXCs for {node}: {e}")

        return vms, containers

    def get_vm_status(self, node: str, vmid: str) -> Optional[Dict]:
        """Get detailed status for a VM including disk usage"""
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/status/current",
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            print(f"Error getting VM status for {node}/{vmid}: {e}")
            return None

    def get_vm_agent_status(self, node: str, vmid: str) -> Dict:
        """Determine whether the QEMU guest agent is available for a VM."""
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/agent/info",
                timeout=10,
            )
            response.raise_for_status()
            return {"installed": True, "error": None}
        except requests.HTTPError as error:
            response = getattr(error, "response", None)
            message = None

            if response is not None:
                try:
                    payload = response.json()
                    message = payload.get("errors") or payload.get("message") or payload.get("data")
                    if isinstance(message, dict):
                        message = json.dumps(message)
                except Exception:
                    message = response.text

            return {
                "installed": False,
                "error": message or str(error),
            }
        except Exception as error:
            return {
                "installed": False,
                "error": str(error),
            }

    def get_vm_guest_fsinfo(self, node: str, vmid: str) -> Optional[Dict]:
        """Get filesystem information from QEMU guest agent (only works if agent is installed and running)"""
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/agent/get-fsinfo",
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception:
            # If this fails, guest agent may not have filesystem info available
            return None

    def get_container_status(self, node: str, vmid: str) -> Optional[Dict]:
        """Get detailed status for a container including disk usage"""
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/lxc/{vmid}/status/current",
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            print(f"Error getting container status for {node}/{vmid}: {e}")
            return None

    def get_disk_info(self, node: str, storage: str) -> Optional[Dict]:
        """Get detailed disk information for a storage"""
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/storage/{storage}/content",
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            print(f"Error getting disk info for {node}/{storage}: {e}")
            return None


def get_proxmox_disk_data(host_ip: str, cluster_config: Dict) -> Dict:
    """
    Retrieve disk space data from a Proxmox host
    
    :param host_ip: Proxmox cluster host IP
    :param cluster_config: Cluster configuration dict with keys: host, user, token_id, token_secret, verify_ssl (optional)
    :return: Dictionary with disk space information
    """
    try:
        # Extract credentials from cluster config
        user = cluster_config.get("user")
        token_id = cluster_config.get("token_id")
        token_secret = cluster_config.get("token_secret")
        verify_ssl = cluster_config.get("verify_ssl", False)

        if not all([user, token_id, token_secret]):
            return {"error": "Invalid cluster configuration. Missing user, token_id, or token_secret"}

        client = ProxmoxClient(
            host=host_ip,
            user=user,
            token_id=token_id,
            token_secret=token_secret,
            verify_ssl=verify_ssl
        )

        def _to_int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0

        result = {
            "host": host_ip,
            "nodes": [],
            "error": None
        }

        nodes = client.get_nodes()
        if not nodes:
            result["error"] = "Could not retrieve nodes"
            return result

        for node in nodes:
            node_name = node.get("node")
            node_info = {
                "name": node_name,
                "status": node.get("status"),
                "storage": [],
                "vms": [],
                "containers": []
            }

            # Get storage info
            storage_list = client.get_storage(node_name)
            for storage in storage_list:
                storage_name = storage.get("storage")
                storage_info = {
                    "name": storage_name,
                    "type": storage.get("type"),
                    "enabled": storage.get("enabled", 1),
                    "total": storage.get("total"),
                    "used": storage.get("used"),
                    "available": storage.get("available")
                }
                node_info["storage"].append(storage_info)

            # Get VMs and containers
            vms, containers = client.get_vms_and_containers(node_name)

            for vm in vms:
                vmid = vm.get("vmid")
                vm_status = client.get_vm_status(node_name, str(vmid))
                agent_status = client.get_vm_agent_status(node_name, str(vmid))
                maxdisk = vm.get("maxdisk")
                disk = vm_status.get("disk") if vm_status else None
                is_running = str(vm.get("status") or "").lower() == "running"
                
                # Determine if QEMU guest agent is truly installed
                # If agent/info call succeeds, it's installed
                qemu_truly_installed = agent_status.get("installed", False)
                
                # If agent is installed and running VM has zero disk reported, try to get real disk info from guest
                guest_disk_info = None
                if qemu_truly_installed and is_running and _to_int(disk) == 0:
                    guest_disk_info = client.get_vm_guest_fsinfo(node_name, str(vmid))
                    # Extract root filesystem info if available
                    if guest_disk_info:
                        fsinfo = guest_disk_info.get("result", [])
                        for fs in fsinfo:
                            if fs.get("mountpoint") == "/":
                                disk = fs.get("used-bytes")
                                maxdisk = fs.get("total-bytes")
                                break
                
                # Check if disk is reported as zero for a running VM (agent may exist but disk metrics unavailable)
                qemu_warning_inferred = (
                    is_running
                    and _to_int(maxdisk) > 0
                    and _to_int(disk) == 0
                )
                
                vm_info = {
                    "id": vmid,
                    "name": vm.get("name"),
                    "status": vm.get("status"),
                    "maxdisk": maxdisk,
                    "disk": disk,
                    "maxmem": vm.get("maxmem"),
                    "mem": vm_status.get("mem") if vm_status else None,
                    "qemu_guest_agent_installed": qemu_truly_installed,
                    "qemu_guest_agent_error": agent_status.get("error"),
                    "qemu_guest_agent_warning_inferred": qemu_warning_inferred,
                }
                # Include raw guest info for debugging if available
                if guest_disk_info:
                    vm_info["_debug_guest_fsinfo"] = guest_disk_info
                node_info["vms"].append(vm_info)

            for container in containers:
                vmid = container.get("vmid")
                container_status = client.get_container_status(node_name, str(vmid))
                container_info = {
                    "id": vmid,
                    "name": container.get("name"),
                    "status": container.get("status"),
                    "maxdisk": container.get("maxdisk"),
                    "disk": container_status.get("disk") if container_status else None,
                    "maxmem": container.get("maxmem"),
                    "mem": container_status.get("mem") if container_status else None
                }
                node_info["containers"].append(container_info)

            result["nodes"].append(node_info)

        return result

    except Exception as e:
        return {"error": f"Failed to get Proxmox data: {str(e)}", "host": host_ip}
