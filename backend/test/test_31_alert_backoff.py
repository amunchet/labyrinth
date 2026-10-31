#!/usr/bin/env python3
"""
Notification backoff (watcher.py): repeat notifications for an ongoing
problem come exponentially less often, while new problems still notify at once
"""
import json
import os
import time
from unittest.mock import Mock

import pytest
import redis

import serve
import watcher
from common.test import unwrap

START = 1_800_000_000.0
CFG = {"enabled": True, "first_minutes": 60, "multiplier": 2, "max_hours": 4}


class FakeRedis(dict):
    """Just the get/set the backoff uses"""

    def set(self, key, value):
        self[key] = value


@pytest.fixture
def clock(monkeypatch):
    """Controllable time.time(), as hours after START"""
    now = {"t": START}
    monkeypatch.setattr(watcher.time, "time", lambda: now["t"])

    def at(hours):
        now["t"] = START + hours * 3600

    return at


@pytest.fixture
def am(monkeypatch, tmp_path):
    """Records Alertmanager API calls; silences get ids s1, s2, ..."""
    calls = []

    def fake(method, path, **kwargs):
        calls.append((method, path, json.loads(kwargs.get("data") or "null")))
        res = Mock(ok=True, text="")
        res.json.return_value = {"silenceID": "s{}".format(len(calls))}
        return res

    monkeypatch.setattr(watcher, "_alertmanager", fake)
    # No alertmanager.yml: Alertmanager's default timings, so a 6 minute grace
    monkeypatch.setattr(watcher, "ALERTMANAGER_CONFIG", str(tmp_path / "none.yml"))
    return calls


def _alert(instance="host1", severity="error"):
    return {
        "alert_name": "PROBLEM",
        "service": "cpu",
        "instance": instance,
        "severity": severity,
        "summary": "A service failed the metric check.",
    }


def _silences(calls):
    return [body for method, path, body in calls if path == "/silences"]


# Digest emails (Proxmox disk, EC2)


def test_digest_reminders_back_off_exponentially_up_to_the_cap(clock):
    """An issue seen by every hourly run is emailed at 0, 1, 3, 7, 11, 15h"""
    rc, sent = FakeRedis(), []
    for hour in range(16):
        # Cron runs drift; a run a little early still sends a due reminder
        clock(hour - (0.01 if hour % 2 else 0))
        watcher.send_digest(rc, "disk", ["vm-101"], CFG, lambda: sent.append(hour))
    assert sent == [0, 1, 3, 7, 11, 15]


def test_digest_new_issue_emails_at_once_and_a_cleared_issue_starts_over(clock):
    rc, sent = FakeRedis(), []

    def run(hour, keys):
        clock(hour)
        return watcher.send_digest(rc, "disk", keys, CFG, lambda: sent.append(hour))

    assert run(0, ["a"])
    assert not run(0.5, ["a"])
    assert run(0.6, ["a", "b"])  # b is new
    assert not run(0.7, ["a", "b"])
    assert run(1, ["a", "b"])  # a's first reminder

    # a clears; when it returns it is new again, despite b's backoff
    run(2, ["b"])
    assert run(2.1, ["a", "b"])
    assert sent == [0, 0.6, 1, 2, 2.1]


def test_digest_failed_send_is_retried_next_run(clock):
    rc = FakeRedis()

    def broken():
        raise RuntimeError("SMTP down")

    clock(0)
    with pytest.raises(RuntimeError):
        watcher.send_digest(rc, "disk", ["a"], CFG, broken)
    clock(1 / 60)
    assert watcher.send_digest(rc, "disk", ["a"], CFG, lambda: None)


def test_digest_disabled_emails_every_run(clock):
    rc, cfg = FakeRedis(), {**CFG, "enabled": False}
    for minute in range(3):
        clock(minute / 60)
        assert watcher.send_digest(rc, "disk", ["a"], cfg, lambda: None)
    clock(0.1)
    assert not watcher.send_digest(rc, "disk", [], cfg, lambda: None)


# Alertmanager alerts (watcher, alive)


