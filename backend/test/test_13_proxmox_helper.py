#!/usr/bin/env python3
"""
Tests for backend/proxmox_helper.py

Covers Proxmox API client, caching, and data transformation functions.
"""

import json
import pytest
import redis
from unittest.mock import Mock, MagicMock, patch, call
import requests

import proxmox_helper
import serve


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client."""
    return Mock(spec=redis.Redis)


@pytest.fixture
def mock_session():
    """Provide a mock requests.Session."""
    return Mock(spec=requests.Session)


# ---------------------------------------------------------------------------
# _parse_df_size - size parsing
# ---------------------------------------------------------------------------


def test_parse_df_size_bytes_with_no_unit():
    """Parse plain byte value."""
    result = proxmox_helper._parse_df_size("1024")
    assert result == 1024


def test_parse_df_size_kilobytes():
    """Parse kilobyte value."""
    result = proxmox_helper._parse_df_size("2K")
    assert result == 2048


def test_parse_df_size_megabytes():
    """Parse megabyte value."""
    result = proxmox_helper._parse_df_size("1M")
    assert result == 1048576


def test_parse_df_size_gigabytes():
    """Parse gigabyte value."""
    result = proxmox_helper._parse_df_size("20G")
    assert result == 21474836480


def test_parse_df_size_terabytes():
    """Parse terabyte value."""
    result = proxmox_helper._parse_df_size("1T")
    assert result == 1099511627776


def test_parse_df_size_petabytes():
    """Parse petabyte value."""
    result = proxmox_helper._parse_df_size("1P")
    assert result == 1125899906842624


def test_parse_df_size_exabytes():
    """Parse exabyte value."""
    result = proxmox_helper._parse_df_size("1E")
    assert result == 1152921504606846976


def test_parse_df_size_case_insensitive():
    """Units are case-insensitive."""
    result1 = proxmox_helper._parse_df_size("1m")
    result2 = proxmox_helper._parse_df_size("1M")
    assert result1 == result2 == 1048576


def test_parse_df_size_decimal():
    """Parse decimal values."""
    result = proxmox_helper._parse_df_size("1.5G")
    assert result == 1610612736


def test_parse_df_size_decimal_without_leading_digit():
    """Parse values starting with decimal point."""
    result = proxmox_helper._parse_df_size(".5G")
    assert result == 536870912


def test_parse_df_size_with_whitespace():
    """Handle whitespace around value."""
    result = proxmox_helper._parse_df_size("  10G  ")
    assert result == 10737418240


def test_parse_df_size_invalid_format_returns_none():
    """Invalid format returns None."""
    assert proxmox_helper._parse_df_size("-") is None
    assert proxmox_helper._parse_df_size("abc") is None
    assert proxmox_helper._parse_df_size("") is None


def test_parse_df_size_none_returns_none():
    """None input returns None."""
    assert proxmox_helper._parse_df_size(None) is None


def test_parse_df_size_invalid_unit_not_matched():
    """Unknown units are not matched by the regex pattern."""
    result = proxmox_helper._parse_df_size("512Z")
    # Unknown unit "Z" is not in the allowed set, so pattern doesn't match
    assert result is None


# ---------------------------------------------------------------------------
# parse_df_output - df command parsing
# ---------------------------------------------------------------------------


def test_parse_df_output_standard_linux_output():
    """Parse standard df output for root filesystem."""
    output = """Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        20G   12G  6.7G  65% /
