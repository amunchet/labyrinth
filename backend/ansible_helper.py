#!/usr/bin/env python3
"""
Ansible helper functions

>>> a = ansible_runner.run(private_data_dir="/src/test/ansible", playbook="install.yml", cmdline="--vault-password-file ../vault.pass")
>>> b = "\n".join([x for x in a.stdout])
>>> c = aconv().convert(b).replace("\x1b[", "")
>>> with open('test.html', 'w') as f:
...     f.write(c)
...
3398
>>> aconv
<class 'ansi2html.converter.Ansi2HTMLConverter'>

"""
import os
import re
import subprocess
import shutil
import uuid

import ansi2html
import ansible_runner
import yaml

from werkzeug.utils import secure_filename
from typing import List


def check_file(filename, file_type, raw=""):
    """
    Verifies the file uploaded is a valid file of the specified type
    """
    retval = False
    temp_file = "/tmp/{}".format(str(uuid.uuid1()))

    filename = secure_filename(filename)
    file_type = secure_filename(file_type)

    look_file = "/src/uploads/{}/{}".format(file_type, filename)

    if filename not in os.listdir("/src/uploads/{}".format(file_type)):
        look_file = "/tmp/{}".format(filename)

    if raw == "" and not os.path.exists(look_file):
        return False

    if file_type == "ansible" and filename and raw != "":
        # We have a raw data to write out
        with open(temp_file, "w") as f:
            f.write(raw)

        x = subprocess.run(
            ["ansible-playbook", temp_file, "--check"],
            capture_output=True,
        )
        if x.returncode >= 4:
            retval = False
        else:
            retval = True

        if retval:
            if not os.path.exists("/src/uploads/ansible"):  # pragma: no cover
                os.makedirs("/src/uploads/ansible")
            shutil.move(temp_file, "/src/uploads/ansible/{}.yml".format(filename))

        return [retval, x.stdout, x.stderr]

    elif file_type == "ansible":
        x = subprocess.run(
            ["ansible-playbook", look_file, "--check"],
            capture_output=True,
        )
        if x.returncode >= 4:
            retval = False
        else:
            retval = True
        return [retval, x.stdout, x.stderr]

    elif file_type == "telegraf":
        if os.path.exists("/etc/telegraf/telegraf.conf"):  # pragma: no cover
            os.remove("/etc/telegraf/telegraf.conf")

        shutil.copy(look_file, "/etc/telegraf/telegraf.conf")

        x = subprocess.run(["telegraf", "--test"], capture_output=True)
        if x.returncode != 0:
            retval = False
        else:
            retval = True

        os.remove("/etc/telegraf/telegraf.conf")
        return [retval, x.stdout, x.stderr]

    elif file_type == "other":
        return True
    elif file_type == "ssh":
        # Checking for encrypted file
        with open(look_file) as f:
            count = 0
            for item in f.readlines():
                if count == 0:
                    if "--BEGIN OPENSSH PRIVATE KEY--" in item:
                        return True
                break
        return False

    else:
        # Checking for encrypted file
        with open(look_file) as f:
            count = 0
            for item in f.readlines():
                if count == 0:
                    if "ANSIBLE_VAULT" in item:
                        return True
                break
        return False


