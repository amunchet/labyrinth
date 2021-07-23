#!/usr/bin/env python3
"""
Tests for ansible functions

```
ansible_runner.run(\
    private_data_dir="/src/test/ansible", \
    playbook="sample.yml", \
    cmdline="--vault-password-file ../vault.pass")
```

"""

from ansible_helper import check_file

def test_list_files():
    """
    Lists different types of key files
        - SSH Keys
        - Ansible
        - etc.
    """

def test_find_ip():
    """
    Tests finding the IP of the labyrinth network
    """

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


    valid_type = ["ssh", "totp", "become", "telegraf", "ansible", "other"]

    # Encrypted files

    assert check_file("/src/test/sample_encrypted_file", "ssh")
    assert check_file("/src/test/sample_encrypted_file", "totp") 
    assert check_file("/src/test/sample_encrypted_file", "become")
    assert not check_file("/src/test/sample_telegraf.json", "become")
    assert not check_file("/src/test/sample_telegraf.json", "totp")
    assert not check_file("/src/test/sample_telegraf.json", "ssh")

    # Telegraf
    assert check_file("/src/test/sample_telegraf.conf", "telegraf")
    assert not check_file("/src/test/sample_telegraf.json", "telegraf")

    # Ansible 
    assert check_file("/src/test/ansible/project/startup.yml", "ansible")
    assert not check_file("/src/test/sample_telegraf.json", "ansible")

    # Other
    assert check_file("/src/test/sample_telegraf.json", "other")


def test_create_vault_password_file():
    """Tests creating the vault password file"""

def test_check_vault_password_file():
    """If the vault password file is present when it shouldn't be, throw a fit"""

def test_run_ansible():
    """
    Tests running a given ansible file and getting expected output
    """