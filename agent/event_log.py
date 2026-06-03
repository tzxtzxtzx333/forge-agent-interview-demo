"""
Append-only JSONL event logging.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from agent.task import Action, Event, EventType, Observation, Task


class EventLog:
    def __init__(self, path: Path, task_id: str | None = None) -> None:
        self._path = path
        self._file = open(path, "a", encoding="utf-8")
        self._task_id = task_id or self._infer_task_id()

    @classmethod
    def create(cls, task: Task, log_dir: str = "./logs") -> "EventLog":
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{task.task_id}_{timestamp}.jsonl"
        return cls(log_path / filename, task_id=task.task_id)

    @classmethod
    def open_existing(cls, path: str | Path, task_id: str | None = None) -> "EventLog":
        return cls(Path(path), task_id=task_id)

    def log_task_start(self, task: Task) -> None:
        self._append(Event(
            event_type=EventType.TASK_START,
            task_id=task.task_id,
            payload={"task": task.to_dict()},
        ))

    def log_action(self, step: int, action: Action, raw_content: str = "") -> None:
        self._append(Event(
            event_type=EventType.ACTION,
            task_id=self._current_task_id,
            payload={
                "step": step,
                "action": action.to_dict(),
                "raw_content": raw_content,
            },
        ))

    def log_observation(self, step: int, observation: Observation) -> None:
        self._append(Event(
            event_type=EventType.OBSERVATION,
            task_id=self._current_task_id,
            payload={
                "step": step,
                "observation": observation.to_dict(),
            },
        ))

    def log_reflection(self, step: int, reason: str, prompt: str) -> None:
        self._append(Event(
            event_type=EventType.REFLECTION,
            task_id=self._current_task_id,
            payload={
                "step": step,
                "reason": reason,
                "prompt": prompt,
            },
        ))

    def log_task_complete(self, steps: int, summary: str) -> None:
        self._append(Event(
            event_type=EventType.TASK_COMPLETE,
            task_id=self._current_task_id,
            payload={
                "steps": steps,
                "summary": summary,
            },
        ))

    def log_task_failed(self, steps: int, reason: str) -> None:
        self._append(Event(
            event_type=EventType.TASK_FAILED,
            task_id=self._current_task_id,
            payload={
                "steps": steps,
                "reason": reason,
            },
        ))

    def replay(self) -> list[Event]:
        if not self._file.closed:
            self._file.flush()
        events: list[Event] = []
        with open(self._path, encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                events.append(Event(
                    event_id=raw["event_id"],
                    event_type=EventType(raw["event_type"]),
                    task_id=raw["task_id"],
                    timestamp=raw["timestamp"],
                    payload=raw["payload"],
                ))
        return events

    def iter_events(self) -> Iterator[Event]:
        if not self._file.closed:
            self._file.flush()
        with open(self._path, encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                yield Event(
                    event_id=raw["event_id"],
                    event_type=EventType(raw["event_type"]),
                    task_id=raw["task_id"],
                    timestamp=raw["timestamp"],
                    payload=raw["payload"],
                )

    def get_actions(self) -> list[Action]:
        from agent.task import ActionType, ToolCall

        actions: list[Action] = []
        for event in self.iter_events():
            if event.event_type != EventType.ACTION:
                continue
            raw_action = event.payload["action"]
            raw_tc = raw_action.get("tool_call")
            tool_call = None
            if raw_tc:
                tool_call = ToolCall(
                    name=raw_tc["name"],
                    params=raw_tc["params"],
                    call_id=raw_tc.get("call_id"),
                )
            actions.append(Action(
                action_type=ActionType(raw_action["action_type"]),
                thought=raw_action["thought"],
                tool_call=tool_call,
                message=raw_action.get("message"),
            ))
        return actions

    @property
    def path(self) -> Path:
        return self._path

    @property
    def _current_task_id(self) -> str:
        return self._task_id

    def _infer_task_id(self) -> str:
        if self._path.exists() and self._path.stat().st_size > 0:
            try:
                with open(self._path, encoding="utf-8") as file:
                    first_line = file.readline().strip()
                if first_line:
                    return json.loads(first_line)["task_id"]
            except Exception:
                pass
        return self._path.stem

    def _append(self, event: Event) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        if not self._file.closed:
            self._file.flush()
            self._file.close()

    def __enter__(self) -> "EventLog":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"EventLog(path={self._path})"


def summarize_run(log: EventLog) -> dict:
    events = log.replay()

    stats = {
        "total_events": len(events),
        "actions": 0,
        "reflections": 0,
        "tool_calls": {},
        "observations_ok": 0,
        "observations_err": 0,
        "final_status": None,
    }

    for event in events:
        if event.event_type == EventType.ACTION:
            stats["actions"] += 1
            tc = event.payload["action"].get("tool_call")
            if tc:
                name = tc["name"]
                stats["tool_calls"][name] = stats["tool_calls"].get(name, 0) + 1
        elif event.event_type == EventType.OBSERVATION:
            obs = event.payload["observation"]
            if obs["status"] == "success":
                stats["observations_ok"] += 1
            else:
                stats["observations_err"] += 1
        elif event.event_type == EventType.REFLECTION:
            stats["reflections"] += 1
        elif event.event_type in (EventType.TASK_COMPLETE, EventType.TASK_FAILED):
            stats["final_status"] = event.event_type.value

    return stats


def build_execution_trace(log: EventLog) -> dict:
    events = log.replay()

    trace = {
        "task_id": log._current_task_id,
        "description": None,
        "repo_path": None,
        "issue_url": None,
        "provider": "unknown",
        "model": "unknown",
        "start_time": events[0].timestamp if events else None,
        "end_time": events[-1].timestamp if events else None,
        "duration_seconds": None,
        "tool_calls": [],
        "tool_results": [],
        "modified_files": [],
        "test_runs": [],
        "final_status": None,
        "final_summary": None,
        "final_error": None,
        "steps": 0,
    }

    modified_files: set[str] = set()
    seen_test_runs: set[tuple[str, str]] = set()

    for event in events:
        payload = event.payload or {}

        if event.event_type == EventType.TASK_START:
            task_payload = payload.get("task", {})
            trace["task_id"] = task_payload.get("task_id", trace["task_id"])
            trace["description"] = task_payload.get("description")
            trace["repo_path"] = task_payload.get("repo_path")
            trace["issue_url"] = task_payload.get("issue_url")
            meta = payload.get("meta", {})
            trace["provider"] = meta.get("provider", trace["provider"])
            trace["model"] = meta.get("model", trace["model"])

        elif event.event_type == EventType.ACTION:
            step = payload.get("step", 0)
            trace["steps"] = max(trace["steps"], step)
            action = payload.get("action", {})
            tool_call = action.get("tool_call")
            if tool_call:
                call = {
                    "step": step,
                    "tool": tool_call.get("name"),
                    "params": tool_call.get("params", {}),
                    "thought": action.get("thought", ""),
                    "timestamp": event.timestamp,
                }
                trace["tool_calls"].append(call)
                modified_files.update(_extract_modified_files_from_tool_call(call["tool"], call["params"]))

        elif event.event_type == EventType.OBSERVATION:
            step = payload.get("step", 0)
            trace["steps"] = max(trace["steps"], step)
            observation = payload.get("observation", {})
            tool_name = observation.get("tool_name", "")
            output = observation.get("output", "")
            result = {
                "step": step,
                "tool": tool_name,
                "status": observation.get("status"),
                "error": observation.get("error"),
                "output_preview": _preview_output(output),
                "timestamp": event.timestamp,
            }
            trace["tool_results"].append(result)
            modified_files.update(_extract_modified_files_from_observation(tool_name, output))

            test_run = _extract_test_run(tool_name, output, observation.get("status"), observation.get("error"))
            if test_run is not None:
                key = (test_run["tool"], test_run["summary"])
                if key not in seen_test_runs:
                    seen_test_runs.add(key)
                    trace["test_runs"].append(test_run)

        elif event.event_type == EventType.TASK_COMPLETE:
            trace["final_status"] = event.event_type.value
            trace["steps"] = max(trace["steps"], payload.get("steps", 0))
            trace["final_summary"] = payload.get("summary")
        elif event.event_type == EventType.TASK_FAILED:
            trace["final_status"] = event.event_type.value
            trace["steps"] = max(trace["steps"], payload.get("steps", 0))
            trace["final_error"] = payload.get("reason")

    trace["modified_files"] = sorted(modified_files)

    if trace["start_time"] and trace["end_time"]:
        try:
            start = datetime.fromisoformat(trace["start_time"])
            end = datetime.fromisoformat(trace["end_time"])
            trace["duration_seconds"] = max(0.0, (end - start).total_seconds())
        except ValueError:
            trace["duration_seconds"] = None

    return trace


def render_replay_lines(log: EventLog) -> list[str]:
    trace = build_execution_trace(log)
    events = log.replay()
    lines = [
        f"[TASK] {trace['task_id']}",
        f"Start   : {trace['start_time'] or 'unknown'}",
        f"End     : {trace['end_time'] or 'unknown'}",
        f"Provider: {trace['provider']}",
        f"Model   : {trace['model']}",
    ]
    if trace["description"]:
        lines.append(f"Task    : {trace['description']}")
    if trace["repo_path"]:
        lines.append(f"Repo    : {trace['repo_path']}")
    lines.append("")

    for event in events:
        payload = event.payload or {}
        if event.event_type == EventType.ACTION:
            action = payload.get("action", {})
            step = payload.get("step", "?")
            tool_call = action.get("tool_call")
            lines.append(f"[STEP {step}] {action.get('action_type', 'action')}")
            if action.get("thought"):
                lines.append(f"  Thought: {action['thought'][:200]}")
            if tool_call:
                lines.append(f"  Tool   : {tool_call.get('name')}")
                params = tool_call.get("params", {})
                if params:
                    lines.append(f"  Params : {params}")
        elif event.event_type == EventType.OBSERVATION:
            observation = payload.get("observation", {})
            status = observation.get("status", "unknown")
            tool = observation.get("tool_name", "unknown")
            prefix = "[OK]" if status == "success" else "[ERROR]"
            lines.append(f"{prefix} [{tool}]")
            preview = _preview_output(observation.get("output", ""))
            for line in preview.splitlines():
                lines.append(f"  {line}")
            if observation.get("error"):
                lines.append(f"  Error  : {observation['error']}")
        elif event.event_type == EventType.REFLECTION:
            lines.append(f"[WARN] Reflection: {payload.get('reason', '')}")
        elif event.event_type == EventType.TASK_COMPLETE:
            lines.append(f"[OK] Final: {payload.get('summary', '')}")
        elif event.event_type == EventType.TASK_FAILED:
            lines.append(f"[ERROR] Final: {payload.get('reason', '')}")

    if trace["modified_files"]:
        lines.append("")
        lines.append("Modified files:")
        for path in trace["modified_files"]:
            lines.append(f"  - {path}")

    if trace["test_runs"]:
        lines.append("")
        lines.append("Test runs:")
        for test_run in trace["test_runs"]:
            lines.append(f"  - [{test_run['tool']}] {test_run['summary']}")

    return lines


def _preview_output(output: str, max_lines: int = 5, max_chars: int = 400) -> str:
    if not output:
        return ""
    lines = output.splitlines()[:max_lines]
    preview = "\n".join(lines)
    if len(preview) > max_chars:
        preview = preview[:max_chars] + " ..."
    return preview


def _extract_modified_files_from_tool_call(tool_name: str | None, params: dict) -> set[str]:
    if not tool_name:
        return set()
    if tool_name == "file_write":
        path = params.get("path")
        return {str(path)} if path else set()
    if tool_name == "git_add":
        paths = params.get("paths") or []
        return {str(path) for path in paths if path and path != "."}
    if tool_name == "git_diff":
        path = params.get("path")
        return {str(path)} if path else set()
    return set()


def _extract_modified_files_from_observation(tool_name: str, output: str) -> set[str]:
    paths: set[str] = set()
    if tool_name == "file_write":
        for match in output.splitlines():
            if "path=" in match:
                paths.add(match.split("path=", 1)[1].strip())
    if tool_name.startswith("git"):
        for line in output.splitlines():
            if line.startswith("+++ b/"):
                paths.add(line[6:].strip())
            elif line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 4 and parts[3].startswith("b/"):
                    paths.add(parts[3][2:])
    return paths


def _extract_test_run(tool_name: str, output: str, status: str | None, error: str | None) -> dict | None:
    lowered = output.lower()
    if tool_name == "test" or "pytest" in lowered or "passed" in lowered or "failed" in lowered:
        summary = _extract_test_summary(output) or error or "test execution recorded"
        return {
            "tool": tool_name or "unknown",
            "status": status or "unknown",
            "summary": summary,
        }
    return None


def _extract_test_summary(output: str) -> str | None:
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if any(token in stripped for token in ("passed", "failed", "error", "skipped", "no tests")):
            return stripped
    return None
