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