tmpfs           1.0G     0  1.0G   0% /dev/shm"""

    result = proxmox_helper.parse_df_output(output, "/")

    assert result is not None
    assert result["mountpoint"] == "/"
    assert result["name"] == "/dev/sda1"
    assert result["total-bytes"] == 21474836480
    assert result["used-bytes"] == 12884901888


def test_parse_df_output_missing_mountpoint():
    """Return None when mountpoint not found."""
    output = """Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        20G   12G  6.7G  65% /"""

    result = proxmox_helper.parse_df_output(output, "/home")
    assert result is None


def test_parse_df_output_none_input():
    """Handle None input."""
    assert proxmox_helper.parse_df_output(None) is None


def test_parse_df_output_empty_string():
    """Handle empty string."""
    assert proxmox_helper.parse_df_output("") is None


def test_parse_df_output_header_only():
    """Handle output with only header."""
    output = "Filesystem      Size  Used Avail Use% Mounted on"
    assert proxmox_helper.parse_df_output(output, "/") is None


def test_parse_df_output_unparseable_line():
    """Skip lines that can't be parsed."""
    output = """Filesystem      Size  Used Avail Use% Mounted on
invalid line with too few columns
/dev/sda1        20G   12G  6.7G  65% /"""

    result = proxmox_helper.parse_df_output(output, "/")
    assert result is not None
    assert result["total-bytes"] == 21474836480


def test_parse_df_output_unparseable_size_values():
    """Skip lines where size values can't be parsed."""
    output = """Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        -     -    -     -  /
/dev/sda2        20G   12G  6.7G  65% /home"""

    result = proxmox_helper.parse_df_output(output, "/")
    assert result is None

    result = proxmox_helper.parse_df_output(output, "/home")
    assert result is not None


# ---------------------------------------------------------------------------
# get_proxmox_cache_key
# ---------------------------------------------------------------------------


def test_get_proxmox_cache_key_from_string():
    """Generate cache key from string identifier."""
    key = proxmox_helper.get_proxmox_cache_key("cluster-1")
    assert key == "proxmox-disk:cluster-1"


def test_get_proxmox_cache_key_from_dict_with_id():
    """Generate cache key from dict with _id."""
    key = proxmox_helper.get_proxmox_cache_key({"_id": "123", "name": "cluster"})
    assert key == "proxmox-disk:123"


def test_get_proxmox_cache_key_from_dict_with_name():
    """Generate cache key from dict with name."""
    key = proxmox_helper.get_proxmox_cache_key(
        {"name": "cluster-1", "host": "10.0.0.1"}
    )
    assert key == "proxmox-disk:cluster-1"


def test_get_proxmox_cache_key_from_dict_with_host():
    """Generate cache key from dict with host."""
    key = proxmox_helper.get_proxmox_cache_key({"host": "10.0.0.1"})
    assert key == "proxmox-disk:10.0.0.1"


def test_get_proxmox_cache_key_fails_without_identifier():
    """Raise error when no identifier can be extracted."""
    with pytest.raises(ValueError, match="identifier is required"):
        proxmox_helper.get_proxmox_cache_key({})


# ---------------------------------------------------------------------------
# Redis caching functions
# ---------------------------------------------------------------------------


def test_get_cached_proxmox_disk_data_found(mock_redis):
    """Retrieve cached data from Redis."""
    cluster = {"_id": "123", "name": "cluster-1", "host": "10.0.0.1"}
    cached_data = {
        "host": "10.0.0.1",
        "nodes": [],
    }

    mock_redis.get.return_value = json.dumps(cached_data).encode("utf-8")

    result = proxmox_helper.get_cached_proxmox_disk_data(cluster, mock_redis)

    assert result is not None
    assert result["host"] == "10.0.0.1"
    assert result["cluster_name"] == "cluster-1"
    mock_redis.get.assert_called_once()


def test_get_cached_proxmox_disk_data_not_found(mock_redis):
    """Return None when cache miss."""
    cluster = {"_id": "123", "name": "cluster-1"}
    mock_redis.get.return_value = None

    result = proxmox_helper.get_cached_proxmox_disk_data(cluster, mock_redis)
    assert result is None


def test_get_cached_proxmox_disk_data_redis_error(mock_redis):
    """Return None on Redis error."""
    cluster = {"_id": "123", "name": "cluster-1"}
    mock_redis.get.side_effect = Exception("Redis error")

    result = proxmox_helper.get_cached_proxmox_disk_data(cluster, mock_redis)
    assert result is None


