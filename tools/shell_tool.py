"""
Shell command execution with lightweight safety classification.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from tools.base import BaseTool, ToolResult
from tools.runtime import LocalRuntime, Runtime


MAX_OUTPUT_CHARS = 8_000

_BLOCKED_PATTERNS: tuple[str, ...] = (
    "rm -rf /",
    "rm -rf ~",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "chmod -R 777 /",
    "chown -R",
    "> /dev/sda",
)

_READONLY_PREFIXES: tuple[str, ...] = (
    "ls", "ll", "la",
    "cat", "head", "tail", "less", "more",
    "echo", "printf",
    "pwd", "whoami", "which", "type",
    "find", "locate",
    "grep", "egrep", "fgrep", "rg", "ag",
    "wc", "sort", "uniq", "cut", "awk", "sed -n",
    "diff", "diff3",
    "file", "stat",
    "python -c", "python3 -c",
    "python -m pytest", "python3 -m pytest", "pytest",
    "git status", "git diff", "git log", "git show",
    "git branch", "git tag", "git remote",
    "git stash list",
    "tree",
    "env", "printenv",
    "ps", "top", "htop",
    "df", "du",
    "uname", "hostname",
    "date", "cal",
    "man", "help",
)

_CONFIRM_KEYWORDS: tuple[str, ...] = (
    "rm ", "rmdir",
    "mv ",
    "cp -r", "cp -f",
    "chmod", "chown",
    "pip install", "pip uninstall",
    "npm install", "npm uninstall",
    "git commit", "git push", "git reset",
    "git checkout", "git merge", "git rebase",
    "git clean",
    "sudo",
    "curl", "wget",
    "kill", "pkill", "killall",
    "shutdown", "reboot",
    "docker", "kubectl",
    "make", "make install",
    "> ",
    "| tee ",
)

_SHELL_CONTROL_RE = re.compile(r"(;|&&|\|\||(?<!\|)\|(?!\|))")
_REDIRECTION_RE = re.compile(r"(?<![>])>(?![>])|<")
_NESTED_SHELL_RE = re.compile(
    r"^\s*(bash|sh|zsh|ksh|cmd|powershell|pwsh)\s+(-c|/c|-command)\b",
    re.IGNORECASE,
)
_PYTHON_INLINE_WRITE_RE = re.compile(
    r"""^\s*python(?:3)?\s+-c\s+.*(
        open\s*\([^)]*,\s*['"][wax]['"]|
        write_text\s*\(|
        write_bytes\s*\(|
        unlink\s*\(|
        rename\s*\(|
        replace\s*\(
    )""",
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)

ConfirmCallback = Callable[[str], bool]


class ShellTool(BaseTool):
    def __init__(
        self,
        confirm_callback: ConfirmCallback | None = None,
        runtime: Runtime | None = None,
    ) -> None:
        self._confirm_callback = confirm_callback
        self._runtime = runtime or LocalRuntime()

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command and return its output (stdout + stderr combined). "
            "Timeout is 30s by default. This tool provides basic guardrails against "
            "obvious write operations, but Docker sandboxing is the stronger isolation boundary."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cmd": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30)",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (optional)",
                },
            },
            "required": ["cmd"],
        }

    def execute(self, params: dict[str, Any]) -> ToolResult:
        cmd: str = params.get("cmd", "").strip()
        timeout: int = int(params.get("timeout", 30))
        cwd: str | None = params.get("cwd", None)

        if not cmd:
            return ToolResult(success=False, output="", error="cmd is required")

        blocked = _check_blocked(cmd)
        if blocked:
            return ToolResult(
                success=False,
                output="",
                error=f"Command blocked for safety: matched '{blocked}'",
            )

        if not _needs_confirm(cmd):
            return self._run(cmd, timeout, cwd)

        if self._confirm_callback is not None:
            allowed = self._confirm_callback(cmd)
            if not allowed:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command rejected by user: {cmd!r}",
                )

        return self._run(cmd, timeout, cwd)

    def _run(self, cmd: str, timeout: int, cwd: str | None) -> ToolResult:
        result = self._runtime.exec(cmd, cwd=cwd, timeout=timeout)
        output = _truncate(result.output, MAX_OUTPUT_CHARS)
        if not result.success:
            if "timed out" in result.stderr.lower():
                error = result.stderr.strip()
            else:
                error = f"Exit code: {result.returncode}"
        else:
            error = None
        return ToolResult(success=result.success, output=output, error=error)


def _check_blocked(cmd: str) -> str | None:
    cmd_lower = cmd.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern.lower() in cmd_lower:
            return pattern
    return None


def _has_shell_control_operators(cmd: str) -> bool:
    return bool(_SHELL_CONTROL_RE.search(cmd))


def _has_redirection(cmd: str) -> bool:
    return bool(_REDIRECTION_RE.search(cmd))


def _uses_nested_shell(cmd: str) -> bool:
    return bool(_NESTED_SHELL_RE.search(cmd))


def _python_inline_may_write(cmd: str) -> bool:
    return bool(_PYTHON_INLINE_WRITE_RE.search(cmd))


def _is_readonly(cmd: str) -> bool:
    if (
        _has_redirection(cmd)
        or _has_shell_control_operators(cmd)
        or _uses_nested_shell(cmd)
        or _python_inline_may_write(cmd)
    ):
        return False

    stripped = cmd.strip().lower()
    for prefix in _READONLY_PREFIXES:
        if stripped == prefix or stripped.startswith(prefix + " "):
            return True
    return False


def _needs_confirm(cmd: str) -> bool:
    if _is_readonly(cmd):
        return False
    if (
        _has_redirection(cmd)
        or _has_shell_control_operators(cmd)
        or _uses_nested_shell(cmd)
        or _python_inline_may_write(cmd)
    ):
        return True
    cmd_lower = cmd.lower()
    return any(keyword in cmd_lower for keyword in _CONFIRM_KEYWORDS)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.6)
    tail = max_chars - head
    omitted = len(text) - max_chars
    return (
        text[:head]
        + f"\n... [{omitted} characters truncated] ...\n"
        + text[-tail:]
    )


def terminal_confirm(cmd: str) -> bool:
    import sys

    if not sys.stdin.isatty():
        print(f"\n[confirm] Non-interactive terminal, rejecting: {cmd!r}", flush=True)
        return False

    print("\n\033[33m  Agent wants to run:\033[0m")
    print(f"     \033[1m$ {cmd}\033[0m")

    while True:
        try:
            ans = input("  Allow? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False

        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no", ""):
            print("  \033[31mRejected\033[0m")
            return False
        print("  Please enter y or n.")


def always_allow(cmd: str) -> bool:
    return True


def always_deny(cmd: str) -> bool:
    return False
