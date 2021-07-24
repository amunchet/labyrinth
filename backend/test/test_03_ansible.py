#!/usr/bin/env python3
"""
Tests for ansible functions


"""
import socket
import json
import shutil
import os


import pytest

from common.test import unwrap
from ansible_helper import check_file, run_ansible
from serve import find_ip, list_directory, get_ansible_file, save_ansible_file

valid_type = ["ssh", "totp", "become", "telegraf", "ansible", "other"]


@pytest.fixture
def setup():
    if not os.path.exists("/src/uploads/ansible"):
        os.mkdir("/src/uploads/ansible")
    if not os.path.exists("/src/uploads/ansible/deploy.yml"):
        shutil.copy("/src/test/ansible/project/install.yml", "/src/uploads/ansible/deploy.yml")

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
    
    a = unwrap(save_ansible_file)(data=lines, fname="test")
    assert a[1] == 200

    with open("/src/uploads/ansible/test.yml") as f:
        assert lines == f.read()

    # Broken file - check if vali
    with open("/src/test/sample_dashboard.json") as f:
        lines = f.read()
    
    a = unwrap(save_ansible_file)(data=lines, fname="test2.yml")
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
        if not os.path.exists("/src/uploads/{}".format(fname)):
            os.mkdir("/src/uploads/{}".format(fname))
        
        output = os.listdir("/src/uploads/{}".format(fname))
        if not output:
            with open("/src/uploads/{}/_test".format(fname), "w") as f:
                f.write("\n")

        output = os.listdir("/src/uploads/{}".format(fname))
        a = unwrap(list_directory)(fname)
        assert a[1] == 200
        assert json.loads(a[0]) == output

    os.system("rm /src/uploads/*/_test")

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
        if not os.path.exists(output):
            shutil.copy(src, output)
        
        assert check_file(last, type) == expected

    # Encrypted files

    helper("/src/test/sample_encrypted_file", "ssh")
    helper("/src/test/sample_encrypted_file", "totp") 
    helper("/src/test/sample_encrypted_file", "become")
    helper("/src/test/sample_telegraf.json", "become", False)
    helper("/src/test/sample_telegraf.json", "totp", False)
    helper("/src/test/sample_telegraf.json", "ssh", False)

    # Telegraf
    helper("/src/test/sample_telegraf.conf", "telegraf")
    helper("/src/test/sample_telegraf.json", "telegraf", False)

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

    output = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">\n<html>\n<head>\n<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n<title></title>\n<style type="text/css">\n.ansi2html-content { display: inline; white-space: pre-wrap; word-wrap: break-word; }\n.body_foreground { color: #AAAAAA; }\n.body_background { background-color: #000000; }\n.body_foreground > .bold,.bold > .body_foreground, body.body_foreground > pre > .bold { color: #FFFFFF; font-weight: normal; }\n.inv_foreground { color: #000000; }\n.inv_background { background-color: #AAAAAA; }\n.ansi1 { font-weight: bold; }\n.ansi32 { color: #00aa00; }\n.ansi33 { color: #aa5500; }\n.ansi35 { color: #E850A8; }\n</style>\n</head>\n<body class="body_foreground body_background" style="font-size: normal;" >\n<pre class="ansi2html-content">\n\nPLAY [localhost] ***************************************************************\n\nTASK [Gathering Facts] *********************************************************\n<span class="ansi32">ok: [localhost]</span>\n<span class="ansi32">\x1b[\n\nTASK [Remove password file] ****************************************************\n</span><span class="ansi33">changed: [localhost]</span>\n<span class="ansi33">\x1b[\n\nPLAY [all] *********************************************************************\n\nTASK [Ensure python installed] *************************************************\n</span><span class="ansi33">changed: [sampleclient]</span>\n<span class="ansi33">\x1b[\n\nPLAY [all] *********************************************************************\n\nTASK [Gathering Facts] *********************************************************\n</span><span class="ansi1 ansi35">[WARNING]: Platform linux on host sampleclient is using the discovered Python</span>\n<span class="ansi1 ansi35">interpreter at /usr/bin/python, but future installation of another Python</span>\n<span class="ansi1 ansi35">interpreter could change this. See https://docs.ansible.com/ansible/2.9/referen</span>\n<span class="ansi1 ansi35">ce_appendices/interpreter_discovery.html for more information.</span>\n<span class="ansi1 ansi35">\x1b[\n</span><span class="ansi32">ok: [sampleclient]</span>\n<span class="ansi32">\x1b[\n\nTASK [Add Repo key] ************************************************************\n</span><span class="ansi33">changed: [sampleclient]</span>\n<span class="ansi33">\x1b[\n\nTASK [Add InfluxDB repo] *******************************************************\n</span><span class="ansi33">changed: [sampleclient]</span>\n<span class="ansi33">\x1b[\n\nTASK [Telegraf installation] ***************************************************\n</span><span class="ansi32">ok: [sampleclient]</span>\n<span class="ansi32">\x1b[\n\nTASK [Start Telegraf service] **************************************************\n</span><span class="ansi33">changed: [sampleclient]</span>\n<span class="ansi33">\x1b[\n\nPLAY RECAP *********************************************************************\n</span><span class="ansi33">localhost</span>                  : <span class="ansi32">ok=2   </span> <span class="ansi33">changed=1   </span> unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   \n<span class="ansi33">sampleclient</span>               : <span class="ansi32">ok=6   </span> <span class="ansi33">changed=4   </span> unreachable=0    failed=0  skipped=0    rescued=0    ignored=0   \n\n\n</pre>\n</body>\n\n</html>\n"""


    # Copy over files
    file_moves = [
        ("/src/test/ansible/project/install.yml", "/src/uploads/ansible/install.yml"),
        ("/src/test/ansible/vars/vault.yml", "/src/uploads/become/vault.yml")
    ]

    


    for src,dest in file_moves:
        if not os.path.exists(dest):
            shutil.copy(src, dest)
    # Check a clean run

    x = run_ansible(hosts="sampleclient", playbook="install", become_file="vault", vault_password="test")
    
    def compare(old, newer):
        old_parsed = [x.replace(" ", "") for x in old.split("\n") if x.strip() != ""]
        new_parsed = [x.replace(" ", "") for x in newer.split("\n") if x.strip() != ""]

        for i in range(0, len(old_parsed)):
            assert old_parsed[i] == new_parsed[i]

    compare(x, output)
    assert not os.path.exists("/vault.pass")

    # Check a second run

    x = run_ansible(hosts="sampleclient", playbook="install", become_file="vault", vault_password="test")

    compare(x, output)
    assert not os.path.exists("/vault.pass")
