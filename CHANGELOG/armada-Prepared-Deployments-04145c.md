# Changelog: Prepared Deployments

- Armada session: `Prepared Deployments`
- Branch: `armada/Prepared-Deployments-04145c`
- Base branch: `master`
- Started: 2026-11-25 20:42 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-11-25 15:08 CST
A prepared (MCP-staged) deployment can now only run once at a time, however many windows have its link open. Launching takes a per-deployment Redis lock (`ansible-request-run:<request_id>`, SET NX under the new job id) before the staged playbook is saved, and the run's own process adopts it and keeps it alive with a heartbeat until Ansible finishes; a second launch meanwhile gets 409 and changes nothing (it no longer rewrites the running playbook's become file). A crashed run frees the lock within its 120s TTL, so a backend restart can't leave the deployment stuck. `RedisSingleRunLock` gained a `token` argument so one process can take the lock and another adopt it.

`GET /ansible_request/<id>` now reports `active_job` from that lock (not from the run records, which a restart can leave saying "running"). The Deploy page uses it: opening the link while a run is going shows that run's live log with Deploy disabled, opening it afterwards shows the last result with the button reading "Deploy again", and a launch refused with 409 switches to following the run that is already going.
