import os

from ai import main as app_main


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


def test_defaults_when_nothing_saved(monkeypatch):
    monkeypatch.delenv("EMAIL_TO", raising=False)
    db = FakeMongo()

    settings = app_main.get_ai_alert_settings(db)

    assert settings["prompt"] == app_main.DEFAULT_AI_PROMPT
    assert settings["model"] == app_main.DEFAULT_AI_MODEL
    assert settings["subject_template"] == app_main.DEFAULT_AI_ALERT_SUBJECT_TEMPLATE
    assert settings["from_name"] == app_main.DEFAULT_AI_ALERT_FROM_NAME
    assert settings["recipients"] == []


def test_saved_values_override_defaults(monkeypatch):
    monkeypatch.delenv("EMAIL_TO", raising=False)
    db = FakeMongo(
        [
            {"name": "ai_prompt", "value": "Custom prompt"},
            {"name": "ai_model", "value": "gpt-4.1-mini"},
            {"name": "ai_alert_recipients", "value": "a@example.com, b@example.com"},
            {"name": "ai_alert_subject_template", "value": "Custom [{time}]"},
            {"name": "ai_alert_from_name", "value": "Custom Bot"},
        ]
    )

    settings = app_main.get_ai_alert_settings(db)

    assert settings["prompt"] == "Custom prompt"
    assert settings["model"] == "gpt-4.1-mini"
    assert settings["recipients"] == ["a@example.com", "b@example.com"]
    assert settings["subject_template"] == "Custom [{time}]"
    assert settings["from_name"] == "Custom Bot"


def test_recipients_accepts_list_value(monkeypatch):
    monkeypatch.delenv("EMAIL_TO", raising=False)
    db = FakeMongo(
        [
            {
                "name": "ai_alert_recipients",
                "value": ["ops@example.com", " it@example.com "],
            }
        ]
    )

    settings = app_main.get_ai_alert_settings(db)

    assert settings["recipients"] == ["ops@example.com", "it@example.com"]


def test_recipients_fall_back_to_email_to_env_when_unset(monkeypatch):
    monkeypatch.setenv("EMAIL_TO", "legacy@example.com")
    db = FakeMongo()

    settings = app_main.get_ai_alert_settings(db)

    assert settings["recipients"] == ["legacy@example.com"]


def test_saved_empty_recipients_do_not_fall_back_to_env(monkeypatch):
    monkeypatch.setenv("EMAIL_TO", "legacy@example.com")
    db = FakeMongo([{"name": "ai_alert_recipients", "value": "ops@example.com"}])

    settings = app_main.get_ai_alert_settings(db)

    assert settings["recipients"] == ["ops@example.com"]


def test_blank_saved_string_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.delenv("EMAIL_TO", raising=False)
    db = FakeMongo(
        [
            {"name": "ai_prompt", "value": ""},
            {"name": "ai_model", "value": ""},
        ]
    )

    settings = app_main.get_ai_alert_settings(db)

    assert settings["prompt"] == app_main.DEFAULT_AI_PROMPT
    assert settings["model"] == app_main.DEFAULT_AI_MODEL
