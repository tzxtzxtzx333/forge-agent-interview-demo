from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_config(tmp_path):
    return SimpleNamespace(
        agent=SimpleNamespace(max_steps=5, budget_tokens=1000, log_dir=str(tmp_path / "logs")),
    )


def _make_result(summary="fixed", status="success"):
    result = MagicMock()
    result.summary = summary
    result.status = SimpleNamespace(value=status)
    result.steps_taken = 2
    result.total_tokens = 42
    result.is_success.return_value = True
    return result


class _FakeEventLog:
    def __init__(self, path, events=None):
        self.path = Path(path)
        self._events = events or []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def replay(self):
        return list(self._events)


def _make_test_events():
    return [
        SimpleNamespace(
            event_type=SimpleNamespace(value="action"),
            payload={
                "action": {
                    "tool_call": {
                        "name": "test",
                        "params": {"path": "tests/", "args": "-q"},
                    }
                }
            },
        ),
        SimpleNamespace(
            event_type=SimpleNamespace(value="observation"),
            payload={
                "observation": {
                    "status": "success",
                    "output": "1 passed in 0.10s",
                }
            },
        ),
    ]


class TestGitHubIssueFlow:
    def test_no_diff_skips_push_and_pr(self, tmp_path):
        from entry.github_issue import run_on_issue

        fake_log = _FakeEventLog(tmp_path / "logs" / "run.jsonl")
        backend_parts = {"backend": MagicMock(), "registry": MagicMock()}
        agent_instance = MagicMock()
        agent_instance.run.return_value = _make_result()

        with patch("entry.github_issue.fetch_issue", return_value=("Fix bug", "body", "url")), \
             patch("entry.github_issue.clone_repo"), \
             patch("entry.github_issue.create_branch"), \
             patch("entry.github_issue.list_modified_files", return_value=[]), \
             patch("entry.github_issue.push_branch") as push_mock, \
             patch("entry.github_issue.create_pull_request") as pr_mock, \
             patch("entry.github_issue.load_config", return_value=_make_config(tmp_path)), \
             patch("entry.github_issue._build_app_components", return_value=backend_parts), \
             patch("entry.github_issue.Agent", return_value=agent_instance), \
             patch("entry.github_issue.EventLog.create", return_value=fake_log):
            code = run_on_issue("owner/repo", 1, str(tmp_path), dry_run=False, create_pr=True)

        assert code == 0
        push_mock.assert_not_called()
        pr_mock.assert_not_called()

    def test_diff_requires_add_and_commit_before_pr(self, tmp_path):
        from entry.github_issue import run_on_issue

        fake_log = _FakeEventLog(tmp_path / "logs" / "run.jsonl", events=_make_test_events())
        backend_parts = {"backend": MagicMock(), "registry": MagicMock()}
        agent_instance = MagicMock()
        agent_instance.run.return_value = _make_result(summary="updated files")

        with patch("entry.github_issue.fetch_issue", return_value=("Fix bug", "body", "url")), \
             patch("entry.github_issue.clone_repo"), \
             patch("entry.github_issue.create_branch"), \
             patch("entry.github_issue.list_modified_files", return_value=["src/a.py", "tests/test_a.py"]), \
             patch("entry.github_issue.commit_all_changes", return_value=(True, "committed")) as commit_mock, \
             patch("entry.github_issue.push_branch"), \
             patch("entry.github_issue.create_pull_request", return_value="https://github.com/pull/1"), \
             patch("entry.github_issue.load_config", return_value=_make_config(tmp_path)), \
             patch("entry.github_issue._build_app_components", return_value=backend_parts), \
             patch("entry.github_issue.Agent", return_value=agent_instance), \
             patch("entry.github_issue.EventLog.create", return_value=fake_log):
            code = run_on_issue("owner/repo", 1, str(tmp_path), dry_run=False, create_pr=True)

        assert code == 0
        commit_mock.assert_called_once()

    def test_dry_run_stops_before_push_and_pr(self, tmp_path):
        from entry.github_issue import run_on_issue

        fake_log = _FakeEventLog(tmp_path / "logs" / "run.jsonl", events=_make_test_events())
        backend_parts = {"backend": MagicMock(), "registry": MagicMock()}
        agent_instance = MagicMock()
        agent_instance.run.return_value = _make_result()

        with patch("entry.github_issue.fetch_issue", return_value=("Fix bug", "body", "url")), \
             patch("entry.github_issue.clone_repo"), \
             patch("entry.github_issue.create_branch"), \
             patch("entry.github_issue.list_modified_files", return_value=["src/a.py"]), \
             patch("entry.github_issue.commit_all_changes", return_value=(True, "committed")), \
             patch("entry.github_issue.push_branch") as push_mock, \
             patch("entry.github_issue.create_pull_request") as pr_mock, \
             patch("entry.github_issue.load_config", return_value=_make_config(tmp_path)), \
             patch("entry.github_issue._build_app_components", return_value=backend_parts), \
             patch("entry.github_issue.Agent", return_value=agent_instance), \
             patch("entry.github_issue.EventLog.create", return_value=fake_log):
            code = run_on_issue("owner/repo", 1, str(tmp_path), dry_run=True, create_pr=True)

        assert code == 0
        push_mock.assert_not_called()
        pr_mock.assert_not_called()

    def test_pr_body_contains_files_and_test_result(self, tmp_path):
        from entry.github_issue import build_pr_body

        body = build_pr_body(
            issue_number=7,
            issue_title="Fix parser",
            task_summary="Adjusted parser behavior",
            modified_files=["src/parser.py", "tests/test_parser.py"],
            test_command="test path=tests/ args=-q",
            test_result="success: 1 passed in 0.10s",
            event_log_path=str(tmp_path / "logs" / "run.jsonl"),
        )

        assert "#7: Fix parser" in body
        assert "- src/parser.py" in body
        assert "- tests/test_parser.py" in body
        assert "Test command: test path=tests/ args=-q" in body
        assert "Test result: success: 1 passed in 0.10s" in body
        assert "run.jsonl" in body

    def test_temp_repo_path_is_windows_safe(self):
        from entry.github_issue import resolve_local_repo_path

        repo_path, temp_dir = resolve_local_repo_path("owner/repo", None)
        try:
            assert isinstance(repo_path, Path)
            assert repo_path.name == "repo"
            assert temp_dir is not None
        finally:
            temp_dir.cleanup()

    def test_clone_repo_does_not_embed_token_in_url(self, tmp_path, monkeypatch):
        from entry.github_issue import clone_repo

        recorded = {}

        def fake_run_git(args, cwd):
            recorded["args"] = args
            recorded["cwd"] = cwd
            return True, ""

        monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
        with patch("entry.github_issue._run_git", side_effect=fake_run_git):
            clone_repo("owner/repo", tmp_path / "repo")

        clone_args = recorded["args"]
        assert clone_args[0] == "clone"
        assert "secret-token" not in " ".join(clone_args)
