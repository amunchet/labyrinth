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

    def scan_iter(self, match=None):
        prefix = (match or "*").rstrip("*")
        for name in list(self.h.keys()) + list(self.s.keys()):
            if name.decode().startswith(prefix):
                yield name


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


@patch("ai.chat_store.session_store.save")
@patch("ai.chat_store.redis.Redis")
def test_configure_session_persists_non_secret_metadata(mock_redis_cls, mock_save):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault", vault_password="secret")
    chat_store.configure_session(
        session_id,
        prompt="Be concise",
        skill_ids=["network_inventory"],
        target_hosts=["10.0.0.5"],
        title="Disk incident",
    )

    record = mock_save.call_args.args[1]
    assert record["target_hosts"] == ["10.0.0.5"]
    assert record["prompt"] == "Be concise"
    assert "vault_password" not in record


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


# Turn state - one in-flight agent turn per session, kept server-side so a
# closed page doesn't lose it and any client can poll or cancel it.


@patch("ai.chat_store.redis.Redis")
def test_start_and_get_turn(mock_redis_cls):
    mock_redis_cls.return_value = FakeRedis()

    session_id = chat_store.create_session("openai", "vault")
    turn = chat_store.start_turn(session_id, "turn-1", "why is disk full?")

    assert turn["turn_id"] == "turn-1"
    assert turn["status"] == "queued"
    assert turn["message"] == "why is disk full?"


@patch("ai.chat_store.redis.Redis")
def test_get_turn_missing_returns_none(mock_redis_cls):
    mock_redis_cls.return_value = FakeRedis()
    assert chat_store.get_turn("no-such-session") is None


@patch("ai.chat_store.redis.Redis")
def test_update_turn_round_trips_json_fields(mock_redis_cls):
    mock_redis_cls.return_value = FakeRedis()

    session_id = chat_store.create_session("openai", "vault")
    chat_store.start_turn(session_id, "turn-1", "hi")
    chat_store.update_turn(
        session_id,
        status="completed",
        reply="done",
        tool_trace=[{"name": "list_hosts"}],
        draft={"filename": "fix"},
    )

    turn = chat_store.get_turn(session_id)
    assert turn["status"] == "completed"
    assert turn["reply"] == "done"
    assert turn["tool_trace"] == [{"name": "list_hosts"}]
    assert turn["draft"] == {"filename": "fix"}


@patch("ai.chat_store.redis.Redis")
def test_update_turn_handles_none_draft(mock_redis_cls):
    mock_redis_cls.return_value = FakeRedis()

    session_id = chat_store.create_session("openai", "vault")
    chat_store.start_turn(session_id, "turn-1", "hi")
    chat_store.update_turn(session_id, status="completed", draft=None)

    assert chat_store.get_turn(session_id)["draft"] is None


@patch("ai.chat_store.redis.Redis")
def test_cancel_flag_round_trips(mock_redis_cls):
    mock_redis_cls.return_value = FakeRedis()

    session_id = chat_store.create_session("openai", "vault")
    chat_store.start_turn(session_id, "turn-1", "hi")
    assert chat_store.is_cancel_requested(session_id) is False

    chat_store.request_cancel(session_id)
    assert chat_store.is_cancel_requested(session_id) is True


@patch("ai.chat_store.redis.Redis")
def test_start_turn_clears_previous_cancel_flag(mock_redis_cls):
    """A stale cancel from the last turn must not abort the next one."""
    mock_redis_cls.return_value = FakeRedis()

    session_id = chat_store.create_session("openai", "vault")
    chat_store.start_turn(session_id, "turn-1", "hi")
    chat_store.request_cancel(session_id)

    chat_store.start_turn(session_id, "turn-2", "again")
    assert chat_store.is_cancel_requested(session_id) is False


@patch("ai.chat_store.redis.Redis")
def test_replace_history_overwrites(mock_redis_cls):
    mock_redis_cls.return_value = FakeRedis()

    session_id = chat_store.create_session("openai", "vault")
    chat_store.append_message(session_id, {"role": "user", "content": "hi"})
    chat_store.replace_history(session_id, [{"role": "user", "content": "repaired"}])

    assert chat_store.get_history(session_id) == [
        {"role": "user", "content": "repaired"}
    ]


