#!/usr/bin/env python3
"""
Tests for ai/chat_store.py - Redis-backed session/history/draft persistence
for the AI chat feature.
"""
from unittest.mock import patch

from ai import chat_store


class FakeRedis:
    def __init__(self):
        self.h = {}
        self.s = {}
        self.ttls = {}

    def _norm(self, name):
        return name.encode() if isinstance(name, str) else name

    def hset(self, name, key, value):
        name = self._norm(name)
        key = self._norm(key)
        value = value if isinstance(value, (bytes, bytearray)) else str(value).encode()
        self.h.setdefault(name, {})
        self.h[name][key] = value

    def hgetall(self, name):
        name = self._norm(name)
        return dict(self.h.get(name, {}))

    def hget(self, name, key):
        name = self._norm(name)
        key = self._norm(key)
        return self.h.get(name, {}).get(key)

    def set(self, name, value):
        name = self._norm(name)
        value = value if isinstance(value, (bytes, bytearray)) else str(value).encode()
        self.s[name] = value

    def get(self, name):
        name = self._norm(name)
        return self.s.get(name)

    def expire(self, name, ttl):
        self.ttls[self._norm(name)] = ttl

    def delete(self, *names):
        for name in names:
            name = self._norm(name)
            self.h.pop(name, None)
            self.s.pop(name, None)


@patch("ai.chat_store.redis.Redis")
def test_create_and_get_session(mock_redis_cls):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session(
        "openai", "vault", ssh_key="key1", vault_password="secret"
    )
    assert session_id

    session = chat_store.get_session(session_id)
    assert session["provider"] == "openai"
    assert session["become_file"] == "vault"
    assert session["ssh_key"] == "key1"
    assert session["vault_password"] == "secret"

    # New session starts with empty history
    assert chat_store.get_history(session_id) == []


@patch("ai.chat_store.redis.Redis")
def test_get_session_missing_returns_none(mock_redis_cls):
    mock_redis_cls.return_value = FakeRedis()
    assert chat_store.get_session("does-not-exist") is None


@patch("ai.chat_store.redis.Redis")
def test_append_and_get_history_round_trips(mock_redis_cls):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    chat_store.append_message(session_id, {"role": "user", "content": "hi"})
    chat_store.append_message(
        session_id, {"role": "assistant", "content": "hello", "tool_calls": []}
    )

    history = chat_store.get_history(session_id)
    assert len(history) == 2
    assert history[0]["content"] == "hi"
    assert history[1]["role"] == "assistant"


@patch("ai.chat_store.redis.Redis")
def test_draft_set_get_clear(mock_redis_cls):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    assert chat_store.get_draft(session_id) is None

    draft = {"yaml": "---\n", "filename": "fix", "description": "d"}
    chat_store.set_draft(session_id, draft)
    assert chat_store.get_draft(session_id) == draft

    chat_store.clear_draft(session_id)
    assert chat_store.get_draft(session_id) is None


@patch("ai.chat_store.redis.Redis")
def test_discard_session_removes_everything(mock_redis_cls):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    chat_store.append_message(session_id, {"role": "user", "content": "hi"})
    chat_store.set_draft(
        session_id, {"yaml": "---\n", "filename": "f", "description": "d"}
    )

    chat_store.discard_session(session_id)

    assert chat_store.get_session(session_id) is None
    assert chat_store.get_history(session_id) == []
    assert chat_store.get_draft(session_id) is None
