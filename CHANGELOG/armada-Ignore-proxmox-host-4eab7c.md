# Changelog: Ignore proxmox host

- Armada session: `Ignore proxmox host`
- Branch: `armada/Ignore-proxmox-host-4eab7c`
- Base branch: `master`
- Started: 2026-09-11 17:06 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-09-11 13:00 CDT
Added a Settings-driven exception list for Proxmox VMs whose QEMU guest agent
never responds (e.g. a macOS guest). New `labyrinth.settings` entry
`proxmox_qemu_agent_ignore_vms` (comma/newline list of VM names or VMIDs,
optionally scoped as `cluster/target`) is parsed by
`proxmox_helper.parse_qemu_agent_ignore_list` and applied at read time via
`apply_qemu_agent_ignore_list`, which sets `qemu_guest_agent_ignored` on each
VM without touching the cached payload. `proxmox_disk_check` skips
`vm_qemu_missing` issues for flagged VMs (so they never hit the alert email or
the "full" test email), and `/disk-space/proxmox` + `/refresh` return the flag
so the Disk Space page swaps the warning icon for a muted "ignored" marker.
`/disk-space/settings` returns the normalized list. UI: a warning-bordered
"QEMU Guest Agent Exceptions" card on Settings > Disk Space > Proxmox Clusters,
gated behind an "I understand" button and a confirm dialog, with Clear All
deleting the setting outright. Backend + frontend tests added; no schema change.

## 2026-09-11 15:13 CDT
Merged `origin/master` (Postgres/TimescaleDB migration, last-known-good disk
readings, MCP changes) into this branch and resolved the conflicts. In
`_collect_vm_issues` master's last-known-good handling now runs first (a real
over-threshold reading is still reported as a stale `vm` issue even for a
listed VM), then the Settings opt-out skips the `vm_qemu_missing` issue, then
the existing missing-agent reporting. Updated the new ignore-list call sites and
tests to `serve.db` (master renamed `mongo_client`). Verified against a scratch
TimescaleDB: 1018 backend tests pass at 95.14% coverage (the two
`test_01_alertmanager` failures need a live alertmanager and fail identically on
pristine master here); 192 frontend unit tests pass and lint is clean.
