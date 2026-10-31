#!/usr/bin/env python3
"""
Watcher - sends alerts to Alertmanager and spaces out their notifications

Notification backoff:
    - A failing check is reported to Alertmanager on every run, held firing
      until it recovers (then resolved explicitly), so Alertmanager's view
      stays truthful and alerts no longer flap between FIRING and RESOLVED
    - Repeat notifications follow an exponential backoff: the first goes out
      at once, the first reminder after `first_minutes`, and each gap after
      that is `multiplier` times longer, up to `max_hours`. Between
      reminders the alert is muted with an Alertmanager silence
    - The Proxmox disk and EC2 digest emails use the same schedule
      (send_digest)
    - A problem that clears and later fails again starts over
"""
import datetime
import json
import re
import time

import requests
import yaml

ALERTMANAGER = "http://alertmanager:9093/api/v2"
ALERTMANAGER_CONFIG = "/alertmanager/alertmanager.yml"

BACKOFF_SETTING = "alert_backoff"
BACKOFF_DEFAULTS = {
    "enabled": True,
    "first_minutes": 60,
    "multiplier": 2,
    "max_hours": 24,
}
BACKOFF_KEY = "alert-backoff:{}"

# Alertmanager label -> send_alert() argument; together they identify an alert
LABELS = {
    "alertname": "alert_name",
    "service": "service",
    "instance": "instance",
    "severity": "severity",
}

# Digest checks run hourly from cron, so a reminder due a few minutes from now
# goes out on this run instead of waiting a whole extra hour
DIGEST_EARLY_SECONDS = 300


def _iso(epoch):
    """RFC 3339 timestamp, as Alertmanager expects"""
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat()


def _alertmanager(method, path, **kwargs):
    """Calls the Alertmanager v2 API with the shared admin password"""
    password = open("/alertmanager/pass").read()
    return requests.request(
        method,
        ALERTMANAGER + path,
        auth=("admin", password),
        headers={"Content-Type": "application/json"},
        **kwargs,
    )


def send_alert(
    alert_name,
    service,
    instance,
    severity="error",
    summary="A Service is failing.",
    url="",
    ends_at=None,
):
    """
    Sends an alert

    :param alert_name - Name of the alert
    :param service - Name of the service
    :param instance - Host name

    :param serverity - defaults to error
    :param ends_at - epoch time the alert stops firing unless sent again
        (Alertmanager's resolve_timeout when omitted; now = resolved)
    """
    data = {
        "status": "firing",
        "labels": {
            "alertname": alert_name,
            "service": service,
            "severity": severity,
            "instance": instance,
        },
        "annotations": {"summary": summary},
        "generatorURL": url or ALERTMANAGER + "/alerts",
    }
    if ends_at is not None:
        data["endsAt"] = _iso(ends_at)

    return _alertmanager("POST", "/alerts", data=json.dumps([data]))


def backoff_settings(db):
    """
    Effective notification backoff settings: the saved `alert_backoff`
    setting over the defaults
    """
    row = db["labyrinth"]["settings"].find_one({"name": BACKOFF_SETTING})
    return {**BACKOFF_DEFAULTS, **(row["value"] if row else {})}


def _schedule(state, cfg, now):
    """Records a notification going out now and schedules the next reminder"""
    if state.get("gap"):
        state["gap"] = min(state["gap"] * cfg["multiplier"], cfg["max_hours"] * 3600)
    else:
        state["gap"] = cfg["first_minutes"] * 60
    state["sent"] = state.get("sent", 0) + 1
    state["next"] = now + state["gap"]


