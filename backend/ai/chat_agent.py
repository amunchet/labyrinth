"""
Agentic loop orchestrating a single chat turn: send the conversation + tool
definitions to the session's selected LLM provider, dispatch any tool calls,
feed results back, and repeat until the model answers in plain text or stages
a playbook draft via `propose_playbook`.
"""

import json
import traceback
import uuid

from ai import agent_tools
from ai import chat_store
from ai.ai_settings import DEFAULT_AI_CHAT_PROMPT
from ai.providers import factory
from ai.providers.base import ChatMessage, ToolCall

MAX_ITERATIONS = 8

CANCELLED_REPLY = "This turn was cancelled."

SYSTEM_PROMPT = (
    "You are a network operations assistant for Labyrinth, a network monitor/mapper. "
    "A human describes a problem (e.g. high disk usage, an unresponsive docker container). "
    "Investigate using the available tools (list_hosts, get_host, read_metrics, list_services, "
    "run_diagnostic_command) before proposing a fix - don't guess at the cause. "
    "run_diagnostic_command only supports a fixed set of safe, read-only commands; it cannot "
    "run arbitrary shell. "
    "When you have a concrete fix, call propose_playbook with a complete Ansible playbook. "
    "propose_playbook only validates and stages a draft for human review - it does NOT deploy "
    "anything. Never claim you have fixed, deployed, or changed anything until the human "
    "approves and runs the draft themselves."
)


def _system_prompt(session):
    """Build the system message without exposing deployment target hosts."""
    prompt = session.get("prompt") or DEFAULT_AI_CHAT_PROMPT
    return f"{SYSTEM_PROMPT}\n\nOperator guidance:\n{prompt}"


def _max_iterations(session):
    try:
        return max(1, min(20, int(session.get("max_iterations", MAX_ITERATIONS))))
    except (TypeError, ValueError):
        return MAX_ITERATIONS


def _to_chat_message(message):
    return ChatMessage(
        role=message["role"],
        content=message.get("content", ""),
        tool_calls=[ToolCall(**tc) for tc in message.get("tool_calls") or []],
        tool_call_id=message.get("tool_call_id"),
        tool_name=message.get("tool_name"),
    )


def _from_chat_message(message):
    return {
        "role": message.role,
        "content": message.content,
        "tool_calls": [
            {"id": tc.id, "name": tc.name, "input": tc.input}
            for tc in message.tool_calls
        ],
        "tool_call_id": message.tool_call_id,
        "tool_name": message.tool_name,
    }


def repair_history(history):
    """Closes any tool_calls that never got a matching tool result.

    A turn killed part-way through (worker timeout, container restart, cancel)
    persists the assistant message announcing its tool_calls but not the tool
    results that answer them. Both OpenAI and Anthropic reject a conversation
    containing such a dangling call, so without this every later message in
    that session fails with a 400 and the session is effectively bricked.

    Returns (repaired_history, changed).
    """
    repaired = []
    changed = False
    index = 0

    while index < len(history):
        message = history[index]
        repaired.append(message)
        index += 1

        tool_calls = message.get("tool_calls") or []
        if message.get("role") != "assistant" or not tool_calls:
            continue

        # Carry over the tool results that did land, keeping their order...
        answered = set()
        while index < len(history) and history[index].get("role") == "tool":
            answered.add(history[index].get("tool_call_id"))
            repaired.append(history[index])
            index += 1

        # ...then close out the calls that never got one.
        for tool_call in tool_calls:
            if tool_call.get("id") in answered:
                continue
            changed = True
            repaired.append(
                {
                    "role": "tool",
                    "content": json.dumps(
                        {"error": "Tool call did not complete (interrupted)."}
                    ),
                    "tool_calls": [],
                    "tool_call_id": tool_call.get("id"),
                    "tool_name": tool_call.get("name"),
                }
            )

    return repaired, changed


