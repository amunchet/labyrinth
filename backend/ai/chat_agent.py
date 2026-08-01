"""
Agentic loop orchestrating a single chat turn: send the conversation + tool
definitions to the session's selected LLM provider, dispatch any tool calls,
feed results back, and repeat until the model answers in plain text or stages
a playbook draft via `propose_playbook`.
"""

import json

from ai import agent_tools
from ai import chat_store
from ai.providers import factory
from ai.providers.base import ChatMessage, ToolCall

MAX_ITERATIONS = 8

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


def run_agent_turn(session_id, user_message, provider=None):
    """Runs one chat turn to completion. Persists the full turn to chat_store.

    :param provider: optional LLMProvider override, primarily for tests -
        normally resolved from the session's stored provider name.
    """
    session = chat_store.get_session(session_id)
    if not session:
        raise ValueError("Chat session not found or expired")

    if provider is None:
        provider = factory.get_provider(session["provider"])

    history = [_to_chat_message(m) for m in chat_store.get_history(session_id)]

    user_msg = ChatMessage(role="user", content=user_message)
    history.append(user_msg)
    chat_store.append_message(session_id, _from_chat_message(user_msg))

    tool_trace = []
    draft = None
    reply_text = ""

    for _ in range(MAX_ITERATIONS):
        result = provider.chat(history, agent_tools.TOOL_DEFS, SYSTEM_PROMPT)

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

        if draft_staged:
            reply_text = result.text or "I've drafted a playbook for you to review."
            break
    else:
        reply_text = (
            "I wasn't able to resolve this within the allotted number of steps. "
            "Please refine your request or review the tool trace so far."
        )

    return {"reply": reply_text, "tool_trace": tool_trace, "draft": draft}