def test_reminders_are_muted_by_silences_until_due(clock, am):
    rc = FakeRedis()
    clock(0)
    watcher.report_problems(rc, "watcher", [_alert()], CFG, hold=1800)

    (post,) = [body for method, path, body in am if path == "/alerts"]
    assert post[0]["labels"] == {
        "alertname": "PROBLEM",
        "service": "cpu",
        "severity": "error",
        "instance": "host1",
    }
    # Held firing past the next run, so it no longer flaps to RESOLVED
    assert post[0]["endsAt"] == watcher._iso(START + 1800)

    # Muted once Alertmanager has had time to send it, until the reminder
    (silence,) = _silences(am)
    assert silence["startsAt"] == watcher._iso(START + 360)
    assert silence["endsAt"] == watcher._iso(START + 3600)
    assert {m["name"]: m["value"] for m in silence["matchers"]} == post[0]["labels"]

    # Still failing: posted again, but the silence stands
    am.clear()
    clock(0.5)
    watcher.report_problems(rc, "watcher", [_alert()], CFG, hold=1800)
    assert len(am) == 1 and not _silences(am)

    # Reminder due: the gap doubles
    clock(1)
    watcher.report_problems(rc, "watcher", [_alert()], CFG, hold=1800)
    (silence,) = _silences(am)
    assert silence["endsAt"] == watcher._iso(START + 3 * 3600)
    assert "2 sent" in silence["comment"]


def test_recovered_problem_is_resolved_and_unmuted(clock, am):
    rc = FakeRedis()
    clock(0)
    watcher.report_problems(rc, "watcher", [_alert("a"), _alert("b")], CFG, 1800)
    am.clear()

    clock(0.5)
    watcher.report_problems(rc, "watcher", [_alert("b")], CFG, hold=1800)
    assert ("DELETE", "/silence/s2", None) in am
    resolved = [
        body[0]
        for method, path, body in am
        if path == "/alerts" and body[0]["labels"]["instance"] == "a"
    ]
    assert resolved[0]["endsAt"] == watcher._iso(START + 1800)

    # Failing again later is a new problem: notified at once, then muted anew
    am.clear()
    clock(0.6)
    watcher.report_problems(rc, "watcher", [_alert("a"), _alert("b")], CFG, 1800)
    (silence,) = _silences(am)
    assert silence["endsAt"] == watcher._iso(START + 1.6 * 3600)


def test_severity_change_is_a_new_problem(clock, am):
    rc = FakeRedis()
    clock(0)
    watcher.report_problems(rc, "watcher", [_alert(severity="warning")], CFG, 1800)
    am.clear()
    clock(0.2)
    watcher.report_problems(rc, "watcher", [_alert(severity="error")], CFG, 1800)
    # The warning is resolved and unmuted, the error notifies and gets its own silence
    assert ("DELETE", "/silence/s2", None) in am
    assert len(_silences(am)) == 1


def test_no_silence_when_the_gap_is_shorter_than_alertmanager_needs(clock, am):
    rc = FakeRedis()
    clock(0)
    watcher.report_problems(rc, "alive", [_alert()], {**CFG, "first_minutes": 5}, 300)
    assert not _silences(am)


def test_disabling_backoff_lifts_silences_and_stops_muting(clock, am):
    rc, off = FakeRedis(), {**CFG, "enabled": False}
    clock(0)
    watcher.report_problems(rc, "watcher", [_alert()], CFG, hold=1800)
    am.clear()

    clock(0.2)
    watcher.report_problems(rc, "watcher", [_alert()], off, hold=1800)
    assert ("DELETE", "/silence/s2", None) in am
    clock(5)
    watcher.report_problems(rc, "watcher", [_alert()], off, hold=1800)
    assert not _silences(am)


def test_silence_expired_by_hand_does_not_stop_alerting(clock, am, monkeypatch):
    rc = FakeRedis()
    clock(0)
    watcher.report_problems(rc, "watcher", [_alert()], CFG, hold=1800)

    gone = Mock(ok=False, text="silence s2 already expired")
    real = watcher._alertmanager
    monkeypatch.setattr(
        watcher,
        "_alertmanager",
        lambda method, path, **kw: (
            gone if method == "DELETE" else real(method, path, **kw)
        ),
    )
    clock(0.5)
    watcher.report_problems(rc, "watcher", [], CFG, hold=1800)
    assert json.loads(rc[watcher.BACKOFF_KEY.format("watcher")]) == {}


