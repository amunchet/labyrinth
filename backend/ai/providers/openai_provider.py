import json
import os

import requests

from .base import ChatMessage, ChatResult, LLMProvider, ToolCall, ToolDef

OPENAI_BASE_URL = "https://api.openai.com/v1/chat/completions"

# Without an explicit timeout a stalled response holds the worker forever.
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("AI_CHAT_REQUEST_TIMEOUT", "120"))


class OpenAIProvider(LLMProvider):
    """Adapter for OpenAI's chat-completions tool-calling API."""

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.environ.get("OPENAI_KEY")
        self.model = model or os.environ.get("OPENAI_CHAT_MODEL", "gpt-5-mini")
        if not self.api_key:
            raise ValueError("No OPENAI_KEY set. Please correct in .env")

    def _to_wire_messages(self, messages):
        wire = []
        for m in messages:
            if m.role == "tool":
                wire.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.tool_call_id,
                        "content": m.content,
                    }
                )
            elif m.role == "assistant" and m.tool_calls:
                wire.append(
                    {
                        "role": "assistant",
                        "content": m.content or None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.input),
                                },
                            }
                            for tc in m.tool_calls
                        ],
                    }
                )
            else:
                wire.append({"role": m.role, "content": m.content})
        return wire

    def _to_wire_tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]

    def chat(self, messages, tools, system):
        wire_messages = [{"role": "system", "content": system}]
        wire_messages.extend(self._to_wire_messages(messages))

        data = {"model": self.model, "messages": wire_messages}
        if tools:
            data["tools"] = self._to_wire_tools(tools)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        response = requests.post(
            OPENAI_BASE_URL,
            headers=headers,
            json=data,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            # Surface the API's own explanation - a bare "400 Bad Request" gives
            # nothing to debug a rejected payload with.
            raise requests.exceptions.HTTPError(
                f"OpenAI {response.status_code}: {response.text}", response=response
            ) from exc
        payload = response.json()

        message = payload["choices"][0]["message"]
        finish_reason = payload["choices"][0].get("finish_reason")

        tool_calls = []
        for tc in message.get("tool_calls") or []:
            tool_calls.append(
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    input=json.loads(tc["function"]["arguments"] or "{}"),
                )
            )

        return ChatResult(
            text=message.get("content") or "",
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
            raw=payload,
        )
