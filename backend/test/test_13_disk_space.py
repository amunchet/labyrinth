#!/usr/bin/env python3

import json
import bson

import pytest
import proxmox_helper
import proxmox_refresh
import serve

from common.test import unwrap


class FakeRedis:
    """Minimal Redis double for Proxmox cache tests."""

    def __init__(self, store=None):
        self.store = store or {}
        self.setex_calls = []
        self.deleted = []

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.setex_calls.append((key, ttl, value))
        self.store[key] = value

    def delete(self, key):
        self.deleted.append(key)
        self.store.pop(key, None)


class FakeResponse:
    """Minimal requests.Response double for ProxmoxClient session tests."""

    def __init__(self, json_data=None, status_code=200, raise_exc=None):
        self._json_data = json_data or {}
        self.status_code = status_code
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


def _make_proxmox_client():
    """Build a real ProxmoxClient whose .session can be swapped for a fake."""
    return proxmox_helper.ProxmoxClient(
        host="10.0.0.1",
        user="root@pam",
        token_id="token",
        token_secret="secret",
        verify_ssl=False,
    )


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


def test_get_proxmox_disk_space_prefers_redis_cache(setup, monkeypatch):
    """Uses cached Proxmox payloads from Redis before attempting live API calls."""
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

    clusters = list(serve.mongo_client["labyrinth"]["proxmox_clusters"].find({}).sort("name", 1))
    fake_redis = FakeRedis(
        store={
            proxmox_helper.get_proxmox_cache_key(clusters[0]): json.dumps({
                "nodes": [{"name": "node-a", "storage": [], "vms": [], "containers": []}],
            }).encode("utf-8"),
            proxmox_helper.get_proxmox_cache_key(clusters[1]): json.dumps({
                "nodes": [{"name": "node-b", "storage": [], "vms": [], "containers": []}],
            }).encode("utf-8"),
        }
    )

    monkeypatch.setattr(serve.proxmox_helper, "get_redis_client", lambda: fake_redis)

    def fake_get_proxmox_disk_data(host_ip, cluster_config):
        raise AssertionError("live Proxmox query should not run when Redis cache is present")

    monkeypatch.setattr(serve.proxmox_helper, "get_proxmox_disk_data", fake_get_proxmox_disk_data)

    response = unwrap(serve.get_proxmox_disk_space)()
    assert response[1] == 200

    data = json.loads(response[0])
    assert len(data["proxmox_hosts"]) == 2
    assert data["proxmox_hosts"][0]["cluster_name"] == "cluster-1"
    assert data["proxmox_hosts"][1]["cluster_name"] == "cluster-2"
    assert data["proxmox_hosts"][0]["nodes"][0]["name"] == "node-a"
    assert data["proxmox_hosts"][1]["nodes"][0]["name"] == "node-b"


def test_get_proxmox_disk_space_falls_back_to_live_query_and_caches(setup, monkeypatch):
    """Falls back to live Proxmox API calls and stores the payload in Redis."""
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_one({
        "name": "cluster-live",
        "host": "10.1.1.10",
        "user": "root@pam",
        "token_id": "token-live",
        "token_secret": "secret-live",
        "verify_ssl": False,
    })

    fake_redis = FakeRedis()
    calls = []

    monkeypatch.setattr(serve.proxmox_helper, "get_redis_client", lambda: fake_redis)

    def fake_get_proxmox_disk_data(host_ip, cluster_config):
        calls.append((host_ip, cluster_config["name"]))
        return {"nodes": [{"name": "node-live", "storage": [], "vms": [], "containers": []}]}

    monkeypatch.setattr(serve.proxmox_helper, "get_proxmox_disk_data", fake_get_proxmox_disk_data)

    response = unwrap(serve.get_proxmox_disk_space)()
    assert response[1] == 200

    data = json.loads(response[0])
    assert len(data["proxmox_hosts"]) == 1
    assert calls == [("10.1.1.10", "cluster-live")]
    assert fake_redis.setex_calls

    cluster = serve.mongo_client["labyrinth"]["proxmox_clusters"].find_one({"name": "cluster-live"})
    cache_key = proxmox_helper.get_proxmox_cache_key(cluster)
    assert cache_key in fake_redis.store


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

    monkeypatch.setattr(serve.proxmox_helper, "get_redis_client", lambda: FakeRedis())
    monkeypatch.setattr(serve.proxmox_helper, "get_proxmox_disk_data", fake_get_proxmox_disk_data)

    response = unwrap(serve.get_proxmox_disk_space)()
    assert response[1] == 200

    payload = json.loads(response[0])
    vm = payload["proxmox_hosts"][0]["nodes"][0]["vms"][0]
    assert vm["qemu_guest_agent_warning_inferred"] is True
    assert vm["qemu_guest_agent_installed"] is False
    assert "QEMU guest agent" in vm["qemu_guest_agent_error"]


