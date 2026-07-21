#!/usr/bin/env python3
"""
Proxmox API integration for disk space monitoring
"""

import os
import re
import requests
import json
import ssl
import time
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

# Per-VM/LXC status fallback cache. Individual guest status calls
# (get_vm_status / get_container_status) occasionally fail transiently
# (network blip, node under load) even though the guest itself is fine.
# Treating a failed call as "0 disk used" previously caused false-positive
# "missing QEMU guest agent" alerts. Instead, the last known-good status is
# retained for up to two hours so a single failed check has time to be
# followed by a successful one before an alert email would go out.
PROXMOX_GUEST_STATUS_CACHE_PREFIX = "proxmox-guest-status"
PROXMOX_GUEST_STATUS_CACHE_TTL_SECONDS = int(
    os.environ.get("PROXMOX_GUEST_STATUS_CACHE_TTL_SECONDS", str(2 * 60 * 60))
)

# Last known-good *measured* disk usage for a single VM, independent of the
# guest-status cache above. A VM can have a perfectly successful status call
# and a perfectly successful guest-agent call, and still fail to resolve real
# filesystem usage for a single cycle (get-fsinfo/df escape valve both come up
# empty) - that's a transient blip, not proof the guest agent is actually
# missing. Before treating a zero-disk reading as a real "can't measure this"
# problem, we check whether a real (non-zero) reading was seen within the
# last two hours; if so, the zero reading is suppressed as a flaky read
# instead of triggering an alert. Same TTL as the guest-status cache.
PROXMOX_GOOD_DISK_CACHE_PREFIX = "proxmox-good-disk"


def get_good_disk_cache_key(cluster_or_identifier, node: str, kind: str, vmid) -> str:
    """Build the Redis cache key for a VM/LXC's last known-good disk reading."""
    cluster_identifier = _resolve_cluster_identifier(cluster_or_identifier)
    return (
        f"{PROXMOX_GOOD_DISK_CACHE_PREFIX}:{cluster_identifier}:{node}:{kind}:{vmid}"
    )


def get_cached_good_disk(
    cluster_or_identifier, node: str, kind: str, vmid, redis_client=None
) -> Optional[Dict]:
    """Read the last known-good measured disk usage for a single VM/LXC."""
    redis_client = redis_client or get_redis_client()

    try:
        cached = redis_client.get(
            get_good_disk_cache_key(cluster_or_identifier, node, kind, vmid)
        )
    except Exception:
        return None

    if not cached:
        return None

    if isinstance(cached, bytes):
        cached = cached.decode("utf-8")

    try:
        return json.loads(cached)
    except Exception:
        return None


def set_cached_good_disk(
    cluster_or_identifier,
    node: str,
    kind: str,
    vmid,
    used,
    total,
    redis_client=None,
) -> None:
    """Store a successful, non-zero disk reading with a two-hour TTL."""
    redis_client = redis_client or get_redis_client()

    try:
        redis_client.setex(
            get_good_disk_cache_key(cluster_or_identifier, node, kind, vmid),
            PROXMOX_GUEST_STATUS_CACHE_TTL_SECONDS,
            json.dumps({"used": used, "total": total}, default=str),
        )
    except Exception:
        pass


def get_redis_client():
    """Return the shared Redis client used for cached Proxmox payloads."""
    return redis.Redis(host=(os.environ.get("REDIS_HOST") or "redis"))


def _resolve_cluster_identifier(cluster_or_identifier):
    """Extract a stable identifier from a cluster dict or raw identifier."""
    identifier = cluster_or_identifier

    if isinstance(cluster_or_identifier, dict):
        identifier = (
            cluster_or_identifier.get("_id")
            or cluster_or_identifier.get("name")
            or cluster_or_identifier.get("host")
        )

    if identifier is None:
        raise ValueError(
            "Proxmox cluster identifier is required for cache key generation"
        )

    return identifier


def get_proxmox_cache_key(cluster_or_identifier) -> str:
    """Build the Redis cache key for a Proxmox cluster."""
    return (
        f"{PROXMOX_CACHE_PREFIX}:{_resolve_cluster_identifier(cluster_or_identifier)}"
    )


