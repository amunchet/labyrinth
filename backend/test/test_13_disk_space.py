#!/usr/bin/env python3

import json

import pytest
import proxmox_helper
import serve

from common.test import unwrap


def tearDown():
    """Tears down disk-space test data."""
    serve.mongo_client["labyrinth"]["hosts"].delete_many({})
    serve.mongo_client["labyrinth"]["settings"].delete_many({})


@pytest.fixture
def setup():
    """Sets up tests."""
    tearDown()
    yield "Setting up..."
    tearDown()
    return "Done"


def test_get_proxmox_disk_space_uses_tag_and_key_resolution(setup, monkeypatch):
    """Uses configured proxmox tag and resolves host-specific/global API keys."""
    serve.mongo_client["labyrinth"]["settings"].insert_many(
        [
            {"name": "proxmox_tag", "value": "hypervisor"},
            {"name": "proxmox_api_key", "value": "global-key"},
            {"name": "proxmox_api_key_00-00-00-00-01", "value": "host-key"},
        ]
    )

    serve.mongo_client["labyrinth"]["hosts"].insert_many(
        [
            {
                "ip": "10.1.1.1",
                "mac": "00-00-00-00-01",
                "name": "pve-a",
                "tags": "hypervisor,linux",
            },
            {
                "ip": "10.1.1.2",
                "mac": "00-00-00-00-02",
                "name": "pve-b",
                "tags": "hypervisor",
            },
            {
                "ip": "10.1.1.3",
                "mac": "00-00-00-00-03",
                "name": "ignored",
                "tags": "linux",
            },
        ]
    )

    calls = []

    def fake_get_proxmox_disk_data(host_ip, api_key):
        calls.append((host_ip, api_key))
        return {"nodes": [{"name": "node-1", "storage": [], "vms": [], "containers": []}]}

    monkeypatch.setattr(serve.proxmox_helper, "get_proxmox_disk_data", fake_get_proxmox_disk_data)

    response = unwrap(serve.get_proxmox_disk_space)()
    assert response[1] == 200

    data = json.loads(response[0])
    assert len(data["proxmox_hosts"]) == 2

    assert ("10.1.1.1", "host-key") in calls
    assert ("10.1.1.2", "global-key") in calls


def test_get_proxmox_disk_space_prefers_host_field_api_key(setup, monkeypatch):
    """Uses host.proxmox_api_key before legacy per-mac settings and global key."""
    serve.mongo_client["labyrinth"]["settings"].insert_many(
        [
            {"name": "proxmox_tag", "value": "Proxmox"},
            {"name": "proxmox_api_key", "value": "global-key"},
            {"name": "proxmox_api_key_00-00-00-00-99", "value": "legacy-host-key"},
        ]
    )

    serve.mongo_client["labyrinth"]["hosts"].insert_one(
        {
            "ip": "10.1.9.9",
            "mac": "00-00-00-00-99",
            "host": "pve-prefer-host-field",
            "tags": "Proxmox",
            "proxmox_api_key": "host-field-key",
        }
    )

    calls = []

    def fake_get_proxmox_disk_data(host_ip, api_key):
        calls.append((host_ip, api_key))
        return {"nodes": []}

    monkeypatch.setattr(serve.proxmox_helper, "get_proxmox_disk_data", fake_get_proxmox_disk_data)

    response = unwrap(serve.get_proxmox_disk_space)()
    assert response[1] == 200
    assert ("10.1.9.9", "host-field-key") in calls


def test_get_proxmox_disk_space_no_api_key_returns_host_error(setup):
    """Returns per-host error if no global or host key is configured."""
    serve.mongo_client["labyrinth"]["hosts"].insert_one(
        {
            "ip": "10.2.2.2",
            "mac": "00-00-00-00-22",
            "name": "pve-no-key",
            "tags": "Proxmox",
        }
    )

    response = unwrap(serve.get_proxmox_disk_space)()
    assert response[1] == 200

    data = json.loads(response[0])
    assert len(data["proxmox_hosts"]) == 1
    assert data["proxmox_hosts"][0]["error"] == "No API key configured"


def test_manual_disk_host_crud(setup):
    """Adds, lists, and deletes a manual disk-space host."""
    with serve.app.test_request_context(
        "/disk-space/manual",
        method="POST",
        json={
            "name": "ec2-a",
            "ip": "172.31.0.10",
            "type": "ec2",
            "description": "aws instance",
        },
    ):
        create_resp = unwrap(serve.add_manual_disk_host)()

    assert create_resp[1] == 201
    created = json.loads(create_resp[0])
    host_id = created["id"]

    list_resp = unwrap(serve.get_manual_disk_space)()
    assert list_resp[1] == 200
    listed = json.loads(list_resp[0])["manual_hosts"]

    assert len(listed) == 1
    assert listed[0]["id"] == host_id
    assert listed[0]["name"] == "ec2-a"
    assert listed[0]["type"] == "ec2"
    assert "created" in listed[0]
    assert "updated" in listed[0]

    delete_resp = unwrap(serve.delete_manual_disk_host)(host_id)
    assert delete_resp[1] == 200

    list_resp = unwrap(serve.get_manual_disk_space)()
    assert list_resp[1] == 200
    assert json.loads(list_resp[0])["manual_hosts"] == []


