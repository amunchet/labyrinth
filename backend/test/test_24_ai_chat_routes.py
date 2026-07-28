#!/usr/bin/env python3
"""
Tests for the new /ai_chat/* routes in serve.py. These routes lazily import
ai.chat_store/ai.chat_agent/ai.providers.factory inside each route function
(to avoid a module-level circular import with serve.py), so tests patch
those target modules directly rather than attributes on `serve`.
"""
import json
from unittest.mock import patch

from common.test import unwrap
from serve import (
    ai_chat_providers,
    ai_chat_create_session,
    ai_chat_message,
    ai_chat_history,
    ai_chat_discard,
)


@patch("ai.providers.factory.list_available_providers")
def test_ai_chat_providers(mock_list):
    mock_list.return_value = ["openai", "anthropic"]

    resp, code = unwrap(ai_chat_providers)()

    assert code == 200
    assert json.loads(resp) == ["openai", "anthropic"]


@patch("ai.chat_store.create_session")
def test_ai_chat_create_session(mock_create_session):
    mock_create_session.return_value = "session-123"

    payload = json.dumps({"provider": "openai", "become_file": "vault"})
    resp, code = unwrap(ai_chat_create_session)(inp_data=payload)

    assert code == 200
    assert resp == {"session_id": "session-123"}
    mock_create_session.assert_called_once_with(
        "openai", "vault", ssh_key="", vault_password=""
    )


def test_ai_chat_create_session_missing_field_returns_482():
    payload = json.dumps({"provider": "openai"})
    resp, code = unwrap(ai_chat_create_session)(inp_data=payload)
    assert code == 482


@patch("ai.chat_agent.run_agent_turn")
def test_ai_chat_message(mock_run_turn):
    mock_run_turn.return_value = {"reply": "hi", "tool_trace": [], "draft": None}

    payload = json.dumps({"message": "why is disk usage high?"})
    resp, code = unwrap(ai_chat_message)(session_id="sess1", inp_data=payload)

    assert code == 200
    assert resp == {"reply": "hi", "tool_trace": [], "draft": None}
    mock_run_turn.assert_called_once_with("sess1", "why is disk usage high?")


def test_ai_chat_message_missing_field_returns_482():
    payload = json.dumps({})
    resp, code = unwrap(ai_chat_message)(session_id="sess1", inp_data=payload)
    assert code == 482


@patch("ai.chat_agent.run_agent_turn")
def test_ai_chat_message_unknown_session_returns_404(mock_run_turn):
    mock_run_turn.side_effect = ValueError("Chat session not found or expired")

    payload = json.dumps({"message": "hi"})
    resp, code = unwrap(ai_chat_message)(session_id="missing", inp_data=payload)

    assert code == 404
    assert "not found" in resp["error"]


@patch("ai.chat_store.get_history")
@patch("ai.chat_store.get_session")
def test_ai_chat_history(mock_get_session, mock_get_history):
    mock_get_session.return_value = {"provider": "openai"}
    mock_get_history.return_value = [{"role": "user", "content": "hi"}]

    resp, code = unwrap(ai_chat_history)("sess1")

    assert code == 200
    assert json.loads(resp) == [{"role": "user", "content": "hi"}]


@patch("ai.chat_store.get_session")
def test_ai_chat_history_missing_session_returns_404(mock_get_session):
    mock_get_session.return_value = None

    resp, code = unwrap(ai_chat_history)("missing")

    assert code == 404


@patch("ai.chat_store.discard_session")
def test_ai_chat_discard(mock_discard):
    resp, code = unwrap(ai_chat_discard)("sess1")

    assert code == 200
    assert resp == "Success"
    mock_discard.assert_called_once_with("sess1")
