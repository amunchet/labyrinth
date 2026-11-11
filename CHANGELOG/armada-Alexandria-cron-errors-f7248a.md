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
