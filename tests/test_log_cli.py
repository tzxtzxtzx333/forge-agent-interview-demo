from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from entry.cli import cli


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _sample_rows() -> list[dict]:
    return [
        {
            "event_id": "e1",
            "event_type": "task_start",
            "task_id": "task-1",
            "timestamp": "2026-06-03T10:00:00+00:00",
            "payload": {
                "task": {
                    "task_id": "task-1",
                    "description": "Fix failing tests",
                    "repo_path": ".",
                }
            },
        },
        {
            "event_id": "e2",
            "event_type": "action",
            "task_id": "task-1",
            "timestamp": "2026-06-03T10:00:01+00:00",
            "payload": {
                "step": 1,
                "action": {
                    "action_type": "tool_call",
                    "thought": "Read app file",
                    "tool_call": {
                        "name": "file_read",
                        "params": {"path": "src/app.py"},
                    },
                },
            },
        },
        {
            "event_id": "e3",
            "event_type": "observation",
            "task_id": "task-1",
            "timestamp": "2026-06-03T10:00:02+00:00",
            "payload": {
                "step": 1,
                "observation": {
                    "tool_name": "file_read",
                    "status": "success",
                    "output": "file content",
                },
            },
        },
        {
            "event_id": "e4",
            "event_type": "action",
            "task_id": "task-1",
            "timestamp": "2026-06-03T10:00:03+00:00",
            "payload": {
                "step": 2,
                "action": {
                    "action_type": "tool_call",
                    "thought": "Run tests",
                    "tool_call": {
                        "name": "test",
                        "params": {"cmd": "pytest"},
                    },
                },
            },
        },
        {
            "event_id": "e5",
            "event_type": "observation",
            "task_id": "task-1",
            "timestamp": "2026-06-03T10:00:04+00:00",
            "payload": {
                "step": 2,
                "observation": {
                    "tool_name": "test",
                    "status": "error",
                    "output": "1 failed",
                    "error": "1 failed",
                },
            },
        },
        {
            "event_id": "e6",
            "event_type": "reflection",
            "task_id": "task-1",
            "timestamp": "2026-06-03T10:00:05+00:00",
            "payload": {
                "step": 2,
                "reason": "test_failed",
                "prompt": "Re-check the failing test.",
            },
        },
        {
            "event_id": "e7",
            "event_type": "task_complete",
            "task_id": "task-1",
            "timestamp": "2026-06-03T10:00:06+00:00",
            "payload": {
                "steps": 3,
                "summary": "Fixed tests",
            },
        },
    ]


def test_log_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["log", "--help"])
    assert result.exit_code == 0
    assert "Inspect event logs" in result.output


def test_log_list_lists_jsonl_files(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    _write_jsonl(log_dir / "example.jsonl", _sample_rows())

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "list", "--dir", str(log_dir)])

    assert result.exit_code == 0
    assert "example.jsonl" in result.output
    assert "modified=" in result.output
    assert "status=task_complete" in result.output


def test_log_show_summarizes_counts_and_tool_distribution(tmp_path: Path) -> None:
    path = tmp_path / "example.jsonl"
    _write_jsonl(path, _sample_rows())

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "show", str(path)])

    assert result.exit_code == 0
    assert "Total events     : 7" in result.output
    assert "Actions          : 2" in result.output
    assert "Observations     : 2" in result.output
    assert "Reflections      : 1" in result.output
    assert "'file_read': 1" in result.output
    assert "'test': 1" in result.output
    assert "Final status     : task_complete" in result.output


def test_log_replay_prints_events_in_order(tmp_path: Path) -> None:
    path = tmp_path / "example.jsonl"
    _write_jsonl(path, _sample_rows())

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "replay", str(path)])

    assert result.exit_code == 0
    output = result.output
    assert output.index("[STEP 1] tool_call") < output.index("[STEP 2] tool_call")
    assert "[OK] [file_read]" in output
    assert "[ERROR] [test]" in output
    assert "[WARN] Reflection: test_failed" in output
    assert "[OK] Final: Fixed tests" in output


def test_log_show_missing_file_friendly_error(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["log", "show", str(tmp_path / "missing.jsonl")])
    assert result.exit_code != 0
    assert "File not found" in result.output


def test_log_replay_missing_file_friendly_error(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["log", "replay", str(tmp_path / "missing.jsonl")])
    assert result.exit_code != 0
    assert "File not found" in result.output


def test_log_list_missing_directory_friendly_message(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["log", "list", "--dir", str(tmp_path / "missing")])
    assert result.exit_code == 0
    assert "Log directory not found" in result.output


def test_log_show_handles_corrupt_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text("{not valid json}\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "show", str(path)])

    assert result.exit_code != 0
    assert "failed to read log file" in result.output


def test_log_replay_handles_corrupt_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text("{not valid json}\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "replay", str(path)])

    assert result.exit_code != 0
    assert "failed to replay log file" in result.output