@patch("ai.chat_store.redis.Redis")
def test_discard_session_clears_turn_state(mock_redis_cls):
    mock_redis_cls.return_value = FakeRedis()

    session_id = chat_store.create_session("openai", "vault")
    chat_store.start_turn(session_id, "turn-1", "hi")
    chat_store.discard_session(session_id)

    assert chat_store.get_turn(session_id) is None
    assert chat_store.get_session(session_id) is None


@patch("ai.chat_store.redis.Redis")
def test_list_sessions_summarises_live_sessions(mock_redis_cls):
    mock_redis_cls.return_value = FakeRedis()

    first = chat_store.create_session("openai", "vault")
    chat_store.append_message(first, {"role": "user", "content": "hi"})
    second = chat_store.create_session("anthropic", "vault")
    chat_store.start_turn(second, "turn-1", "working")

    sessions = chat_store.list_sessions()
    by_id = {s["session_id"]: s for s in sessions}

    # Only the bare session hashes, not their :messages/:turn children.
    assert set(by_id) == {first, second}
    assert by_id[first]["message_count"] == 1
    assert by_id[second]["provider"] == "anthropic"
    assert by_id[second]["turn_status"] == "queued"


@patch("ai.chat_store.redis.Redis")
def test_configure_session_raises_when_session_missing(mock_redis_cls):
    mock_redis_cls.return_value = FakeRedis()

    import pytest
    with pytest.raises(ValueError, match="not found"):
        chat_store.configure_session("nonexistent-id", prompt="test")


@patch("ai.chat_store.session_store.save")
@patch("ai.chat_store.session_store.get")
@patch("ai.chat_store.redis.Redis")
def test_sync_durable_updates_when_durable_flag_set(mock_redis_cls, mock_get, mock_save):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake
    mock_get.return_value = {"title": "old title"}

    session_id = chat_store.create_session("openai", "vault")
    # Set durable flag directly in fake redis
    fake.hset(chat_store._session_key(session_id), "durable", "1")

    chat_store.append_message(session_id, {"role": "user", "content": "hello"})

    assert mock_save.called


@patch("ai.chat_store.session_store.save")
@patch("ai.chat_store.session_store.get", side_effect=Exception("db down"))
@patch("ai.chat_store.redis.Redis")
def test_sync_durable_swallows_exception(mock_redis_cls, mock_get, mock_save):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    fake.hset(chat_store._session_key(session_id), "durable", "1")

    # Should not raise even if session_store.get fails
    chat_store.append_message(session_id, {"role": "user", "content": "hi"})
    assert not mock_save.called


