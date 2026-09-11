#!/usr/bin/env python3
"""
Tests for ai/chat_agent.py - the agentic loop that calls a scripted/fake
LLMProvider, dispatches tool calls, and stops on plain text, a staged
playbook draft, or MAX_ITERATIONS exhaustion.
"""
from unittest.mock import patch

import pytest

from ai import chat_agent
from ai.providers.base import ChatResult, ToolCall


class ScriptedProvider:
    """Returns pre-scripted ChatResults in order, one per .chat() call."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def chat(self, messages, tools, system):
        self.calls.append((list(messages), tools, system))
        return self.results.pop(0)


class RepeatingProvider:
    """Always returns the same ChatResult - used to exercise MAX_ITERATIONS."""

    def __init__(self, result):
        self.result = result
        self.call_count = 0

    def chat(self, messages, tools, system):
        self.call_count += 1
        return self.result


FAKE_SESSION = {
    "provider": "openai",
    "become_file": "vault",
    "vault_password": "secret",
    "ssh_key": "",
}


@pytest.fixture(autouse=True)
def no_redis_turn_state():
    """The loop publishes progress and checks for cancellation via Redis;
    stub both so these tests stay pure-in-memory."""
    with patch("ai.chat_agent.chat_store.update_turn"), patch(
        "ai.chat_agent.chat_store.is_cancel_requested", return_value=False
    ), patch("ai.chat_agent.chat_store.replace_history"):
        yield


@patch("ai.chat_agent.agent_tools.dispatch")
@patch("ai.chat_agent.chat_store.append_message")
@patch("ai.chat_agent.chat_store.get_history")
@patch("ai.chat_agent.chat_store.get_session")
def test_immediate_text_reply(
    mock_get_session, mock_get_history, mock_append, mock_dispatch
):
    mock_get_session.return_value = FAKE_SESSION
    mock_get_history.return_value = []

    provider = ScriptedProvider(
        [ChatResult(text="Hello there", tool_calls=[], stop_reason="end_turn")]
    )

    result = chat_agent.run_agent_turn("sess1", "hi", provider=provider)

    assert result["reply"] == "Hello there"
    assert result["tool_trace"] == []
    assert result["draft"] is None
    mock_dispatch.assert_not_called()


@patch("ai.chat_agent.agent_tools.dispatch")
@patch("ai.chat_agent.chat_store.append_message")
@patch("ai.chat_agent.chat_store.get_history")
@patch("ai.chat_agent.chat_store.get_session")
def test_one_tool_call_round_then_text(
    mock_get_session, mock_get_history, mock_append, mock_dispatch
):
    mock_get_session.return_value = FAKE_SESSION
    mock_get_history.return_value = []
    mock_dispatch.return_value = {"hosts": []}

    provider = ScriptedProvider(
        [
            ChatResult(
                text="Let me check hosts.",
                tool_calls=[ToolCall(id="1", name="list_hosts", input={})],
                stop_reason="tool_use",
            ),
            ChatResult(text="No hosts found.", tool_calls=[], stop_reason="end_turn"),
        ]
    )

    result = chat_agent.run_agent_turn(
        "sess1", "why is disk usage high?", provider=provider
    )

    assert result["reply"] == "No hosts found."
    assert len(result["tool_trace"]) == 1
    assert result["tool_trace"][0]["name"] == "list_hosts"
    assert result["draft"] is None
    mock_dispatch.assert_called_once_with("sess1", "list_hosts", {})


@patch("ai.chat_agent.agent_tools.dispatch")
@patch("ai.chat_agent.chat_store.append_message")
@patch("ai.chat_agent.chat_store.get_history")
@patch("ai.chat_agent.chat_store.get_session")
def test_tool_call_then_propose_playbook_stops_loop(
    mock_get_session, mock_get_history, mock_append, mock_dispatch
):
    mock_get_session.return_value = FAKE_SESSION
    mock_get_history.return_value = []

    draft = {"yaml": "---\n", "filename": "fix_disk", "description": "clears logs"}
    mock_dispatch.return_value = {"valid": True, "draft": draft}

    provider = ScriptedProvider(
        [
            ChatResult(
                text="Here's a fix.",
                tool_calls=[ToolCall(id="1", name="propose_playbook", input={})],
                stop_reason="tool_use",
            ),
        ]
    )

    result = chat_agent.run_agent_turn("sess1", "fix it", provider=provider)

    assert result["draft"] == draft
    assert result["reply"] == "Here's a fix."
    assert len(result["tool_trace"]) == 1
    # Loop stops immediately after staging the draft - provider.chat() called once only
    assert len(provider.calls) == 1


@patch("ai.chat_agent.agent_tools.dispatch")
@patch("ai.chat_agent.chat_store.append_message")
@patch("ai.chat_agent.chat_store.get_history")
@patch("ai.chat_agent.chat_store.get_session")
def test_max_iterations_exhaustion(
    mock_get_session, mock_get_history, mock_append, mock_dispatch
):
    mock_get_session.return_value = FAKE_SESSION
    mock_get_history.return_value = []
    mock_dispatch.return_value = {"hosts": []}

    looping_result = ChatResult(
        text="",
        tool_calls=[ToolCall(id="1", name="list_hosts", input={})],
        stop_reason="tool_use",
    )
    provider = RepeatingProvider(looping_result)

    result = chat_agent.run_agent_turn(
        "sess1", "investigate forever", provider=provider
    )

    assert result["draft"] is None
    assert "allotted number of steps" in result["reply"]
    assert provider.call_count == chat_agent.MAX_ITERATIONS
    assert len(result["tool_trace"]) == chat_agent.MAX_ITERATIONS


@patch("ai.chat_agent.chat_store.get_session")
def test_missing_session_raises(mock_get_session):
    mock_get_session.return_value = None
    with pytest.raises(ValueError):
        chat_agent.run_agent_turn("does-not-exist", "hi", provider=ScriptedProvider([]))


@patch("ai.chat_agent.agent_tools.dispatch")
@patch("ai.chat_agent.chat_store.append_message")
@patch("ai.chat_agent.chat_store.get_history")
@patch("ai.chat_agent.chat_store.get_session")
def test_prior_history_round_trips_through_chat_message(
    mock_get_session, mock_get_history, mock_append, mock_dispatch
):
    """Stored plain-dict history (including a prior tool call/result pair) is
    correctly rehydrated into ChatMessage objects for the next provider.chat() call."""
    mock_get_session.return_value = FAKE_SESSION
    mock_get_history.return_value = [
        {"role": "user", "content": "why is disk usage high?", "tool_calls": []},
        {
            "role": "assistant",
            "content": "Let me check.",
            "tool_calls": [{"id": "1", "name": "list_hosts", "input": {}}],
        },
        {
            "role": "tool",
            "content": "{}",
            "tool_calls": [],
            "tool_call_id": "1",
            "tool_name": "list_hosts",
        },
    ]

    provider = ScriptedProvider(
        [ChatResult(text="All clear.", tool_calls=[], stop_reason="end_turn")]
    )

    result = chat_agent.run_agent_turn("sess1", "anything else?", provider=provider)

    assert result["reply"] == "All clear."
    # The rehydrated history (3 prior + 1 new user message) was passed to the provider
    sent_messages = provider.calls[0][0]
    assert len(sent_messages) == 4
    assert sent_messages[1].tool_calls[0].name == "list_hosts"
    assert sent_messages[2].tool_call_id == "1"


@patch("ai.chat_agent.factory.get_provider")
@patch("ai.chat_agent.agent_tools.dispatch")
@patch("ai.chat_agent.chat_store.append_message")
@patch("ai.chat_agent.chat_store.get_history")
@patch("ai.chat_agent.chat_store.get_session")
def test_default_provider_resolved_from_session(
    mock_get_session, mock_get_history, mock_append, mock_dispatch, mock_get_provider
):
    """When no provider override is passed, the session's stored provider name
    is resolved via the factory."""
    mock_get_session.return_value = FAKE_SESSION
    mock_get_history.return_value = []
    mock_get_provider.return_value = ScriptedProvider(
        [ChatResult(text="Hi", tool_calls=[], stop_reason="end_turn")]
    )

    result = chat_agent.run_agent_turn("sess1", "hi")

    assert result["reply"] == "Hi"
    mock_get_provider.assert_called_once_with("openai")


# History repair: a turn killed mid-flight (worker timeout, restart, cancel)
# leaves an assistant message whose tool_calls were never answered. Both
# OpenAI and Anthropic reject that shape, so every later message in the
# session 400s until it's healed.


def test_repair_history_closes_dangling_tool_call():
    history = [
        {"role": "user", "content": "why is disk full?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "name": "list_hosts", "input": {}}],
        },
    ]

    repaired, changed = chat_agent.repair_history(history)

    assert changed is True
    assert repaired[-1]["role"] == "tool"
    assert repaired[-1]["tool_call_id"] == "call_1"
    assert "interrupted" in repaired[-1]["content"]


def test_repair_history_leaves_complete_history_alone():
    history = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "name": "list_hosts", "input": {}}],
        },
        {"role": "tool", "content": "[]", "tool_call_id": "call_1"},
        {"role": "assistant", "content": "done", "tool_calls": []},
    ]

    repaired, changed = chat_agent.repair_history(history)

    assert changed is False
    assert repaired == history


def test_repair_history_closes_only_the_unanswered_call():
    history = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_1", "name": "list_hosts", "input": {}},
                {"id": "call_2", "name": "get_host", "input": {}},
            ],
        },
        {"role": "tool", "content": "[]", "tool_call_id": "call_1"},
    ]

    repaired, changed = chat_agent.repair_history(history)

    assert changed is True
    tool_ids = [m["tool_call_id"] for m in repaired if m["role"] == "tool"]
    assert tool_ids == ["call_1", "call_2"]


@patch("ai.chat_agent.chat_store.replace_history")
@patch("ai.chat_agent.chat_store.get_history")
def test_load_repaired_history_persists_the_repair(mock_get_history, mock_replace):
    """Healed once and written back, so the session isn't re-broken next turn."""
    mock_get_history.return_value = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "name": "list_hosts", "input": {}}],
        }
    ]

    chat_agent._load_repaired_history("sess1")

    mock_replace.assert_called_once()


