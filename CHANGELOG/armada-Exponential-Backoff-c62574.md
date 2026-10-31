# Changelog: Exponential Backoff

- Armada session: `Exponential Backoff`
- Branch: `armada/Exponential-Backoff-c62574`
- Base branch: `master`
- Started: 2026-10-31 19:07 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-31 14:29 CDT
Exponential backoff for alert notifications, configurable via `GET`/`POST /alert-backoff/settings` (on by default: notify at once, then reminders after 1h, 2h, 4h, ... capped at 24h). Watcher and alive-check alerts are now held firing in Alertmanager for as long as the problem lasts and resolved explicitly when it clears. Before, watcher alerts expired after Alertmanager's 5 minute `resolve_timeout` but were only re-posted every 10 minutes, so every failing service flapped FIRING/RESOLVED into Slack. Between reminders each alert is muted by a Labyrinth-managed Alertmanager silence, so it stays visible but quiet. The hourly Proxmox disk and EC2 digest emails use the same schedule per issue, and a new issue still emails at once. All of it lives in `backend/watcher.py`; new tests in `test_31_alert_backoff.py`, including a round trip against a real Alertmanager.
