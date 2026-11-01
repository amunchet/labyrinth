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

## 2026-10-22 17:32 CDT
Fixed the MCP server judging every Telegraf-reporting guest as ~5 hours stale.
Compose passed `TZ` to the MCP image as a build arg, but its Dockerfile never
declared it, so the MCP container ran on UTC while the backend/cron containers
that write the (naive, local-time) metric timestamps run on Central. The web UI
was unaffected; agents using the MCP Telegraf/Graylog checks were not.

## 2026-11-01 01:22 CST
Merged master in for review. Master had added a README section on alert
notification backoff where this branch added its Proxmox guest deploy section;
both are kept. Master had also landed the identical MCP timezone fix
separately, so that change merged cleanly with no net difference.

## 2026-11-01 02:51 CST
Fixed a reflected XSS in `POST /proxmox_deploy/` that CodeQL failed the PR
on. When guests couldn't be deployed, the 484 response repeated the submitted
cluster/node/type/id back as text/html. It now returns JSON naming each guest by
its position in the request, with fixed problem text, and the 483 "credentials
file not found" response no longer repeats the file name. Also merged master's
MCP Ansible conversations work (#84), which merged cleanly alongside the
Proxmox deploy path.