@patch("ai.chat_agent.chat_store.get_history")
@patch("ai.chat_agent.chat_store.replace_history")
def test_load_repaired_history_skips_write_when_clean(mock_replace, mock_get_history):
    mock_get_history.return_value = [{"role": "user", "content": "hi"}]

    chat_agent._load_repaired_history("sess1")

    mock_replace.assert_not_called()


@patch("ai.chat_agent.agent_tools.dispatch")
@patch("ai.chat_agent.chat_store.append_message")
@patch("ai.chat_agent.chat_store.get_history")
@patch("ai.chat_agent.chat_store.get_session")
def test_cancel_stops_the_loop(
    mock_get_session, mock_get_history, mock_append, mock_dispatch
):
    mock_get_session.return_value = FAKE_SESSION
    mock_get_history.return_value = []

    provider = RepeatingProvider(
        ChatResult(
            text="",
            tool_calls=[ToolCall(id="c1", name="list_hosts", input={})],
            stop_reason="tool_use",
        )
    )

    with patch("ai.chat_agent.chat_store.is_cancel_requested", return_value=True):
        result = chat_agent.run_agent_turn("sess1", "hi", provider=provider)

    assert result["cancelled"] is True
    assert result["reply"] == chat_agent.CANCELLED_REPLY
    assert provider.call_count == 0