def test_refresh_proxmox_disk_space_bypasses_cache_and_recaches(setup, monkeypatch):
    """The refresh endpoint always performs a live query, ignoring any cached value, and updates Redis."""
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_one({
        "name": "cluster-refresh",
        "host": "10.1.1.20",
        "user": "root@pam",
        "token_id": "token-refresh",
        "token_secret": "secret-refresh",
        "verify_ssl": False,
    })

    cluster = serve.mongo_client["labyrinth"]["proxmox_clusters"].find_one(
        {"name": "cluster-refresh"}
    )
    stale_payload = json.dumps({
        "nodes": [{"name": "node-stale", "storage": [], "vms": [], "containers": []}],
    }).encode("utf-8")
    fake_redis = FakeRedis(store={
        proxmox_helper.get_proxmox_cache_key(cluster): stale_payload,
    })
    calls = []

    monkeypatch.setattr(serve.proxmox_helper, "get_redis_client", lambda: fake_redis)

    def fake_get_proxmox_disk_data(host_ip, cluster_config):
        calls.append((host_ip, cluster_config["name"]))
        return {"nodes": [{"name": "node-fresh", "storage": [], "vms": [], "containers": []}]}

    monkeypatch.setattr(serve.proxmox_helper, "get_proxmox_disk_data", fake_get_proxmox_disk_data)

    response = unwrap(serve.refresh_proxmox_disk_space)()
    assert response[1] == 200

    data = json.loads(response[0])
    # Live query ran despite a value already being present in the cache.
    assert calls == [("10.1.1.20", "cluster-refresh")]
    assert len(data["proxmox_hosts"]) == 1
    assert data["proxmox_hosts"][0]["nodes"][0]["name"] == "node-fresh"

    # Redis was overwritten with the freshly fetched payload.
    cache_key = proxmox_helper.get_proxmox_cache_key(cluster)
    cached_value = fake_redis.store[cache_key]
    if isinstance(cached_value, bytes):
        cached_value = cached_value.decode("utf-8")
    assert json.loads(cached_value)["nodes"][0]["name"] == "node-fresh"


def test_refresh_proxmox_disk_space_no_clusters_returns_empty(setup):
    """Returns an empty list when no Proxmox clusters are configured."""
    response = unwrap(serve.refresh_proxmox_disk_space)()
    assert response[1] == 200
    assert json.loads(response[0])["proxmox_hosts"] == []


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
            # Intentionally empty - this is a test stub that doesn't need initialization
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
            # Intentionally empty - this is a test stub that doesn't need initialization
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
            # Intentionally empty - this is a test stub that doesn't need initialization
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


def test_refresh_proxmox_cluster_cache_writes_redis_entries(monkeypatch):
    """Refresh helper fetches each cluster and stores the normalized payload in Redis."""
    fake_redis = FakeRedis()
    clusters = [
        {"_id": "1", "name": "cluster-a", "host": "10.1.1.1"},
        {"_id": "2", "name": "cluster-b", "host": "10.1.1.2"},
    ]
    calls = []

    def fake_get_proxmox_disk_data(host_ip, cluster_config):
        calls.append((host_ip, cluster_config["name"]))
        return {"nodes": [{"name": f"node-{cluster_config['name']}", "storage": [], "vms": [], "containers": []}]}

    monkeypatch.setattr(proxmox_helper, "get_proxmox_disk_data", fake_get_proxmox_disk_data)

    result = proxmox_helper.refresh_proxmox_cluster_cache(clusters, redis_client=fake_redis)

    assert len(result) == 2
    assert calls == [("10.1.1.1", "cluster-a"), ("10.1.1.2", "cluster-b")]
    assert len(fake_redis.setex_calls) == 2
    assert proxmox_helper.get_proxmox_cache_key(clusters[0]) in fake_redis.store
    assert proxmox_helper.get_proxmox_cache_key(clusters[1]) in fake_redis.store