def test_add_manual_disk_host_requires_fields(setup):
    """Validates required payload fields for manual host creation."""
    with serve.app.test_request_context(
        "/disk-space/manual",
        method="POST",
        json={"name": "bad"},
    ):
        resp = unwrap(serve.add_manual_disk_host)()

    assert resp[1] == 400
    assert "Missing required fields" in json.loads(resp[0])["error"]


def test_disk_space_settings_and_api_key_management(setup):
    """Sets/gets/deletes global and host-specific Proxmox API keys."""
    serve.mongo_client["labyrinth"]["hosts"].insert_one(
        {
            "ip": "10.9.0.5",
            "mac": "AA-BB-CC-DD-EE",
            "name": "pve-keyed",
            "tags": "Proxmox",
        }
    )

    with serve.app.test_request_context(
        "/disk-space/settings/proxmox-api-key",
        method="POST",
        json={"api_key": "global-123"},
    ):
        resp = unwrap(serve.set_global_proxmox_api_key)()
    assert resp[1] == 200

    with serve.app.test_request_context(
        "/disk-space/settings/proxmox-api-key/AA-BB-CC-DD-EE",
        method="POST",
        json={"api_key": "host-123"},
    ):
        resp = unwrap(serve.set_host_proxmox_api_key)("AA-BB-CC-DD-EE")
    assert resp[1] == 200

    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "proxmox_tag", "value": "Proxmox"}
    )

    settings_resp = unwrap(serve.get_disk_space_settings)()
    assert settings_resp[1] == 200
    settings = json.loads(settings_resp[0])

    assert settings["proxmox_tag"] == "Proxmox"
    assert settings["global_api_key_configured"] is True
    assert settings["host_specific_keys"][0]["mac"] == "AA-BB-CC-DD-EE"
    host_doc = serve.mongo_client["labyrinth"]["hosts"].find_one({"mac": "AA-BB-CC-DD-EE"})
    assert host_doc["proxmox_api_key"] == "host-123"

    delete_global_resp = unwrap(serve.delete_global_proxmox_api_key)()
    assert delete_global_resp[1] == 200

    delete_host_resp = unwrap(serve.delete_host_proxmox_api_key)("AA-BB-CC-DD-EE")
    assert delete_host_resp[1] == 200

    assert (
        serve.mongo_client["labyrinth"]["settings"].find_one({"name": "proxmox_api_key"})
        is None
    )
    assert (
        serve.mongo_client["labyrinth"]["settings"].find_one(
            {"name": "proxmox_api_key_AA-BB-CC-DD-EE"}
        )
        is None
    )
    host_doc = serve.mongo_client["labyrinth"]["hosts"].find_one({"mac": "AA-BB-CC-DD-EE"})
    assert "proxmox_api_key" not in host_doc


def test_get_proxmox_disk_data_marks_missing_qemu_guest_agent(monkeypatch):
    """Annotates VM records when the QEMU guest agent is unavailable."""

    class FakeClient:
        def __init__(self, host, user, token_id, token_secret, verify_ssl=False):
            pass

        def get_nodes(self):
            return [{"node": "pve-1", "status": "online"}]

        def get_storage(self, node):
            return []

        def get_vms_and_containers(self, node):
            return (
                [{"vmid": 101, "name": "vm-101", "status": "running", "maxdisk": 100, "maxmem": 200}],
                [],
            )

        def get_vm_status(self, node, vmid):
            return {"disk": 25, "mem": 50}

        def get_vm_agent_status(self, node, vmid):
            return {"installed": False, "error": "QEMU guest agent is not running"}

        def get_container_status(self, node, vmid):
            return {}

    monkeypatch.setattr(proxmox_helper, "ProxmoxClient", FakeClient)

    result = proxmox_helper.get_proxmox_disk_data(
        "10.0.0.1", "root@pam!token=secret"
    )

    vm = result["nodes"][0]["vms"][0]
    assert vm["qemu_guest_agent_installed"] is False
    assert "QEMU guest agent" in vm["qemu_guest_agent_error"]


def test_get_proxmox_disk_data_infers_missing_qemu_from_zero_disk(monkeypatch):
    """Marks running VMs as missing guest-agent data when guest disk is reported as zero."""

    class FakeClient:
        def __init__(self, host, user, token_id, token_secret, verify_ssl=False):
            pass

        def get_nodes(self):
            return [{"node": "pve-1", "status": "online"}]

        def get_storage(self, node):
            return []

        def get_vms_and_containers(self, node):
            return (
                [{"vmid": 102, "name": "vm-102", "status": "running", "maxdisk": 10737418240, "maxmem": 200}],
                [],
            )

        def get_vm_status(self, node, vmid):
            return {"disk": 0, "mem": 50}

        def get_vm_agent_status(self, node, vmid):
            return {"installed": True, "error": None}

        def get_container_status(self, node, vmid):
            return {}

    monkeypatch.setattr(proxmox_helper, "ProxmoxClient", FakeClient)

    result = proxmox_helper.get_proxmox_disk_data(
        "10.0.0.2", "root@pam!token=secret"
    )

    vm = result["nodes"][0]["vms"][0]
    assert vm["qemu_guest_agent_warning_inferred"] is True
    assert vm["qemu_guest_agent_installed"] is False
