# Changelog: Proxmox deployment bypass

- Armada session: `Proxmox deployment bypass`
- Branch: `armada/Proxmox-deployment-bypass-a38047`
- Base branch: `master`
- Started: 2026-10-22 18:44 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-22 17:21 CDT
Added a Proxmox guest deploy option (Deploy → "Deploy to Proxmox Guests",
`POST /proxmox_deploy/`). Ansible connects only to the hypervisors, using
per-node root credentials from an uploaded Ansible Vault become file, and runs
inside each selected guest - LXCs via `pct exec`, VMs via `qm guest exec` - so
guests no longer need their own SSH access. Actions: install/configure Telegraf
(pushes each guest's saved `{ip}.conf`), apt update/upgrade, or a custom script.
Hypervisor SSH host keys must be pinned in the vault (strict checking, so the
root password can't go to an impostor); guests are re-resolved against live
Proxmox data server-side; passwords and Telegraf configs stay out of run logs;
one failing guest doesn't stop the rest. Verified end to end with ansible-core
2.21 against stand-in `pct`/`qm` commands, plus backend tests.