def test_proxmox_refresh_worker_loads_clusters_and_refreshes(monkeypatch):
    """Cron refresh worker loads configured clusters and delegates cache refresh."""
    expected_clusters = [{"_id": "1", "name": "cluster-a", "host": "10.1.1.1"}]
    fake_redis = FakeRedis()
    captured = {}

    class FakeCollection:
        def find(self, query):
            assert query == {}
            return expected_clusters

    class FakeDatabase:
        def __getitem__(self, name):
            assert name == "proxmox_clusters"
            return FakeCollection()

    class FakeMongoClient:
        def __getitem__(self, name):
            assert name == "labyrinth"
            return FakeDatabase()

    class FakePidFile:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            captured["pid_name"] = self.name
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_refresh(clusters, redis_client=None):
        captured["clusters"] = clusters
        captured["redis_client"] = redis_client
        return [{"cluster_name": "cluster-a"}]

    monkeypatch.setattr(proxmox_refresh, "mongo_client", FakeMongoClient())
    monkeypatch.setattr(proxmox_refresh, "PidFile", FakePidFile)
    monkeypatch.setattr(proxmox_refresh.proxmox_helper, "get_redis_client", lambda: fake_redis)
    monkeypatch.setattr(proxmox_refresh.proxmox_helper, "refresh_proxmox_cluster_cache", fake_refresh)

    proxmox_refresh.refresh_proxmox_cache()

    assert captured["pid_name"] == "labyrinth-proxmox-refresh"
    assert captured["clusters"] == expected_clusters
    assert captured["redis_client"] is fake_redis


# ---------------------------------------------------------------------------
# `df -h` escape valve - _parse_df_size / parse_df_output
# ---------------------------------------------------------------------------


def test_parse_df_size_handles_units_and_bare_numbers():
    """Human-readable df -h suffixes (K/M/G/T) convert to bytes correctly."""
    assert proxmox_helper._parse_df_size("20G") == 20 * 1024 ** 3
    assert proxmox_helper._parse_df_size("6.7G") == int(6.7 * 1024 ** 3)
    assert proxmox_helper._parse_df_size("395M") == int(395 * 1024 ** 2)
    assert proxmox_helper._parse_df_size("0") == 0
    assert proxmox_helper._parse_df_size("512") == 512


def test_parse_df_size_returns_none_for_unparsable_value():
    """Non-numeric or missing values are not treated as a size."""
    assert proxmox_helper._parse_df_size("-") is None
    assert proxmox_helper._parse_df_size(None) is None
    assert proxmox_helper._parse_df_size("") is None


def test_parse_df_output_finds_root_filesystem():
    """Parses a typical `df -h` listing and extracts the root ("/") row."""
    output = (
        "Filesystem      Size  Used Avail Use% Mounted on\n"
        "udev            2.0G     0  2.0G   0% /dev\n"
        "tmpfs           395M  1.1M  394M   1% /run\n"
        "/dev/sda1        20G   12G  6.7G  65% /\n"
    )

    result = proxmox_helper.parse_df_output(output)

    assert result == {
        "mountpoint": "/",
        "name": "/dev/sda1",
        "total-bytes": 20 * 1024 ** 3,
        "used-bytes": 12 * 1024 ** 3,
    }


def test_parse_df_output_returns_none_when_mountpoint_missing():
    """Returns None when the requested mountpoint never appears in the output."""
    output = (
        "Filesystem      Size  Used Avail Use% Mounted on\n"
        "udev            2.0G     0  2.0G   0% /dev\n"
    )

    assert proxmox_helper.parse_df_output(output) is None


def test_parse_df_output_returns_none_for_empty_or_missing_output():
    """Empty/None input is handled gracefully."""
    assert proxmox_helper.parse_df_output("") is None
    assert proxmox_helper.parse_df_output(None) is None


