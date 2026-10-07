# Changelog: Bugfix - ignored proxmox item

- Armada session: `Bugfix - ignored proxmox item`
- Branch: `armada/Bugfix---ignored-proxmox-item-fedaff`
- Base branch: `master`
- Started: 2026-10-07 18:52 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-07 14:08 CDT
Fixed VMs on the QEMU guest agent ignore list (Settings -> `proxmox_qemu_agent_ignore_vms`) still showing up in disk-space alert emails. `_collect_vm_issues` checked the ignore flag only after the "last known-good reading" fallback, so an ignored VM whose agent answers only some of the time (e.g. `haos-18.2` on `pve5`) was re-reported through that fallback as a stale over-threshold VM. The ignore check now runs first. Added a regression test.