def get_guest_status_cache_key(
    cluster_or_identifier, node: str, kind: str, vmid
) -> str:
    """Build the Redis cache key for a single VM/LXC status fallback entry."""
    cluster_identifier = _resolve_cluster_identifier(cluster_or_identifier)
    return (
        f"{PROXMOX_GUEST_STATUS_CACHE_PREFIX}:{cluster_identifier}:{node}:{kind}:{vmid}"
    )


def get_cached_guest_status(
    cluster_or_identifier, node: str, kind: str, vmid, redis_client=None
) -> Optional[Dict]:
    """Read the last known-good status for a single VM/LXC from Redis."""
    redis_client = redis_client or get_redis_client()

    try:
        cached = redis_client.get(
            get_guest_status_cache_key(cluster_or_identifier, node, kind, vmid)
        )
    except Exception:
        return None

    if not cached:
        return None

    if isinstance(cached, bytes):
        cached = cached.decode("utf-8")

    try:
        return json.loads(cached)
    except Exception:
        return None


def set_cached_guest_status(
    cluster_or_identifier, node: str, kind: str, vmid, status: Dict, redis_client=None
) -> None:
    """Store a successful VM/LXC status result in Redis with a two-hour TTL."""
    redis_client = redis_client or get_redis_client()

    try:
        redis_client.setex(
            get_guest_status_cache_key(cluster_or_identifier, node, kind, vmid),
            PROXMOX_GUEST_STATUS_CACHE_TTL_SECONDS,
            json.dumps(status, default=str),
        )
    except Exception:
        pass


# Tracks how long a VM has *continuously* shown the zero-disk/missing-agent
# warning - distinct from PROXMOX_GUEST_STATUS_CACHE above, which only
# remembers the last known-good status. Without this, an alert email had no
# way to say whether a warning was a brand-new (possibly flaky) reading or
# one that has persisted across many checks, since the last-known-good cache
# is never even consulted once a live check succeeds - even if it reports a
# zero disk.
PROXMOX_GUEST_WARNING_STREAK_PREFIX = "proxmox-guest-warning-streak"
PROXMOX_GUEST_WARNING_STREAK_TTL_SECONDS = int(
    os.environ.get("PROXMOX_GUEST_WARNING_STREAK_TTL_SECONDS", str(7 * 24 * 60 * 60))
)


def get_guest_warning_streak_key(
    cluster_or_identifier, node: str, kind: str, vmid
) -> str:
    """Build the Redis key tracking an in-progress warning streak for a guest."""
    cluster_identifier = _resolve_cluster_identifier(cluster_or_identifier)
    return (
        f"{PROXMOX_GUEST_WARNING_STREAK_PREFIX}:"
        f"{cluster_identifier}:{node}:{kind}:{vmid}"
    )


def record_guest_warning_seen(
    cluster_or_identifier, node: str, kind: str, vmid, redis_client=None
) -> float:
    """Record that a guest's zero-disk/missing-agent warning fired right now.

    Returns the epoch timestamp the current unbroken streak began - the
    first time it was observed, not necessarily now - so callers can tell a
    brand-new warning (possibly a flaky one-off) apart from one that has
    persisted across many checks.
    """
    redis_client = redis_client or get_redis_client()
    key = get_guest_warning_streak_key(cluster_or_identifier, node, kind, vmid)
    now = time.time()

    try:
        existing = redis_client.get(key)
    except Exception:
        return now

    if existing:
        try:
            return float(existing)
        except (TypeError, ValueError):
            pass

    try:
        redis_client.setex(key, PROXMOX_GUEST_WARNING_STREAK_TTL_SECONDS, str(now))
    except Exception:
        pass
    return now