def _load_repaired_history(session_id):
    """Loads history, healing (and persisting) any interrupted tool calls."""
    stored = chat_store.get_history(session_id)
    if not stored:
        stored = chat_store.get_durable_history(session_id)
    repaired, changed = repair_history(stored)
    if changed:
        chat_store.replace_history(session_id, repaired)
    return repaired


def run_turn_background(session_id, user_message, turn_id):
    """Runs a turn out-of-band, recording status/result in Redis.

    Runs in a forked process so the HTTP request can return immediately: the
    agentic loop makes several sequential LLM calls and easily outlives
    gunicorn's request timeout, which used to kill the worker mid-turn.
    """
    try:
        result = run_agent_turn(session_id, user_message, turn_id=turn_id)
    except Exception as exc:  # noqa: BLE001 - surfaced to the client as status
        chat_store.update_turn(
            session_id,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )
        return

    chat_store.update_turn(
        session_id,
        status="cancelled" if result.get("cancelled") else "completed",
        reply=result["reply"],
        tool_trace=result["tool_trace"],
        draft=result["draft"],
    )


def run_agent_turn(session_id, user_message, provider=None, turn_id=None):
    """Runs one chat turn to completion. Persists the full turn to chat_store.

    :param provider: optional LLMProvider override, primarily for tests -
        normally resolved from the session's stored provider name.
    """
    session = chat_store.get_durable_session(session_id)
    if not session:
        raise ValueError("Chat session not found or expired")

    # A retained session can be viewed after Redis expiry, but it cannot start
    # a new turn without its ephemeral credential context.
    if not session.get("become_file"):
        raise ValueError("Chat session credentials expired; start a new session")

    if provider is None:
        provider = factory.get_provider(session["provider"])

    if turn_id is None:
        turn_id = str(uuid.uuid4())

    history = [_to_chat_message(m) for m in _load_repaired_history(session_id)]

    user_msg = ChatMessage(role="user", content=user_message)
    history.append(user_msg)
    chat_store.append_message(session_id, _from_chat_message(user_msg))

    tool_trace = []
    draft = None
    reply_text = ""
    cancelled = False

    chat_store.update_turn(session_id, status="running", step="0")

    for step in range(_max_iterations(session)):
        if chat_store.is_cancel_requested(session_id):
            cancelled = True
            reply_text = CANCELLED_REPLY
            break

        chat_store.update_turn(session_id, step=str(step + 1))
        result = provider.chat(
            history,
            agent_tools.tool_defs_for_session(session),
            _system_prompt(session),
        )

        assistant_msg = ChatMessage(
            role="assistant", content=result.text, tool_calls=result.tool_calls
        )
        history.append(assistant_msg)
        chat_store.append_message(session_id, _from_chat_message(assistant_msg))

        if result.stop_reason != "tool_use" or not result.tool_calls:
            reply_text = result.text
            break

        draft_staged = False
        for tool_call in result.tool_calls:
            tool_result = agent_tools.dispatch(
                session_id, tool_call.name, tool_call.input
            )
            tool_trace.append(
                {
                    "name": tool_call.name,
                    "input": tool_call.input,
                    "result": tool_result,
                }
            )

            tool_msg = ChatMessage(
                role="tool",
                content=json.dumps(tool_result, default=str),
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
            )
            history.append(tool_msg)
            chat_store.append_message(session_id, _from_chat_message(tool_msg))

            if tool_call.name == "propose_playbook" and tool_result.get("valid"):
                draft = tool_result["draft"]
                draft_staged = True

        # Publish the trace as it grows so a polling client sees progress
        # rather than a spinner until the whole turn lands.
        chat_store.update_turn(session_id, tool_trace=tool_trace)

        if draft_staged:
            reply_text = result.text or "I've drafted a playbook for you to review."
            break
    else:
        reply_text = (
            "I wasn't able to resolve this within the allotted number of steps. "
            "Please refine your request or review the tool trace so far."
        )

    return {
        "reply": reply_text,
        "tool_trace": tool_trace,
        "draft": draft,
        "cancelled": cancelled,
        "turn_id": turn_id,
    }
