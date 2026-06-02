from __future__ import annotations

from pathlib import Path

import pytest

from tools.file_tool import FileReadTool, FileViewTool, FileWriteTool


def test_file_read_allows_repo_internal_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "src" / "main.py"
    target.parent.mkdir()
    target.write_text("print('ok')\n", encoding="utf-8")

    result = FileReadTool(repo_root=repo).execute({"path": "src/main.py"})

    assert result.success
    assert "print('ok')" in result.output


def test_file_write_allows_repo_internal_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    result = FileWriteTool(repo_root=repo).execute(
        {"path": "src/generated.py", "content": "value = 1\n"}
    )

    assert result.success
    assert (repo / "src" / "generated.py").read_text(encoding="utf-8") == "value = 1\n"


def test_file_read_rejects_parent_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")

    result = FileReadTool(repo_root=repo).execute({"path": "../outside.txt"})

    assert not result.success
    assert result.error == "path outside repo is not allowed"


def test_file_write_rejects_absolute_path_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"

    result = FileWriteTool(repo_root=repo).execute(
        {"path": str(outside), "content": "secret"}
    )

    assert not result.success
    assert result.error == "path outside repo is not allowed"


def test_file_view_rejects_absolute_path_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    result = FileViewTool(repo_root=repo).execute({"path": str(outside), "start_line": 1})

    assert not result.success
    assert result.error == "path outside repo is not allowed"


def test_file_write_rejects_symlink_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link_dir = repo / "link"
    try:
        link_dir.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not available on this platform")

    result = FileWriteTool(repo_root=repo).execute(
        {"path": "link/escape.txt", "content": "secret"}
    )

    assert not result.success
    assert result.error == "path outside repo is not allowed"