@patch("ai.chat_agent.chat_store.update_turn")
@patch("ai.chat_agent.run_agent_turn")
def test_run_turn_background_records_completion(mock_run_turn, mock_update_turn):
    mock_run_turn.return_value = {
        "reply": "all good",
        "tool_trace": [],
        "draft": None,
        "cancelled": False,
    }

    chat_agent.run_turn_background("sess1", "hi", "turn1")

    _, kwargs = mock_update_turn.call_args
    assert kwargs["status"] == "completed"
    assert kwargs["reply"] == "all good"


@patch("ai.chat_agent.chat_store.update_turn")
@patch("ai.chat_agent.run_agent_turn")
def test_run_turn_background_records_error(mock_run_turn, mock_update_turn):
    """A provider failure must land as turn status, not vanish with the process."""
    mock_run_turn.side_effect = RuntimeError("OpenAI 400: bad payload")

    chat_agent.run_turn_background("sess1", "hi", "turn1")

    _, kwargs = mock_update_turn.call_args
    assert kwargs["status"] == "error"
    assert "OpenAI 400" in kwargs["error"]


@patch("ai.chat_agent.chat_store.update_turn")
@patch("ai.chat_agent.run_agent_turn")
def test_run_turn_background_records_cancellation(mock_run_turn, mock_update_turn):
    mock_run_turn.return_value = {
        "reply": chat_agent.CANCELLED_REPLY,
        "tool_trace": [],
        "draft": None,
        "cancelled": True,
    }

    chat_agent.run_turn_background("sess1", "hi", "turn1")

    _, kwargs = mock_update_turn.call_args
    assert kwargs["status"] == "cancelled"
