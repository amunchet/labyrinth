import os

import anthropic

from .base import ChatMessage, ChatResult, LLMProvider, ToolCall, ToolDef

DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(LLMProvider):
    """Adapter for Anthropic's Messages API tool-use format."""

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("ANTHROPIC_CHAT_MODEL", "claude-sonnet-5")
        if not self.api_key:
            raise ValueError("No ANTHROPIC_API_KEY set. Please correct in .env")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def _to_wire_messages(self, messages):
        wire = []
        for m in messages:
            if m.role == "tool":
                wire.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id,
                                "content": m.content,
                            }
                        ],
                    }
                )
            elif m.role == "assistant" and m.tool_calls:
                content = []
                if m.content:
                    content.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.input,
                        }
                    )
                wire.append({"role": "assistant", "content": content})
            else:
                wire.append({"role": m.role, "content": m.content})
        return wire

    def _to_wire_tools(self, tools):
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]

    def chat(self, messages, tools, system):
        kwargs = {
            "model": self.model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "system": system,
            "messages": self._to_wire_messages(messages),
        }
        if tools:
            kwargs["tools"] = self._to_wire_tools(tools)

        response = self.client.messages.create(**kwargs)

        text_parts = []
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )

        stop_reason = "tool_use" if response.stop_reason == "tool_use" else "end_turn"

        return ChatResult(
            text="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=response,
        )
