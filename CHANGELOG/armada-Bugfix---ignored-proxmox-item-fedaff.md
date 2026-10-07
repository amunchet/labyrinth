# Changelog: Bugfix - ignored proxmox item

- Armada session: `Bugfix - ignored proxmox item`
- Branch: `armada/Bugfix---ignored-proxmox-item-fedaff`
- Base branch: `master`
- Started: 2026-10-07 18:52 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-07 14:08 CDT
Fixed VMs on the QEMU guest agent ignore list (Settings -> `proxmox_qemu_agent_ignore_vms`) still showing up in disk-space alert emails. `_collect_vm_issues` checked the ignore flag only after the "last known-good reading" fallback, so an ignored VM whose agent answers only some of the time (e.g. `haos-18.2` on `pve5`) was re-reported through that fallback as a stale over-threshold VM. The ignore check now runs first. Added a regression test.

## 2026-10-07 15:02 CDT
Merged latest `master` (AI assistant removal, #70). Only conflict was the session-specific Armada block in `CLAUDE.md`; kept this session's values.

## 2026-10-07 15:09 CDT
Stopped treating read-only image root filesystems (squashfs/erofs/iso9660/cramfs) as a VM's disk usage. Appliance OSes like Home Assistant OS mount their OS image at `/`, which is always ~100% full, so `haos-18.2` showed as a red, near-full VM (and could trigger a real over-threshold alert) instead of the muted "ignored" state its entry on the QEMU agent ignore list should give it. Such roots are now left unresolved, which flows into the existing missing-agent/ignore handling.
