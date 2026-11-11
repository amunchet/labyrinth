# Changelog: Alexandria cron errors

- Armada session: `Alexandria cron errors`
- Branch: `armada/Alexandria-cron-errors-f7248a`
- Base branch: `master`
- Started: 2026-11-09 18:26 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-11-10 15:52 CST
No Labyrinth code changed; this session used Labyrinth's MCP deployments to fix the Alexandria host (192.168.10.242).
Graylog cron error emails came from the Alexandria cron image (Python 3.6) missing backend packages, and from reports.py.
The cron image was rebuilt on ubuntu:24.04 / Python 3.12 with the backend's requirements, and pushed to Alexandria master as 3f24f0b.
reports.py still called `serve.gb_orders`, which the 2022 serve refactor removed.
A playbook that imports `gunbroker.orders` directly, tests it, and commits and pushes only backend/reports.py is staged as alexandria-reports-fix.

## 2026-11-10 20:11 CST
The alexandria-reports-fix run succeeded.
reports.py now imports gunbroker.orders directly and completed a test run in the cron container.
Pushed to Alexandria master as 0489973; only backend/reports.py was committed.

## 2026-11-10 20:30 CST
Removed the startup `pip3 install -r /src/requirements.txt` from Alexandria's cron/entrypoint.sh.
Ubuntu 24.04 rejects that install (PEP 668), so it errored on every container start, and the image already installs those requirements.
Rebuilt and recreated the cron container, checked a clean start, and pushed to Alexandria master as a4e0760.
Found that the hourly ALEXANDRIA_ERROR emails (a Graylog south event) come from balexandria (192.168.0.216), not alexandria.
Balexandria's bitnami Redis has crash-looped since 2026-11-04 on "appendonlydir: Permission denied", so its cron cannot resolve `redis`.

## 2026-11-10 21:16 CST
Fixed balexandria's (192.168.0.216) Redis crash loop, the source of the hourly ALEXANDRIA_ERROR emails.
The data dir redis_data was owned by 1000:1000, but the bitnami container runs as 1001, so Redis 7 could not create appendonlydir.
Backed it up to redis_data.bak-20261111.tgz and chowned it to 1001:1001; Redis migrated the old AOF and stays up, and the cron container reaches it.
No compose or git change on balexandria.
Killed Labyrinth run ansible_job_5c0061f1, which had hung about 24h in its own ansible-playbook process on 192.168.10.244.
