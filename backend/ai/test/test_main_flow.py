import json
import os
import importlib
import types
import pytest


# Helpers / fakes
class FakeRedis:
    def __init__(self, store=None, fail_get=False, fail_set=False):
        self.store = store or {}
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.setex_calls = []

    def get(self, key):
        if self.fail_get:
            raise RuntimeError("redis get failed")
        val = self.store.get(key)
        if val is None:
            return None
        # emulate redis returning bytes
        return val if isinstance(val, bytes) else str(val).encode("utf-8")

    def setex(self, key, ttl, value):
        if self.fail_set:
            raise RuntimeError("redis setex failed")
        self.setex_calls.append((key, ttl, value))
        self.store[key] = value


class FakeSettingsCollection:
    """Minimal stand-in for the `labyrinth.settings` Mongo collection."""

    def __init__(self, docs=None):
        self._docs = {d["name"]: d for d in (docs or [])}

    def find_one(self, query):
        return self._docs.get(query.get("name"))


class FakeMongo:
    """Minimal stand-in for a pymongo client: db["labyrinth"]["settings"]."""

    def __init__(self, settings_docs=None):
        self._settings = FakeSettingsCollection(settings_docs)

    def __getitem__(self, _dbname):
        return {"settings": self._settings}


def load_main_with_mocks(
    monkeypatch,
    redis_obj,
    ml_json_payload,
    email_enabled=True,
    alert_ttl="7200",
    settings_docs=None,
):
    # Mock environment
    os.environ["EMAIL_TO"] = "alerts@example.com"
    os.environ["ALERT_TTL_SECONDS"] = alert_ttl

    # Mock redis.Redis to return our fake
    import redis as redis_mod

    monkeypatch.setattr(redis_mod, "Redis", lambda host=None: redis_obj)

    # Mock chatgpt_helper.ml_process -> returns an object with .json()
    class FakeResp:
        def json(self):
            return ml_json_payload

    from ai import chatgpt_helper

    monkeypatch.setattr(chatgpt_helper, "ml_process", lambda *a, **k: FakeResp())

    # Mock email_helper.email_helper
    sent = {"called": False, "args": None, "kwargs": None}

    def fake_email_helper(**kwargs):
        sent["called"] = True
        sent["kwargs"] = kwargs
        return "<fake@msg>"

    from ai import email_helper

    monkeypatch.setattr(
        email_helper,
        "email_helper",
        fake_email_helper if email_enabled else lambda **k: None,
    )

    # Reload main to pick up monkeypatches/env
    from ai import main as app_main

    importlib.reload(app_main)
    fake_db = FakeMongo(settings_docs)
    return app_main, sent, fake_db


def make_dashboard_bytes(payload):
    return json.dumps(payload).encode("utf-8")


def minimal_dashboard_with_failure():
    return [
        {
            "groups": [
                {
                    "hosts": [
                        {
                            "host": "api-1",
                            "monitor": True,
                            "services": [{"name": "db_conn", "state": False}],
                        }
                    ]
                }
            ]
        }
    ]


def test_main_sends_email_on_new_critical_services(monkeypatch, capsys):
    dashboard = minimal_dashboard_with_failure()
    redis_obj = FakeRedis(store={"dashboard": make_dashboard_bytes(dashboard)})

    # ChatGPT output: wake up + list of critical_services (host/service)
    ml_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "wake_up_it_director": True,
                            "host_alerts": [
                                {
                                    "host": "api-1",
                                    "severity": "critical",
                                    "likely_connection_issue": False,
                                    "failing_services": ["db_conn"],
                                    "notes": "Database connection failing.",
                                }
                            ],
                            "critical_services": [
                                {"host": "api-1", "service_name": "db_conn"}
                            ],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent, fake_db = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )

    app_main.main("inital_prompt.txt.example", db=fake_db)

    out = capsys.readouterr().out
    assert "Waking Up IT Director..." in out
    assert "New critical issues since last email" in out  # updated message
    assert sent["called"] is True
    # email rendered from template (contains host name from host_alerts)
    assert "api-1" in sent["kwargs"]["html"]
    assert "CRITICAL" in sent["kwargs"]["html"]
    # last_email stored with TTL
    assert redis_obj.setex_calls
    key, ttl, value = redis_obj.setex_calls[0]
    assert key == "last_email"
    assert ttl == int(os.environ["ALERT_TTL_SECONDS"])
    # normalized pairs JSON (sorted list of pairs)
    assert value == json.dumps([("api-1", "db_conn")], separators=(",", ":"))


