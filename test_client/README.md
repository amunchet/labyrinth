## Test Client

Many things needed for this test client:
    - SSH server for ansible automation
    - Telegraf client installation
    - [FUTURE] Tiny http server, serving statistics like the Prometheus client would

Notes on SSH Keys:
    - https://stackoverflow.com/questions/54991392/using-ansible-vault-for-ansibles-ssh-keyfile

    - We'll force SSH keys to have strong passphrases (or suggest it nicely), then have an additional field in the `vault.yml` to unlock the SSH key.  I don't see a reason to use Ansible vault on the keyfile, when the passphrase should be good enough.  