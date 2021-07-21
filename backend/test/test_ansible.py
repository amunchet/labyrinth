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

def test_create_vault_password_file():
    """Tests creating the vault password file"""

def test_check_vault_password_file():
    """If the vault password file is present when it shouldn't be, throw a fit"""

def test_deploy():
    """
    Tests deploying a new telegraf installation
        - An annoying problem is this will differ depending on host (ARM get a different deploy than Ubuntu, etc.)
    """

    # A major point will be hostname - this might be the MAC Address that we can see


def test_deploy_update():
    """Tests deploying an update"""

def test_restart():
    """Tests restarting a client that's failed for whatever reason"""
