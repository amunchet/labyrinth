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
import subprocess
import shutil
import uuid

import ansi2html
import ansible_runner


from typing import List


def check_file(filename, file_type, raw=""):
    """
    Verifies the file uploaded is a valid file of the specified type
    """
    retval = False
    temp_file = "/tmp/{}".format(str(uuid.uuid1()))

    look_file = "/src/uploads/{}/{}".format(file_type, filename)

    if not os.path.exists(look_file):
        look_file = "/tmp/{}".format(filename)

    if raw == "" and not os.path.exists(look_file):
        return False

    if file_type == "ansible" and filename and raw != "":
        # We have a raw data to write out
        with open(temp_file, "w") as f:
            f.write(raw)

        x = subprocess.run(
            ["ansible-playbook {} --check".format(temp_file)],
            shell=True,
            capture_output=True,
        )
        if x.returncode >= 4:
            retval = False
        else:
            retval = True

        if retval:
            if not os.path.exists("/src/uploads/ansible"):  # pragma: no cover
                os.mkdir("/src/uploads/ansible")
            shutil.move(temp_file, "/src/uploads/ansible/{}.yml".format(filename))

        return [retval, x.stdout, x.stderr]

    elif file_type == "ansible":
        x = subprocess.run(
            ["ansible-playbook {} --check".format(look_file)],
            shell=True,
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

        x = subprocess.run(["telegraf --test"], shell=True, capture_output=True)
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


def run_ansible(
    hosts: List, playbook: str, vault_password: str, become_file: str, ssh_key_file=""
):
    """
    Runs ansible playbook
        - Key is to first remove the directory
    
    :param hosts - hosts to run the ansible playbook
    :param playbook - playbook to run
    :param vault_password - this is the temporary vault password to store 
    :param become_file - Encrypted vault file that contains the become password

    :param ssh_key_file - SSH key to use for hosts

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

    if not os.path.exists("/run"):  # pragma: no cover
        os.mkdir("/run")

    os.mkdir(RUN_DIR)

    folders = ["inventory", "project", "vars", "env"]
    for folder in folders:
        os.mkdir("{}/{}".format(RUN_DIR, folder))

    # Copy over playbook
    src_playbook = "{}/{}.yml".format(SRC_DIR, playbook)
    if not os.path.exists(src_playbook):
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
            f.write(host)

    # Become file
    old_become = "{}/{}.yml".format(BECOME_DIR, become_file)
    if not os.path.exists(old_become):
        raise Exception("Become file not found" + str(old_become))

    shutil.copy(old_become, "{}/vars/{}.yml".format(RUN_DIR, become_file))

    # Write password
    with open("{}/vault.pass".format(RUN_DIR), "w") as f:
        f.write(vault_password)

    # Write password
    with open("{}/vault.pass".format(RUN_DIR), "w") as f:
        f.write(vault_password)

    # Run ansible and return HTML
    try:
        a = ansible_runner.run(
            private_data_dir=RUN_DIR,
            playbook="{}.yml".format(playbook),
            cmdline="-v --vault-password-file ../vault.pass",
        )
        raise Exception("Done.")
    except Exception:
        # Delete Vault Password
        if os.path.exists("{}/vault.pass".format(RUN_DIR)):
            os.remove("{}/vault.pass".format(RUN_DIR))

    if os.path.exists("/vault.pass"):
        os.remove("/vault.pass")

    z = ansi2html.Ansi2HTMLConverter()
    output = z.convert("".join(a.stdout))
    # Delete all files
    shutil.rmtree(RUN_DIR)

    return output
