from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from entry.cli import cli, load_task_text


def test_example_task_fix_quicksort_exists_and_nonempty() -> None:
    path = Path("examples/tasks/fix_quicksort.md")
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip()


def test_example_task_add_linked_list_tests_exists_and_nonempty() -> None:
    path = Path("examples/tasks/add_linked_list_tests.md")
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip()


def test_load_task_text_from_inline_task() -> None:
    assert load_task_text("fix it", None) == "fix it"


def test_load_task_text_from_task_file(tmp_path: Path) -> None:
    task_file = tmp_path / "task.txt"
    task_file.write_text("Fix the parser bug\n", encoding="utf-8")
    assert load_task_text(None, str(task_file)) == "Fix the parser bug"


def test_load_task_text_rejects_both_task_and_task_file(tmp_path: Path) -> None:
    task_file = tmp_path / "task.txt"
    task_file.write_text("Fix it", encoding="utf-8")
    with pytest.raises(SystemExit):
        load_task_text("inline", str(task_file))


def test_load_task_text_requires_task_or_task_file() -> None:
    with pytest.raises(SystemExit):
        load_task_text(None, None)


def test_load_task_text_rejects_missing_task_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.md"
    with pytest.raises(SystemExit):
        load_task_text(None, str(missing))


def test_load_task_text_rejects_empty_task_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit):
        load_task_text(None, str(empty))


def test_run_help_shows_task_file_option() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "--task-file" in result.output


def test_run_rejects_both_task_and_task_file(tmp_path: Path) -> None:
    runner = CliRunner()
    task_file = tmp_path / "task.txt"
    task_file.write_text("Fix it", encoding="utf-8")
    result = runner.invoke(
        cli,
        [
            "run",
            "--repo",
            str(tmp_path),
            "--task",
            "inline",
            "--task-file",
            str(task_file),
        ],
        obj={},
    )
    assert result.exit_code != 0
    assert "provide either --task or --task-file" in result.output


def test_run_rejects_missing_task_inputs(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--repo", str(tmp_path)], obj={})
    assert result.exit_code != 0
    assert "provide --task or --task-file" in result.output


def test_run_rejects_missing_task_file(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            "--repo",
            str(tmp_path),
            "--task-file",
            str(tmp_path / "missing.md"),
        ],
        obj={},
    )
    assert result.exit_code != 0
    assert "task file does not exist" in result.output


def test_run_rejects_empty_task_file(tmp_path: Path) -> None:
    runner = CliRunner()
    task_file = tmp_path / "empty.md"
    task_file.write_text("", encoding="utf-8")
    result = runner.invoke(
        cli,
        [
            "run",
            "--repo",
            str(tmp_path),
            "--task-file",
            str(task_file),
        ],
        obj={},
    )
    assert result.exit_code != 0
    assert "task file is empty" in result.output
