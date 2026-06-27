#!/usr/bin/env python3
"""
Tests for ansible functions


"""
import socket
import json
import shutil
import os


import pytest
import serve

from common.test import unwrap
from ansible_helper import check_file, run_ansible
from serve import (
    build_ansible_cmdline,
    delete_file,
    find_ip,
    list_files,
    list_directory,
    get_ansible_file,
    normalize_managed_filename,
    rename_file,
    save_ansible_file,
    save_setting,
    new_ansible_file,
)

valid_type = ["ssh", "totp", "become", "telegraf", "ansible", "other"]


@pytest.fixture
def setup():  # pragma: no cover
    serve.mongo_client["labyrinth"]["settings"].delete_many({})
    if not os.path.exists("/src/uploads/ansible"):
        os.mkdir("/src/uploads/ansible")
    if not os.path.exists("/src/uploads/ansible/deploy.yml"):
        shutil.copy(
            "/src/test/ansible/project/deploy.yml", "/src/uploads/ansible/deploy.yml"
        )
    if not os.path.exists("/src/uploads/become"):
        os.mkdir("/src/uploads/become")


def test_get_ansible_file(setup):
    """Returns an ansible file for edit"""
    # Normal file
    a = unwrap(get_ansible_file)("deploy")
    assert a[1] == 200

    with open("/src/uploads/ansible/deploy.yml") as f:
        assert f.read() == a[0]


def test_save_ansible_file(setup):
    """Saves an ansible file back to disk"""

    # Normal file
    with open("/src/uploads/ansible/deploy.yml") as f:
        lines = f.read()

    a = unwrap(save_ansible_file)(inp_data=lines, fname="test", vars_file="vault")
    assert a[1] == 200

    with open("/src/uploads/ansible/test.yml") as f:
        assert (
            lines.replace(
                "/src/test/ansible/vars/vault.yml", "/src/uploads/become/vault.yml"
            )
            == f.read()
        )

    unwrap(save_setting)("ansible_manage_vars_files", "0")
    a = unwrap(save_ansible_file)(inp_data=lines, fname="test3", vars_file="vault")
    assert a[1] == 200

    with open("/src/uploads/ansible/test3.yml") as f:
        assert f.read() == lines

    # Broken file - check if valid
    with open("/src/test/sample_dashboard.json") as f:
        lines = f.read()

    a = unwrap(save_ansible_file)(inp_data=lines, fname="test2.yml")
    assert a[1] == 471

    assert not os.path.exists("/src/uploads/ansible/test2.yml")


def test_list_files():
    """
    Lists different types of key files
        - SSH Keys
        - Ansible
        - etc.
    """
    for fname in valid_type:
        if not os.path.exists("/src/uploads/{}".format(fname)):  # pragma: no cover
            os.mkdir("/src/uploads/{}".format(fname))

        output = os.listdir("/src/uploads/{}".format(fname))
        if not output:  # pragma: no cover
            with open("/src/uploads/{}/_test".format(fname), "w") as f:
                f.write("\n")

        output = os.listdir("/src/uploads/{}".format(fname))
        a = unwrap(list_directory)(fname)
        assert a[1] == 200
        assert json.loads(a[0]) == output

    os.system("rm /src/uploads/*/_test")


def test_create_ansible_file():
    """
    Tests creating an ansible file
    """
    if os.path.exists("/src/uploads/ansible/test-cicd.yml"):
        os.remove("/src/uploads/ansible/test-cicd.yml")

    a = unwrap(new_ansible_file)("test-cicd.yml")
    assert a[1] == 200

    assert os.path.exists("/src/uploads/ansible/test-cicd.yml")

    a = unwrap(new_ansible_file)("test-cicd.yml")
    assert a[1] == 407

    if os.path.exists("/src/uploads/ansible/test-cicd.yml"):
        os.remove("/src/uploads/ansible/test-cicd.yml")


def test_file_management(setup):
    become_dir = "/src/uploads/become"
    source = os.path.join(become_dir, "test_file")
    renamed = os.path.join(become_dir, "renamed_file.yml")

    if os.path.exists(source):
        os.remove(source)
    if os.path.exists(source + ".yml"):
        os.remove(source + ".yml")
    if os.path.exists(renamed):
        os.remove(renamed)

    with open(source + ".yml", "w") as f:
        f.write("test")

    a = unwrap(list_files)("become")
    assert a[1] == 200
    assert "test_file.yml" in json.loads(a[0])

    b = unwrap(rename_file)("become", "test_file.yml", "renamed_file")
    assert b[1] == 200
    assert b[0] == "renamed_file.yml"
    assert os.path.exists(renamed)

    c = unwrap(rename_file)("become", "../renamed_file.yml", "ignored")
    assert c[1] == 448

    d = unwrap(delete_file)("become", "renamed_file.yml")
    assert d[1] == 200
    assert not os.path.exists(renamed)


