"""
Proxmox guest deploys: Ansible connects only to the hypervisors and reaches each
VM/LXC through `qm guest exec` / `pct exec`, using per-node credentials from an
encrypted become file.
"""

import json
import os
import shutil
from unittest.mock import MagicMock, patch

import pytest
import yaml

import ansible_helper
import serve
from common.test import unwrap


def _guest(cluster, node, kind, vmid, name, ips=(), running=True):
    return {
        "cluster_name": cluster,
        "node": node,
        "type": kind,
        "id": vmid,
        "name": name,
        "running": running,
        "labyrinth_matches": [{"ip": ip, "host": name} for ip in ips],
    }


GUESTS = [
    _guest("north", "pve3", "vm", 215, "jupiter", ["10.0.0.6"]),
    # Same Labyrinth host matched twice (two host records, one IP) is unambiguous
    _guest("north", "pve6", "lxc", "113", "polaris", ["10.0.0.5", "10.0.0.5"]),
    _guest("south", "pve3", "lxc", 120, "dropbox-mirror"),
    _guest("south", "pve2", "vm", 112, "medusa", ["10.0.0.7", "10.0.0.8"]),
    _guest("north", "pve6", "lxc", 119, "videolxc", ["10.0.0.9"], running=False),
]


@pytest.fixture
def deploy(monkeypatch):
    """Live Proxmox data, uploaded files and the job launcher, all faked."""
    monkeypatch.setattr(serve, "_proxmox_guests_with_matches", lambda: ([], GUESTS, []))
    files = {
        "/src/uploads/become": ["proxmox-root.yml"],
        "/src/uploads/telegraf": ["10.0.0.5.conf", "10.0.0.6.conf"],
    }
    real_listdir = serve.os.listdir
    monkeypatch.setattr(
        serve.os, "listdir", lambda p: files[p] if p in files else real_listdir(p)
    )
    with patch("serve.start_ansible_job") as start:
        yield start


def _post(action="telegraf", guests=None, **extra):
    data = {
        "action": action,
        "credentials_file": "proxmox-root.yml",
        "vault_password": "pw",
        "guests": guests if guests is not None else [],
        **extra,
    }
    return unwrap(serve.run_proxmox_deploy)(json.dumps(data))


def _pick(cluster, node, kind, vmid):
    return {"cluster_name": cluster, "node": node, "type": kind, "id": vmid}


def test_telegraf_deploy_targets_each_guest_with_its_own_config(deploy):
    resp, status = _post(
        guests=[_pick("north", "pve3", "vm", 215), _pick("north", "pve6", "lxc", 113)]
    )

    assert status == 200
    job_id, data = deploy.call_args.args
    assert job_id == resp["job_id"]
    assert data["proxmox_action"] == "telegraf"
    assert data["become_file"] == "proxmox-root"
    assert data["proxmox_targets"] == [
        {
            "cluster": "north",
            "node": "pve3",
            "type": "vm",
            "vmid": "215",
            "name": "jupiter",
            "telegraf_conf": "10.0.0.6",
        },
        {
            "cluster": "north",
            "node": "pve6",
            "type": "lxc",
            "vmid": "113",
            "name": "polaris",
            "telegraf_conf": "10.0.0.5",
        },
    ]
    assert data["hosts"] == [
        "north/pve3/vm 215 (jupiter)",
        "north/pve6/lxc 113 (polaris)",
    ]


def test_script_actions_need_no_labyrinth_match(deploy):
    resp, status = _post(
        "script", [_pick("south", "pve3", "lxc", 120)], script="apt-get update"
    )

    assert status == 200
    data = deploy.call_args.args[1]
    assert data["proxmox_script"] == "apt-get update"
    assert data["proxmox_targets"][0]["telegraf_conf"] == ""


