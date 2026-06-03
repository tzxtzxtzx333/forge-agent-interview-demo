from __future__ import annotations

from tools.runtime import RunResult
from tools.shell_tool import ShellTool, _check_blocked, _is_readonly, _needs_confirm


def test_required_dangerous_commands_are_blocked() -> None:
    blocked = [
        "rm -rf /",
        "rm -rf ~",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/tmp/x",
        ":(){:|:&};:",
        "chmod -R 777 /",
        "echo hi > /dev/sda",
    ]
    for cmd in blocked:
        assert _check_blocked(cmd) is not None, cmd


def test_required_readonly_commands_are_allowed_without_confirm() -> None:
    readonly = [
        "pwd",
        "ls",
        "cat README.md",
        "grep TODO README.md",
        "find . -name *.py",
        "git status",
        "git diff",
        "python -m pytest",
        "pytest",
    ]
    for cmd in readonly:
        assert _is_readonly(cmd), cmd
        assert not _needs_confirm(cmd), cmd


def test_required_confirm_commands_need_confirmation() -> None:
    commands = [
        "rm file.txt",
        "mv a.txt b.txt",
        "pip install requests",
        "git commit -m test",
        "git push origin main",
        "curl https://example.com",
        "wget https://example.com/file.txt",
        "chmod 755 script.sh",
        "sudo ls",
        "docker ps",
        "echo hello > output.txt",
    ]
    for cmd in commands:
        assert _needs_confirm(cmd), cmd


def test_shelltool_wraps_runtime_exception_as_failure() -> None:
    class ExplodingRuntime:
        def exec(self, cmd, cwd=None, timeout=30):
            raise RuntimeError("boom")

    tool = ShellTool(runtime=ExplodingRuntime())
    result = tool.execute({"cmd": "pwd"})

    assert not result.success
    assert result.output == ""
    assert "boom" in result.error.lower()


def test_shelltool_blocked_command_returns_error_result() -> None:
    class RecordingRuntime:
        def __init__(self):
            self.called = False

        def exec(self, cmd, cwd=None, timeout=30):
            self.called = True
            return RunResult(returncode=0, stdout="ok", stderr="")

    runtime = RecordingRuntime()
    tool = ShellTool(runtime=runtime)

    result = tool.execute({"cmd": "rm -rf /"})

    assert not result.success
    assert "blocked" in result.error.lower()
    assert runtime.called is False
