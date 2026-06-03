"""
OpenAI-compatible backend for OpenAI, DeepSeek, Groq, and Ollama.
"""

from __future__ import annotations

import json
import logging
import re
from types import SimpleNamespace
from typing import Any

from agent.task import Action, ActionType, ToolCall
from llm.base import LLMBackend, LLMMessage, LLMResponse, LLMToolSchema, StreamCallback

logger = logging.getLogger(__name__)

_NO_FUNCTION_CALLING: tuple[str, ...] = (
    "deepseek-reasoner",
    "deepseek-r1",
)
_THINKING_MODE_MODELS: tuple[str, ...] = (
    "deepseek-v4-flash",
    "deepseek-v4-pro",
)


class OpenAICompatBackend(LLMBackend):
    """
    Backend for OpenAI-compatible chat completion APIs.
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str | None = None,
        max_tokens: int = 4096,
    ) -> None:
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key, base_url=base_url)
        except ImportError as exc:
            raise ImportError("openai package not installed. Run: pip install openai") from exc

        self._model = model
        self._max_tokens = max_tokens
        self._use_function_calling = not any(
            model.lower().startswith(prefix) for prefix in _NO_FUNCTION_CALLING
        )
        self._thinking_mode_model = any(
            model.lower().startswith(prefix) for prefix in _THINKING_MODE_MODELS
        )
        if self._thinking_mode_model:
            logger.warning(
                "Model %s may require reasoning_content round-trip. "
                "deepseek-chat remains the default stable path.",
                model,
            )

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def supports_function_calling(self) -> bool:
        return self._use_function_calling

    def complete(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSchema],
    ) -> LLMResponse:
        if self._use_function_calling:
            api_messages = _to_openai_messages(messages)
            logger.debug(
                "OpenAI-compat request: model=%s messages=%d tools=%d fc=%s",
                self._model,
                len(api_messages),
                len(tools),
                self._use_function_calling,
            )
            return self._complete_with_tools(api_messages, tools)

        api_messages = _to_text_only_openai_messages(messages)
        logger.debug(
            "OpenAI-compat text-only request: model=%s messages=%d tools=%d fc=%s",
            self._model,
            len(api_messages),
            len(tools),
            self._use_function_calling,
        )
        return self._complete_text_only(api_messages, tools)

    def _complete_with_tools(
        self,
        api_messages: list[dict],
        tools: list[LLMToolSchema],
    ) -> LLMResponse:
        api_tools = [_to_openai_tool(tool) for tool in tools]

        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=api_messages,
            tools=api_tools,
            tool_choice="auto",
        )

        choice = response.choices[0]
        message = choice.message
        thought = message.content or "(no thought)"

        logger.debug(
            "OpenAI-compat response: finish_reason=%s input=%d output=%d",
            choice.finish_reason,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
        )

        return LLMResponse(
            action=_parse_openai_response(choice, thought),
            raw_content=thought,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

    def _complete_text_only(
        self,
        api_messages: list[dict],
        tools: list[LLMToolSchema],
    ) -> LLMResponse:
        tool_desc = _build_tool_description_for_text(tools)
        augmented = list(api_messages)
        if augmented and augmented[0]["role"] == "system":
            augmented[0] = {
                "role": "system",
                "content": augmented[0]["content"] + "\n\n" + tool_desc,
            }

        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=augmented,
        )

        choice = response.choices[0]
        raw_text = choice.message.content or ""
        return LLMResponse(
            action=_parse_text_response(raw_text),
            raw_content=raw_text,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

    def stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSchema],
        on_text: StreamCallback | None = None,
        on_thought: StreamCallback | None = None,
    ) -> LLMResponse:
        if self._use_function_calling:
            api_messages = _to_openai_messages(messages)
            return _stream_with_tools(self, api_messages, tools, on_text, on_thought)

        api_messages = _to_text_only_openai_messages(messages)
        return _stream_text_only(self, api_messages, tools, on_text)


def _sanitize_llm_messages(messages: list[LLMMessage]) -> list[LLMMessage]:
    """Drop orphan tool messages before provider-specific conversion."""
    sanitized: list[LLMMessage] = []
    valid_tool_call_ids: set[str] = set()

    for message in messages:
        if message.tool_call:
            if message.tool_call.call_id:
                valid_tool_call_ids.add(message.tool_call.call_id)
            sanitized.append(message)
            continue

        if message.role == "tool":
            if message.tool_call_id and message.tool_call_id in valid_tool_call_ids:
                sanitized.append(message)
            else:
                logger.warning(
                    "Dropping orphan tool history message before provider request: tool_call_id=%r",
                    message.tool_call_id,
                )
            continue

        sanitized.append(message)

    return sanitized


def _to_openai_messages(messages: list[LLMMessage]) -> list[dict]:
    """Convert internal message objects to OpenAI-compatible payloads."""
    result: list[dict] = []
    for message in _sanitize_llm_messages(messages):
        if message.tool_call:
            result.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": message.tool_call.call_id or f"call_{message.tool_call.name}",
                            "type": "function",
                            "function": {
                                "name": message.tool_call.name,
                                "arguments": json.dumps(message.tool_call.params, ensure_ascii=False),
                            },
                        }
                    ],
                }
            )
            continue

        if message.tool_call_id:
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": message.content,
                }
            )
            continue

        result.append({"role": message.role, "content": message.content})

    return _sanitize_openai_message_dicts(result)


def _sanitize_openai_message_dicts(messages: list[dict]) -> list[dict]:
    """Ensure tool messages always have a valid preceding assistant.tool_calls parent."""
    sanitized: list[dict] = []
    valid_tool_call_ids: set[str] = set()

    for message in messages:
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            for tool_call in tool_calls:
                call_id = tool_call.get("id")
                if call_id:
                    valid_tool_call_ids.add(call_id)
            sanitized.append(message)
            continue

        if message.get("role") == "tool":
            tool_call_id = message.get("tool_call_id")
            if tool_call_id and tool_call_id in valid_tool_call_ids:
                sanitized.append(message)
            else:
                logger.warning(
                    "Dropping orphan tool payload before OpenAI-compatible request: tool_call_id=%r",
                    tool_call_id,
                )
            continue

        sanitized.append(message)

    return sanitized


def _flatten_message_for_text(message: LLMMessage) -> dict:
    """Flatten structured messages for models without native function calling."""
    if message.tool_call:
        return {
            "role": "assistant",
            "content": (
                f"Thought: {message.content}\n"
                f"Action: {message.tool_call.name}\n"
                f"Params: {json.dumps(message.tool_call.params, ensure_ascii=False)}"
            ),
        }
    if message.tool_call_id:
        tool_name = message.tool_name or "tool"
        return {
            "role": "user",
            "content": f"[Tool: {tool_name}]\n{message.content}",
        }
    return {"role": message.role, "content": message.content}


def _to_text_only_openai_messages(messages: list[LLMMessage]) -> list[dict]:
    return [_flatten_message_for_text(message) for message in _sanitize_llm_messages(messages)]


def _to_openai_tool(schema: LLMToolSchema) -> dict:
    return {
        "type": "function",
        "function": {
            "name": schema.name,
            "description": schema.description,
            "parameters": schema.parameters,
        },
    }


def _parse_openai_response(choice: Any, thought: str) -> Action:
    finish_reason = choice.finish_reason
    message = choice.message

    if finish_reason == "tool_calls" and message.tool_calls:
        tool_call = message.tool_calls[0]
        try:
            params = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            params = {"raw": tool_call.function.arguments}

        return Action(
            action_type=ActionType.TOOL_CALL,
            thought=thought,
            tool_call=ToolCall(
                name=tool_call.function.name,
                params=params,
                call_id=getattr(tool_call, "id", None),
            ),
        )

    if finish_reason == "stop":
        if thought and thought != "(no thought)":
            return Action(
                action_type=ActionType.FINISH,
                thought="",
                message=thought,
            )
        return Action(
            action_type=ActionType.GIVE_UP,
            thought=thought,
            message="Model stopped with no content",
        )

    return Action(
        action_type=ActionType.GIVE_UP,
        thought=thought,
        message=f"Unexpected finish_reason: {finish_reason}",
    )


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_INLINE_JSON_RE = re.compile(r"\{[^{}]+\}", re.DOTALL)

_FINISH_KEYWORDS = ("task complete", "task is complete", "i have finished", "all done")
_GIVE_UP_KEYWORDS = ("cannot solve", "give up", "unable to", "i cannot")


def _build_tool_description_for_text(tools: list[LLMToolSchema]) -> str:
    if not tools:
        return ""

    lines = [
        "## Available tools",
        "To call a tool, output ONLY a JSON block in this exact format:",
        '```json\n{"tool": "<tool_name>", "params": {<params>}}\n```',
        "",
        "To finish the task, output: TASK_COMPLETE: <summary>",
        "To give up, output: GIVE_UP: <reason>",
        "",
        "Tools:",
    ]
    for tool in tools:
        lines.append(f"- {tool.name}: {tool.description}")
    return "\n".join(lines)


def _parse_text_response(text: str) -> Action:
    text_stripped = text.strip()

    if text_stripped.upper().startswith("TASK_COMPLETE:"):
        summary = text_stripped[len("TASK_COMPLETE:") :].strip()
        return Action(
            action_type=ActionType.FINISH,
            thought=text_stripped,
            message=summary or "Task complete",
        )

    if text_stripped.upper().startswith("GIVE_UP:"):
        reason = text_stripped[len("GIVE_UP:") :].strip()
        return Action(
            action_type=ActionType.GIVE_UP,
            thought=text_stripped,
            message=reason or "Agent gave up",
        )

    block_match = _JSON_BLOCK_RE.search(text)
    if block_match:
        action = _try_parse_tool_json(block_match.group(1), thought=text_stripped)
        if action is not None:
            return action

    for match in _INLINE_JSON_RE.finditer(text):
        action = _try_parse_tool_json(match.group(0), thought=text_stripped)
        if action is not None:
            return action

    text_lower = text.lower()
    if any(keyword in text_lower for keyword in _FINISH_KEYWORDS):
        return Action(
            action_type=ActionType.FINISH,
            thought=text_stripped,
            message=text_stripped,
        )
    if any(keyword in text_lower for keyword in _GIVE_UP_KEYWORDS):
        return Action(
            action_type=ActionType.GIVE_UP,
            thought=text_stripped,
            message=text_stripped,
        )

    logger.warning("Could not parse action from text: %s", text_stripped[:100])
    return Action(
        action_type=ActionType.GIVE_UP,
        thought=text_stripped,
        message="Could not parse a valid action from model output",
    )


def _try_parse_tool_json(json_str: str, thought: str) -> Action | None:
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    tool_name = data.get("tool") or data.get("name") or data.get("function")
    params = data.get("params") or data.get("arguments") or data.get("input") or {}

    if not tool_name or not isinstance(tool_name, str):
        return None

    return Action(
        action_type=ActionType.TOOL_CALL,
        thought=thought,
        tool_call=ToolCall(name=tool_name, params=params if isinstance(params, dict) else {}),
    )


def _stream_with_tools(
    backend: OpenAICompatBackend,
    api_messages: list[dict],
    tools: list[LLMToolSchema],
    on_text: StreamCallback | None,
    on_thought: StreamCallback | None = None,
) -> LLMResponse:
    api_tools = [_to_openai_tool(tool) for tool in tools] if tools else None
    kwargs = {
        "model": backend._model,
        "max_tokens": backend._max_tokens,
        "messages": api_messages,
        "stream": True,
    }
    if api_tools:
        kwargs["tools"] = api_tools
        kwargs["tool_choice"] = "auto"

    full_text = ""
    full_reasoning = ""
    finish_reason = None
    tool_calls_raw: list[dict[str, Any]] = []

    stream = backend._client.chat.completions.create(**kwargs)
    for chunk in stream:
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            continue

        delta = choice.delta
        finish_reason = choice.finish_reason or finish_reason

        reasoning_delta = getattr(delta, "reasoning_content", None)
        if reasoning_delta:
            full_reasoning += reasoning_delta
            if on_thought:
                on_thought(reasoning_delta)

        if delta.content:
            full_text += delta.content
            if on_text:
                on_text(delta.content)

        if delta.tool_calls:
            for tool_call_delta in delta.tool_calls:
                index = tool_call_delta.index
                while len(tool_calls_raw) <= index:
                    tool_calls_raw.append({"id": None, "name": "", "arguments": ""})
                if getattr(tool_call_delta, "id", None):
                    tool_calls_raw[index]["id"] = tool_call_delta.id
                if tool_call_delta.function.name:
                    tool_calls_raw[index]["name"] += tool_call_delta.function.name
                if tool_call_delta.function.arguments:
                    tool_calls_raw[index]["arguments"] += tool_call_delta.function.arguments

    if tool_calls_raw and finish_reason == "tool_calls":
        tool_calls = []
        for tool_call in tool_calls_raw:
            tool_calls.append(
                SimpleNamespace(
                    function=SimpleNamespace(
                        name=tool_call["name"],
                        arguments=tool_call["arguments"],
                    ),
                    id=tool_call["id"],
                )
            )
        mock_message = SimpleNamespace(content=full_text or None, tool_calls=tool_calls)
    else:
        mock_message = SimpleNamespace(content=full_text or None, tool_calls=None)

    mock_choice = SimpleNamespace(finish_reason=finish_reason or "stop", message=mock_message)
    thought_for_parse = full_text or "(no thought)"
    action = _parse_openai_response(mock_choice, thought_for_parse)
    if full_reasoning and action.action_type == ActionType.FINISH:
        action = Action(
            action_type=action.action_type,
            thought=full_reasoning,
            tool_call=action.tool_call,
            message=action.message,
        )

    from context.token_budget import estimate_tokens

    return LLMResponse(
        action=action,
        raw_content=full_text,
        input_tokens=sum(estimate_tokens(message.get("content", "")) for message in api_messages),
        output_tokens=estimate_tokens(full_text),
    )


def _stream_text_only(
    backend: OpenAICompatBackend,
    api_messages: list[dict],
    tools: list[LLMToolSchema],
    on_text: StreamCallback | None,
) -> LLMResponse:
    tool_desc = _build_tool_description_for_text(tools)
    augmented = list(api_messages)
    if augmented and augmented[0]["role"] == "system":
        augmented[0] = {
            "role": "system",
            "content": augmented[0]["content"] + "\n\n" + tool_desc,
        }

    full_text = ""
    stream = backend._client.chat.completions.create(
        model=backend._model,
        max_tokens=backend._max_tokens,
        messages=augmented,
        stream=True,
    )
    for chunk in stream:
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            continue
        delta = choice.delta
        if delta.content:
            full_text += delta.content
            if on_text:
                on_text(delta.content)

    from context.token_budget import estimate_tokens

    return LLMResponse(
        action=_parse_text_response(full_text),
        raw_content=full_text,
        input_tokens=sum(estimate_tokens(message.get("content", "")) for message in augmented),
        output_tokens=estimate_tokens(full_text),
    )
