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


@patch("ai.chat_agent.agent_tools.dispatch")
@patch("ai.chat_agent.chat_store.append_message")
@patch("ai.chat_agent.chat_store.get_history")
@patch("ai.chat_agent.chat_store.get_session")
def test_immediate_text_reply(mock_get_session, mock_get_history, mock_append, mock_dispatch):
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

    result = chat_agent.run_agent_turn("sess1", "why is disk usage high?", provider=provider)

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

    result = chat_agent.run_agent_turn("sess1", "investigate forever", provider=provider)

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
