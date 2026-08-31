import json

import pytest

from ai import ai_pipeline
from ai import chatgpt_helper
from ai import email_helper


class FakeSettingsCollection:
    def __init__(self, docs=None):
        self._docs = {d["name"]: d for d in (docs or [])}

    def find_one(self, query):
        return self._docs.get(query.get("name"))


class FakeMongo:
    def __init__(self, settings_docs=None):
        self._settings = FakeSettingsCollection(settings_docs)

    def __getitem__(self, _dbname):
        return {"settings": self._settings}


def test_render_alert_email_html_prefers_host_alerts():
    output = {"host_alerts": [], "summary_email": "<p>legacy</p>"}
    assert ai_pipeline.render_alert_email_html(output) == "<p>No active alerts.</p>"


def test_render_alert_email_html_falls_back_to_summary_email():
    output = {"summary_email": "<p>legacy</p>"}
    assert ai_pipeline.render_alert_email_html(output) == "<p>legacy</p>"


def test_render_alert_email_html_falls_back_to_default_placeholder():
    output = {}
    assert ai_pipeline.render_alert_email_html(output) == "See HTML version"


def test_run_ai_judgement_parses_chatgpt_response(monkeypatch):
    class FakeResp:
        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"wake_up_it_director": True, "host_alerts": []}
                            )
                        }
                    }
                ]
            }

    captured = {}

    def fake_ml_process(first_pass, prompt, model_override=None):
        captured["first_pass"] = first_pass
        captured["prompt"] = prompt
        captured["model_override"] = model_override
        return FakeResp()

    monkeypatch.setattr(chatgpt_helper, "ml_process", fake_ml_process)

    output = ai_pipeline.run_ai_judgement("a prompt", "gpt-test", dashboard_data=[])

    assert output == {"wake_up_it_director": True, "host_alerts": []}
    assert captured["prompt"] == "a prompt"
    assert captured["model_override"] == "gpt-test"


def test_send_simple_test_email_requires_recipients():
    with pytest.raises(ValueError):
        ai_pipeline.send_simple_test_email(
            [], {"from_name": "Bot", "subject_template": "X"}
        )


def test_send_simple_test_email_sends_with_settings(monkeypatch):
    sent = {}
    monkeypatch.setattr(
        email_helper,
        "email_helper",
        lambda **kwargs: sent.update(kwargs) or "<msg-id>",
    )

    ai_settings = {
        "subject_template": "Custom [{time}]",
        "from_name": "Custom Bot",
    }
    msg_id = ai_pipeline.send_simple_test_email(["a@example.com"], ai_settings)

    assert msg_id == "<msg-id>"
    assert sent["to"] == ["a@example.com"]
    assert sent["from_name"] == "Custom Bot"
    assert sent["subject"].startswith("[TEST] Custom [")


def test_send_full_test_email_requires_recipients(monkeypatch):
    monkeypatch.delenv("EMAIL_TO", raising=False)
    db = FakeMongo()

    with pytest.raises(ValueError):
        ai_pipeline.send_full_test_email(db=db)


def test_send_full_test_email_runs_pipeline_and_sends(monkeypatch):
    db = FakeMongo([{"name": "ai_alert_recipients", "value": "ops@example.com"}])

    class FakeResp:
        def json(self):
            return {
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
                                            "failing_services": ["db_conn"],
                                            "notes": "Database down.",
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

    monkeypatch.setattr(chatgpt_helper, "ml_process", lambda *a, **k: FakeResp())

    sent = {}
    monkeypatch.setattr(
        email_helper,
        "email_helper",
        lambda **kwargs: sent.update(kwargs) or "<full-msg-id>",
    )

    result = ai_pipeline.send_full_test_email(db=db)

    assert result["message_id"] == "<full-msg-id>"
    assert result["wake_up_it_director"] is True
    assert result["host_alerts_count"] == 1
    assert result["critical_services_count"] == 1
    assert sent["to"] == ["ops@example.com"]
    assert "api-1" in sent["html"]


def test_send_full_test_email_recipients_override_saved_settings(monkeypatch):
    db = FakeMongo([{"name": "ai_alert_recipients", "value": "saved@example.com"}])

    class FakeResp:
        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"wake_up_it_director": False, "host_alerts": []}
                            )
                        }
                    }
                ]
            }

    monkeypatch.setattr(chatgpt_helper, "ml_process", lambda *a, **k: FakeResp())

    sent = {}
    monkeypatch.setattr(
        email_helper,
        "email_helper",
        lambda **kwargs: sent.update(kwargs) or "<id>",
    )

    ai_pipeline.send_full_test_email(["override@example.com"], db=db)

    assert sent["to"] == ["override@example.com"]
