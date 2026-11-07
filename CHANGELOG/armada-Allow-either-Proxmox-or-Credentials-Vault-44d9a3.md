# Changelog: Allow either Proxmox or Credentials Vault

- Armada session: `Allow either Proxmox or Credentials Vault`
- Branch: `armada/Allow-either-Proxmox-or-Credentials-Vault-44d9a3`
- Base branch: `master`
- Started: 2026-11-07 08:27 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-11-07 03:06 CST
Added a **Vault format** dropdown (Standard / Proxmox) to the Deploy page, on both the manual form and the Prepared Deployment card. An ordinary playbook can now log in to the Proxmox hypervisors with the same `proxmox_nodes` vault (e.g. `proxmox-root.yml`) the guest deploy uses, so there is one set of hypervisor credentials instead of two. Before this, a run only read top-level `ansible_user`/`ansible_ssh_pass`, so picking the Proxmox vault ended in "Permission denied".
- The format travels with staged requests (`vault_format` on `POST /ansible_request/` and `mcp_prepare_deployment`, overridable on the Prepared Deployment card; older requests read as standard), with deploy links (`&vault_format=proxmox`), and is recorded on `ansible_runs`. Unknown values get a fixed 482.
- In the Proxmox format, `run_ansible` gives each target the login of the `proxmox_nodes` entry whose `ansible_host` is its address: user (default root), password, become password. These are group vars for `clients`, so a playbook's `localhost` plays never get them. Root escalates with `su`, because Proxmox has no sudo. The run copy drops the vault the playbook was last saved with from its `vars_files`, since play vars would override the logins and a vault with another password would fail to decrypt. The saved playbook is untouched. A first play stops the run before anything connects if any target lacks a complete entry, naming those targets in the run's failure list, then pins every target's `ssh_host_key`.
- Fixed host key pinning for password logins, in the existing guest deploy too. ansible-runner turns host key checking off, and its `StrictHostKeyChecking=no` came first on the ssh command line, where it wins. A wrong key was still refused, but an unusable pin (a pasted fingerprint, a truncated key) sent the root password to whatever answered. Both playbooks now set `ansible_host_key_checking: true`.
- Verified against a real sshd with ansible-core 2.21.5 / ansible-runner 2.4.3: two nodes with their own logins in one run (root through `su` with no sudo installed, a user through real sudo), a stale `vars_files` vault with another password, a `localhost` play, wrong and unusable pins (no password sent, before vs. after), missing entries, a standard vault read as Proxmox, and the standard format unchanged.

## 2026-11-07 11:32 CST
Fixed the SonarCloud quality gate on PR #86 (Reliability Rating on New Code was C, the gate requires A). SonarCloud's new rule `javascript:S9383` ("Promises should not be left unhandled", added 2026-09-29, first applied to these files by this PR's analysis) flagged two old `this.loadFilesList(type)` calls in `Deploy.vue`'s vault and file upload callbacks as Major bugs. Both callbacks now await the list refresh, so a failure lands in the chain's existing `.catch`. Also took the optional chain Sonar suggested in `Conversations.vue`'s `staged()`. No behavior change: `loadFilesList` resolves at once and handles its own errors.
