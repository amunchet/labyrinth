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

from ai import session_store

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


def configure_session(
    session_id,
    *,
    prompt="",
    skill_ids=None,
    target_hosts=None,
    title="",
    max_iterations=8,
):
    """Mark a Redis session durable and persist non-secret session metadata."""
    rc = _client()
    rc.hset(_session_key(session_id), "durable", "1")
    rc.hset(_session_key(session_id), "prompt", prompt)
    rc.hset(_session_key(session_id), "skill_ids", json.dumps(list(skill_ids or [])))
    rc.hset(_session_key(session_id), "target_hosts", json.dumps(list(target_hosts or [])))
    rc.hset(_session_key(session_id), "title", title)
    rc.hset(_session_key(session_id), "max_iterations", str(max_iterations))
    session = get_session(session_id)
    if not session:
        raise ValueError("Chat session not found or expired")
    now = float(session.get("created_at") or time.time())
    record = {
        "provider": session.get("provider", ""),
        "created_at": now,
        "updated_at": time.time(),
        "prompt": prompt,
        "skills": list(skill_ids or []),
        "target_hosts": list(target_hosts or []),
        "title": title,
        "max_iterations": max_iterations,
        "status": "active",
        "message_count": 0,
        "messages": [],
    }
    session_store.save(session_id, record)
    return record


def _sync_durable(session_id, fields=None):
    """Refresh the durable record without ever copying session credentials."""
    try:
        session = get_session(session_id)
        if not session or session.get("durable") != "1":
            return
        record = session_store.get(session_id) or {}
        history = get_history(session_id)
        record.update(fields or {})
        record.update(
            {
                "provider": session.get("provider", ""),
                "updated_at": time.time(),
                "message_count": len(history),
                "messages": history,
            }
        )
        session_store.save(session_id, record)
    except Exception:
        # Active turns must remain usable if the management database is down;
        # Redis still retains the short-lived session and turn state.
        return


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
    durable_fields = {}
    if message.get("role") == "user":
        record = session_store.get(session_id) or {}
        if not record.get("title"):
            durable_fields["title"] = message.get("content", "")[:80]
    _sync_durable(session_id, durable_fields)


def replace_history(session_id, history):
    """Overwrites the session's message history (used to persist a repair)."""
    rc = _client()
    rc.set(_messages_key(session_id), json.dumps(history))
    rc.expire(_messages_key(session_id), SESSION_TTL_SECONDS)
    _sync_durable(session_id)


def set_draft(session_id, draft):
    """Stores (overwriting) the session's current unapproved draft playbook."""
    rc = _client()
    rc.set(_draft_key(session_id), json.dumps(draft))
    rc.expire(_draft_key(session_id), SESSION_TTL_SECONDS)
    _sync_durable(session_id, {"draft": draft, "status": "draft_ready"})


def get_draft(session_id):
    """Returns the session's current draft playbook dict, or None."""
    rc = _client()
    raw = rc.get(_draft_key(session_id))
    if not raw:
        try:
            return (session_store.get(session_id) or {}).get("draft")
        except Exception:
            return None
    return json.loads(_decode(raw))


def clear_draft(session_id):
    """Clears the session's draft (on discard, or once approved/deployed)."""
    rc = _client()
    rc.delete(_draft_key(session_id))
    _sync_durable(session_id, {"draft": None, "status": "active"})


def discard_session(session_id):
    """Deletes a session's config, history, draft, and turn state entirely."""
    rc = _client()
    rc.delete(_session_key(session_id))
    rc.delete(_messages_key(session_id))
    rc.delete(_draft_key(session_id))
    rc.delete(_turn_key(session_id))
    try:
        session_store.delete(session_id)
    except Exception:
        # Redis-backed sessions remain deletable when the management database
        # is temporarily unavailable.
        pass


def set_deployment(session_id, job_id, target_hosts):
    """Record a human-approved deployment without storing its credentials."""
    fields = {
        "deployment_job_id": job_id,
        "deployment_hosts": list(target_hosts),
        "deployment_status": "queued",
        "status": "deploying",
    }
    _sync_durable(session_id, fields)


def update_deployment(session_id, status, error="", logs=None, results=None):
    """Update deployment state even if the Redis session has expired."""
    fields = {"deployment_status": status, "status": status}
    if error:
        fields["deployment_error"] = error
    if logs is not None:
        fields["deployment_logs"] = list(logs)
    if results is not None:
        fields["deployment_results"] = results
    try:
        record = session_store.get(session_id)
        if record:
            record.update(fields)
            record["updated_at"] = time.time()
            session_store.save(session_id, record)
    except Exception:
        pass
    _sync_durable(session_id, fields)


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
    # Durable records are the source of truth once Redis expires. Merge them
    # when available, but keep the Redis-only behavior for legacy/test sessions.
    try:
        durable = {item.get("session_id"): item for item in session_store.list_sessions()}
        for item in sessions:
            if item["session_id"] in durable:
                durable[item["session_id"]].update(item)
        sessions = list(durable.values()) or sessions
    except Exception:
        pass
    sessions.sort(key=lambda s: float(s.get("updated_at") or 0), reverse=True)
    # Session listings are summaries, never conversation contents or secrets.
    for item in sessions:
        item.pop("messages", None)
        item.pop("vault_password", None)
        item.pop("become_file", None)
        item.pop("ssh_key", None)
    return sessions


def get_durable_session(session_id):
    """Return durable metadata, falling back to the active Redis session."""
    try:
        active = get_session(session_id)
    except Exception:
        active = None
    if active and active.get("durable") != "1":
        return active
    try:
        record = session_store.get(session_id)
    except Exception:
        record = None
    if record:
        if active:
            record.update(
                {
                    key: active[key]
                    for key in ("provider", "become_file", "ssh_key", "vault_password")
                    if key in active
                }
            )
        return record
    return active


def get_durable_history(session_id):
    """Return retained history even after the Redis session has expired."""
    try:
        active = get_session(session_id)
    except Exception:
        active = None
    if active:
        return get_history(session_id)
    try:
        record = session_store.get(session_id)
    except Exception:
        record = None
    if record and record.get("messages") is not None:
        return record.get("messages") or []
    return get_history(session_id)


def get_durable_draft(session_id):
    """Return an unapproved draft from Redis or its durable session record."""
    try:
        draft = get_draft(session_id)
    except Exception:
        draft = None
    if draft is not None:
        return draft
    try:
        return (session_store.get(session_id) or {}).get("draft")
    except Exception:
        return None


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
    _sync_durable(session_id, {"turn_status": "queued", "turn_id": turn_id})

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
    durable_fields = {}
    if "status" in fields:
        durable_fields["turn_status"] = fields["status"]
    if "step" in fields:
        durable_fields["turn_step"] = fields["step"]
    if "error" in fields:
        durable_fields["turn_error"] = fields["error"]
    if "reply" in fields:
        durable_fields["last_reply"] = fields["reply"]
    if durable_fields:
        _sync_durable(session_id, durable_fields)


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