def test_build_ansible_cmdline_from_settings():
    serve.mongo_client["labyrinth"]["settings"].delete_many({})
    assert build_ansible_cmdline() == "-vvvvv --vault-password-file ../vault.pass"

    unwrap(save_setting)("ansible_verbosity", "2")
    assert build_ansible_cmdline() == "-vv --vault-password-file ../vault.pass"


def test_filename_normalization():
    assert normalize_managed_filename("become", "vault") == "vault.yml"
    assert normalize_managed_filename("ssh", "id_rsa") == "id_rsa.yml"
    assert normalize_managed_filename("telegraf", "agent.conf") == "agent.conf"


def test_find_ip():
    """
    Tests finding the IP of the labyrinth network
    """
    ip = socket.gethostbyname(socket.gethostname())
    a = unwrap(find_ip)()
    assert a[1] == 200
    assert a[0] == ip


def test_check_file():
    """
    Runs the different checks for the given files
        - Is it an encrypted ansible vault file?  `$ANSIBLE_VAULT;` on the first line
        - Is it a valid toml file?  Should we actually run telegraf on it?
            - We have to install telegraf on backend, then copy the file to test into `/etc/telegraf/telegraf.conf`
            - Then we run `telegraf --test` and check for a non-zero exit status

        - Is it a valid ansible file?
            - Run `ansible-playbook [FILE].yml --check`

        - FUTURE - check for viruses or other malware

    """

    def helper(src, type, expected=True):
        last = src.split("/")[-1]
        output = "/src/uploads/{}/{}".format(type, last)
        if not os.path.exists(output):  # pragma: no cover
            shutil.copy(src, output)

        assert (
            check_file(last, type) == expected or check_file(last, type)[0] == expected
        )

    # Encrypted files

    helper("/src/test/ansible/sample_key", "ssh")
    helper("/src/test/sample_encrypted_file", "totp")
    helper("/src/test/sample_encrypted_file", "become")
    helper("/src/test/sample_telegraf.json", "become", False)
    helper("/src/test/sample_telegraf.json", "totp", False)
    helper("/src/test/sample_telegraf.json", "ssh", False)

    # Telegraf
    src = "/src/test/sample_telegraf.json"

    if not os.path.exists("/src/uploads/telegraf"):  # pragma: no cover
        os.mkdir("/src/uploads/telegraf")

    if not os.path.exists("/src/uploads/telegraf/sample_telegraf.conf"):
        print("Copying to sample telegraf...")
        shutil.copy(src, "/src/uploads/telegraf/sample_telegraf.conf")

    b = check_file(src.split("/")[-1], "telegraf")

    # No file found
    assert not b

    src = "/src/test/sample_telegraf.conf"
    print("Copying to sample telegraf...")
    shutil.copy(src, "/src/uploads/telegraf/sample_telegraf.conf")

    b = check_file(src.split("/")[-1], "telegraf")
    print(b)
    assert b[0]

    # Ansible
    helper("/src/test/ansible/project/startup.yml", "ansible")
    helper("/src/test/sample_telegraf.json", "ansible", False)

    # Other
    helper("/src/test/sample_telegraf.json", "other")


def test_run_ansible():
    """
    Tests running a given ansible file and getting expected output

    Basically we need to generate the runner directory.  Make sure it's cleared first.

        - Hosts?
        - Env?
        - Vault password?
    """

    # Copy over files
    file_moves = [
        ("/src/test/ansible/project/deploy.yml", "/src/uploads/ansible/install.yml"),
        ("/src/test/ansible/vars/vault.yml", "/src/uploads/become/vault.yml"),
    ]

    for src, dest in file_moves:
        if not os.path.exists(dest):
            shutil.copy(src, dest)
    # Check a clean run

    x, y = run_ansible(
        hosts="sampleclient",
        playbook="install",
        become_file="vault",
        vault_password="test",
    )
    assert "run" in x
    assert y == "install"

    # Check failing SSH key
    try:
        x = run_ansible(
            hosts="sampleclient",
            playbook="install",
            become_file="vault",
            vault_password="test",
            ssh_key_file="asdfsadfasdf",
        )
        assert False
    except Exception:
        assert True

    assert not os.path.exists("/vault.pass")
