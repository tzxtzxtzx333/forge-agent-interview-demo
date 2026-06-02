"""
Shared tool abstractions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from agent.task import Observation, ObservationStatus
from llm.base import LLMToolSchema


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_observation(self, tool_name: str) -> Observation:
        return Observation(
            status=ObservationStatus.SUCCESS if self.success else ObservationStatus.ERROR,
            output=self.output,
            tool_name=tool_name,
            error=self.error,
        )


class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def execute(self, params: dict[str, Any]) -> ToolResult:
        ...

    def to_llm_schema(self) -> LLMToolSchema:
        return LLMToolSchema(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema,
        )


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> "ToolRegistry":
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool
        return self

    def execute_tool(self, name: str, params: dict[str, Any]) -> ToolResult:
        if name not in self._tools:
            available = ", ".join(self._tools.keys()) or "none"
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool '{name}'. Available tools: {available}",
            )

        tool = self._tools[name]
        try:
            return tool.execute(params)
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{name}' raised an unexpected error: {exc}",
            )

    def get_schemas(self) -> list[LLMToolSchema]:
        return [tool.to_llm_schema() for tool in self._tools.values()]

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={self.tool_names})"


class NoopTool(BaseTool):
    def __init__(self, tool_name: str = "noop", output: str = "ok") -> None:
        self._name = tool_name
        self._output = output
        self.call_count = 0
        self.last_params: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"No-op tool '{self._name}' for testing."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Anything"},
            },
            "required": [],
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        self.call_count += 1
        self.last_params = params
        return ToolResult(success=True, output=self._output)


class FailingTool(BaseTool):
    def __init__(self, tool_name: str = "test", error_msg: str = "AssertionError: 1 != 2") -> None:
        self._name = tool_name
        self._error_msg = error_msg
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Always-failing tool '{self._name}' for testing."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def execute(self, params: dict[str, Any]) -> ToolResult:
        self.call_count += 1
        return ToolResult(
            success=False,
            output=self._error_msg,
            error=self._error_msg,
        )