def validate_ai_playbook(raw, forbidden_hosts=None):
    """Reject unsafe agent-generated playbook structure before Ansible runs it.

    Used for playbooks staged through the MCP server.  Deployment scope comes
    from the staged host list, so the playbook may target only the generic
    groups and may not embed credentials or a concrete IP/hostname.
    """
    try:
        docs = list(yaml.safe_load_all(raw))
    except yaml.YAMLError:
        return "Invalid YAML syntax."
    # yaml.safe_load_all wraps each YAML document; a playbook is a sequence of
    # play dicts, so each document is a list.  Flatten one level.
    plays = []
    for doc in docs:
        if isinstance(doc, list):
            plays.extend(doc)
        elif doc is not None:
            plays.append(doc)
    if not plays or any(not isinstance(play, dict) for play in plays):
        return "The playbook must contain one or more Ansible plays."

    secret_names = {
        "ansible_password",
        "ansible_become_password",
        "ansible_ssh_pass",
        "vault_password",
        "ssh_password",
    }
    allowed_hosts = {"all", "clients"}
    forbidden_hosts = {
        str(host).strip().lower()
        for host in (forbidden_hosts or [])
        if str(host).strip()
    }

    def walk(value):
        if isinstance(value, str) and any(
            host in value.lower() for host in forbidden_hosts
        ):
            return "Generated playbooks must not contain deployment target hosts."
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in secret_names:
                    return "Playbooks must reference encrypted vars files, never cleartext passwords."
                error = walk(child)
                if error:
                    return error
        elif isinstance(value, list):
            for child in value:
                error = walk(child)
                if error:
                    return error
        return None

    for play in plays:
        hosts = play.get("hosts")
        if hosts not in allowed_hosts:
            return "Generated playbooks must use hosts: all or hosts: clients; deployment targets are selected separately."
        if play.get("vars_files"):
            return "Generated playbooks must not choose credential files; the approved encrypted become file is attached by the controller."
        error = walk(play)
        if error:
            return error
    return None


def persist_reviewed_playbook(filename, raw, vars_file, forbidden_hosts=None):
    """Attach the encrypted become vars and save a validated agent-generated playbook."""
    validation_error = validate_ai_playbook(raw, forbidden_hosts=forbidden_hosts)
    if validation_error:
        raise ValueError(validation_error)
    # Each YAML document of a playbook is a list of plays
    plays = []
    for doc in yaml.safe_load_all(raw):
        plays.extend(doc if isinstance(doc, list) else [doc])
    for play in plays:
        play["vars_files"] = [
            "/src/uploads/become/{}.yml".format(
                secure_filename(vars_file).replace(".yml", "")
            )
        ]
    return check_file(
        secure_filename(filename).replace(".yml", ""),
        "ansible",
        raw=yaml.safe_dump(plays, sort_keys=False),
    )


