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

## 2026-11-14 15:16 CST
Fixes from the PR #90 review. The SVG icon check now ignores tabs, newlines and other control characters when looking for `javascript:`. Browsers drop those characters from URLs, so an encoded tab (`java&#9;script:`) used to get through. The mcp container now mounts its own code (`./backend`) read-only, so running as root can't rewrite code the backend runs. `update_mac` (used by the UI and `mcp_change_host_address`) now moves uplinks and map placements to the new key, and refuses a key another host already has.

## 2026-11-16 14:35 CST
Cleared the SonarCloud gate failure on PR #90: four "temporary files in publicly writable directories" findings (S5443). `mcp_upload_map_image` now checks the image in memory and writes it straight to `/src/uploads/images`, and `mcp_upload_icon` writes straight to `/public/icons`. Neither goes through `/tmp` any more. A bad image is now refused with "Not a valid image" before anything is written. Also flattened `get_dashboard` to stay under Sonar's complexity limit, and split the composite asserts and multi-call `pytest.raises` blocks it flagged in `test_31`.

## 2026-11-16 14:42 CST
SonarCloud also counted three `/tmp` findings (S5443) against this PR in `serve.py`'s file upload route. Those lines are older than the PR, but they still failed the gate. Uploads are now staged in a private `tempfile.mkdtemp()` directory, and `ansible_helper.check_file` takes the staged `path` and checks that copy. Two existing bugs go away with this. A failed vault upload no longer deletes the vault already saved: the old code removed the saved file before checking the new one. And re-uploading a file whose name already exists now checks the new upload, not the saved file.

## 2026-11-16 22:16 CST
Fixed the 12 SonarCloud bugs listed under master's new code. These are in the frontend and predate this PR. Calls to async methods that already catch and report their own errors are now marked `void` (Sonar's floating-promise rule): disk space auto-refresh, map image loads and draft saves, and rack and location drops. The tag-key sort in `AwsInstancesView` and the service-type sort in `ProblemServices` now compare with `localeCompare` instead of the default sort.

## 2026-11-16 23:28 CST
Cleared the rest of SonarCloud's code-quality findings on PR #90:
- `ansible_helper.check_file` was rewritten to bring it under the complexity limit, with the same results for every file type. Raw playbooks are still checked from a scratch copy and saved only if they pass. SSH keys and vault files are still recognised by their first line. The Telegraf check drops a redundant delete before copying the config.
- `serve.py` gets `BECOME_DIR` and `become_file_exists()` in place of three copies of the become-folder lookup.
- `custom_dashboard_image_upload` now stages browser uploads in a private temporary directory instead of `/tmp`.

The Dockerfile's root user is left for acceptance in SonarCloud.

## 2026-11-16 23:31 CST
SonarCloud's /tmp findings (S5443) also covered the two remaining /tmp paths on lines this PR edited. The map image route (`custom_dashboard_image_upload`) now checks the uploaded bytes in memory and writes the file straight to `/src/uploads/images`. Its test-only `override` hook is gone, and `test_10` posts real files instead. `check_file` now takes the scratch copy of a raw playbook from `tempfile.mkstemp` and deletes it when the check fails. Before, a failed check left the copy behind.

## 2026-11-16 23:35 CST
`check_file` no longer falls back to `/tmp/<filename>` when a file isn't among the saved uploads. Nothing relies on that any more: uploads pass their staged `path`, and the other callers pass raw content. Its cleanup branch is also flattened, which brings the function under Sonar's complexity limit.

## 2026-11-16 23:50 CST
Rebased onto master to take in #89 (adding an Ansible vault by hand on the Deploy page), which conflicted in `serve.py`'s upload route. Master's handling of a hand-entered vault is kept as it is: it validates the input, scratches the file beside its destination with `mkstemp` and moves it into place atomically. Browser file uploads now use the same scratch-beside-destination pattern, replacing this branch's temp directory. The become-file lookups use this branch's shared `become_file_exists()`.
