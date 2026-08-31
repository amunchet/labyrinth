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
    ai_chat_turn_status,
    ai_chat_turn_cancel,
    ai_chat_sessions,
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


@patch("serve.Process")
@patch("ai.chat_store.start_turn")
@patch("ai.chat_store.update_turn")
@patch("ai.chat_store.get_turn")
@patch("ai.chat_store.get_session")
def test_ai_chat_message_starts_background_turn(
    mock_get_session, mock_get_turn, mock_update_turn, mock_start_turn, mock_process
):
    """The route must return immediately, not run the turn inline - running it
    inline is what blew past gunicorn's timeout and killed the worker."""
    mock_get_session.return_value = {"provider": "openai"}
    mock_get_turn.return_value = None
    mock_process.return_value.pid = 4242

    payload = json.dumps({"message": "why is disk usage high?"})
    resp, code = unwrap(ai_chat_message)(session_id="sess1", inp_data=payload)

    assert code == 200
    assert resp["status"] == "started"
    assert resp["turn_id"]

    mock_start_turn.assert_called_once()
    mock_process.return_value.start.assert_called_once()

    # The turn runs in a separate process, not the request's.
    _, kwargs = mock_process.call_args
    assert kwargs["args"][0] == "sess1"
    assert kwargs["args"][1] == "why is disk usage high?"


def test_ai_chat_message_missing_field_returns_482():
    payload = json.dumps({})
    resp, code = unwrap(ai_chat_message)(session_id="sess1", inp_data=payload)
    assert code == 482


@patch("ai.chat_store.get_session")
def test_ai_chat_message_unknown_session_returns_404(mock_get_session):
    mock_get_session.return_value = None

    payload = json.dumps({"message": "hi"})
    resp, code = unwrap(ai_chat_message)(session_id="missing", inp_data=payload)

    assert code == 404
    assert "not found" in resp["error"]


@patch("ai.chat_store.get_turn")
@patch("ai.chat_store.get_session")
def test_ai_chat_message_rejects_concurrent_turn(mock_get_session, mock_get_turn):
    mock_get_session.return_value = {"provider": "openai"}
    mock_get_turn.return_value = {"status": "running", "turn_id": "t1"}

    payload = json.dumps({"message": "hi"})
    resp, code = unwrap(ai_chat_message)(session_id="sess1", inp_data=payload)

    assert code == 409


@patch("ai.chat_store.get_turn")
def test_ai_chat_turn_status(mock_get_turn):
    mock_get_turn.return_value = {
        "status": "completed",
        "reply": "done",
        "traceback": "secret internals",
    }

    resp, code = unwrap(ai_chat_turn_status)("sess1")

    assert code == 200
    assert resp["reply"] == "done"
    # Internal traceback must not leak to the client.
    assert "traceback" not in resp


@patch("ai.chat_store.get_turn")
def test_ai_chat_turn_status_missing_returns_404(mock_get_turn):
    mock_get_turn.return_value = None

    resp, code = unwrap(ai_chat_turn_status)("sess1")

    assert code == 404


@patch("serve.os.kill")
@patch("ai.chat_store.update_turn")
@patch("ai.chat_store.request_cancel")
@patch("ai.chat_store.get_turn")
def test_ai_chat_turn_cancel(
    mock_get_turn, mock_request_cancel, mock_update_turn, mock_kill
):
    mock_get_turn.return_value = {"status": "running", "pid": "999"}

    resp, code = unwrap(ai_chat_turn_cancel)("sess1")

    assert code == 200
    assert resp["status"] == "cancelled"
    mock_request_cancel.assert_called_once_with("sess1")
    mock_kill.assert_called_once()


@patch("serve.os.kill")
@patch("ai.chat_store.update_turn")
@patch("ai.chat_store.request_cancel")
@patch("ai.chat_store.get_turn")
def test_ai_chat_turn_cancel_survives_dead_pid(
    mock_get_turn, mock_request_cancel, mock_update_turn, mock_kill
):
    """The worker may already have exited; cancelling must still succeed."""
    mock_get_turn.return_value = {"status": "running", "pid": "999"}
    mock_kill.side_effect = ProcessLookupError()

    resp, code = unwrap(ai_chat_turn_cancel)("sess1")

    assert code == 200


@patch("ai.chat_store.get_turn")
def test_ai_chat_turn_cancel_missing_returns_404(mock_get_turn):
    mock_get_turn.return_value = None

    resp, code = unwrap(ai_chat_turn_cancel)("sess1")

    assert code == 404


@patch("ai.chat_store.list_sessions")
def test_ai_chat_sessions(mock_list_sessions):
    mock_list_sessions.return_value = [{"session_id": "s1", "provider": "openai"}]

    resp, code = unwrap(ai_chat_sessions)()

    assert code == 200
    assert json.loads(resp)[0]["session_id"] == "s1"


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