def clear_guest_warning_streak(
    cluster_or_identifier, node: str, kind: str, vmid, redis_client=None
) -> None:
    """Clear a guest's warning streak once it reports real disk usage again,
    so a future recurrence is correctly treated as a new streak."""
    redis_client = redis_client or get_redis_client()
    try:
        redis_client.delete(
            get_guest_warning_streak_key(cluster_or_identifier, node, kind, vmid)
        )
    except Exception:
        pass


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# `df -h` size suffixes are powers of 1024 (K/M/G/T/P/E), matching what
# coreutils' `df -h` emits. A bare number (no suffix) is already in bytes.
_DF_SIZE_UNITS = {
    "": 1,
    "K": 1024,
    "M": 1024**2,
    "G": 1024**3,
    "T": 1024**4,
    "P": 1024**5,
    "E": 1024**6,
}
_DF_SIZE_PATTERN = re.compile(
    r"^((?:\d+(?:\.\d+)?)|(?:\.\d+))\s*([KMGTPE]?)$",
    re.IGNORECASE,
)


def _parse_df_size(value: Optional[str]) -> Optional[int]:
    """Convert a `df -h` human-readable size (e.g. '20G', '512M', '0') to bytes.

    Returns None if the value isn't a recognizable size (e.g. '-').
    """
    if value is None:
        return None

    match = _DF_SIZE_PATTERN.match(value.strip())
    if not match:
        return None

    number, unit = match.groups()

    try:
        number = float(number)
    except ValueError:
        return None

    return int(number * _DF_SIZE_UNITS.get(unit.upper(), 1))


def parse_df_output(output: Optional[str], mountpoint: str = "/") -> Optional[Dict]:
    """
    Parse the plain-text output of `df -h` and extract the used/total byte
    counts for the given mountpoint (defaults to the root filesystem "/").

    This is an "escape valve" fallback used when the QEMU guest agent's
    structured `get-fsinfo` command is unavailable, errors out, or simply
    doesn't report the filesystem we need - by instead running `df -h`
    inside the guest and parsing its human-readable text output directly.

    Expected input looks like::

        Filesystem      Size  Used Avail Use% Mounted on
        /dev/sda1        20G   12G  6.7G  65% /

    Returns a dict shaped like a single `get-fsinfo` result entry (with
    "mountpoint", "total-bytes", "used-bytes", "name") so it can be used as
    a drop-in fallback entry, or None if no matching/parsable line for the
    requested mountpoint was found.
    """
    if not output:
        return None

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 6:
            continue

        # Filesystem  Size  Used  Avail  Use%  Mounted-on
        if parts[-1] != mountpoint:
            continue

        total = _parse_df_size(parts[-5])
        used = _parse_df_size(parts[-4])

        if total is None or used is None:
            continue

        return {
            "mountpoint": mountpoint,
            "name": parts[0],
            "total-bytes": total,
            "used-bytes": used,
        }

    return None


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


def set_cached_proxmox_disk_data(
    cluster: Dict, payload: Dict, redis_client=None
) -> Dict:
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
    redis_client = redis_client or get_redis_client()
    payload = get_proxmox_disk_data(
        cluster.get("host"), cluster, redis_client=redis_client
    )
    return set_cached_proxmox_disk_data(cluster, payload, redis_client=redis_client)


def get_proxmox_disk_data_cached(cluster: Dict, redis_client=None) -> Dict:
    """Return cached Proxmox data when available, otherwise fetch live data."""
    cached_payload = get_cached_proxmox_disk_data(cluster, redis_client=redis_client)
    if cached_payload is not None:
        return cached_payload

    return fetch_and_cache_proxmox_disk_data(cluster, redis_client=redis_client)


def refresh_proxmox_cluster_cache(
    clusters: List[Dict], redis_client=None
) -> List[Dict]:
    """Refresh Redis cache entries for all configured Proxmox clusters."""
    redis_client = redis_client or get_redis_client()
    results = []

    for cluster in clusters or []:
        results.append(
            fetch_and_cache_proxmox_disk_data(cluster, redis_client=redis_client)
        )

    return results


