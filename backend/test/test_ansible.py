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
def test_deploy():
    """Tests deploying a new telegraf installation"""

    # A major point will be hostname - this might be the MAC Address that we can see


def test_deploy_update():
    """Tests deploying an update"""

def test_restart():
    """Tests restarting a client that's failed for whatever reason"""
