from __future__ import annotations

from context.history import ConversationHistory
from context.token_budget import TokenBudget
from llm.base import LLMMessage
from llm.openai_compat import _sanitize_openai_message_dicts, _to_openai_messages
from agent.task import ToolCall
from config.schema import load_config


def test_to_openai_messages_preserves_valid_tool_sequence():
    messages = [
        LLMMessage(
            role="assistant",
            content="running tests",
            tool_call=ToolCall(name="shell", params={"cmd": "pytest"}, call_id="call_1"),
        ),
        LLMMessage(
            role="tool",
            content="[Tool: shell | SUCCESS]\n5 passed",
            tool_call_id="call_1",
            tool_name="shell",
        ),
    ]

    converted = _to_openai_messages(messages)

    assert converted[0]["role"] == "assistant"
    assert converted[0]["tool_calls"][0]["id"] == "call_1"
    assert converted[1]["role"] == "tool"
    assert converted[1]["tool_call_id"] == "call_1"


def test_sanitize_openai_messages_drops_orphan_tool_message():
    raw_messages = [
        {"role": "assistant", "content": "plain response"},
        {"role": "tool", "tool_call_id": "call_1", "content": "orphan tool"},
    ]

    sanitized = _sanitize_openai_message_dicts(raw_messages)

    assert sanitized == [{"role": "assistant", "content": "plain response"}]


def test_sanitize_openai_messages_keeps_multi_round_tool_sequence():
    raw_messages = [
        {
            "role": "assistant",
            "content": "step one",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "file_read", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "read ok"},
        {
            "role": "assistant",
            "content": "step two",
            "tool_calls": [
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "shell", "arguments": "{\"cmd\": \"pytest\"}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_2", "content": "pytest ok"},
    ]

    sanitized = _sanitize_openai_message_dicts(raw_messages)

    assert sanitized == raw_messages


def test_history_trim_does_not_leave_orphan_tool_messages():
    history = ConversationHistory(max_messages=3)
    history.add(LLMMessage(role="user", content="Fix the bug"))
    history.add(
        LLMMessage(
            role="assistant",
            content="inspect repo",
            tool_call=ToolCall(name="find_files", params={"pattern": "*.py"}, call_id="call_1"),
        )
    )
    history.add(
        LLMMessage(
            role="tool",
            content="[Tool: find_files | SUCCESS]\napp.py",
            tool_call_id="call_1",
            tool_name="find_files",
        )
    )
    history.add(LLMMessage(role="assistant", content="done"))

    dicts = history.to_dicts()

    assert [message["role"] for message in dicts] == ["user", "assistant"]
    assert dicts[-1]["content"] == "done"
    assert all(message.get("tool_call_id") is None for message in dicts)


def test_token_budget_trim_history_keeps_tool_pairs_together():
    messages = [
        {"role": "user", "content": "task"},
        {
            "role": "assistant",
            "content": "step one",
            "tool_call": {
                "name": "file_read",
                "params": {"path": "README.md"},
                "call_id": "call_1",
            },
        },
        {
            "role": "tool",
            "content": "[Tool: file_read | SUCCESS]\ncontent",
            "tool_call_id": "call_1",
            "tool_name": "file_read",
        },
        {"role": "assistant", "content": "final"},
    ]

    trimmed = TokenBudget(total=20).trim_history(messages, token_limit=10)

    orphan_tools = []
    seen_tool_call_ids: set[str] = set()
    for message in trimmed:
        tool_call = message.get("tool_call")
        if tool_call:
            seen_tool_call_ids.add(tool_call.get("call_id"))
        if message.get("role") == "tool" and message.get("tool_call_id") not in seen_tool_call_ids:
            orphan_tools.append(message)

    assert orphan_tools == []


def test_default_config_uses_deepseek_chat():
    config = load_config()

    assert config.llm.provider == "deepseek"
    assert config.llm.model == "deepseek-chat"