def test_rejects_the_whole_deploy_when_any_guest_is_unusable(deploy):
    resp, status = _post(
        guests=[
            _pick("north", "pve3", "vm", 215),  # fine
            _pick("north", "pve6", "lxc", 999),  # unknown
            _pick("north", "pve6", "lxc", 119),  # stopped
            _pick("south", "pve3", "lxc", 120),  # no Labyrinth host
            _pick("south", "pve2", "vm", 112),  # two candidate configs
        ]
    )

    assert status == 484
    errors = json.loads(resp)["errors"]
    assert errors == [
        "north/pve6/lxc/999: not found on Proxmox",
        "north/pve6/lxc/119: not running",
        "south/pve3/lxc/120: needs exactly one matching Labyrinth host IP to pick its Telegraf config, found 0",
        "south/pve2/vm/112: needs exactly one matching Labyrinth host IP to pick its Telegraf config, found 2",
    ]
    deploy.assert_not_called()


def test_rejects_guest_without_saved_telegraf_config(deploy, monkeypatch):
    monkeypatch.setattr(
        serve,
        "_proxmox_guests_with_matches",
        lambda: ([], [_guest("north", "pve4", "vm", 107, "zeus", ["10.0.0.20"])], []),
    )
    resp, status = _post(guests=[_pick("north", "pve4", "vm", 107)])

    assert status == 484
    assert json.loads(resp)["errors"] == [
        "north/pve4/vm/107: no Telegraf config saved for 10.0.0.20"
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "rm_everything"},
        {"vault_password": ""},
        {"credentials_file": ""},
        {"guests": []},
        {"action": "script", "script": "   "},
    ],
)
def test_rejects_incomplete_requests(deploy, overrides):
    data = {
        "action": "telegraf",
        "credentials_file": "proxmox-root",
        "vault_password": "pw",
        "guests": [_pick("north", "pve3", "vm", 215)],
        **overrides,
    }
    resp, status = unwrap(serve.run_proxmox_deploy)(json.dumps(data))
    assert status == 482
    deploy.assert_not_called()


def test_rejects_unknown_credentials_file(deploy):
    resp, status = _post(
        guests=[_pick("north", "pve3", "vm", 215)],
        credentials_file="../../etc/passwd",
    )
    assert status == 483
    deploy.assert_not_called()


def test_background_runner_uses_the_proxmox_layout():
    """A Proxmox job lays out its own run dir instead of the playbook/inventory one."""
    thread = MagicMock()
    thread.is_alive.return_value = False
    targets = [{"cluster": "north", "node": "pve3"}]
    with patch(
        "serve.ansible_helper.prepare_proxmox_run",
        return_value=("/tmp/RUN_DIR_PX", "proxmox_guests"),
    ) as prepare, patch("serve.ansible_helper.run_ansible") as run_ansible, patch(
        "serve.ansible_runner.run_async", return_value=(thread, MagicMock(events=[]))
    ) as run_async, patch(
        "serve.redis.Redis"
    ), patch(
        "serve.db"
    ), patch(
        "serve.os.listdir", return_value=[]
    ), patch(
        "serve.shutil.rmtree"
    ):
        serve.run_ansible_background(
            "job-px",
            {
                "playbook": "proxmox:script",
                "hosts": ["north/pve3/lxc 101 (a)"],
                "become_file": "proxmox-root",
                "vault_password": "pw",
                "proxmox_targets": targets,
                "proxmox_action": "script",
                "proxmox_script": "uptime",
            },
        )

    prepare.assert_called_once_with(
        targets, "script", "pw", "proxmox-root", script="uptime"
    )
    run_ansible.assert_not_called()
    assert run_async.call_args.kwargs["playbook"] == "proxmox_guests.yml"


