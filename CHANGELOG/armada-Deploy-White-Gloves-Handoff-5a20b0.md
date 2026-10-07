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
