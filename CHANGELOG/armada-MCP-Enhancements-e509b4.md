# Changelog: MCP Enhancements

- Armada session: `MCP Enhancements`
- Branch: `armada/MCP-Enhancements-e509b4`
- Base branch: `master`
- Started: 2026-11-14 08:52 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-11-14 03:02 CST
Gave the Labyrinth MCP server a tool for nearly every backend route (92 tools, up from 56): the judged dashboard (`ok`/`failing`/`stale` per service), scan output, host group and IP/key changes, service deletion, latest-metric listing/deletion, ingest-counter reset, saved Telegraf configs, upload listings, test alerts and Alertmanager reload, notification backoff, generic settings, themes, icons, DNS lookup, disk-space/AI/EC2 settings and test emails, manual disk hosts, and add/update/delete for Proxmox clusters, AWS accounts and UniFi controllers. Secrets stay write-only, and a blank Proxmox token secret on update now keeps the saved one instead of erasing it. Still left out on purpose: secrets that would leave the backend (Telegraf key, Alertmanager password/config, become/ssh/totp files), the human's side of Ansible and conversations, `settings/restart` (it would exit the MCP server), filesystem writes, and scans. `delete_service` no longer fails where `/src/snippets` doesn't exist (the MCP container). The MCP container now mounts `/public/icons` read-only.

## 2026-11-14 03:15 CST
MCP file writes: `mcp_save_playbook`, `mcp_save_telegraf_config`, `mcp_upload_map_image`/`mcp_delete_map_image` and `mcp_upload_icon`/`mcp_delete_icon` (98 tools). Playbooks keep the existing rule that agent content never replaces a human's playbook: agent-saved files start with a marker line, and `serve.agent_may_replace_playbook` (now shared with staged deployments) accepts only those or earlier generated ones; a human claims one by deleting the line. Icons are public static files, so SVGs with scripts, event handlers, `foreignObject` or `javascript:` links are refused. Map images still in use by a map can't be deleted. To write into the root-owned bind mounts, the MCP container now runs as root like the backend and cron containers, with `uploads`, `snippets` (so service deletion also removes its snippet) and `public/icons` mounted writable; `alertmanager/` stays read-only.
