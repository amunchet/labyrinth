import json
import os

import requests

from .base import ChatMessage, ChatResult, LLMProvider, ToolCall, ToolDef


class OllamaProvider(LLMProvider):
    """Adapter for a local/self-hosted Ollama server's OpenAI-compatible tool-calling chat API."""

    def __init__(self, host=None, model=None):
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip(
            "/"
        )
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.1")

    def _to_wire_messages(self, messages):
        wire = []
        for m in messages:
            if m.role == "tool":
                wire.append(
                    {"role": "tool", "content": m.content, "name": m.tool_name or ""}
                )
            elif m.role == "assistant" and m.tool_calls:
                wire.append(
                    {
                        "role": "assistant",
                        "content": m.content or "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": tc.name,
                                    "arguments": tc.input,
                                }
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

        data = {"model": self.model, "messages": wire_messages, "stream": False}
        if tools:
            data["tools"] = self._to_wire_tools(tools)

        response = requests.post(f"{self.host}/api/chat", json=data)
        response.raise_for_status()
        payload = response.json()

        message = payload.get("message", {})
        tool_calls = []
        for i, tc in enumerate(message.get("tool_calls") or []):
            function = tc.get("function", {})
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments or "{}")
            tool_calls.append(
                ToolCall(id=f"call_{i}", name=function.get("name"), input=arguments)
            )

        return ChatResult(
            text=message.get("content") or "",
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
            raw=payload,
        )