def test_notify_grace_uses_the_slowest_route(monkeypatch, tmp_path):
    config = tmp_path / "alertmanager.yml"
    config.write_text(
        "route:\n"
        "  group_wait: 30s\n"
        "  group_interval: 1h\n"
        "  routes:\n"
        "    - receiver: slow\n"
        "      group_interval: 1h30m\n"
    )
    monkeypatch.setattr(watcher, "ALERTMANAGER_CONFIG", str(config))
    assert watcher._notify_grace() == 5400 + 60


# Settings routes


@pytest.fixture
def no_saved_backoff():
    serve.db["labyrinth"]["settings"].delete_many({"name": watcher.BACKOFF_SETTING})
    yield
    serve.db["labyrinth"]["settings"].delete_many({"name": watcher.BACKOFF_SETTING})


def _save(payload):
    with serve.app.test_request_context(
        "/alert-backoff/settings", method="POST", json=payload
    ):
        return unwrap(serve.save_alert_backoff)()


def test_settings_default_then_partial_save_round_trips(no_saved_backoff):
    assert json.loads(unwrap(serve.get_alert_backoff)()[0]) == watcher.BACKOFF_DEFAULTS

    body, status = _save({"first_minutes": 30, "max_hours": 12})
    assert status == 200
    expected = {**watcher.BACKOFF_DEFAULTS, "first_minutes": 30, "max_hours": 12}
    assert json.loads(body) == expected
    assert watcher.backoff_settings(serve.db) == expected
    assert json.loads(unwrap(serve.get_alert_backoff)()[0]) == expected


@pytest.mark.parametrize(
    "payload",
    [
        {"enabled": "false"},
        {"first_minutes": 0},
        {"first_minutes": "60"},
        {"multiplier": 0.5},
        {"multiplier": float("nan")},
        {"max_hours": 0.5},
        {"first_minutes": 120, "max_hours": 1},
    ],
)
def test_settings_reject_values_that_would_break_the_schedule(
    no_saved_backoff, payload
):
    body, status = _save(payload)
    assert status == 400
    assert "multiplier at least 1" in json.loads(body)["error"]
    assert watcher.backoff_settings(serve.db) == watcher.BACKOFF_DEFAULTS


def test_settings_accept_json_sent_without_a_content_type(no_saved_backoff):
    """The frontend's Helper.apiPost sends the JSON body with no Content-Type"""
    with serve.app.test_request_context(
        "/alert-backoff/settings", method="POST", data=json.dumps({"multiplier": 3})
    ):
        body, status = unwrap(serve.save_alert_backoff)()
    assert status == 200
    assert json.loads(body)["multiplier"] == 3


def test_settings_reject_a_non_json_body(no_saved_backoff):
    with serve.app.test_request_context(
        "/alert-backoff/settings", method="POST", data="not json"
    ):
        body, status = unwrap(serve.save_alert_backoff)()
    assert status == 400


# Against the real Alertmanager and Redis


def test_backoff_round_trip_through_alertmanager():
    """The silence Labyrinth creates mutes the alert, and recovery lifts it"""
    rc = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
    rc.delete(watcher.BACKOFF_KEY.format("test-backoff"))
    alert = _alert(instance="backoff-test-{}".format(time.time()))

    def silence_state(silence_id):
        res = watcher._alertmanager("GET", "/silence/{}".format(silence_id))
        res.raise_for_status()
        return res.json()["status"]["state"]

    cfg = {**CFG, "first_minutes": 24 * 60, "max_hours": 48}
    watcher.report_problems(rc, "test-backoff", [alert], cfg, hold=600)
    state = json.loads(rc.get(watcher.BACKOFF_KEY.format("test-backoff")))
    (silence_id,) = [s["silence"] for s in state.values()]
    assert silence_state(silence_id) == "pending"

    firing = [
        a
        for a in watcher._alertmanager("GET", "/alerts").json()
        if a["labels"]["instance"] == alert["instance"]
    ]
    assert len(firing) == 1

    watcher.report_problems(rc, "test-backoff", [], cfg, hold=600)
    assert silence_state(silence_id) == "expired"
    assert rc.get(watcher.BACKOFF_KEY.format("test-backoff")) == b"{}"
