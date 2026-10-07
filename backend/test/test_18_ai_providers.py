#!/usr/bin/env python3
"""
Tests for the LLM provider abstraction (backend/ai/providers/).
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from ai.providers.base import ChatMessage, ToolCall, ToolDef
from ai.providers import factory


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


def test_openai_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_KEY", raising=False)
    from ai.providers.openai_provider import OpenAIProvider

    with pytest.raises(ValueError):
        OpenAIProvider(api_key=None)


@patch("ai.providers.openai_provider.requests.post")
def test_openai_provider_text_reply(mock_post):
    from ai.providers.openai_provider import OpenAIProvider

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "Hello there"},
                "finish_reason": "stop",
            }
        ]
    }
    mock_post.return_value = mock_response

    provider = OpenAIProvider(api_key="key", model="gpt-5-mini")
    result = provider.chat(
        [ChatMessage(role="user", content="hi")], [], "system prompt"
    )

    assert result.text == "Hello there"
    assert result.tool_calls == []
    assert result.stop_reason == "end_turn"
    mock_response.raise_for_status.assert_called_once()


@patch("ai.providers.openai_provider.requests.post")
def test_openai_provider_tool_call(mock_post):
    from ai.providers.openai_provider import OpenAIProvider

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "list_hosts",
                                "arguments": "{}",
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }
    mock_post.return_value = mock_response

    provider = OpenAIProvider(api_key="key")
    tools = [
        ToolDef(name="list_hosts", description="d", input_schema={"type": "object"})
    ]
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="call_1", name="list_hosts", input={})],
        ),
        ChatMessage(
            role="tool", content="{}", tool_call_id="call_1", tool_name="list_hosts"
        ),
    ]
    result = provider.chat(messages, tools, "system")

    assert result.stop_reason == "tool_use"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "list_hosts"

    # Verify the wire request actually included the tool + tool result messages
    sent = mock_post.call_args.kwargs["json"]
    assert sent["tools"][0]["function"]["name"] == "list_hosts"
    roles = [m["role"] for m in sent["messages"]]
    assert "tool" in roles


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class _FakeBlock:
    def __init__(self, type_, **kwargs):
        self.type = type_
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_anthropic_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from ai.providers.anthropic_provider import AnthropicProvider

    with pytest.raises(ValueError):
        AnthropicProvider(api_key=None)


@patch("ai.providers.anthropic_provider.anthropic.Anthropic")
def test_anthropic_provider_text_reply(mock_anthropic_cls):
    from ai.providers.anthropic_provider import AnthropicProvider

    fake_response = MagicMock()
    fake_response.content = [_FakeBlock("text", text="Hello from Claude")]
    fake_response.stop_reason = "end_turn"

    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_response
    mock_anthropic_cls.return_value = mock_client

    provider = AnthropicProvider(api_key="key", model="claude-sonnet-5")
    result = provider.chat([ChatMessage(role="user", content="hi")], [], "system")

    assert result.text == "Hello from Claude"
    assert result.tool_calls == []
    assert result.stop_reason == "end_turn"


@patch("ai.providers.anthropic_provider.anthropic.Anthropic")
def test_anthropic_provider_tool_use(mock_anthropic_cls):
    from ai.providers.anthropic_provider import AnthropicProvider

    fake_response = MagicMock()
    fake_response.content = [
        _FakeBlock("text", text="Let me check."),
        _FakeBlock("tool_use", id="toolu_1", name="list_hosts", input={}),
    ]
    fake_response.stop_reason = "tool_use"

    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_response
    mock_anthropic_cls.return_value = mock_client

    provider = AnthropicProvider(api_key="key")
    tools = [
        ToolDef(name="list_hosts", description="d", input_schema={"type": "object"})
    ]
    messages = [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="toolu_1", name="list_hosts", input={})],
        ),
        ChatMessage(
            role="tool", content="{}", tool_call_id="toolu_1", tool_name="list_hosts"
        ),
    ]
    result = provider.chat(messages, tools, "system")

    assert result.stop_reason == "tool_use"
    assert result.tool_calls[0].name == "list_hosts"

    sent_kwargs = mock_client.messages.create.call_args.kwargs
    assert sent_kwargs["tools"][0]["name"] == "list_hosts"
    tool_result_msgs = [
        m
        for m in sent_kwargs["messages"]
        if m["role"] == "user" and isinstance(m["content"], list)
    ]
    assert any(
        block.get("type") == "tool_result"
        for m in tool_result_msgs
        for block in m["content"]
    )


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


@patch("ai.providers.ollama_provider.requests.post")
def test_ollama_provider_text_reply(mock_post):
    from ai.providers.ollama_provider import OllamaProvider

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"role": "assistant", "content": "Hi from Ollama"}
    }
    mock_post.return_value = mock_response

    provider = OllamaProvider(host="http://localhost:11434", model="llama3.1")
    result = provider.chat([ChatMessage(role="user", content="hi")], [], "system")

    assert result.text == "Hi from Ollama"
    assert result.stop_reason == "end_turn"


@patch("ai.providers.ollama_provider.requests.post")
def test_ollama_provider_tool_call(mock_post):
    from ai.providers.ollama_provider import OllamaProvider

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "list_hosts", "arguments": {}}},
            ],
        }
    }
    mock_post.return_value = mock_response

    provider = OllamaProvider(host="http://localhost:11434")
    tools = [
        ToolDef(name="list_hosts", description="d", input_schema={"type": "object"})
    ]
    result = provider.chat([ChatMessage(role="user", content="hi")], tools, "system")

    assert result.stop_reason == "tool_use"
    assert result.tool_calls[0].name == "list_hosts"
    assert result.tool_calls[0].id == "call_0"


@patch("ai.providers.ollama_provider.requests.post")
def test_ollama_provider_tool_call_string_arguments(mock_post):
    """Some Ollama versions send arguments as a JSON string rather than a dict."""
    from ai.providers.ollama_provider import OllamaProvider

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "get_host",
                        "arguments": json.dumps({"host_key": "abc"}),
                    }
                }
            ],
        }
    }
    mock_post.return_value = mock_response

    provider = OllamaProvider()
    result = provider.chat([], [], "system")

    assert result.tool_calls[0].input == {"host_key": "abc"}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_factory_list_available_providers(monkeypatch):
    monkeypatch.setenv("OPENAI_KEY", "x")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    assert factory.list_available_providers() == ["openai"]

    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    assert factory.list_available_providers() == ["openai", "anthropic", "ollama"]


def test_factory_get_provider_unknown_raises():
    with pytest.raises(ValueError):
        factory.get_provider("does-not-exist")


def test_factory_get_provider_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_KEY", "x")
    from ai.providers.openai_provider import OpenAIProvider

    provider = factory.get_provider("openai")
    assert isinstance(provider, OpenAIProvider)


def test_factory_get_provider_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "y")
    from ai.providers.anthropic_provider import AnthropicProvider

    provider = factory.get_provider("anthropic")
    assert isinstance(provider, AnthropicProvider)


def test_factory_get_provider_ollama(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    from ai.providers.ollama_provider import OllamaProvider

    provider = factory.get_provider("ollama")
    assert isinstance(provider, OllamaProvider)
