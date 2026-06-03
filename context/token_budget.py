"""
Token budgeting helpers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

_tiktoken_enc = None
_tiktoken_available = False


def _init_tiktoken() -> None:
    global _tiktoken_enc, _tiktoken_available
    if _tiktoken_available or _tiktoken_enc is not None:
        return
    try:
        import tiktoken

        _tiktoken_enc = tiktoken.get_encoding("cl100k_base")
        _tiktoken_available = True
    except Exception:
        _tiktoken_available = False


def estimate_tokens(text: str) -> int:
    if not _tiktoken_available:
        _init_tiktoken()

    if _tiktoken_available and _tiktoken_enc is not None:
        try:
            return max(1, len(_tiktoken_enc.encode(text)))
        except Exception:
            pass

    return max(1, len(text) // 4)


def estimate_chars(tokens: int) -> int:
    return tokens * 4


def _message_token_cost(message: dict) -> int:
    return estimate_tokens(json.dumps(message, ensure_ascii=False, sort_keys=True))


def _message_chunk_cost(messages: list[dict]) -> int:
    return sum(_message_token_cost(message) for message in messages)


def _group_history_messages(messages: list[dict]) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        tool_call = message.get("tool_call")
        if tool_call:
            call_id = tool_call.get("call_id")
            if (
                index + 1 < len(messages)
                and messages[index + 1].get("role") == "tool"
                and call_id
                and messages[index + 1].get("tool_call_id") == call_id
            ):
                chunks.append([message, messages[index + 1]])
                index += 2
                continue
        chunks.append([message])
        index += 1
    return chunks


def _sanitize_history_messages(messages: list[dict]) -> list[dict]:
    """Drop orphan tool messages so trimming cannot preserve invalid pairs."""
    sanitized: list[dict] = []
    valid_tool_call_ids: set[str] = set()

    for message in messages:
        tool_call = message.get("tool_call")
        if tool_call:
            call_id = tool_call.get("call_id")
            if call_id:
                valid_tool_call_ids.add(call_id)
            sanitized.append(message)
            continue

        if message.get("role") == "tool":
            tool_call_id = message.get("tool_call_id")
            if tool_call_id and tool_call_id in valid_tool_call_ids:
                sanitized.append(message)
            continue

        sanitized.append(message)

    return sanitized


def is_tiktoken_available() -> bool:
    _init_tiktoken()
    return _tiktoken_available


@dataclass
class BudgetPlan:
    total: int
    system_core: int
    repo_map: int
    history: int
    observation: int
    reserve: int

    @property
    def available(self) -> int:
        return self.total - self.reserve


class TokenBudget:
    def __init__(self, total: int = 80_000) -> None:
        self._total = total

    def default_plan(self) -> BudgetPlan:
        total = self._total
        reserve = int(total * 0.15)
        available = total - reserve
        return BudgetPlan(
            total=total,
            reserve=reserve,
            system_core=int(available * 0.10),
            repo_map=int(available * 0.15),
            history=int(available * 0.50),
            observation=int(available * 0.25),
        )

    def trim_to(self, text: str, token_limit: int) -> str:
        if estimate_tokens(text) <= token_limit:
            return text

        char_limit = token_limit * 4
        candidate = text[:char_limit]
        while estimate_tokens(candidate) > token_limit and len(candidate) > 0:
            candidate = candidate[: int(len(candidate) * 0.9)]
        omitted = estimate_tokens(text[len(candidate) :])
        return candidate + f"\n... [{omitted} tokens truncated]"

    def trim_history(
        self,
        messages: list[dict],
        token_limit: int,
    ) -> list[dict]:
        if not messages:
            return messages

        messages = _sanitize_history_messages(messages)

        token_counts = [_message_token_cost(message) for message in messages]
        total = sum(token_counts)
        if total <= token_limit:
            return messages

        result = [messages[0]]
        remaining_budget = token_limit - token_counts[0]
        if remaining_budget <= 0:
            return result

        dropped = 0
        selected_chunks: list[list[dict]] = []
        budget_left = remaining_budget

        for chunk in reversed(_group_history_messages(messages[1:])):
            chunk_cost = _message_chunk_cost(chunk)
            if budget_left - chunk_cost >= 0:
                selected_chunks.append(chunk)
                budget_left -= chunk_cost
            else:
                dropped += len(chunk)

        selected_chunks.reverse()

        if dropped > 0:
            result.append({
                "role": "user",
                "content": f"[{dropped} earlier messages were truncated to fit context window]",
            })

        for chunk in selected_chunks:
            result.extend(chunk)
        return result

    def fit_all(
        self,
        system_text: str,
        repo_map_text: str,
        history: list[dict],
        observation_text: str,
    ) -> tuple[str, str, list[dict], str]:
        plan = self.default_plan()
        trimmed_system = self.trim_to(system_text, plan.system_core)
        trimmed_map = self.trim_to(repo_map_text, plan.repo_map)
        trimmed_history = self.trim_history(history, plan.history)
        trimmed_obs = self.trim_to(observation_text, plan.observation)
        return trimmed_system, trimmed_map, trimmed_history, trimmed_obs

    def usage_report(
        self,
        system_text: str,
        repo_map_text: str,
        history: list[dict],
        observation_text: str,
    ) -> dict[str, int]:
        history_tokens = sum(_message_token_cost(message) for message in history)
        return {
            "system": estimate_tokens(system_text),
            "repo_map": estimate_tokens(repo_map_text),
            "history": history_tokens,
            "observation": estimate_tokens(observation_text),
            "total": (
                estimate_tokens(system_text)
                + estimate_tokens(repo_map_text)
                + history_tokens
                + estimate_tokens(observation_text)
            ),
            "budget": self._total,
            "tiktoken_used": is_tiktoken_available(),
        }
