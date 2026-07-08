#!/usr/bin/env python3

import json
import bson

import pytest
import proxmox_helper
import serve

from common.test import unwrap


def tearDown():
    """Tears down disk-space test data."""
    serve.mongo_client["labyrinth"]["hosts"].delete_many({})
    serve.mongo_client["labyrinth"]["settings"].delete_many({})
    serve.mongo_client["labyrinth"]["proxmox_clusters"].delete_many({})


@pytest.fixture
def setup():
    """Sets up tests."""
    tearDown()
    yield "Setting up..."
    tearDown()
    return "Done"


def test_get_proxmox_disk_space_queries_all_clusters(setup, monkeypatch):
    """Queries each configured cluster directly using its own host IP."""
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_many([
        {
            "name": "cluster-1",
            "host": "10.1.1.1",
            "user": "root@pam",
            "token_id": "token-1",
            "token_secret": "secret-1",
            "verify_ssl": False,
        },
        {
            "name": "cluster-2",
            "host": "10.1.1.2",
            "user": "root@pam",
            "token_id": "token-2",
            "token_secret": "secret-2",
            "verify_ssl": False,
        },
    ])

    calls = []

    def fake_get_proxmox_disk_data(host_ip, cluster_config):
        calls.append((host_ip, cluster_config["name"]))
        return {"nodes": [{"name": "node-1", "storage": [], "vms": [], "containers": []}]}

    monkeypatch.setattr(serve.proxmox_helper, "get_proxmox_disk_data", fake_get_proxmox_disk_data)

    response = unwrap(serve.get_proxmox_disk_space)()
    assert response[1] == 200

    data = json.loads(response[0])
    assert len(data["proxmox_hosts"]) == 2
    assert ("10.1.1.1", "cluster-1") in calls
    assert ("10.1.1.2", "cluster-2") in calls


def test_get_proxmox_disk_space_no_clusters_returns_empty(setup):
    """Returns empty list when no clusters are configured."""
    response = unwrap(serve.get_proxmox_disk_space)()
    assert response[1] == 200
    data = json.loads(response[0])
    assert data["proxmox_hosts"] == []


