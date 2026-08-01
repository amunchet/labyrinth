"""
Redis-backed persistence for AI chat sessions.

Mirrors the existing ephemeral job/session usage of Redis in this codebase
(ansible job status/logs, Telegraf config staging) rather than introducing a
new Mongo collection - a chat session + draft playbook is single-consumer,
ad-hoc, and naturally expires, same shape as those existing keys.
"""

import json
import os
import time
import uuid

import redis

SESSION_TTL_SECONDS = int(os.environ.get("AI_CHAT_SESSION_TTL_SECONDS", "86400"))


def _client():
    return redis.Redis(host=os.environ.get("REDIS_HOST"))


def _session_key(session_id):
    return f"ai_chat:{session_id}"


def _messages_key(session_id):
    return f"ai_chat:{session_id}:messages"


def _draft_key(session_id):
    return f"ai_chat:{session_id}:draft"


def _turn_key(session_id):
    return f"ai_chat:{session_id}:turn"


def _decode(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def create_session(provider, become_file, ssh_key="", vault_password=""):
    """Creates a new chat session, returns its session_id.

    become_file/ssh_key/vault_password are chosen once by the human at session
    start (same picker UX as the Deploy page) so the model never sees or picks
    credentials; they're reused for every diagnostic tool call in the session.
    """
    session_id = str(uuid.uuid4())
    rc = _client()
    now = str(time.time())

    session_key = _session_key(session_id)
    rc.hset(session_key, "provider", provider)
    rc.hset(session_key, "become_file", become_file)
    rc.hset(session_key, "ssh_key", ssh_key)
    rc.hset(session_key, "vault_password", vault_password)
    rc.hset(session_key, "created_at", now)
    rc.hset(session_key, "updated_at", now)
    rc.expire(session_key, SESSION_TTL_SECONDS)

    rc.set(_messages_key(session_id), json.dumps([]))
    rc.expire(_messages_key(session_id), SESSION_TTL_SECONDS)

    return session_id


def get_session(session_id):
    """Returns the session's config hash, or None if it doesn't exist/expired."""
    rc = _client()
    data = rc.hgetall(_session_key(session_id))
    if not data:
        return None
    return {_decode(k): _decode(v) for k, v in data.items()}


def get_history(session_id, _rc=None):
    """Returns the session's message history as a list of plain dicts."""
    rc = _rc or _client()
    raw = rc.get(_messages_key(session_id))
    if not raw:
        return []
    return json.loads(_decode(raw))


def append_message(session_id, message):
    """Appends a plain-dict message to the session's history."""
    rc = _client()
    history = get_history(session_id, _rc=rc)
    history.append(message)

    rc.set(_messages_key(session_id), json.dumps(history))
    rc.expire(_messages_key(session_id), SESSION_TTL_SECONDS)

    session_key = _session_key(session_id)
    rc.hset(session_key, "updated_at", str(time.time()))
    rc.expire(session_key, SESSION_TTL_SECONDS)


def replace_history(session_id, history):
    """Overwrites the session's message history (used to persist a repair)."""
    rc = _client()
    rc.set(_messages_key(session_id), json.dumps(history))
    rc.expire(_messages_key(session_id), SESSION_TTL_SECONDS)


def set_draft(session_id, draft):
    """Stores (overwriting) the session's current unapproved draft playbook."""
    rc = _client()
    rc.set(_draft_key(session_id), json.dumps(draft))
    rc.expire(_draft_key(session_id), SESSION_TTL_SECONDS)


def get_draft(session_id):
    """Returns the session's current draft playbook dict, or None."""
    rc = _client()
    raw = rc.get(_draft_key(session_id))
    if not raw:
        return None
    return json.loads(_decode(raw))


def clear_draft(session_id):
    """Clears the session's draft (on discard, or once approved/deployed)."""
    rc = _client()
    rc.delete(_draft_key(session_id))


def discard_session(session_id):
    """Deletes a session's config, history, draft, and turn state entirely."""
    rc = _client()
    rc.delete(_session_key(session_id))
    rc.delete(_messages_key(session_id))
    rc.delete(_draft_key(session_id))
    rc.delete(_turn_key(session_id))


def list_sessions():
    """Returns a summary of every live chat session, newest activity first.

    Lets a second client (or the same browser after a reload) discover and
    resume a session it doesn't hold the id for - the whole point of keeping
    turn state server-side rather than in the page.
    """
    rc = _client()
    sessions = []
    for key in rc.scan_iter(match="ai_chat:*"):
        key = _decode(key)
        # Only the bare session hash; skip the :messages/:draft/:turn children.
        if key.count(":") != 1:
            continue
        session_id = key.split(":", 1)[1]
        data = get_session(session_id)
        if not data:
            continue
        turn = get_turn(session_id, _rc=rc)
        sessions.append(
            {
                "session_id": session_id,
                "provider": data.get("provider", ""),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": len(get_history(session_id, _rc=rc)),
                "turn_status": (turn or {}).get("status", ""),
            }
        )
    sessions.sort(key=lambda s: float(s.get("updated_at") or 0), reverse=True)
    return sessions


# Turn state: one in-flight agent turn per session. Kept in Redis (not in the
# request) so a turn survives the page being closed, can be polled by any
# client, and can be cancelled.

_JSON_TURN_FIELDS = ("tool_trace", "draft")


def start_turn(session_id, turn_id, user_message):
    """Marks a turn as queued. Returns the turn dict."""
    rc = _client()
    now = str(time.time())
    turn_key = _turn_key(session_id)

    rc.delete(turn_key)
    rc.hset(turn_key, "turn_id", turn_id)
    rc.hset(turn_key, "status", "queued")
    rc.hset(turn_key, "message", user_message)
    rc.hset(turn_key, "created_at", now)
    rc.hset(turn_key, "updated_at", now)
    rc.expire(turn_key, SESSION_TTL_SECONDS)

    return get_turn(session_id, _rc=rc)


def update_turn(session_id, **fields):
    """Updates fields on the current turn (status, reply, tool_trace, ...)."""
    rc = _client()
    turn_key = _turn_key(session_id)
    for key, value in fields.items():
        if key in _JSON_TURN_FIELDS:
            value = json.dumps(value, default=str)
        rc.hset(turn_key, key, "" if value is None else value)
    rc.hset(turn_key, "updated_at", str(time.time()))
    rc.expire(turn_key, SESSION_TTL_SECONDS)


def get_turn(session_id, _rc=None):
    """Returns the current turn's state dict, or None if no turn has been run."""
    rc = _rc or _client()
    data = rc.hgetall(_turn_key(session_id))
    if not data:
        return None

    turn = {_decode(k): _decode(v) for k, v in data.items()}
    for field in _JSON_TURN_FIELDS:
        raw = turn.get(field)
        turn[field] = json.loads(raw) if raw else None
    return turn


def request_cancel(session_id):
    """Flags the in-flight turn for cancellation.

    The agent loop checks this between steps, so cancelling takes effect at the
    next step boundary rather than tearing down a half-finished tool call.
    """
    update_turn(session_id, cancel_requested="1")


def is_cancel_requested(session_id):
    """True if a cancel has been requested for the current turn."""
    rc = _client()
    return _decode(rc.hget(_turn_key(session_id), "cancel_requested")) == "1"