@pytest.fixture
def uploads():
    """A real encrypted credentials file and Telegraf config under /src/uploads."""
    for folder in ["become", "telegraf"]:
        os.makedirs(f"/src/uploads/{folder}", exist_ok=True)
    shutil.copy("/src/test/ansible/vars/vault.yml", "/src/uploads/become/px-test.yml")
    with open("/src/uploads/telegraf/10.99.0.5.conf", "w") as f:
        f.write('[agent]\n  interval = "60s"\n')
    run_dirs = []
    yield run_dirs
    os.remove("/src/uploads/become/px-test.yml")
    os.remove("/src/uploads/telegraf/10.99.0.5.conf")
    for run_dir in run_dirs:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_prepare_run_groups_guests_by_hypervisor(uploads):
    targets = [
        {
            "cluster": "north",
            "node": "pve3",
            "type": "vm",
            "vmid": 215,
            "name": "jupiter",
            "telegraf_conf": "10.99.0.5",
        },
        {
            "cluster": "north",
            "node": "pve3",
            "type": "lxc",
            "vmid": "104",
            "name": "central",
            "telegraf_conf": "",
        },
        # Same node name in another cluster is a different hypervisor
        {
            "cluster": "south site",
            "node": "pve3",
            "type": "lxc",
            "vmid": "120",
            "name": "mirror",
            "telegraf_conf": "",
        },
    ]
    run_dir, playbook = ansible_helper.prepare_proxmox_run(
        targets, "telegraf", "vault-pw", "px-test"
    )
    uploads.append(run_dir)

    assert playbook == "proxmox_guests"
    assert sorted(os.listdir(run_dir + "/project")) == [
        "files",
        "proxmox_guest.yml",
        "proxmox_guests.yml",
    ]
    assert os.listdir(run_dir + "/project/files") == ["10.99.0.5.conf"]
    with open("/src/uploads/become/px-test.yml") as src, open(
        run_dir + "/vars/proxmox_credentials.yml"
    ) as copied:
        assert copied.read() == src.read()
    assert oct(os.stat(run_dir + "/vault.pass").st_mode & 0o777) == "0o600"

    with open(run_dir + "/inventory/hosts.yml") as f:
        nodes = yaml.safe_load(f)["all"]["children"]["proxmox_nodes"]["hosts"]
    assert sorted(nodes) == ["north__pve3", "south_site__pve3"]
    assert nodes["north__pve3"]["proxmox_cluster"] == "north"
    assert nodes["north__pve3"]["proxmox_guests"] == [
        {
            "type": "vm",
            "vmid": "215",
            "name": "jupiter",
            "telegraf_conf": "10.99.0.5.conf",
        },
        {"type": "lxc", "vmid": "104", "name": "central", "telegraf_conf": ""},
    ]
    assert nodes["south_site__pve3"]["proxmox_cluster"] == "south site"

    with open(run_dir + "/env/extravars") as f:
        extravars = yaml.safe_load(f)
    assert "telegraf" in extravars["guest_script"]
    assert "telegraf --once" in extravars["guest_post_script"]


def test_prepare_run_uses_the_custom_script(uploads):
    targets = [
        {
            "cluster": "north",
            "node": "pve3",
            "type": "lxc",
            "vmid": "104",
            "name": "central",
        }
    ]
    run_dir, _ = ansible_helper.prepare_proxmox_run(
        targets, "script", "vault-pw", "px-test", script="uptime"
    )
    uploads.append(run_dir)

    with open(run_dir + "/env/extravars") as f:
        assert yaml.safe_load(f) == {"guest_script": "uptime", "guest_post_script": ""}


def test_prepare_run_refuses_empty_script_and_missing_credentials(uploads):
    targets = [
        {
            "cluster": "north",
            "node": "pve3",
            "type": "lxc",
            "vmid": "104",
            "name": "central",
        }
    ]
    with pytest.raises(Exception, match="No script"):
        ansible_helper.prepare_proxmox_run(
            targets, "script", "pw", "px-test", script=" "
        )
    with pytest.raises(Exception, match="Credentials file not found"):
        ansible_helper.prepare_proxmox_run(targets, "apt_upgrade", "pw", "nope")