def test_get_proxmox_disk_space_backfills_qemu_warning_fields(setup, monkeypatch):
    """Adds QEMU guest-agent flags to API output even when helper returns old VM shape."""
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_one({
        "name": "cluster-old",
        "host": "10.5.5.5",
        "user": "root@pam",
        "token_id": "token-old",
        "token_secret": "secret-old",
        "verify_ssl": False,
    })

    def fake_get_proxmox_disk_data(host_ip, cluster_config):
        return {
            "nodes": [
                {
                    "name": "pve-node",
                    "storage": [],
                    "containers": [],
                    "vms": [
                        {
                            "id": 101,
                            "name": "vm-101",
                            "status": "running",
                            "maxdisk": 10737418240,
                            "disk": 0,
                            "maxmem": 1024,
                            "mem": 512,
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(serve.proxmox_helper, "get_proxmox_disk_data", fake_get_proxmox_disk_data)

    response = unwrap(serve.get_proxmox_disk_space)()
    assert response[1] == 200

    payload = json.loads(response[0])
    vm = payload["proxmox_hosts"][0]["nodes"][0]["vms"][0]
    assert vm["qemu_guest_agent_warning_inferred"] is True
    assert vm["qemu_guest_agent_installed"] is False
    assert "QEMU guest agent" in vm["qemu_guest_agent_error"]


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


def test_proxmox_cluster_crud(setup):
    """Creates, lists, updates, and deletes Proxmox clusters."""
    # Create cluster
    with serve.app.test_request_context(
        "/proxmox-clusters",
        method="POST",
        json={
            "name": "test-cluster",
            "host": "10.1.1.1",
            "user": "root@pam",
            "token_id": "token-123",
            "token_secret": "secret-123",
            "verify_ssl": False,
        },
    ):
        create_resp = unwrap(serve.create_proxmox_cluster)()

    assert create_resp[1] == 201
    created = json.loads(create_resp[0])
    cluster_id = created["id"]
    assert created["cluster"]["name"] == "test-cluster"
    assert "token_secret" not in created["cluster"]

    # List clusters
    list_resp = unwrap(serve.list_proxmox_clusters)()
    assert list_resp[1] == 200
    listed = json.loads(list_resp[0])
    assert len(listed) == 1
    assert listed[0]["name"] == "test-cluster"
    assert "token_secret" not in listed[0]

    # Get single cluster
    get_resp = unwrap(serve.get_proxmox_cluster)(cluster_id)
    assert get_resp[1] == 200
    cluster = json.loads(get_resp[0])
    assert cluster["name"] == "test-cluster"
    assert "token_secret" not in cluster

    # Update cluster
    with serve.app.test_request_context(
        f"/proxmox-clusters/{cluster_id}",
        method="PUT",
        json={
            "token_secret": "updated-secret",
            "verify_ssl": True,
        },
    ):
        update_resp = unwrap(serve.update_proxmox_cluster)(cluster_id)

    assert update_resp[1] == 200
    updated = json.loads(update_resp[0])
    assert updated["verify_ssl"] is True
    assert "token_secret" not in updated

    # Verify update in database
    db_cluster = serve.mongo_client["labyrinth"]["proxmox_clusters"].find_one(
        {"_id": bson.ObjectId(cluster_id)}
    )
    assert db_cluster["token_secret"] == "updated-secret"

    # Delete cluster
    del_resp = unwrap(serve.delete_proxmox_cluster)(cluster_id)
    assert del_resp[1] == 200

    # Verify deletion
    list_resp = unwrap(serve.list_proxmox_clusters)()
    assert list_resp[1] == 200
    assert json.loads(list_resp[0]) == []


def test_proxmox_cluster_create_requires_fields(setup):
    """Validates required fields for cluster creation."""
    with serve.app.test_request_context(
        "/proxmox-clusters",
        method="POST",
        json={"name": "incomplete"},
    ):
        resp = unwrap(serve.create_proxmox_cluster)()

    assert resp[1] == 400
    assert "Missing required fields" in json.loads(resp[0])["error"]


def test_proxmox_cluster_duplicate_name_rejected(setup):
    """Rejects creation of clusters with duplicate names."""
    cluster_data = {
        "name": "duplicate",
        "host": "10.1.1.1",
        "user": "root@pam",
        "token_id": "token",
        "token_secret": "secret",
    }

    # Create first cluster
    with serve.app.test_request_context("/proxmox-clusters", method="POST", json=cluster_data):
        resp1 = unwrap(serve.create_proxmox_cluster)()
    assert resp1[1] == 201

    # Try to create duplicate
    with serve.app.test_request_context("/proxmox-clusters", method="POST", json=cluster_data):
        resp2 = unwrap(serve.create_proxmox_cluster)()
    assert resp2[1] == 409
    assert "already exists" in json.loads(resp2[0])["error"]


def test_disk_space_settings_includes_clusters(setup):
    """Get disk space settings returns cluster list and unconfigured hosts."""
    # Create clusters
    cluster1_id = serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_one({
        "name": "cluster-a",
        "host": "10.1.1.1",
        "user": "root@pam",
        "token_id": "token-a",
        "token_secret": "secret-a",
        "verify_ssl": False,
    }).inserted_id

    serve.mongo_client["labyrinth"]["settings"].insert_one({
        "name": "proxmox_tag",
        "value": "Proxmox",
    })

    serve.mongo_client["labyrinth"]["hosts"].insert_many([
        {
            "ip": "10.1.1.1",
            "mac": "AA-BB-CC-DD-EE",
            "name": "pve-configured",
            "tags": "Proxmox",
            "proxmox_cluster": str(cluster1_id),
        },
        {
            "ip": "10.1.1.2",
            "mac": "FF-FF-FF-FF-FF",
            "name": "pve-unconfigured",
            "tags": "Proxmox",
        },
    ])

    settings_resp = unwrap(serve.get_disk_space_settings)()
    assert settings_resp[1] == 200
    settings = json.loads(settings_resp[0])

    assert settings["proxmox_tag"] == "Proxmox"
    assert len(settings["clusters"]) == 1
    assert settings["clusters"][0]["name"] == "cluster-a"
    assert "token_secret" not in settings["clusters"][0]

    assert len(settings["unconfigured_proxmox_hosts"]) == 1
    assert settings["unconfigured_proxmox_hosts"][0]["mac"] == "FF-FF-FF-FF-FF"


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

        def get_vm_guest_fsinfo(self, node, vmid):
            return None

        def get_container_status(self, node, vmid):
            return {}

    monkeypatch.setattr(proxmox_helper, "ProxmoxClient", FakeClient)

    result = proxmox_helper.get_proxmox_disk_data(
        "10.0.0.1",
        {
            "user": "root@pam",
            "token_id": "token",
            "token_secret": "secret",
            "verify_ssl": False,
        }
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

        def get_vm_guest_fsinfo(self, node, vmid):
            return None

        def get_container_status(self, node, vmid):
            return {}

    monkeypatch.setattr(proxmox_helper, "ProxmoxClient", FakeClient)

    result = proxmox_helper.get_proxmox_disk_data(
        "10.0.0.2",
        {
            "user": "root@pam",
            "token_id": "token",
            "token_secret": "secret",
            "verify_ssl": False,
        }
    )

    vm = result["nodes"][0]["vms"][0]
    assert vm["qemu_guest_agent_warning_inferred"] is True
    assert vm["qemu_guest_agent_installed"] is True

def test_get_proxmox_disk_data_uses_guest_fsinfo_when_available(monkeypatch):
    """Uses guest filesystem info from QEMU agent when disk is reported as zero."""

    class FakeClient:
        def __init__(self, host, user, token_id, token_secret, verify_ssl=False):
            pass

        def get_nodes(self):
            return [{"node": "pve-1", "status": "online"}]

        def get_storage(self, node):
            return []

        def get_vms_and_containers(self, node):
            return (
                [{"vmid": 103, "name": "labyrinth", "status": "running", "maxdisk": 268435456000, "maxmem": 13509853184}],
                [],
            )

        def get_vm_status(self, node, vmid):
            return {"disk": 0, "mem": 3662069760}

        def get_vm_agent_status(self, node, vmid):
            return {"installed": True, "error": None}

        def get_vm_guest_fsinfo(self, node, vmid):
            # Return actual guest filesystem info with root mount
            return {
                "result": [
                    {
                        "mountpoint": "/boot",
                        "total-bytes": 950239232,
                        "used-bytes": 227233792,
                        "name": "sda2",
                        "type": "ext4",
                    },
                    {
                        "mountpoint": "/",
                        "total-bytes": 250515095552,
                        "used-bytes": 131229454336,
                        "name": "dm-0",
                        "type": "ext4",
                    }
                ]
            }

        def get_container_status(self, node, vmid):
            return {}

    monkeypatch.setattr(proxmox_helper, "ProxmoxClient", FakeClient)

    result = proxmox_helper.get_proxmox_disk_data(
        "10.0.0.3",
        {
            "user": "root@pam",
            "token_id": "token",
            "token_secret": "secret",
            "verify_ssl": False,
        }
    )

    vm = result["nodes"][0]["vms"][0]
    # Should use the guest fsinfo values instead of zero
    assert vm["disk"] == 131229454336
    assert vm["maxdisk"] == 250515095552
    # Warning should no longer be inferred since disk is non-zero now
    assert vm["qemu_guest_agent_warning_inferred"] is False
    assert vm["qemu_guest_agent_installed"] is True
    # Debug info should be included
    assert "_debug_guest_fsinfo" in vm