def test_main_skips_email_if_same_critical_services(monkeypatch, capsys):
    dashboard = minimal_dashboard_with_failure()
    # Pre-store last_email as normalized pairs
    last_norm = json.dumps([("api-1", "db_conn")], separators=(",", ":"))
    redis_obj = FakeRedis(
        store={
            "dashboard": make_dashboard_bytes(dashboard),
            "last_email": last_norm.encode("utf-8"),
        }
    )

    ml_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "wake_up_it_director": True,
                            "host_alerts": [
                                {
                                    "host": "api-1",
                                    "severity": "critical",
                                    "likely_connection_issue": False,
                                    "failing_services": ["db_conn"],
                                    "notes": "Database failing.",
                                }
                            ],
                            "critical_services": [
                                {"host": "api-1", "service_name": "db_conn"}
                            ],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent, fake_db = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )

    app_main.main("inital_prompt.txt.example", db=fake_db)
    out = capsys.readouterr().out
    assert "No NEW critical issues since last email" in out  # updated message
    assert sent["called"] is False  # no email


def test_main_no_wakeup(monkeypatch, capsys):
    dashboard = minimal_dashboard_with_failure()
    redis_obj = FakeRedis(store={"dashboard": make_dashboard_bytes(dashboard)})

    ml_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "wake_up_it_director": False,
                            "host_alerts": [],
                            "critical_services": [],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent, fake_db = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )
    app_main.main("inital_prompt.txt.example", db=fake_db)
    out = capsys.readouterr().out
    assert "wake_up_it_director = False; no email sent." in out
    assert sent["called"] is False


def test_main_handles_legacy_last_email_format(monkeypatch, capsys):
    dashboard = minimal_dashboard_with_failure()
    # Legacy last_email could be some other JSON; new logic treats it as empty baseline,
    # so current issues are considered "new".
    legacy = json.dumps([{"host": "api-1", "service_name": "db_conn"}])
    redis_obj = FakeRedis(
        store={
            "dashboard": make_dashboard_bytes(dashboard),
            "last_email": legacy.encode("utf-8"),
        }
    )

    ml_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "wake_up_it_director": True,
                            "host_alerts": [
                                {
                                    "host": "api-1",
                                    "severity": "critical",
                                    "likely_connection_issue": False,
                                    "failing_services": ["db_conn"],
                                    "notes": "Database failing.",
                                }
                            ],
                            "critical_services": [
                                {"host": "api-1", "service_name": "db_conn"}
                            ],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent, fake_db = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )
    app_main.main("inital_prompt.txt.example", db=fake_db)
    out = capsys.readouterr().out
    assert "New critical issues since last email" in out  # updated message
    assert sent["called"] is True


def test_main_falls_back_to_summary_email_when_no_host_alerts(monkeypatch, capsys):
    """Legacy AI output without host_alerts falls back to summary_email."""
    dashboard = minimal_dashboard_with_failure()
    redis_obj = FakeRedis(store={"dashboard": make_dashboard_bytes(dashboard)})

    ml_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "wake_up_it_director": True,
                            "summary_email": "<h1>LEGACY ALERT</h1>",
                            "critical_services": [
                                {"host": "api-1", "service_name": "db_conn"}
                            ],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent, fake_db = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )
    app_main.main("inital_prompt.txt.example", db=fake_db)
    assert sent["called"] is True
    assert sent["kwargs"]["html"] == "<h1>LEGACY ALERT</h1>"