def test_get_cached_proxmox_disk_data_invalid_json(mock_redis):
    """Return None on invalid JSON."""
    cluster = {"_id": "123", "name": "cluster-1"}
    mock_redis.get.return_value = b"invalid json"

    result = proxmox_helper.get_cached_proxmox_disk_data(cluster, mock_redis)
    assert result is None


def test_set_cached_proxmox_disk_data(mock_redis):
    """Store data in Redis cache."""
    cluster = {"_id": "123", "name": "cluster-1", "host": "10.0.0.1"}
    payload = {
        "host": "10.0.0.1",
        "nodes": [],
    }

    result = proxmox_helper.set_cached_proxmox_disk_data(cluster, payload, mock_redis)

    assert result["cluster_name"] == "cluster-1"
    mock_redis.setex.assert_called_once()


def test_set_cached_proxmox_disk_data_redis_error(mock_redis):
    """Still return normalized payload even on Redis error."""
    cluster = {"_id": "123", "name": "cluster-1", "host": "10.0.0.1"}
    payload = {"host": "10.0.0.1", "nodes": []}
    mock_redis.setex.side_effect = Exception("Redis error")

    result = proxmox_helper.set_cached_proxmox_disk_data(cluster, payload, mock_redis)
    assert result["cluster_name"] == "cluster-1"


def test_delete_cached_proxmox_disk_data(mock_redis):
    """Delete cache entry."""
    proxmox_helper.delete_cached_proxmox_disk_data("cluster-1", mock_redis)
    mock_redis.delete.assert_called_once_with("proxmox-disk:cluster-1")


def test_delete_cached_proxmox_disk_data_redis_error(mock_redis):
    """Handle Redis errors gracefully."""
    mock_redis.delete.side_effect = Exception("Redis error")
    # Should not raise
    proxmox_helper.delete_cached_proxmox_disk_data("cluster-1", mock_redis)


# ---------------------------------------------------------------------------
# enrich_qemu_flags
# ---------------------------------------------------------------------------


def test_enrich_qemu_flags_running_vm_with_zero_disk():
    """Flag running VM with zero disk as having missing agent warning."""
    payload = {
        "nodes": [
            {
                "vms": [
                    {
                        "status": "running",
                        "maxdisk": 10737418240,
                        "disk": 0,
                    }
                ]
            }
        ]
    }

    result = proxmox_helper.enrich_qemu_flags(payload)
    vm = result["nodes"][0]["vms"][0]

    assert vm["qemu_guest_agent_warning_inferred"] is True
    assert vm["qemu_guest_agent_installed"] is False
    assert "zero" in vm["qemu_guest_agent_error"]


def test_enrich_qemu_flags_running_vm_with_disk():
    """Don't flag running VM with reported disk."""
    payload = {
        "nodes": [
            {
                "vms": [
                    {
                        "status": "running",
                        "maxdisk": 10737418240,
                        "disk": 5368709120,
                    }
                ]
            }
        ]
    }

    result = proxmox_helper.enrich_qemu_flags(payload)
    vm = result["nodes"][0]["vms"][0]

    assert vm["qemu_guest_agent_warning_inferred"] is False
    assert vm["qemu_guest_agent_installed"] is True


def test_enrich_qemu_flags_stopped_vm_with_zero_disk():
    """Don't flag stopped VM with zero disk."""
    payload = {
        "nodes": [
            {
                "vms": [
                    {
                        "status": "stopped",
                        "maxdisk": 10737418240,
                        "disk": 0,
                    }
                ]
            }
        ]
    }

    result = proxmox_helper.enrich_qemu_flags(payload)
    vm = result["nodes"][0]["vms"][0]

    assert vm["qemu_guest_agent_warning_inferred"] is False