class ProxmoxClient:
    """Client for interacting with Proxmox API"""

    def __init__(
        self,
        host: str,
        user: str,
        token_id: str,
        token_secret: str,
        verify_ssl: bool = False,
    ):
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
        self.session.headers.update(
            {"Authorization": f"PVEAPIToken={user}!{token_id}={token_secret}"}
        )

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
                f"{self.base_url}/nodes/{node}/storage", timeout=10
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
                f"{self.base_url}/nodes/{node}/qemu", timeout=10
            )
            response.raise_for_status()
            vms = response.json().get("data", [])
        except Exception as e:
            print(f"Error getting VMs for {node}: {e}")

        try:
            response = self.session.get(f"{self.base_url}/nodes/{node}/lxc", timeout=10)
            response.raise_for_status()
            containers = response.json().get("data", [])
        except Exception as e:
            print(f"Error getting LXCs for {node}: {e}")

        return vms, containers

    def get_vm_status(self, node: str, vmid: str) -> Optional[Dict]:
        """Get detailed status for a VM including disk usage"""
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/status/current", timeout=10
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            print(f"Error getting VM status for {node}/{vmid}: {e}")
            return None

    def get_vm_agent_status(self, node: str, vmid: str) -> Dict:
        """Determine whether the QEMU guest agent is available for a VM.

        `reachable` distinguishes a real answer from Proxmox (HTTP error
        response - the agent genuinely isn't there) from a failure to even
        reach Proxmox (connection error/timeout - `installed` is left as
        `None` since we have no idea, rather than falsely asserting "No").
        """
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/agent/info",
                timeout=10,
            )
            response.raise_for_status()
            return {"installed": True, "error": None, "reachable": True}
        except requests.HTTPError as error:
            response = getattr(error, "response", None)
            message = None

            if response is not None:
                try:
                    payload = response.json()
                    message = (
                        payload.get("errors")
                        or payload.get("message")
                        or payload.get("data")
                    )
                    if isinstance(message, dict):
                        message = json.dumps(message)
                except Exception:
                    message = response.text

            return {
                "installed": False,
                "error": message or str(error),
                "reachable": True,
            }
        except Exception as error:
            return {
                "installed": None,
                "error": str(error),
                "reachable": False,
            }

    def get_vm_guest_fsinfo(self, node: str, vmid: str) -> Optional[Dict]:
        """Get filesystem information from QEMU guest agent (only works if agent is installed and running).

        Falls back to running `df -h` inside the guest (via the agent's
        exec API) and parsing its plain-text output as an escape valve when
        the structured `get-fsinfo` QGA command fails outright, or succeeds
        but doesn't include the root ("/") filesystem - e.g. older guest
        agents or OSes that don't implement get-fsinfo.
        """
        result = []
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/agent/get-fsinfo",
                timeout=10,
            )
            response.raise_for_status()
            result = list(response.json().get("data", {}).get("result") or [])
        except Exception:
            # If this fails outright, guest agent may not support get-fsinfo
            # at all - fall through to the df -h escape valve below.
            result = []

        if not any(fs.get("mountpoint") == "/" for fs in result):
            df_root = self.get_vm_guest_df(node, vmid)
            if df_root:
                result.append(df_root)

        if not result:
            return None

        return {"result": result}

    def exec_guest_command(
        self,
        node: str,
        vmid: str,
        command: List[str],
        timeout: int = 10,
        poll_attempts: int = 10,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """
        Run a command inside a VM's guest OS via the QEMU guest agent's
        exec/exec-status API and return its stdout.

        This is the building block for the `df -h` escape valve: when the
        structured `get-fsinfo` guest agent command isn't available or
        reliable, we can still shell out and parse plain-text output
        instead.

        Returns None if the agent isn't available, the command fails to
        launch, or it doesn't finish within `poll_attempts * poll_interval`
        seconds.
        """
        try:
            response = self.session.post(
                f"{self.base_url}/nodes/{node}/qemu/{vmid}/agent/exec",
                data={"command": command},
                timeout=timeout,
            )
            response.raise_for_status()
            pid = response.json().get("data", {}).get("pid")
        except Exception:
            return None

        if not pid:
            return None

        for _ in range(poll_attempts):
            try:
                status_response = self.session.get(
                    f"{self.base_url}/nodes/{node}/qemu/{vmid}/agent/exec-status",
                    params={"pid": pid},
                    timeout=timeout,
                )
                status_response.raise_for_status()
                status = status_response.json().get("data", {})
            except Exception:
                return None

            if status.get("exited"):
                return status.get("out-data")

            time.sleep(poll_interval)

        return None

    def get_vm_guest_df(self, node: str, vmid: str) -> Optional[Dict]:
        """
        Escape valve fallback for filesystem info: run `df -h` inside the
        guest via the QEMU guest agent's exec API and parse its plain-text
        output for the root ("/") filesystem.

        Used by get_vm_guest_fsinfo() when the structured `get-fsinfo` QGA
        command fails outright or doesn't report the root filesystem.
        """
        output = self.exec_guest_command(node, vmid, ["df", "-h"])
        return parse_df_output(output, mountpoint="/")

    def get_container_status(self, node: str, vmid: str) -> Optional[Dict]:
        """Get detailed status for a container including disk usage"""
        try:
            response = self.session.get(
                f"{self.base_url}/nodes/{node}/lxc/{vmid}/status/current", timeout=10
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
                f"{self.base_url}/nodes/{node}/storage/{storage}/content", timeout=10
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            print(f"Error getting disk info for {node}/{storage}: {e}")
            return None


def get_proxmox_disk_data(
    host_ip: str, cluster_config: Dict, redis_client=None
) -> Dict:
    """
    Retrieve disk space data from a Proxmox host

    :param host_ip: Proxmox cluster host IP
    :param cluster_config: Cluster configuration dict with keys: host, user, token_id, token_secret, verify_ssl (optional)
    :param redis_client: Optional Redis client used to fall back to the last
        known-good status for a VM/LXC when its live status call fails
    :return: Dictionary with disk space information
    """
    try:
        # Extract credentials from cluster config
        user = cluster_config.get("user")
        token_id = cluster_config.get("token_id")
        token_secret = cluster_config.get("token_secret")
        verify_ssl = cluster_config.get("verify_ssl", False)

        if not all([user, token_id, token_secret]):
            return {
                "error": "Invalid cluster configuration. Missing user, token_id, or token_secret"
            }

        client = ProxmoxClient(
            host=host_ip,
            user=user,
            token_id=token_id,
            token_secret=token_secret,
            verify_ssl=verify_ssl,
        )

        result = {"host": host_ip, "nodes": [], "error": None}

        nodes = client.get_nodes()
        if not nodes:
            result["error"] = "Could not retrieve nodes"
            return result

        cluster_identifier = (
            cluster_config.get("_id") or cluster_config.get("name") or host_ip
        )

        for node in nodes:
            node_info = _build_node_info(
                node, client, cluster_identifier, redis_client=redis_client
            )
            result["nodes"].append(node_info)

        return result

    except Exception:
        return {"error": "Failed to get Proxmox data", "host": host_ip}


def _to_int(value):
    """Convert value to integer, returning 0 on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _build_node_info(node, client, cluster_identifier=None, redis_client=None) -> Dict:
    """Build node information including storage, VMs, and containers."""
    node_name = node.get("node")
    node_info = {
        "name": node_name,
        "status": node.get("status"),
        "storage": [],
        "vms": [],
        "containers": [],
    }

    # Get storage info
    _add_storage_info(node_info, client, node_name)

    # Get VMs and containers
    vms, containers = client.get_vms_and_containers(node_name)
    _add_vm_info(
        node_info,
        client,
        node_name,
        vms,
        cluster_identifier,
        redis_client=redis_client,
    )
    _add_container_info(
        node_info,
        client,
        node_name,
        containers,
        cluster_identifier,
        redis_client=redis_client,
    )

    return node_info


def _add_storage_info(node_info, client, node_name):
    """Add storage information to node info."""
    storage_list = client.get_storage(node_name)
    for storage in storage_list:
        storage_name = storage.get("storage")
        storage_info = {
            "name": storage_name,
            "type": storage.get("type"),
            "enabled": storage.get("enabled", 1),
            "total": storage.get("total"),
            "used": storage.get("used"),
            "available": storage.get("available"),
        }
        node_info["storage"].append(storage_info)


def _add_vm_info(
    node_info, client, node_name, vms, cluster_identifier=None, redis_client=None
):
    """Add VM information to node info."""
    for vm in vms:
        vmid = vm.get("vmid")
        vm_status = client.get_vm_status(node_name, str(vmid))
        used_cached_status = False
        live_check_failed = vm_status is None
        cache_key = None

        if cluster_identifier is not None:
            cache_key = get_guest_status_cache_key(
                cluster_identifier, node_name, "vm", vmid
            )

        if vm_status is not None:
            if cluster_identifier is not None:
                set_cached_guest_status(
                    cluster_identifier,
                    node_name,
                    "vm",
                    vmid,
                    vm_status,
                    redis_client=redis_client,
                )
        elif cluster_identifier is not None:
            # Live status call failed - fall back to the last known-good
            # status (retained for up to two hours) instead of treating the
            # VM as having zero disk usage / a missing guest agent.
            cached_status = get_cached_guest_status(
                cluster_identifier, node_name, "vm", vmid, redis_client=redis_client
            )
            if cached_status is not None:
                vm_status = cached_status
                used_cached_status = True

        agent_status = client.get_vm_agent_status(node_name, str(vmid))
        agent_used_cached_status = False
        agent_live_check_failed = not agent_status.get("reachable", True)
        agent_cache_key = None

        if cluster_identifier is not None:
            agent_cache_key = get_guest_status_cache_key(
                cluster_identifier, node_name, "vm-agent", vmid
            )

        if agent_status.get("reachable", True):
            if cluster_identifier is not None:
                set_cached_guest_status(
                    cluster_identifier,
                    node_name,
                    "vm-agent",
                    vmid,
                    agent_status,
                    redis_client=redis_client,
                )
        elif cluster_identifier is not None:
            # Couldn't reach Proxmox to ask about the agent at all - fall
            # back to the last known-good answer instead of reporting a
            # confident "agent missing" from a single connection blip.
            cached_agent_status = get_cached_guest_status(
                cluster_identifier,
                node_name,
                "vm-agent",
                vmid,
                redis_client=redis_client,
            )
            if cached_agent_status is not None:
                agent_status = cached_agent_status
                agent_used_cached_status = True

        vm_info = _build_vm_info(
            vm,
            vm_status,
            agent_status,
            client,
            node_name,
            cluster_identifier=cluster_identifier,
            redis_client=redis_client,
        )
        vm_info["_status_from_cache"] = used_cached_status
        vm_info["_status_live_check_failed"] = live_check_failed
        vm_info["_status_cache_key"] = cache_key
        vm_info["_agent_status_from_cache"] = agent_used_cached_status
        vm_info["_agent_status_live_check_failed"] = agent_live_check_failed
        vm_info["_agent_status_cache_key"] = agent_cache_key

        warning_first_seen = None
        if cluster_identifier is not None:
            if vm_info.get("qemu_guest_agent_warning_inferred"):
                warning_first_seen = record_guest_warning_seen(
                    cluster_identifier,
                    node_name,
                    "vm",
                    vmid,
                    redis_client=redis_client,
                )
            else:
                clear_guest_warning_streak(
                    cluster_identifier,
                    node_name,
                    "vm",
                    vmid,
                    redis_client=redis_client,
                )
        vm_info["_warning_first_seen"] = warning_first_seen

        node_info["vms"].append(vm_info)


def _add_container_info(
    node_info,
    client,
    node_name,
    containers,
    cluster_identifier=None,
    redis_client=None,
):
    """Add container information to node info."""
    for container in containers:
        vmid = container.get("vmid")
        container_status = client.get_container_status(node_name, str(vmid))
        used_cached_status = False
        live_check_failed = container_status is None
        cache_key = None

        if cluster_identifier is not None:
            cache_key = get_guest_status_cache_key(
                cluster_identifier, node_name, "lxc", vmid
            )

        if container_status is not None:
            if cluster_identifier is not None:
                set_cached_guest_status(
                    cluster_identifier,
                    node_name,
                    "lxc",
                    vmid,
                    container_status,
                    redis_client=redis_client,
                )
        elif cluster_identifier is not None:
            # Live status call failed - fall back to the last known-good
            # status (retained for up to two hours) instead of treating the
            # container as having no disk usage data.
            cached_status = get_cached_guest_status(
                cluster_identifier, node_name, "lxc", vmid, redis_client=redis_client
            )
            if cached_status is not None:
                container_status = cached_status
                used_cached_status = True

        container_info = {
            "id": vmid,
            "name": container.get("name"),
            "status": container.get("status"),
            "maxdisk": container.get("maxdisk"),
            "disk": container_status.get("disk") if container_status else None,
            "maxmem": container.get("maxmem"),
            "mem": container_status.get("mem") if container_status else None,
            "_status_from_cache": used_cached_status,
            "_status_live_check_failed": live_check_failed,
            "_status_cache_key": cache_key,
        }
        node_info["containers"].append(container_info)


def _get_guest_disk_info(
    client, node_name, vmid, disk, maxdisk, is_running, qemu_truly_installed
):
    """Extract guest filesystem info if available. Returns updated disk and maxdisk."""
    if not (qemu_truly_installed and is_running and _to_int(disk) == 0):
        return disk, maxdisk, None

    guest_disk_info = client.get_vm_guest_fsinfo(node_name, str(vmid))
    if not guest_disk_info:
        return disk, maxdisk, guest_disk_info

    fsinfo = guest_disk_info.get("result", [])
    for fs in fsinfo:
        if fs.get("mountpoint") == "/":
            return fs.get("used-bytes"), fs.get("total-bytes"), guest_disk_info
    return disk, maxdisk, guest_disk_info


def _build_vm_info(
    vm,
    vm_status,
    agent_status,
    client,
    node_name,
    cluster_identifier=None,
    redis_client=None,
) -> Dict:
    """Build VM information from VM data and status."""
    vmid = vm.get("vmid")
    maxdisk = vm.get("maxdisk")
    disk = vm_status.get("disk") if vm_status else None
    is_running = str(vm.get("status") or "").lower() == "running"

    # Determine if QEMU guest agent is confirmed installed. `installed` may
    # be None when the live check couldn't reach Proxmox at all and no
    # cached answer was available - that's "unknown", not "not installed",
    # so only a definite True counts here.
    agent_installed = agent_status.get("installed")
    qemu_truly_installed = agent_installed is True

    # Try to get real disk info from guest if agent is installed and disk shows zero
    disk, maxdisk, guest_disk_info = _get_guest_disk_info(
        client, node_name, vmid, disk, maxdisk, is_running, qemu_truly_installed
    )

    # Check if disk is reported as zero for a running VM (agent may exist but disk metrics unavailable)
    qemu_warning_inferred = is_running and _to_int(maxdisk) > 0 and _to_int(disk) == 0

    last_known_good_disk = None
    if cluster_identifier is not None:
        if qemu_warning_inferred:
            # Zero disk despite the agent/status calls succeeding - before
            # treating this as a real "can't measure" problem, see whether a
            # real reading was captured within the last two hours.
            last_known_good_disk = get_cached_good_disk(
                cluster_identifier, node_name, "vm", vmid, redis_client=redis_client
            )
        elif _to_int(maxdisk) > 0:
            # A genuinely measured, non-zero disk reading - remember it so a
            # later transient zero-read doesn't trigger a false alert.
            set_cached_good_disk(
                cluster_identifier,
                node_name,
                "vm",
                vmid,
                disk,
                maxdisk,
                redis_client=redis_client,
            )

    vm_info = {
        "id": vmid,
        "name": vm.get("name"),
        "status": vm.get("status"),
        "maxdisk": maxdisk,
        "disk": disk,
        "maxmem": vm.get("maxmem"),
        "mem": vm_status.get("mem") if vm_status else None,
        "qemu_guest_agent_installed": agent_installed,
        "qemu_guest_agent_error": agent_status.get("error"),
        "qemu_guest_agent_warning_inferred": qemu_warning_inferred,
        "_last_known_good_disk": last_known_good_disk,
    }
    # Include raw guest info for debugging if available
    if guest_disk_info:
        vm_info["_debug_guest_fsinfo"] = guest_disk_info
    return vm_info
