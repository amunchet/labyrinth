# Changelog: Deploy White Gloves Handoff

- Armada session: `Deploy White Gloves Handoff`
- Branch: `armada/Deploy-White-Gloves-Handoff-5a20b0`
- Base branch: `master`
- Started: 2026-10-07 17:45 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-07 14:10 CDT (19:10 UTC)
Agent -> human Ansible deployment hand-off.
- Every Ansible run is now recorded in Mongo `ansible_runs` (status, success/failed outcome from the play recap, per-host stats, failed tasks, capped log tail), so results survive Redis and can be read back. Setup errors such as a missing playbook now mark the run `error` instead of leaving it stuck at `queued`.
- New admin routes: `/ansible_runs/`, `/ansible_run/<job_id>`, plus staged deployments via `POST /ansible_request/` and `/ansible_request/<id>` (Mongo `ansible_requests`, including the runs launched from each).
- MCP tools to list/read playbooks and become files, stage a deployment (optionally with AI-generated playbook content) that returns a Deploy deep link, and read run results. The MCP server never runs playbooks; it gets a read-only `uploads` mount and a `LABYRINTH_URL` for absolute links.
- Deploy page: `?request=<id>` or `?ips=&playbook=&become=` pre-fills a "Prepared Deployment" card where you review the playbook, type the vault password, and press Enter/Deploy. A staged playbook is saved (validated, become `vars_files` injected) right before the run. Added a "Copy deploy link" button. The Auth0 login now returns to the original URL, so deep links survive a login.

## 2026-10-07 14:26 CDT (19:26 UTC)
Merged `master` (44 commits, including the Postgres/TimescaleDB adapter, the in-app AI chat with draft deploys, and the externally exposed MCP server) and rebuilt the hand-off on top of it. Supersedes the design in the previous entry:
- Run history moves from direct Mongo calls to the `backend/db` adapter, with new `ansible_runs` / `ansible_requests` JSONB tables registered in `postgres_adapter.py`. Both the Deploy page runner and AI chat deploys now go through one `start_ansible_job`, so every run is recorded. Vault-password cleanup now happens before the database write.
- Staged playbook content is validated with the same `validate_ai_playbook` rules as AI chat drafts. It may replace an earlier generated playbook but never a human-written one (409).
- New `POST /ansible_request/<id>/deploy`: the human supplies only the vault password, and the backend saves the staged content with `persist_reviewed_playbook` before running, so what runs is exactly what was staged. The Deploy page's "Prepared Deployment" card is self-contained (review, password, live log, outcome with failed tasks) and leaves the manual form untouched. `ansibleRunner.js` is split into `startPlaybook`/`pollAnsibleJob`.
- MCP deployment tools live on the shared `LabyrinthClient` in `ai/mcp/client.py`.
- `db/__init__.py`: forked children (ansible runs, AI chat turns) now drop the inherited shared client rather than reusing the parent's Postgres sockets. Master's ansible job already wrote to the database from a forked child.

## 2026-10-07 16:04 CDT (21:04 UTC)
Merged `master` again after it removed the in-app AI Assistant (#70). The MCP hand-off no longer has any AI chat hooks: the `chat_store` updates are gone from `run_ansible_background`/`start_ansible_job`, the `ai_chat_sessions` table is dropped, and the chat-only tests are removed. `validate_ai_playbook` and `persist_reviewed_playbook` (deleted with the chat) are restored in `ansible_helper.py`, because MCP-staged playbooks still need them. `persist_reviewed_playbook` now flattens YAML documents into plays before attaching `vars_files`. The old helper indexed the document list as if it were a play, which crashed on every real playbook. The Deploy page's start/poll logic moves from the deleted `ansibleRunner.js` into `startAnsibleJob`/`pollAnsibleJob` methods, shared by the manual runner and the Prepared Deployment card.