def _notify_grace():
    """
    Seconds Alertmanager may take to send a newly firing alert: the longest
    group_wait/group_interval in alertmanager.yml, at least Alertmanager's
    default 5m group_interval, plus a minute. A silence starting sooner could
    swallow that notification.
    """
    try:
        with open(ALERTMANAGER_CONFIG) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        config = None
    units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    longest = 300  # Alertmanager's default group_interval
    routes = [config.get("route") or {}] if isinstance(config, dict) else []
    while routes:
        route = routes.pop()
        routes.extend(route.get("routes") or [])
        for name in ("group_wait", "group_interval"):
            parts = re.findall(r"(\d+)(ms|s|m|h|d|w)", str(route.get(name, "")))
            longest = max(longest, sum(int(n) * units[u] for n, u in parts))
    return longest + 60


def _unmute(state, now):
    """
    Ends the silence holding back a problem's reminders, if it is still running
        - Failures are only logged: the silence may already have been expired
          by hand in Alertmanager, and that must not stop alerting
    """
    if state.get("silence") and state.get("next", 0) > now + 60:
        res = _alertmanager("DELETE", "/silence/{}".format(state["silence"]))
        if not res.ok:
            print("Could not expire silence {}: {}".format(state["silence"], res.text))
    state["silence"] = None


def report_problems(rc, source, alerts, cfg, hold):
    """
    Reports one check's failing problems to Alertmanager with notification backoff
        - `alerts` is every problem the check (`source`) sees failing right
          now, as send_alert() keyword arguments
        - Each is posted firing until `hold` seconds from now, so it stays
          firing while the check keeps running
        - New problems notify at once; reminders are muted with a silence
          until they are due
        - Problems from the previous run that are no longer failing are
          resolved, and their silence is lifted
    """
    now = time.time()
    alerts = {"|".join(a[k] for k in LABELS.values()): a for a in alerts}
    previous = json.loads(rc.get(BACKOFF_KEY.format(source)) or "{}")
    grace = _notify_grace()
    current = {}

    for key, alert in alerts.items():
        send_alert(ends_at=now + hold, **alert)
        state = previous.pop(key, {})
        state["alert"] = {k: alert[k] for k in LABELS.values()}

        if not cfg["enabled"]:
            _unmute(state, now)
            state = {"alert": state["alert"]}
        elif now >= state.get("next", 0):
            _schedule(state, cfg, now)
            state["silence"] = None
            if state["next"] > now + grace:
                silence = {
                    "matchers": [
                        {"name": name, "value": alert[k], "isRegex": False}
                        for name, k in LABELS.items()
                    ],
                    "startsAt": _iso(now + grace),
                    "endsAt": _iso(state["next"]),
                    "createdBy": "Labyrinth",
                    "comment": "Notification backoff: {} sent, next reminder {}".format(
                        state["sent"],
                        time.strftime("%Y-%m-%d %H:%M", time.localtime(state["next"])),
                    ),
                }
                res = _alertmanager("POST", "/silences", data=json.dumps(silence))
                res.raise_for_status()
                state["silence"] = res.json()["silenceID"]
        current[key] = state

    for state in previous.values():
        _unmute(state, now)
        send_alert(ends_at=now, summary="Recovered.", **state["alert"])

    rc.set(BACKOFF_KEY.format(source), json.dumps(current))


def send_digest(rc, source, keys, cfg, send):
    """
    Exponential backoff for a periodic digest email listing every current issue
        - `keys` identify each issue the check (`source`) found this run
        - Each issue backs off on its own; send() is called when any issue is
          new or due a reminder (every run when backoff is disabled)
        - The backoff is only recorded once send() returns, so a failed send
          is retried on the next run
    Returns whether send() was called
    """
    now = time.time()
    previous = json.loads(rc.get(BACKOFF_KEY.format(source)) or "{}")
    current = {}
    due = False
    for key in keys:
        state = previous.get(key, {}) if cfg["enabled"] else {}
        if now >= state.get("next", 0) - DIGEST_EARLY_SECONDS:
            _schedule(state, cfg, now)
            due = True
        current[key] = state

    if due:
        send()
    rc.set(BACKOFF_KEY.format(source), json.dumps(current))
    return due
