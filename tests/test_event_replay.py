from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent.event_log import EventLog, build_execution_trace, render_replay_lines, summarize_run
from agent.task import Action, ActionType, Observation, ObservationStatus, Task, ToolCall
from entry.cli import cli


def _make_task(tmp_path: Path) -> Task:
    return Task(
        task_id="trace123",
        description="Fix parser bug",
        repo_path=str(tmp_path),
        test_cmd="pytest tests/test_parser.py -q",
        max_steps=6,
    )


def test_build_execution_trace_collects_audit_fields(tmp_path):
    task = _make_task(tmp_path)
    log_dir = tmp_path / "logs"
    action = Action(
        action_type=ActionType.TOOL_CALL,
        thought="Run tests first",
        tool_call=ToolCall(name="test", params={"path": "tests/test_parser.py"}),
    )
    write_action = Action(
        action_type=ActionType.TOOL_CALL,
        thought="Patch file",
        tool_call=ToolCall(name="file_write", params={"path": "src/parser.py", "content": "x = 1"}),
    )
    test_obs = Observation(
        status=ObservationStatus.ERROR,
        output="FAILED tests/test_parser.py::test_empty_input\n1 failed, 2 passed in 0.12s",
        tool_name="test",
        error="pytest exited with code 1",
    )
    write_obs = Observation(
        status=ObservationStatus.SUCCESS,
        output="Wrote file path=src/parser.py",
        tool_name="file_write",
    )

    with EventLog.create(task, log_dir=str(log_dir)) as log:
        log.log_task_start(task)
        log.log_action(step=1, action=action)
        log.log_observation(step=1, observation=test_obs)
        log.log_reflection(step=1, reason="test_failed", prompt="retry")
        log.log_action(step=2, action=write_action)
        log.log_observation(step=2, observation=write_obs)
        log.log_task_complete(steps=2, summary="Patched parser and reran tests")

        trace = build_execution_trace(log)

    assert trace["task_id"] == "trace123"
    assert trace["description"] == "Fix parser bug"
    assert trace["repo_path"] == str(tmp_path)
    assert trace["start_time"] is not None
    assert trace["end_time"] is not None
    assert trace["provider"] == "unknown"
    assert trace["model"] == "unknown"
    assert trace["final_status"] == "task_complete"
    assert trace["final_summary"] == "Patched parser and reran tests"
    assert trace["steps"] == 2
    assert any(call["tool"] == "test" for call in trace["tool_calls"])
    assert any(result["tool"] == "file_write" for result in trace["tool_results"])
    assert "src/parser.py" in trace["modified_files"]
    assert any("1 failed, 2 passed" in run["summary"] for run in trace["test_runs"])


def test_old_log_compatibility_defaults_missing_fields(tmp_path):
    log_path = tmp_path / "old.jsonl"
    old_events = [
        {
            "event_id": "e1",
            "event_type": "task_start",
            "task_id": "old123",
            "timestamp": "2026-06-03T00:00:00+00:00",
            "payload": {"task": {"task_id": "old123", "description": "old task", "repo_path": "C:/repo"}},
        },
        {
            "event_id": "e2",
            "event_type": "action",
            "task_id": "old123",
            "timestamp": "2026-06-03T00:00:01+00:00",
            "payload": {
                "step": 1,
                "action": {
                    "action_type": "tool_call",
                    "thought": "inspect",
                    "message": None,
                    "tool_call": {"name": "shell", "params": {"cmd": "pytest"}, "call_id": None},
                },
            },
        },
        {
            "event_id": "e3",
            "event_type": "task_failed",
            "task_id": "old123",
            "timestamp": "2026-06-03T00:00:02+00:00",
            "payload": {"steps": 1, "reason": "max_steps"},
        },
    ]
    log_path.write_text("\n".join(json.dumps(event) for event in old_events), encoding="utf-8")

    with EventLog.open_existing(log_path) as log:
        trace = build_execution_trace(log)
        stats = summarize_run(log)
        replay_lines = render_replay_lines(log)

    assert trace["provider"] == "unknown"
    assert trace["model"] == "unknown"
    assert trace["final_status"] == "task_failed"
    assert trace["final_error"] == "max_steps"
    assert stats["final_status"] == "task_failed"
    assert any("[TASK] old123" in line for line in replay_lines)


def test_cli_log_replay_outputs_execution_trace(tmp_path):
    task = _make_task(tmp_path)
    with EventLog.create(task, log_dir=str(tmp_path / "logs")) as log:
        log.log_task_start(task)
        log.log_action(
            step=1,
            action=Action(
                action_type=ActionType.TOOL_CALL,
                thought="Run tests",
                tool_call=ToolCall(name="test", params={"path": "tests/test_parser.py"}),
            ),
        )
        log.log_observation(
            step=1,
            observation=Observation(
                status=ObservationStatus.SUCCESS,
                output="3 passed in 0.05s",
                tool_name="test",
            ),
        )
        log.log_task_complete(steps=1, summary="All tests passing")
        log_path = log.path

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "replay", str(log_path)], obj={})
    assert result.exit_code == 0
    assert "[TASK] trace123" in result.output
    assert "[STEP 1] tool_call" in result.output
    assert "[OK] [test]" in result.output
    assert "[OK] Final: All tests passing" in result.output


def test_cli_log_show_uses_audit_summary(tmp_path):
    task = _make_task(tmp_path)
    with EventLog.create(task, log_dir=str(tmp_path / "logs")) as log:
        log.log_task_start(task)
        log.log_task_complete(steps=0, summary="done")
        log_path = log.path

    runner = CliRunner()
    result = runner.invoke(cli, ["log", "show", str(log_path)], obj={})
    assert result.exit_code == 0
    assert "Task id" in result.output
    assert "Provider" in result.output
    assert "Final status" in result.output