def test_parse_df_output_ignores_malformed_lines():
    """Lines that don't look like a df row are skipped rather than raising."""
    output = "not a real df line\n/dev/sda1 20G 12G 6.7G 65% /\n"

    result = proxmox_helper.parse_df_output(output)

    assert result["total-bytes"] == 20 * 1024 ** 3
    assert result["used-bytes"] == 12 * 1024 ** 3


# ---------------------------------------------------------------------------
# `df -h` escape valve - ProxmoxClient.exec_guest_command
# ---------------------------------------------------------------------------


def test_exec_guest_command_success_after_polling(monkeypatch):
    """Posts the exec command, polls exec-status until exited, and returns stdout."""
    client = _make_proxmox_client()
    monkeypatch.setattr(proxmox_helper.time, "sleep", lambda *_: None)

    poll_state = {"calls": 0}

    class FakeSession:
        def post(self, url, data=None, timeout=None):
            assert url.endswith("/agent/exec")
            assert data == {"command": ["df", "-h"]}
            return FakeResponse({"data": {"pid": 4242}})

        def get(self, url, params=None, timeout=None):
            assert url.endswith("/agent/exec-status")
            assert params == {"pid": 4242}
            poll_state["calls"] += 1
            if poll_state["calls"] == 1:
                return FakeResponse({"data": {"exited": 0}})
            return FakeResponse({"data": {"exited": 1, "out-data": "df output"}})

    client.session = FakeSession()

    output = client.exec_guest_command("node-a", "101", ["df", "-h"])

    assert output == "df output"
    assert poll_state["calls"] == 2


def test_exec_guest_command_returns_none_when_exec_post_fails():
    """A failed exec POST (agent unavailable, etc.) returns None."""
    client = _make_proxmox_client()

    class FakeSession:
        def post(self, url, data=None, timeout=None):
            raise Exception("connection refused")

    client.session = FakeSession()

    assert client.exec_guest_command("node-a", "101", ["df", "-h"]) is None


def test_exec_guest_command_returns_none_when_pid_missing():
    """A response without a pid means the command never launched."""
    client = _make_proxmox_client()

    class FakeSession:
        def post(self, url, data=None, timeout=None):
            return FakeResponse({"data": {}})

    client.session = FakeSession()

    assert client.exec_guest_command("node-a", "101", ["df", "-h"]) is None


def test_exec_guest_command_returns_none_on_status_poll_failure():
    """An exception while polling exec-status is treated as a failure."""
    client = _make_proxmox_client()

    class FakeSession:
        def post(self, url, data=None, timeout=None):
            return FakeResponse({"data": {"pid": 99}})

        def get(self, url, params=None, timeout=None):
            raise Exception("timed out")

    client.session = FakeSession()

    assert client.exec_guest_command("node-a", "101", ["df", "-h"]) is None


def test_exec_guest_command_times_out_when_never_exits(monkeypatch):
    """Gives up and returns None after poll_attempts if the command never exits."""
    client = _make_proxmox_client()
    monkeypatch.setattr(proxmox_helper.time, "sleep", lambda *_: None)

    class FakeSession:
        def post(self, url, data=None, timeout=None):
            return FakeResponse({"data": {"pid": 99}})

        def get(self, url, params=None, timeout=None):
            return FakeResponse({"data": {"exited": 0}})

    client.session = FakeSession()

    output = client.exec_guest_command(
        "node-a", "101", ["df", "-h"], poll_attempts=3, poll_interval=0
    )

    assert output is None


# ---------------------------------------------------------------------------
# `df -h` escape valve - ProxmoxClient.get_vm_guest_df
# ---------------------------------------------------------------------------


def test_get_vm_guest_df_parses_root_filesystem_from_exec_output(monkeypatch):
    """Runs df -h via exec_guest_command and parses out the root filesystem."""
    client = _make_proxmox_client()
    df_output = (
        "Filesystem      Size  Used Avail Use% Mounted on\n"
        "udev            2.0G     0  2.0G   0% /dev\n"
        "/dev/sda1        20G   12G  6.7G  65% /\n"
    )

    captured = {}

    def fake_exec(node, vmid, command):
        captured["args"] = (node, vmid, command)
        return df_output

    monkeypatch.setattr(client, "exec_guest_command", fake_exec)

    result = client.get_vm_guest_df("node-a", "101")

    assert captured["args"] == ("node-a", "101", ["df", "-h"])
    assert result == {
        "mountpoint": "/",
        "name": "/dev/sda1",
        "total-bytes": 20 * 1024 ** 3,
        "used-bytes": 12 * 1024 ** 3,
    }


