"""
Sliding-window conversation history management.
"""

from __future__ import annotations

from agent.task import ToolCall
from llm.base import LLMMessage


class ConversationHistory:
    """
    Manage conversation history with a capped message window.
    """

    def __init__(self, max_messages: int = 40) -> None:
        self._messages: list[LLMMessage] = []
        self._max = max_messages

    def add(self, message: LLMMessage) -> None:
        self._messages.append(message)
        self._trim()

    def add_many(self, messages: list[LLMMessage]) -> None:
        self._messages.extend(messages)
        self._trim()

    def to_list(self) -> list[LLMMessage]:
        return list(self._messages)

    def to_dicts(self) -> list[dict]:
        return [message.to_dict() for message in self._messages]

    @classmethod
    def from_dicts(cls, dicts: list[dict], max_messages: int = 40) -> "ConversationHistory":
        history = cls(max_messages=max_messages)
        for data in dicts:
            raw_tool_call = data.get("tool_call")
            tool_call = None
            if raw_tool_call:
                tool_call = ToolCall(
                    name=raw_tool_call["name"],
                    params=raw_tool_call["params"],
                    call_id=raw_tool_call.get("call_id"),
                )
            history._messages.append(
                LLMMessage(
                    role=data["role"],
                    content=data["content"],
                    tool_call_id=data.get("tool_call_id"),
                    tool_name=data.get("tool_name"),
                    tool_call=tool_call,
                )
            )
        return history

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def last_message(self) -> LLMMessage | None:
        return self._messages[-1] if self._messages else None

    def clear_except_first(self) -> None:
        if self._messages:
            self._messages = [self._messages[0]]

    def _trim(self) -> None:
        while len(self._messages) > self._max:
            if len(self._messages) <= 1:
                break
            self._drop_oldest_non_root_message()

    def _drop_oldest_non_root_message(self) -> None:
        """Drop the oldest non-root message while preserving tool-call pairs."""
        dropped = self._messages.pop(1)

        if (
            dropped.tool_call
            and len(self._messages) > 1
            and self._messages[1].role == "tool"
            and self._messages[1].tool_call_id == dropped.tool_call.call_id
        ):
            self._messages.pop(1)

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return f"ConversationHistory(messages={len(self._messages)}, max={self._max})"