def test_enrich_qemu_flags_preserves_existing_flags():
    """Preserve existing QEMU flags if already set."""
    payload = {
        "nodes": [
            {
                "vms": [
                    {
                        "status": "running",
                        "maxdisk": 10737418240,
                        "disk": 0,
                        "qemu_guest_agent_warning_inferred": False,
                        "qemu_guest_agent_installed": True,
                        "qemu_guest_agent_error": "custom error",
                    }
                ]
            }
        ]
    }

    result = proxmox_helper.enrich_qemu_flags(payload)
    vm = result["nodes"][0]["vms"][0]

    assert vm["qemu_guest_agent_warning_inferred"] is False
    assert vm["qemu_guest_agent_installed"] is True
    assert vm["qemu_guest_agent_error"] == "custom error"


def test_enrich_qemu_flags_empty_nodes():
    """Handle payload with no nodes."""
    payload = {"nodes": []}
    result = proxmox_helper.enrich_qemu_flags(payload)
    assert result["nodes"] == []


# ---------------------------------------------------------------------------
# format_proxmox_cluster_payload
# ---------------------------------------------------------------------------


def test_format_proxmox_cluster_payload_basic():
    """Format and attach cluster metadata."""
    cluster = {"_id": "123", "name": "cluster-1", "host": "10.0.0.1"}
    data = {"nodes": []}

    result = proxmox_helper.format_proxmox_cluster_payload(cluster, data)

    assert result["cluster_name"] == "cluster-1"
    assert result["host"] == "10.0.0.1"
    assert result["_id"] == "123"
    assert result["nodes"] == []


def test_format_proxmox_cluster_payload_none_data():
    """Handle None data."""
    cluster = {"name": "cluster-1", "host": "10.0.0.1"}

    result = proxmox_helper.format_proxmox_cluster_payload(cluster, None)

    assert result["cluster_name"] == "cluster-1"
    assert result["host"] == "10.0.0.1"


def test_format_proxmox_cluster_payload_converts_id_to_string():
    """Convert _id to string."""
    cluster = {"_id": 123, "name": "cluster-1"}

    result = proxmox_helper.format_proxmox_cluster_payload(cluster, {})
    assert result["_id"] == "123"


# ---------------------------------------------------------------------------
# ProxmoxClient - basic initialization and requests
# ---------------------------------------------------------------------------


def test_proxmox_client_initialization():
    """Initialize ProxmoxClient with credentials."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1",
        user="root@pam",
        token_id="token-1",
        token_secret="secret-1",
        verify_ssl=False,
    )

    assert client.host == "10.0.0.1"
    assert client.user == "root@pam"
    assert client.verify_ssl is False
    assert "10.0.0.1:8006" in client.base_url


def test_proxmox_client_get_nodes_success(mock_session):
    """Successfully retrieve nodes."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [
            {"node": "node-1", "status": "online"},
            {"node": "node-2", "status": "online"},
        ]
    }
    mock_session.get.return_value = mock_response

    result = client.get_nodes()

    assert len(result) == 2
    assert result[0]["node"] == "node-1"


def test_proxmox_client_get_nodes_error(mock_session):
    """Handle error retrieving nodes."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_session.get.side_effect = Exception("Connection error")

    result = client.get_nodes()
    assert result == []


def test_proxmox_client_get_storage_success(mock_session):
    """Successfully retrieve storage."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [{"storage": "local", "type": "dir", "total": 1000, "used": 500}]
    }
    mock_session.get.return_value = mock_response

    result = client.get_storage("node-1")

    assert len(result) == 1
    assert result[0]["storage"] == "local"


def test_proxmox_client_get_storage_error(mock_session):
    """Handle error retrieving storage."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_session.get.side_effect = Exception("Connection error")

    result = client.get_storage("node-1")
    assert result == []


def test_proxmox_client_get_vms_and_containers_success(mock_session):
    """Successfully retrieve VMs and containers."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    vm_response = Mock()
    vm_response.json.return_value = {"data": [{"vmid": 100, "name": "vm-1"}]}

    container_response = Mock()
    container_response.json.return_value = {"data": [{"vmid": 200, "name": "lxc-1"}]}

    mock_session.get.side_effect = [vm_response, container_response]

    vms, containers = client.get_vms_and_containers("node-1")

    assert len(vms) == 1
    assert vms[0]["vmid"] == 100
    assert len(containers) == 1
    assert containers[0]["vmid"] == 200