def test_get_vm_guest_df_returns_none_when_exec_fails(monkeypatch):
    """No exec output (agent unavailable/command failed) yields None."""
    client = _make_proxmox_client()

    monkeypatch.setattr(client, "exec_guest_command", lambda node, vmid, command: None)

    assert client.get_vm_guest_df("node-a", "101") is None


# ---------------------------------------------------------------------------
# `df -h` escape valve - ProxmoxClient.get_vm_guest_fsinfo
# ---------------------------------------------------------------------------


def test_get_vm_guest_fsinfo_uses_structured_data_when_root_present(monkeypatch):
    """When get-fsinfo already reports "/", the df -h fallback is never invoked."""
    client = _make_proxmox_client()

    class FakeSession:
        def get(self, url, timeout=None):
            return FakeResponse({
                "data": {
                    "result": [
                        {"mountpoint": "/", "total-bytes": 100, "used-bytes": 50, "name": "sda1"},
                    ]
                }
            })

    client.session = FakeSession()

    def fail_df(node, vmid):
        raise AssertionError("df -h fallback should not run when get-fsinfo already has root")

    monkeypatch.setattr(client, "get_vm_guest_df", fail_df)

    result = client.get_vm_guest_fsinfo("node-a", "101")

    assert result == {
        "result": [
            {"mountpoint": "/", "total-bytes": 100, "used-bytes": 50, "name": "sda1"},
        ]
    }


def test_get_vm_guest_fsinfo_falls_back_to_df_when_get_fsinfo_raises(monkeypatch):
    """A get-fsinfo call that errors outright still yields data via df -h."""
    client = _make_proxmox_client()

    class FakeSession:
        def get(self, url, timeout=None):
            raise Exception("agent not running")

    client.session = FakeSession()

    monkeypatch.setattr(
        client,
        "get_vm_guest_df",
        lambda node, vmid: {"mountpoint": "/", "total-bytes": 999, "used-bytes": 111, "name": "vda1"},
    )

    result = client.get_vm_guest_fsinfo("node-a", "101")

    assert result == {
        "result": [
            {"mountpoint": "/", "total-bytes": 999, "used-bytes": 111, "name": "vda1"},
        ]
    }


def test_get_vm_guest_fsinfo_appends_df_fallback_when_root_missing(monkeypatch):
    """get-fsinfo succeeding without a root entry still gets the df -h entry appended."""
    client = _make_proxmox_client()

    class FakeSession:
        def get(self, url, timeout=None):
            return FakeResponse({
                "data": {
                    "result": [
                        {"mountpoint": "/boot", "total-bytes": 100, "used-bytes": 50, "name": "sda2"},
                    ]
                }
            })

    client.session = FakeSession()

    monkeypatch.setattr(
        client,
        "get_vm_guest_df",
        lambda node, vmid: {"mountpoint": "/", "total-bytes": 999, "used-bytes": 111, "name": "vda1"},
    )

    result = client.get_vm_guest_fsinfo("node-a", "101")

    assert result == {
        "result": [
            {"mountpoint": "/boot", "total-bytes": 100, "used-bytes": 50, "name": "sda2"},
            {"mountpoint": "/", "total-bytes": 999, "used-bytes": 111, "name": "vda1"},
        ]
    }


def test_get_vm_guest_fsinfo_returns_none_when_everything_fails(monkeypatch):
    """Both get-fsinfo and the df -h escape valve failing yields None overall."""
    client = _make_proxmox_client()

    class FakeSession:
        def get(self, url, timeout=None):
            raise Exception("agent not running")

    client.session = FakeSession()

    monkeypatch.setattr(client, "get_vm_guest_df", lambda node, vmid: None)

    assert client.get_vm_guest_fsinfo("node-a", "101") is None