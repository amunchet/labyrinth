# Changelog: Corel Draw

- Armada session: `Corel Draw`
- Branch: `armada/Corel-Draw-7f5672`
- Base branch: `master`
- Started: 2026-10-30 03:48 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-30 01:09 CDT
Built and installed an MCP server for CorelDRAW X8 on the offline development PC (10.1.1.135:8766/mcp). Its source
is in its own private repository, https://github.com/amunchet/coreldraw-mcp, not in this one: it has nothing to do
with Labyrinth. This branch carries no code changes.

Findings on the host that shaped it:
- With any network connection, CorelDRAW X8 stops at an online sign-in that the firewall blocks. With the adapters
  disabled, the same dialog offers Skip.
- So `cdr_launch` has a SYSTEM scheduled-task guard disable the adapters, presses Skip through UI Automation, and
  re-enables the adapters once COM answers (about 80 s; the agent's connection drops about 35 s).
- X8 never registers in the running object table. The server attaches through the class factory, only once the main
  window is up.

Installed with `install.ps1` (approved by the user): the guard tasks, a logon autostart and a firewall rule. The
end-to-end smoke test passes 45/45, and offline launch, quit and relaunch, self-update and rollback were exercised
on the host.

## 2026-10-30 01:32 CDT
Installed the built CorelDRAW MCP package (coreldraw-mcp commit a6e4133, CorelDrawMCP-update-0.1.0.zip, sha256
b2ff131f...4fe74) on the PC through the server's own update path: HTTP upload, then `server_update` (import check
passed), then the launcher swap (healthy, `ok: true`; the previous version is kept for `server_rollback`). All 72
installed files match the build, the elevated netguard copy matches, and config.toml was preserved. The end-to-end
smoke test passes 45/45 against the updated install.