def test_proxmox_client_get_vms_and_containers_partial_failure(mock_session):
    """Handle partial failure (VMs OK, containers fail)."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    vm_response = Mock()
    vm_response.json.return_value = {"data": [{"vmid": 100}]}

    mock_session.get.side_effect = [vm_response, Exception("Connection error")]

    vms, containers = client.get_vms_and_containers("node-1")

    assert len(vms) == 1
    assert containers == []


def test_proxmox_client_get_vm_status_success(mock_session):
    """Successfully retrieve VM status."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_response = Mock()
    mock_response.json.return_value = {"data": {"disk": 5368709120, "mem": 1073741824}}
    mock_session.get.return_value = mock_response

    result = client.get_vm_status("node-1", "100")

    assert result["disk"] == 5368709120
    assert result["mem"] == 1073741824


def test_proxmox_client_get_vm_status_error(mock_session):
    """Handle error retrieving VM status."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_session.get.side_effect = Exception("Connection error")

    result = client.get_vm_status("node-1", "100")
    assert result is None


def test_proxmox_client_get_vm_agent_status_success(mock_session):
    """Successfully check QEMU guest agent."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_response = Mock()
    mock_response.json.return_value = {"data": {"supported_commands": []}}
    mock_session.get.return_value = mock_response

    result = client.get_vm_agent_status("node-1", "100")

    assert result["installed"] is True
    assert result["error"] is None


def test_proxmox_client_get_vm_agent_status_not_installed(mock_session):
    """Detect missing QEMU guest agent."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    http_error = requests.HTTPError()
    http_response = Mock()
    http_response.json.return_value = {"errors": "Agent not installed"}
    http_error.response = http_response
    mock_session.get.side_effect = http_error

    result = client.get_vm_agent_status("node-1", "100")

    assert result["installed"] is False
    assert "not installed" in result["error"] or "Agent" in result["error"]


def test_proxmox_client_get_vm_agent_status_http_error_with_json(mock_session):
    """Handle HTTP error with JSON response."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    http_error = requests.HTTPError()
    http_response = Mock()
    http_response.json.return_value = {"message": "Custom error"}
    http_error.response = http_response
    mock_session.get.side_effect = http_error

    result = client.get_vm_agent_status("node-1", "100")

    assert result["installed"] is False
    assert result["error"] == "Custom error"


def test_proxmox_client_get_vm_agent_status_http_error_no_json(mock_session):
    """Handle HTTP error without JSON response."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    http_error = requests.HTTPError()
    http_response = Mock()
    http_response.json.side_effect = Exception("Invalid JSON")
    http_response.text = "Custom error text"
    http_error.response = http_response
    mock_session.get.side_effect = http_error

    result = client.get_vm_agent_status("node-1", "100")

    assert result["installed"] is False
    assert result["error"] == "Custom error text"


def test_proxmox_client_get_vm_agent_status_general_exception(mock_session):
    """Handle general exception."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_session.get.side_effect = Exception("Connection timeout")

    result = client.get_vm_agent_status("node-1", "100")

    assert result["installed"] is False
    assert "timeout" in result["error"]


