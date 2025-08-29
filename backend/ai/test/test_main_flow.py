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


def load_main_with_mocks(
    monkeypatch, redis_obj, ml_json_payload, email_enabled=True, alert_ttl="7200"
):
    # Mock environment
    # os.environ["REDIS_HOST"] = "ignored"
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
    return app_main, sent


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
                            "summary_email": "<h1>ALERT</h1>",
                            "critical_services": [
                                {"host": "api-1", "service_name": "db_conn"}
                            ],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )

    app_main.main()

    out = capsys.readouterr().out
    assert "Waking Up IT Director..." in out
    assert "Difference in critical services since last email" in out
    assert "Sending Email" in out
    assert sent["called"] is True
    # last_email stored with TTL
    assert redis_obj.setex_calls
    key, ttl, value = redis_obj.setex_calls[0]
    assert key == "last_email"
    assert ttl == int(os.environ["ALERT_TTL_SECONDS"])
    # normalized pairs JSON
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
                            "summary_email": "<h1>ALERT</h1>",
                            "critical_services": [
                                {"host": "api-1", "service_name": "db_conn"}
                            ],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )
    app_main.main()
    out = capsys.readouterr().out
    assert "No critical differences from last email" in out
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
                            "summary_email": "<h1>nope</h1>",
                            "critical_services": [],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )
    app_main.main()
    out = capsys.readouterr().out
    assert "wake_up_it_director = False; no email sent." in out
    assert sent["called"] is False


def test_main_handles_legacy_last_email_format(monkeypatch, capsys):
    dashboard = minimal_dashboard_with_failure()
    # Legacy last_email could be some other JSON; main treats decoded JSON as "already normalized"
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
                            "summary_email": "<h1>ALERT</h1>",
                            "critical_services": [
                                {"host": "api-1", "service_name": "db_conn"}
                            ],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )
    app_main.main()
    out = capsys.readouterr().out
    # Because legacy JSON != normalized pairs JSON, we expect an email to be sent
    assert "Difference in critical services since last email" in out
    assert sent["called"] is True


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
                            "summary_email": "<h1>ALERT</h1>",
                            "critical_services": [
                                {"host": "api-1", "service_name": "db_conn"}
                            ],
                        }
                    )
                }
            }
        ]
    }

    app_main, sent = load_main_with_mocks(
        monkeypatch, redis_obj, ml_json_payload=ml_json
    )

    # Expect the *entire* run to be fatal due to the initial dashboard fetch
    with pytest.raises(
        Exception
    ):  # or pytest.raises(RuntimeError) if your FakeRedis raises RuntimeError
        app_main.main()

    # Ensure we did NOT proceed to email, since we died before that stage
    assert sent["called"] is False