def test_main_fatal_when_dashboard_redis_fails(monkeypatch, capsys):
    # This FakeRedis is configured to raise on .get(...)
    dashboard = minimal_dashboard_with_failure()
    redis_obj = FakeRedis(
        store={"dashboard": make_dashboard_bytes(dashboard)},
        fail_get=True,  # <- cause .get("dashboard") to blow up
        fail_set=True,
    )

    ml_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "wake_up_it_director": True,
                            "host_alerts": [
                                {
                                    "host": "api-1",
                                    "severity": "critical",
                                    "likely_connection_issue": False,
                                    "failing_services": ["db_conn"],
                                    "notes": "Database failing.",
                                }
                            ],
                            "critical_services": [
                                {"host": "api-1", "service_name": "db_conn"}
                            ],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent, fake_db = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )

    # Expect the *entire* run to be fatal due to the initial dashboard fetch
    with pytest.raises(Exception):
        app_main.main("inital_prompt.txt.example", db=fake_db)

    # Ensure we did NOT proceed to email, since we died before that stage
    assert sent["called"] is False


# ---------------------------------------------------------------------------
# render_email_html tests
# ---------------------------------------------------------------------------


def test_render_email_html_empty():
    from ai.main import render_email_html

    html = render_email_html([])
    assert "No active alerts" in html


def test_render_email_html_critical_row():
    from ai.main import render_email_html

    alerts = [
        {
            "host": "server-1",
            "severity": "critical",
            "likely_connection_issue": False,
            "failing_services": ["db_conn", "api_health"],
            "notes": "Database and API both down.",
        }
    ]
    html = render_email_html(alerts)
    assert "server-1" in html
    assert "CRITICAL" in html
    assert "db_conn" in html
    assert "api_health" in html
    assert "Database and API both down." in html
    # should not show connection-issue badge for False
    assert "connection issue" not in html


def test_render_email_html_connection_issue_badge():
    from ai.main import render_email_html

    alerts = [
        {
            "host": "net-host",
            "severity": "critical",
            "likely_connection_issue": True,
            "failing_services": ["svc1", "svc2", "svc3"],
            "notes": "All services down.",
        }
    ]
    html = render_email_html(alerts)
    assert "possible connection issue" in html


def test_render_email_html_warning_severity():
    from ai.main import render_email_html

    alerts = [
        {
            "host": "worker-1",
            "severity": "warning",
            "likely_connection_issue": False,
            "failing_services": ["disk_space"],
            "notes": "Disk usage elevated.",
        }
    ]
    html = render_email_html(alerts)
    assert "WARNING" in html
    assert "disk_space" in html


def test_render_email_html_multiple_hosts():
    from ai.main import render_email_html

    alerts = [
        {
            "host": "host-a",
            "severity": "critical",
            "likely_connection_issue": False,
            "failing_services": ["svc1"],
            "notes": "Note A.",
        },
        {
            "host": "host-b",
            "severity": "warning",
            "likely_connection_issue": True,
            "failing_services": ["svc2", "svc3"],
            "notes": "Note B.",
        },
    ]
    html = render_email_html(alerts)
    assert "host-a" in html
    assert "host-b" in html
    assert "CRITICAL" in html
    assert "WARNING" in html
    assert "possible connection issue" in html


def test_process_dashboard_includes_all_services():
    """all_services includes non-failing services too."""
    from ai.main import process_dashboard

    data = [
        {
            "groups": [
                {
                    "hosts": [
                        {
                            "host": "mixed-host",
                            "monitor": True,
                            "services": [
                                {"name": "db_conn", "state": False},
                                {"name": "api_health", "state": True},
                                {"name": "disk", "state": True},
                            ],
                        }
                    ]
                }
            ]
        }
    ]
    result = json.loads(process_dashboard(data))
    assert len(result) == 1
    entry = result[0]
    assert entry["host"] == "mixed-host"
    assert "db_conn" in entry["all_services"]
    assert "api_health" in entry["all_services"]
    assert "disk" in entry["all_services"]
    # only the failing one appears in failing
    assert entry["failing"][0] == "db_conn"
