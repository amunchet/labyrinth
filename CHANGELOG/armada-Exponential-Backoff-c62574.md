# Changelog: Exponential Backoff

- Armada session: `Exponential Backoff`
- Branch: `armada/Exponential-Backoff-c62574`
- Base branch: `master`
- Started: 2026-10-31 19:07 UTC

Entries are appended newest last, each stamped with the UTC date and time.

## 2026-10-31 14:29 CDT
Exponential backoff for alert notifications, configurable via `GET`/`POST /alert-backoff/settings` (on by default: notify at once, then reminders after 1h, 2h, 4h, ... capped at 24h). Watcher and alive-check alerts are now held firing in Alertmanager for as long as the problem lasts and resolved explicitly when it clears. Before, watcher alerts expired after Alertmanager's 5 minute `resolve_timeout` but were only re-posted every 10 minutes, so every failing service flapped FIRING/RESOLVED into Slack. Between reminders each alert is muted by a Labyrinth-managed Alertmanager silence, so it stays visible but quiet. The hourly Proxmox disk and EC2 digest emails use the same schedule per issue, and a new issue still emails at once. All of it lives in `backend/watcher.py`; new tests in `test_31_alert_backoff.py`, including a round trip against a real Alertmanager.

## 2026-10-31 14:38 CDT
New **Settings > Notifications** tab to turn notification backoff on or off and set the first reminder, multiplier and longest gap. It validates the values and previews the resulting reminder times (e.g. "1h, 3h, 7h, 15h, 31h, 55h, then every 24h"). The Alerts page now shows each alert's state, so alerts muted between reminders appear as *suppressed* instead of looking unhandled. `POST /alert-backoff/settings` now parses its JSON body regardless of Content-Type, because `Helper.apiPost` sends none.

## 2026-10-31 15:23 CDT
Fixes from reviewing the backoff PR:
- **Missed watcher runs no longer resolve and re-announce every alert.** Missed cron ticks, a restart, or a redeploy left a gap longer than the flapping guard's 1300s. Every ongoing alert was then resolved, and re-sent as new on the next run. Failures held back by the guard are now passed as `held` and stay reported.
- **Reminders are no longer swallowed.** Alertmanager repeats only once `repeat_interval` has fully passed, so the unmuted window now spans two `group_interval` flushes.
- **Alerts show their real start time.** They now carry `startsAt`; Alertmanager had been setting it equal to `endsAt`, a time in the future.
- **Silences stay tracked if Alertmanager fails mid-run.** Backoff state is saved even then, and the watcher cron run takes a `single_run` lock so overlapping runs can't create duplicate silences.
- **Settings are bounded:** multiplier 1-100, longest gap up to 8760 hours. A huge value would have broken every run.
