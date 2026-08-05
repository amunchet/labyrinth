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
import shlex
import subprocess
import shutil
import uuid
import yaml

import ansi2html
import ansible_runner

from werkzeug.utils import secure_filename
from typing import List


def check_file(filename, file_type, raw="", persist=True, vault_password=""):
    """
    Verifies the file uploaded is a valid file of the specified type

    :param persist - when False, validates (e.g. `ansible-playbook --check`) without
        writing the result into /src/uploads/<file_type>/. Used to validate a
        chat-drafted playbook before it has been reviewed/approved.
    """
    retval = False
    temp_file = "/tmp/{}".format(str(uuid.uuid1()))
    if not os.path.exists("/tmp"):  # pragma: no cover
        os.makedirs("/tmp")

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

        command = ["ansible-playbook", temp_file, "--check"]
        password_path = ""
        if vault_password:
            password_path = "{}.vault.pass".format(temp_file)
            fd = os.open(password_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as password_file:
                password_file.write(vault_password)
            command.extend(["--vault-password-file", password_path])
        try:
            x = subprocess.run(command, capture_output=True)
        finally:
            if password_path and os.path.exists(password_path):
                os.remove(password_path)
        if x.returncode >= 4:
            retval = False
        else:
            retval = True

        if retval and persist:
            if not os.path.exists("/src/uploads/ansible"):  # pragma: no cover
                os.makedirs("/src/uploads/ansible")
            shutil.move(temp_file, "/src/uploads/ansible/{}.yml".format(filename))
        elif os.path.exists(temp_file):
            os.remove(temp_file)

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
    """Reject unsafe model-generated playbook structure before Ansible runs it.

    Deployment scope is supplied by the human inventory at approval time. The
    model may target only the controller's generic groups and may not embed
    credentials or a concrete IP/hostname in the playbook.
    """
    try:
        plays = list(yaml.safe_load_all(raw))
    except yaml.YAMLError:
        return "Invalid YAML syntax."
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


def persist_reviewed_playbook(
    filename, raw, vars_file, vault_password="", forbidden_hosts=None
):
    """Attach encrypted become vars and persist a reviewed AI playbook."""
    filename = secure_filename(filename).replace(".yml", "")
    parsed = list(yaml.safe_load_all(raw))
    validation_error = validate_ai_playbook(raw, forbidden_hosts=forbidden_hosts)
    if validation_error:
        raise ValueError(validation_error)
    for play in parsed:
        encrypted_path = "/src/uploads/become/{}.yml".format(
            secure_filename(vars_file).replace(".yml", "")
        )
        play["vars_files"] = [encrypted_path]
    prepared = yaml.safe_dump_all(parsed, sort_keys=False)
    return check_file(
        filename,
        "ansible",
        raw=prepared,
        persist=True,
        vault_password=vault_password,
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

    # Write vault password to a restrictive temp file (required by ansible-runner).
    # The password is necessarily stored as plain text here because ansible-vault
    # reads it from a file at runtime.
    vault_pass_path = "{}/vault.pass".format(RUN_DIR)
    fd = os.open(vault_pass_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(vault_password)

    # Run ansible and return HTML

    return RUN_DIR, playbook


def run_adhoc(
    hosts: List, argv: List[str], vault_password: str, become_file: str, ssh_key_file=""
):
    """
    Synchronously runs a single ad-hoc command (Ansible's `command` module) against
    `hosts` and returns its captured output. Used for short-lived read-only diagnostics
    (disk usage, docker status, logs) - unlike `run_ansible`, this does not go through
    `ansible_runner.run_async`/background job/Redis log streaming, since the command
    is expected to complete quickly.

    :param hosts - hosts to run the command against
    :param argv - argv list for the command module (e.g. ["df", "-h"]); never a shell
        string, so there is no shell interpolation regardless of argument content
    :param vault_password - temporary vault password to store
    :param become_file - Encrypted vault file that contains the become password
    :param ssh_key_file - SSH key to use for hosts
    """
    RUN_DIR = "/run/{}".format(uuid.uuid1())
    BECOME_DIR = "/src/uploads/become"

    if not os.path.exists("/run"):  # pragma: no cover
        os.mkdir("/run")

    os.makedirs(RUN_DIR)

    folders = ["inventory", "project", "vars", "env"]
    for folder in folders:
        os.makedirs("{}/{}".format(RUN_DIR, folder))

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

    # Write vault password to a restrictive temp file (required by ansible-runner)
    vault_pass_path = "{}/vault.pass".format(RUN_DIR)
    fd = os.open(vault_pass_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(vault_password)

    module_args = " ".join(shlex.quote(a) for a in argv)

    try:
        result = ansible_runner.run(
            private_data_dir=RUN_DIR,
            host_pattern="clients",
            module="command",
            module_args=module_args,
            cmdline="--vault-password-file ../vault.pass",
            quiet=True,
        )
        stdout_lines = [event.get("stdout", "") for event in result.events]
        return {
            "status": result.status,
            "rc": result.rc,
            "stdout": "\n".join(line for line in stdout_lines if line),
        }
    finally:
        if os.path.exists("{}/vault.pass".format(RUN_DIR)):
            os.remove("{}/vault.pass".format(RUN_DIR))
        shutil.rmtree(RUN_DIR)