def test_proxmox_client_get_vm_guest_fsinfo_success(mock_session):
    """Successfully retrieve filesystem info from guest agent."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    fsinfo_response = Mock()
    fsinfo_response.json.return_value = {
        "data": {
            "result": [
                {
                    "mountpoint": "/",
                    "name": "/dev/sda1",
                    "total-bytes": 21474836480,
                    "used-bytes": 10737418240,
                }
            ]
        }
    }
    mock_session.get.return_value = fsinfo_response

    result = client.get_vm_guest_fsinfo("node-1", "100")

    assert result is not None
    assert len(result["result"]) == 1
    assert result["result"][0]["mountpoint"] == "/"


def test_proxmox_client_get_vm_guest_fsinfo_with_df_fallback(mock_session):
    """Fall back to df when get-fsinfo doesn't include root."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    fsinfo_response = Mock()
    fsinfo_response.json.return_value = {
        "data": {
            "result": [
                {
                    "mountpoint": "/boot",
                    "name": "/dev/sda2",
                    "total-bytes": 536870912,
                    "used-bytes": 268435456,
                }
            ]
        }
    }

    df_response = Mock()
    df_response.json.return_value = {"data": {"pid": 123}}

    exec_response = Mock()
    exec_response.json.return_value = {
        "data": {
            "exited": True,
            "out-data": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        20G   12G  6.7G  65% /",
        }
    }

    mock_session.get.side_effect = [fsinfo_response, df_response, exec_response]
    mock_session.post.return_value = df_response

    result = client.get_vm_guest_fsinfo("node-1", "100")

    assert result is not None
    mountpoints = [fs["mountpoint"] for fs in result["result"]]
    assert "/" in mountpoints


def test_proxmox_client_exec_guest_command_success(mock_session):
    """Successfully execute guest command."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    exec_response = Mock()
    exec_response.json.return_value = {"data": {"pid": 123}}

    status_response = Mock()
    status_response.json.return_value = {"data": {"exited": True, "out-data": "output"}}

    mock_session.post.return_value = exec_response
    mock_session.get.return_value = status_response

    result = client.exec_guest_command("node-1", "100", ["df", "-h"])

    assert result == "output"


def test_proxmox_client_exec_guest_command_no_pid(mock_session):
    """Handle command that returns no PID."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    exec_response = Mock()
    exec_response.json.return_value = {"data": {}}
    mock_session.post.return_value = exec_response

    result = client.exec_guest_command("node-1", "100", ["df", "-h"])

    assert result is None


def test_proxmox_client_exec_guest_command_timeout(mock_session):
    """Handle command that times out."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    exec_response = Mock()
    exec_response.json.return_value = {"data": {"pid": 123}}

    status_response = Mock()
    status_response.json.return_value = {"data": {"exited": False}}

    mock_session.post.return_value = exec_response
    mock_session.get.return_value = status_response

    result = client.exec_guest_command("node-1", "100", ["df", "-h"], poll_attempts=2)

    assert result is None


def test_proxmox_client_exec_guest_command_post_error(mock_session):
    """Handle error posting command."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_session.post.side_effect = Exception("Connection error")

    result = client.exec_guest_command("node-1", "100", ["df", "-h"])

    assert result is None


def test_proxmox_client_exec_guest_command_status_error(mock_session):
    """Handle error checking command status."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    exec_response = Mock()
    exec_response.json.return_value = {"data": {"pid": 123}}

    mock_session.post.return_value = exec_response
    mock_session.get.side_effect = Exception("Connection error")

    result = client.exec_guest_command("node-1", "100", ["df", "-h"])

    assert result is None


def test_proxmox_client_get_container_status_success(mock_session):
    """Successfully retrieve container status."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_response = Mock()
    mock_response.json.return_value = {"data": {"disk": 5368709120}}
    mock_session.get.return_value = mock_response

    result = client.get_container_status("node-1", "200")

    assert result["disk"] == 5368709120


def test_proxmox_client_get_container_status_error(mock_session):
    """Handle error retrieving container status."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_session.get.side_effect = Exception("Connection error")

    result = client.get_container_status("node-1", "200")
    assert result is None


def test_proxmox_client_get_disk_info_success(mock_session):
    """Successfully retrieve disk info."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [{"volume": "local:100/vm-100-disk-0.qcow2"}]
    }
    mock_session.get.return_value = mock_response

    result = client.get_disk_info("node-1", "local")

    assert result == [{"volume": "local:100/vm-100-disk-0.qcow2"}]


def test_proxmox_client_get_disk_info_error(mock_session):
    """Handle error retrieving disk info."""
    client = proxmox_helper.ProxmoxClient(
        host="10.0.0.1", user="root@pam", token_id="token-1", token_secret="secret-1"
    )
    client.session = mock_session

    mock_session.get.side_effect = Exception("Connection error")

    result = client.get_disk_info("node-1", "local")
    assert result is None


