#!/usr/bin/env python3
"""
Tests for the /ai/settings routes backing the AI Alerts settings page -
these persist prompt/model/recipients/subject/from-name overrides for the
hourly AI dashboard summary job into the generic `labyrinth.settings`
Mongo collection.
"""

import json

import pytest
import serve

from ai import ai_settings
from common.test import unwrap


def cleanup_test_data():
    serve.mongo_client["labyrinth"]["settings"].delete_many(
        {
            "name": {
                "$in": [
                    "ai_prompt",
                    "ai_model",
                    "ai_alert_recipients",
                    "ai_alert_subject_template",
                    "ai_alert_from_name",
                ]
            }
        }
    )


@pytest.fixture
def setup():
    cleanup_test_data()
    yield "Setting up..."
    cleanup_test_data()
    return "Done"


def test_get_ai_settings_defaults_when_unset(setup, monkeypatch):
    """With nothing saved yet, GET returns the built-in defaults."""
    monkeypatch.delenv("EMAIL_TO", raising=False)
    resp = unwrap(serve.get_ai_settings)()
    assert resp[1] == 200
    data = json.loads(resp[0])

    assert data["prompt"] == ai_settings.DEFAULT_AI_PROMPT
    assert data["model"] == ai_settings.DEFAULT_AI_MODEL
    assert data["subject_template"] == ai_settings.DEFAULT_AI_ALERT_SUBJECT_TEMPLATE
    assert data["from_name"] == ai_settings.DEFAULT_AI_ALERT_FROM_NAME
    assert data["recipients"] == []


def test_save_ai_settings_round_trips_all_fields(setup):
    """POST persists every field, and GET reflects the saved values."""
    payload = {
        "prompt": "Custom prompt text for triage.",
        "model": "gpt-4.1-mini",
        "recipients": "a@example.com, b@example.com",
        "subject_template": "Custom Subject [{time}]",
        "from_name": "Custom Bot",
    }

    with serve.app.test_request_context("/ai/settings", method="POST", json=payload):
        save_resp = unwrap(serve.save_ai_settings)()
    assert save_resp[1] == 200
    saved = json.loads(save_resp[0])

    assert saved["prompt"] == "Custom prompt text for triage."
    assert saved["model"] == "gpt-4.1-mini"
    assert saved["recipients"] == ["a@example.com", "b@example.com"]
    assert saved["subject_template"] == "Custom Subject [{time}]"
    assert saved["from_name"] == "Custom Bot"

    get_resp = unwrap(serve.get_ai_settings)()
    assert get_resp[1] == 200
    assert json.loads(get_resp[0]) == saved


def test_save_ai_settings_partial_update_leaves_other_fields(setup):
    """Only fields present in the POST body are changed."""
    with serve.app.test_request_context(
        "/ai/settings",
        method="POST",
        json={"model": "gpt-4.1-mini"},
    ):
        unwrap(serve.save_ai_settings)()

    with serve.app.test_request_context(
        "/ai/settings",
        method="POST",
        json={"prompt": "Only the prompt changes this time."},
    ):
        resp = unwrap(serve.save_ai_settings)()

    data = json.loads(resp[0])
    assert data["model"] == "gpt-4.1-mini"
    assert data["prompt"] == "Only the prompt changes this time."


def test_save_ai_settings_recipients_accepts_list(setup):
    """A JSON list of recipients is normalized/stored the same as a CSV string."""
    with serve.app.test_request_context(
        "/ai/settings",
        method="POST",
        json={"recipients": ["ops@example.com", "it@example.com"]},
    ):
        resp = unwrap(serve.save_ai_settings)()

    data = json.loads(resp[0])
    assert data["recipients"] == ["ops@example.com", "it@example.com"]


def test_get_ai_alert_settings_accepts_list_stored_directly_in_mongo(setup):
    """
    A recipients value stored as a raw list (e.g. legacy data, or written
    directly rather than through the /ai/settings POST route which
    normalizes to a CSV string) is still parsed correctly.
    """
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "ai_alert_recipients", "value": ["a@example.com", " b@example.com "]}
    )

    settings = ai_settings.get_ai_alert_settings(serve.mongo_client)
    assert settings["recipients"] == ["a@example.com", "b@example.com"]


def test_get_ai_settings_recipients_falls_back_to_email_to_env(setup, monkeypatch):
    """With no recipients saved, the legacy EMAIL_TO env var is used."""
    monkeypatch.setenv("EMAIL_TO", "legacy@example.com")

    resp = unwrap(serve.get_ai_settings)()
    data = json.loads(resp[0])

    assert data["recipients"] == ["legacy@example.com"]


def test_save_ai_settings_rejects_invalid_json_body(setup):
    with serve.app.test_request_context(
        "/ai/settings",
        method="POST",
        data="not json",
        content_type="text/plain",
    ):
        resp = unwrap(serve.save_ai_settings)()

    assert resp[1] == 400
    assert "error" in json.loads(resp[0])