def run_ansible(
    hosts: List,
    playbook: str,
    vault_password: str,
    become_file: str,
    ssh_key_file="",
    totp_file="",
):
    """
    Runs ansible playbook
        - Key is to first remove the directory
    
    :param hosts - hosts to run the ansible playbook
    :param playbook - playbook to run
    :param vault_password - this is the temporary vault password to store 
    :param become_file - Encrypted vault file that contains the become password

    :param ssh_key_file - SSH key to use for hosts (optional)
    :param totp_file - TOTP secret file for 2FA hosts (optional)

    ```
    ansible_runner.run(\
        private_data_dir="/src/test/ansible", \
        playbook="install.yml", \
        cmdline="--vault-password-file ../vault.pass")
    ```

    """
    RUN_DIR = "/run/{}".format(uuid.uuid1())
    SRC_DIR = "/src/uploads/ansible"
    BECOME_DIR = "/src/uploads/become"
    SSH_DIR = "/src/uploads/ssh"
    TOTP_DIR = "/src/uploads/totp"

    if not os.path.exists("/run"):  # pragma: no cover
        os.mkdir("/run")

    os.makedirs(RUN_DIR)

    folders = ["inventory", "project", "vars", "env"]
    for folder in folders:
        os.makedirs("{}/{}".format(RUN_DIR, folder))

    # Copy over playbook
    src_playbook = "{}/{}.yml".format(SRC_DIR, playbook)
    if "{}.yml".format(playbook) not in os.listdir(SRC_DIR):
        raise Exception("No YML file found.")

    shutil.copy(src_playbook, "{}/project/".format(RUN_DIR))

    # Hosts
    if type(hosts) == str:
        parsed_hosts = hosts.split(",")
    else:
        parsed_hosts = hosts

    with open("{}/inventory/hosts".format(RUN_DIR), "w") as f:
        f.write("[clients]\n")
        for host in parsed_hosts:
            f.write(f"{host}\n")

    # Become file
    old_become = "{}/{}.yml".format(BECOME_DIR, become_file)
    if "{}.yml".format(become_file) not in os.listdir(BECOME_DIR):
        raise Exception("Become file not found" + str(old_become))

    shutil.copy(old_become, "{}/vars/{}.yml".format(RUN_DIR, become_file))

    # SSH key file (optional)
    if ssh_key_file:
        safe_ssh_key = secure_filename(ssh_key_file)
        ssh_dir_real = os.path.realpath(SSH_DIR)
        ssh_key_path = os.path.realpath(os.path.join(SSH_DIR, safe_ssh_key))
        # Verify resolved path stays within SSH_DIR to prevent directory traversal
        if os.path.commonpath([ssh_dir_real, ssh_key_path]) != ssh_dir_real:
            raise Exception("Invalid SSH key file path: " + ssh_key_file)
        if not os.path.exists(ssh_key_path):
            raise Exception("SSH key file not found: " + str(ssh_key_path))
        dest_key = "{}/env/ssh_key".format(RUN_DIR)
        shutil.copy(ssh_key_path, dest_key)
        os.chmod(dest_key, 0o600)

    # TOTP file for 2FA hosts (optional)
    if totp_file:
        safe_totp = secure_filename(totp_file + ".yml")
        totp_dir_real = os.path.realpath(TOTP_DIR)
        totp_path = os.path.realpath(os.path.join(TOTP_DIR, safe_totp))
        # Verify resolved path stays within TOTP_DIR to prevent directory traversal
        if os.path.commonpath([totp_dir_real, totp_path]) != totp_dir_real:
            raise Exception("Invalid TOTP file path: " + totp_file)
        if not os.path.exists(totp_path):
            raise Exception("TOTP file not found: " + str(totp_path))
        shutil.copy(
            totp_path, "{}/vars/{}.yml".format(RUN_DIR, secure_filename(totp_file))
        )

    write_vault_password(RUN_DIR, vault_password)

    # Run ansible and return HTML

    return RUN_DIR, playbook


def write_vault_password(run_dir, vault_password):
    """
    Write the vault password to a restrictive file in the run directory.
    It is necessarily plain text because ansible-vault reads it from a file at
    runtime; the caller removes it as soon as the run ends.
    """
    fd = os.open(
        "{}/vault.pass".format(run_dir), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
    )
    with os.fdopen(fd, "w") as f:
        f.write(vault_password)


PROXMOX_PLAYBOOK_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "proxmox_deploy"
)

APT_ONLY = """set -e
command -v apt-get >/dev/null || { echo "Only Debian/Ubuntu (apt-get) guests are supported" >&2; exit 3; }
export DEBIAN_FRONTEND=noninteractive
"""

# Same verified-fingerprint InfluxData repo setup as backend/Dockerfile
TELEGRAF_INSTALL = (
    APT_ONLY
    + """apt-get update -q
apt-get install -y -q ca-certificates curl gnupg cron
mkdir -p /etc/apt/keyrings
curl -fsSL https://repos.influxdata.com/influxdata-archive.key -o /tmp/influxdata-archive.key
fingerprint=$(gpg --batch --show-keys --with-colons /tmp/influxdata-archive.key | awk -F: '$1 == "fpr" { print $10; exit }')
test "$fingerprint" = 24C975CBA61A024EE1B631787C3D57159FC2F927
gpg --batch --yes --dearmor -o /etc/apt/keyrings/influxdata-archive.gpg /tmp/influxdata-archive.key
rm /tmp/influxdata-archive.key
echo 'deb [signed-by=/etc/apt/keyrings/influxdata-archive.gpg] https://repos.influxdata.com/debian stable main' > /etc/apt/sources.list.d/influxdata.list
apt-get update -q
apt-get install -y -q telegraf
"""
)

