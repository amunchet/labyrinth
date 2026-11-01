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
    starts_at=None,
    ends_at=None,
):
    """
    Sends an alert

    :param alert_name - Name of the alert
    :param service - Name of the service
    :param instance - Host name

    :param serverity - defaults to error
    :param starts_at - epoch time the problem started. Pass it with ends_at:
        without it Alertmanager sets startsAt = endsAt, a time in the future
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
    if starts_at is not None:
        data["startsAt"] = _iso(starts_at)
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
    How long an alert stays unmuted when a notification is due, before the
    silence holding back its next reminder starts
        - Alertmanager sends only at group flushes, every group_interval, and
          repeats only once repeat_interval has fully passed since the last
          send. The first flush after a reminder falls due can be just short
          of that, so the window spans two flushes: twice the longest
          group_interval in alertmanager.yml (and at least the longest
          group_wait, for new groups), plus a minute
        - Alertmanager's defaults (30s, 5m) apply where they are unset
    """
    try:
        with open(ALERTMANAGER_CONFIG) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        config = None
    units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    longest = {"group_wait": 30, "group_interval": 300}
    routes = [config.get("route") or {}] if isinstance(config, dict) else []
    while routes:
        route = routes.pop()
        routes.extend(route.get("routes") or [])
        for name in longest:
            parts = re.findall(r"(\d+)(ms|s|m|h|d|w)", str(route.get(name, "")))
            longest[name] = max(longest[name], sum(int(n) * units[u] for n, u in parts))
    return max(longest["group_wait"], 2 * longest["group_interval"]) + 60


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


def report_problems(rc, source, alerts, cfg, hold, held=()):
    """
    Reports one check's failing problems to Alertmanager with notification backoff
        - `alerts` is every problem the check (`source`) sees failing right
          now, as send_alert() keyword arguments
        - `held` are failing problems the check is holding back for now (the
          watcher's flapping guard): already reported ones stay reported, the
          rest are ignored, so missed runs don't resolve and re-announce them
        - Each is posted firing until `hold` seconds from now, so it stays
          firing while the check keeps running
        - New problems notify at once; reminders are muted with a silence
          until they are due
        - Problems from the previous run that are no longer failing are
          resolved, and their silence is lifted
    """

    def alert_key(alert):
        return "|".join(alert[k] for k in LABELS.values())

    now = time.time()
    previous = json.loads(rc.get(BACKOFF_KEY.format(source)) or "{}")
    alerts = {
        **{alert_key(a): a for a in held if alert_key(a) in previous},
        **{alert_key(a): a for a in alerts},
    }
    grace = _notify_grace()
    current = {}

    try:
        for key, alert in alerts.items():
            state = current[key] = previous.pop(key, {})
            state["alert"] = {k: alert[k] for k in LABELS.values()}
            state.setdefault("since", now)
            send_alert(starts_at=state["since"], ends_at=now + hold, **alert)

            if not cfg["enabled"]:
                _unmute(state, now)
                for name in ("sent", "next", "gap"):
                    state.pop(name, None)
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
                            time.strftime(
                                "%Y-%m-%d %H:%M", time.localtime(state["next"])
                            ),
                        ),
                    }
                    res = _alertmanager("POST", "/silences", data=json.dumps(silence))
                    res.raise_for_status()
                    state["silence"] = res.json()["silenceID"]

        for key in list(previous):
            state = previous.pop(key)
            _unmute(state, now)
            send_alert(
                starts_at=state["since"],
                ends_at=now,
                summary="Recovered.",
                **state["alert"],
            )
    finally:
        # Saved even when Alertmanager fails partway, so the silences already
        # created stay tracked and unprocessed problems are kept for next run
        rc.set(BACKOFF_KEY.format(source), json.dumps({**previous, **current}))


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
