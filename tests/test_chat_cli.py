from __future__ import annotations

from click.testing import CliRunner

from entry.cli import cli


class _FakeSession:
    last_instance = None

    def __init__(self, *args, **kwargs):
        self.run_round_calls: list[str] = []
        self.clear_calls = 0
        self.stats_calls = 0
        _FakeSession.last_instance = self

    def run_round(self, user_input: str) -> bool:
        self.run_round_calls.append(user_input)
        return True

    def print_stats(self) -> None:
        self.stats_calls += 1
        print("Rounds  : 0")
        print("Steps   : 0")
        print("Tool calls : 0")
        print("Elapsed : 0.0s")

    def clear_session(self) -> None:
        self.clear_calls += 1


def _patch_chat_deps(monkeypatch):
    monkeypatch.setattr(
        "entry.cli._build_app_components",
        lambda *args, **kwargs: {
            "backend": object(),
            "runtime": None,
            "confirm_callback": None,
            "registry": object(),
        },
    )
    monkeypatch.setattr("entry.chat.ChatSession", _FakeSession)


def test_chat_help_available() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["chat", "--help"])
    assert result.exit_code == 0
    assert "--repo" in result.output
    assert "--stream / --no-stream" in result.output or "--stream" in result.output
    assert "--confirm" in result.output


def test_chat_help_command_outputs_builtin_commands(monkeypatch, tmp_path) -> None:
    _patch_chat_deps(monkeypatch)
    inputs = iter(["/help", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    runner = CliRunner()
    result = runner.invoke(cli, ["chat", "--repo", str(tmp_path)], obj={})

    assert result.exit_code == 0
    assert "/exit" in result.output
    assert "/stats" in result.output
    assert "/clear" in result.output


def test_chat_stats_command_outputs_rounds(monkeypatch, tmp_path) -> None:
    _patch_chat_deps(monkeypatch)
    inputs = iter(["/stats", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    runner = CliRunner()
    result = runner.invoke(cli, ["chat", "--repo", str(tmp_path)], obj={})

    assert result.exit_code == 0
    assert "Rounds  :" in result.output
    assert "Tool calls :" in result.output


def test_chat_clear_calls_session_reset(monkeypatch, tmp_path) -> None:
    _patch_chat_deps(monkeypatch)
    inputs = iter(["/clear", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    runner = CliRunner()
    result = runner.invoke(cli, ["chat", "--repo", str(tmp_path)], obj={})

    assert result.exit_code == 0
    assert "Session cleared." in result.output
    assert _FakeSession.last_instance.clear_calls == 1


def test_chat_empty_input_does_not_trigger_agent(monkeypatch, tmp_path) -> None:
    _patch_chat_deps(monkeypatch)
    inputs = iter(["", "   ", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    runner = CliRunner()
    result = runner.invoke(cli, ["chat", "--repo", str(tmp_path)], obj={})

    assert result.exit_code == 0
    assert _FakeSession.last_instance.run_round_calls == []
