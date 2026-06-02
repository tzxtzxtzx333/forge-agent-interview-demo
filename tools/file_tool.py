"""
File tools for reading, viewing, and writing files inside the current repo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.base import BaseTool, ToolResult


MAX_READ_LINES = 500
VIEW_WINDOW_LINES = 100
_OUTSIDE_REPO_ERROR = "path outside repo is not allowed"


class _RepoBoundFileTool(BaseTool):
    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()

    def _resolve_repo_path(self, raw_path: Any, *, allow_create: bool = False) -> Path:
        candidate = Path(str(raw_path or "").strip())
        if not str(candidate):
            raise ValueError("path is required")

        joined = candidate if candidate.is_absolute() else self.repo_root / candidate

        try:
            resolved = joined.resolve(strict=False)
        except OSError:
            raise ValueError(_OUTSIDE_REPO_ERROR) from None

        if not self._is_within_repo(resolved):
            raise ValueError(_OUTSIDE_REPO_ERROR)

        if allow_create:
            parent = resolved.parent
            try:
                parent_resolved = parent.resolve(strict=False)
            except OSError:
                raise ValueError(_OUTSIDE_REPO_ERROR) from None
            if not self._is_within_repo(parent_resolved):
                raise ValueError(_OUTSIDE_REPO_ERROR)

        return resolved

    def _is_within_repo(self, path: Path) -> bool:
        try:
            path.relative_to(self.repo_root)
            return True
        except ValueError:
            return False


class FileReadTool(_RepoBoundFileTool):
    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return (
            f"Read the contents of a file inside the repo root. "
            f"Files longer than {MAX_READ_LINES} lines will be truncated; "
            f"use file_view with line numbers to read specific sections."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read (absolute or relative to repo root)",
                },
            },
            "required": ["path"],
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        try:
            path = self._resolve_repo_path(params.get("path"))
        except ValueError as exc:
            return ToolResult(success=False, output="", error=str(exc))

        if not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path.name}")
        if not path.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {path.name}")

        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            return ToolResult(success=False, output="", error=str(exc))

        total = len(lines)
        display_lines = lines[:MAX_READ_LINES]
        numbered = "\n".join(f"{i + 1:4d} | {line}" for i, line in enumerate(display_lines))

        suffix = ""
        if total > MAX_READ_LINES:
            suffix = (
                f"\n... ({total - MAX_READ_LINES} more lines not shown) "
                f"Use file_view with start_line to read the rest."
            )

        return ToolResult(
            success=True,
            output=f"File: {path.relative_to(self.repo_root)} ({total} lines total)\n{numbered}{suffix}",
        )


class FileViewTool(_RepoBoundFileTool):
    @property
    def name(self) -> str:
        return "file_view"

    @property
    def description(self) -> str:
        return (
            f"View a specific section of a file inside the repo root, {VIEW_WINDOW_LINES} lines at a time. "
            f"Use start_line to scroll through large files. Lines are 1-indexed."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file (inside the repo root)",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to show (1-indexed, default 1)",
                },
            },
            "required": ["path"],
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        start_line = max(1, int(params.get("start_line", 1)))
        try:
            path = self._resolve_repo_path(params.get("path"))
        except ValueError as exc:
            return ToolResult(success=False, output="", error=str(exc))

        if not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path.name}")
        if not path.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {path.name}")

        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            return ToolResult(success=False, output="", error=str(exc))

        total = len(lines)
        if start_line > total:
            return ToolResult(
                success=False,
                output="",
                error=f"start_line {start_line} exceeds file length ({total} lines)",
            )

        end_line = min(start_line + VIEW_WINDOW_LINES - 1, total)
        window = lines[start_line - 1 : end_line]
        numbered = "\n".join(f"{start_line + i:4d} | {line}" for i, line in enumerate(window))
        rel_path = path.relative_to(self.repo_root)

        if end_line < total:
            nav = f"\n[Lines {start_line}-{end_line} of {total}. Next: file_view path={rel_path} start_line={end_line + 1}]"
        else:
            nav = f"\n[Lines {start_line}-{end_line} of {total}. End of file.]"

        return ToolResult(success=True, output=numbered + nav)


class FileWriteTool(_RepoBoundFileTool):
    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return (
            "Write content to a file inside the repo root, replacing its entire contents. "
            "Parent directories are created automatically. "
            "Always read the file first before writing to avoid losing existing content."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write (inside the repo root)",
                },
                "content": {
                    "type": "string",
                    "description": "Full content to write to the file",
                },
            },
            "required": ["path", "content"],
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        content = params.get("content", "")
        try:
            path = self._resolve_repo_path(params.get("path"), allow_create=True)
        except ValueError as exc:
            return ToolResult(success=False, output="", error=str(exc))

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(success=False, output="", error=str(exc))

        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return ToolResult(
            success=True,
            output=f"Written {line_count} lines to {path.relative_to(self.repo_root)}",
            metadata={"writes_files": True},
        )