# Same model as the SSH deploy playbook: no telegraf service, a once-a-minute
# `telegraf --once` from cron.  Drops that playbook's crontab entry so a guest
# moved over from SSH deploys doesn't report twice.
TELEGRAF_SCHEDULE = """set -e
(systemctl disable --now telegraf || service telegraf stop) >/dev/null 2>&1 || true
crontab -l 2>/dev/null | grep -v -e '^#Ansible: Telegraf$' -e 'telegraf --once' | crontab -
echo '* * * * * root /usr/bin/telegraf --once >/dev/null 2>&1' > /etc/cron.d/labyrinth-telegraf
(systemctl enable --now cron || service cron start) >/dev/null 2>&1
"""

APT_UPGRADE = (
    APT_ONLY
    + """apt-get update -q
apt-get upgrade -y -q -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold
"""
)

# action -> (guest script, post script run after the Telegraf config is pushed)
PROXMOX_ACTIONS = {
    "telegraf": (TELEGRAF_INSTALL, TELEGRAF_SCHEDULE),
    "apt_upgrade": (APT_UPGRADE, ""),
    "script": (None, ""),
}


def prepare_proxmox_run(
    targets: List, action: str, vault_password: str, credentials_file: str, script=""
):
    """
    Lay out a run directory for proxmox_deploy/proxmox_guests.yml, which reaches
    each target VM/LXC through its hypervisor using the per-node credentials in
    the encrypted `credentials_file` (an uploaded become file).

    :param targets - dicts of cluster, node, type (vm/lxc), vmid, name and
                     telegraf_conf (the host's /src/uploads/telegraf/ name, or "")
    :param action - a PROXMOX_ACTIONS key; "script" runs `script` instead
    """
    guest_script, post_script = PROXMOX_ACTIONS[action]
    if action == "script":
        guest_script = script
    if not (guest_script or "").strip():
        raise Exception("No script to run.")

    credentials_file = secure_filename(credentials_file).replace(".yml", "")
    if "{}.yml".format(credentials_file) not in os.listdir("/src/uploads/become"):
        raise Exception("Credentials file not found: " + credentials_file)

    RUN_DIR = "/run/{}".format(uuid.uuid1())
    for folder in ["inventory", "project/files", "vars", "env"]:
        os.makedirs("{}/{}".format(RUN_DIR, folder))

    for name in ["proxmox_guests.yml", "proxmox_guest.yml"]:
        shutil.copy(os.path.join(PROXMOX_PLAYBOOK_DIR, name), RUN_DIR + "/project/")

    shutil.copy(
        "/src/uploads/become/{}.yml".format(credentials_file),
        RUN_DIR + "/vars/proxmox_credentials.yml",
    )

    # One inventory host per hypervisor; cluster names are free text
    nodes = {}
    for target in targets:
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{target['cluster']}__{target['node']}")
        node = nodes.setdefault(
            name,
            {
                "proxmox_cluster": target["cluster"],
                "proxmox_node": target["node"],
                "proxmox_guests": [],
            },
        )
        conf = ""
        if target.get("telegraf_conf"):
            conf = secure_filename(target["telegraf_conf"]) + ".conf"
            shutil.copy("/src/uploads/telegraf/" + conf, RUN_DIR + "/project/files/")
        node["proxmox_guests"].append(
            {
                "type": target["type"],
                "vmid": str(target["vmid"]),
                "name": target["name"],
                "telegraf_conf": conf,
            }
        )

    with open(RUN_DIR + "/inventory/hosts.yml", "w") as f:
        yaml.safe_dump({"all": {"children": {"proxmox_nodes": {"hosts": nodes}}}}, f)
    with open(RUN_DIR + "/env/extravars", "w") as f:
        yaml.safe_dump(
            {"guest_script": guest_script, "guest_post_script": post_script}, f
        )

    write_vault_password(RUN_DIR, vault_password)
    return RUN_DIR, "proxmox_guests"