@patch("ai.chat_store.session_store.get")
@patch("ai.chat_store.redis.Redis")
def test_get_draft_falls_back_to_session_store(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake
    mock_get.return_value = {"draft": {"yaml": "- hosts: all"}}

    session_id = chat_store.create_session("openai", "vault")
    # No draft in Redis
    result = chat_store.get_draft(session_id)
    assert result == {"yaml": "- hosts: all"}


@patch("ai.chat_store.session_store.get", side_effect=Exception("db down"))
@patch("ai.chat_store.redis.Redis")
def test_get_draft_fallback_exception_returns_none(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    result = chat_store.get_draft(session_id)
    assert result is None


@patch("ai.chat_store.session_store.delete", side_effect=Exception("db down"))
@patch("ai.chat_store.redis.Redis")
def test_discard_session_swallows_store_exception(mock_redis_cls, mock_delete):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    # Should not raise when session_store.delete fails
    chat_store.discard_session(session_id)
    assert mock_delete.called


@patch("ai.chat_store.session_store.save")
@patch("ai.chat_store.session_store.get")
@patch("ai.chat_store.redis.Redis")
def test_set_deployment_and_update_deployment(mock_redis_cls, mock_get, mock_save):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake
    mock_get.return_value = {"status": "active"}

    session_id = chat_store.create_session("openai", "vault")

    chat_store.set_deployment(session_id, "job-1", ["10.0.0.5"])

    chat_store.update_deployment(session_id, "success", logs=["ok"], results={"rc": 0})
    mock_get.return_value = {"status": "deploying", "deployment_job_id": "job-1"}

    chat_store.update_deployment(session_id, "failed", error="timeout")


@patch("ai.chat_store.session_store.get", side_effect=Exception("db down"))
@patch("ai.chat_store.redis.Redis")
def test_update_deployment_swallows_store_exception(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    # Should not raise
    chat_store.update_deployment(session_id, "success")


@patch("ai.chat_store.session_store.list_sessions")
@patch("ai.chat_store.redis.Redis")
def test_list_sessions_merges_durable_records(mock_redis_cls, mock_list):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    mock_list.return_value = [
        {"session_id": session_id, "title": "Incident", "updated_at": "9999999"}
    ]

    sessions = chat_store.list_sessions()
    by_id = {s["session_id"]: s for s in sessions}
    assert session_id in by_id
    assert by_id[session_id]["title"] == "Incident"
    # Sensitive fields should be stripped
    assert "vault_password" not in by_id[session_id]
    assert "ssh_key" not in by_id[session_id]


@patch("ai.chat_store.session_store.list_sessions", side_effect=Exception("db down"))
@patch("ai.chat_store.redis.Redis")
def test_list_sessions_falls_back_to_redis_on_exception(mock_redis_cls, mock_list):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    sessions = chat_store.list_sessions()
    assert any(s["session_id"] == session_id for s in sessions)


@patch("ai.chat_store.session_store.get")
@patch("ai.chat_store.redis.Redis")
def test_get_durable_session_non_durable_returns_active(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake
    mock_get.return_value = {"title": "durable record"}

    session_id = chat_store.create_session("openai", "vault")
    # session does not have durable flag, returns active Redis session
    result = chat_store.get_durable_session(session_id)
    assert result is not None
    assert result.get("provider") == "openai"


@patch("ai.chat_store.session_store.get")
@patch("ai.chat_store.redis.Redis")
def test_get_durable_session_returns_durable_record(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake
    mock_get.return_value = {"title": "durable record", "session_id": "sid"}

    session_id = chat_store.create_session("openai", "vault")
    fake.hset(chat_store._session_key(session_id), "durable", "1")

    result = chat_store.get_durable_session(session_id)
    assert result["title"] == "durable record"
    # Should have been merged with active session's provider
    assert result.get("provider") == "openai"


@patch("ai.chat_store.session_store.get", return_value=None)
@patch("ai.chat_store.redis.Redis")
def test_get_durable_session_falls_back_to_active_when_no_record(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    fake.hset(chat_store._session_key(session_id), "durable", "1")

    result = chat_store.get_durable_session(session_id)
    # Falls back to active Redis session
    assert result is not None


@patch("ai.chat_store.session_store.get")
@patch("ai.chat_store.redis.Redis")
def test_get_durable_history_from_expired_session(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake
    mock_get.return_value = {"messages": [{"role": "user", "content": "hi"}]}

    # No Redis session for this ID (expired), should fall back to durable
    result = chat_store.get_durable_history("nonexistent-session")
    assert result == [{"role": "user", "content": "hi"}]


@patch("ai.chat_store.session_store.get", return_value=None)
@patch("ai.chat_store.redis.Redis")
def test_get_durable_history_no_record_falls_back_to_redis(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    chat_store.append_message(session_id, {"role": "user", "content": "hello"})

    result = chat_store.get_durable_history(session_id)
    assert result == [{"role": "user", "content": "hello"}]


@patch("ai.chat_store.session_store.get", side_effect=Exception("db down"))
@patch("ai.chat_store.redis.Redis")
def test_get_durable_history_swallows_exception(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    result = chat_store.get_durable_history("nonexistent")
    assert result == []


@patch("ai.chat_store.session_store.get")
@patch("ai.chat_store.redis.Redis")
def test_get_durable_draft_from_session_store(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake
    mock_get.return_value = {"draft": {"yaml": "- hosts: all"}}

    result = chat_store.get_durable_draft("nonexistent-session")
    assert result == {"yaml": "- hosts: all"}


@patch("ai.chat_store.session_store.get", side_effect=Exception("db down"))
@patch("ai.chat_store.redis.Redis")
def test_get_durable_draft_swallows_exception(mock_redis_cls, mock_get):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    result = chat_store.get_durable_draft("nonexistent")
    assert result is None


@patch("ai.chat_store.redis.Redis")
def test_append_message_user_role_sets_title_in_durable(mock_redis_cls):
    fake = FakeRedis()
    mock_redis_cls.return_value = fake

    session_id = chat_store.create_session("openai", "vault")
    # Sets title from first user message (only if no title already set)
    with patch("ai.chat_store.session_store.get", return_value={}):
        with patch("ai.chat_store.session_store.save") as mock_save:
            fake.hset(chat_store._session_key(session_id), "durable", "1")
            chat_store.append_message(session_id, {"role": "user", "content": "Fix disk issue"})
            # _sync_durable called with title from first message
            assert mock_save.called