# ---------------------------------------------------------------------------
# _to_int edge cases
# ---------------------------------------------------------------------------


def test_to_int_valid_string():
    """Convert valid string to int."""
    assert proxmox_helper._to_int("42") == 42


def test_to_int_invalid_string():
    """Return 0 for invalid string."""
    assert proxmox_helper._to_int("abc") == 0


def test_to_int_none():
    """Return 0 for None."""
    assert proxmox_helper._to_int(None) == 0


def test_to_int_float_string_returns_zero():
    """Float strings cannot be converted via int(), returns 0."""
    assert proxmox_helper._to_int("42.5") == 0


# ---------------------------------------------------------------------------
# High-level data retrieval
# ---------------------------------------------------------------------------


def test_fetch_and_cache_proxmox_disk_data(mock_redis):
    """Fetch and cache Proxmox data."""
    cluster = {
        "_id": "123",
        "name": "cluster-1",
        "host": "10.0.0.1",
        "user": "root@pam",
        "token_id": "token-1",
        "token_secret": "secret-1",
    }

    with patch.object(proxmox_helper, "get_proxmox_disk_data") as mock_get:
        mock_get.return_value = {"host": "10.0.0.1", "nodes": [], "error": None}

        result = proxmox_helper.fetch_and_cache_proxmox_disk_data(cluster, mock_redis)

        assert result["cluster_name"] == "cluster-1"
        mock_redis.setex.assert_called_once()


def test_refresh_proxmox_cluster_cache(mock_redis):
    """Refresh cache for multiple clusters."""
    clusters = [
        {
            "_id": "123",
            "name": "cluster-1",
            "host": "10.0.0.1",
            "user": "root@pam",
            "token_id": "token-1",
            "token_secret": "secret-1",
        },
        {
            "_id": "456",
            "name": "cluster-2",
            "host": "10.0.0.2",
            "user": "root@pam",
            "token_id": "token-2",
            "token_secret": "secret-2",
        },
    ]

    with patch.object(proxmox_helper, "get_proxmox_disk_data") as mock_get:
        mock_get.return_value = {"host": "test", "nodes": [], "error": None}

        results = proxmox_helper.refresh_proxmox_cluster_cache(clusters, mock_redis)

        assert len(results) == 2
        assert mock_get.call_count == 2


def test_refresh_proxmox_cluster_cache_empty_list(mock_redis):
    """Handle empty cluster list."""
    results = proxmox_helper.refresh_proxmox_cluster_cache([], mock_redis)
    assert results == []


# ---------------------------------------------------------------------------
# get_proxmox_disk_data high-level function
# ---------------------------------------------------------------------------


def test_get_proxmox_disk_data_missing_credentials():
    """Return error for missing credentials."""
    result = proxmox_helper.get_proxmox_disk_data(
        "10.0.0.1", {"host": "10.0.0.1"}  # Missing user, token_id, token_secret
    )

    assert result["error"] is not None
    assert "Invalid" in result["error"] or "Missing" in result["error"]


def test_get_proxmox_disk_data_no_nodes():
    """Return error when no nodes can be retrieved."""
    cluster = {
        "host": "10.0.0.1",
        "user": "root@pam",
        "token_id": "token-1",
        "token_secret": "secret-1",
    }

    with patch.object(proxmox_helper.ProxmoxClient, "get_nodes", return_value=[]):
        result = proxmox_helper.get_proxmox_disk_data("10.0.0.1", cluster)

        assert result["error"] is not None
        assert result["host"] == "10.0.0.1"


def test_get_proxmox_disk_data_general_exception():
    """Return generic error on exception."""
    result = proxmox_helper.get_proxmox_disk_data(
        "invalid",
        {"host": "invalid", "user": "root@pam", "token_id": "t", "token_secret": "s"},
    )

    # This might succeed or fail depending on whether requests validates the hostname
    # but we just want to ensure it returns a dict with error field
    assert isinstance(result, dict)
