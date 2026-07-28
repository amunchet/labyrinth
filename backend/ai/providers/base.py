"""
Neutral chat/tool-calling contract shared by every LLM provider adapter.

Each adapter translates between this shape and its own wire format so that
callers (the agentic loop) never need to branch on provider name.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class ChatMessage:
    role: Literal["user", "assistant", "tool"]
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None


@dataclass
class ChatResult:
    text: str
    tool_calls: List[ToolCall]
    stop_reason: Literal["end_turn", "tool_use"]
    raw: Any = None


class LLMProvider(ABC):
    """Common interface every provider adapter implements."""

    @abstractmethod
    def chat(
        self, messages: List[ChatMessage], tools: List[ToolDef], system: str
    ) -> ChatResult:
        """Send the conversation + available tools, return a normalized result."""
        raise NotImplementedError  # pragma: no cover
