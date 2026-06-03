"""
GitHub Issue auto-fix demo flow.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import click

from agent.core import Agent, AgentConfig
from agent.event_log import EventLog
from agent.task import Task
from config.schema import load_config
from entry.cli import _build_app_components

logger = logging.getLogger(__name__)


def _get_github_client():
    try:
        from github import Github
    except ImportError:
        raise ImportError("PyGithub not installed. Run: pip install PyGithub")

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ValueError(
            "GITHUB_TOKEN environment variable is not set.\n"
            "Create a token at https://github.com/settings/tokens"
        )
    return Github(token)


def fetch_issue(repo_name: str, issue_number: int) -> tuple[str, str, str]:
    gh = _get_github_client()
    repo = gh.get_repo(repo_name)
    issue = repo.get_issue(issue_number)
    return issue.title, issue.body or "", issue.html_url


def create_pull_request(
    repo_name: str,
    branch: str,
    title: str,
    body: str,
    base: str = "main",
) -> str:
    gh = _get_github_client()
    repo = gh.get_repo(repo_name)
    try:
        repo.get_branch(base)
    except Exception:
        base = "master"

    pr = repo.create_pull(
        title=title,
        body=body,
        head=branch,
        base=base,
    )
    return pr.html_url


def _run_git(args: list[str], cwd: str | Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(cwd),
        )
        output = (proc.stdout + proc.stderr).strip()
        return proc.returncode == 0, output
    except Exception as exc:
        return False, str(exc)


def build_clone_url(repo_name: str) -> str:
    return f"https://github.com/{repo_name}.git"


def clone_repo(repo_name: str, local_path: str | Path) -> None:
    path = Path(local_path)
    if path.exists() and (path / ".git").exists():
        logger.info("Repo already exists at %s, skipping clone", path)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    url = build_clone_url(repo_name)
    click.echo(f"Cloning {repo_name} -> {path} ...")
    ok, out = _run_git(["clone", url, str(path)], cwd=path.parent)
    if not ok:
        raise RuntimeError(f"git clone failed: {out}")


def create_branch(local_path: str | Path, branch: str) -> None:
    ok, _ = _run_git(["checkout", "-b", branch], cwd=local_path)
    if not ok:
        _run_git(["checkout", branch], cwd=local_path)


def push_branch(local_path: str | Path, branch: str) -> None:
    ok, out = _run_git(
        ["push", "--set-upstream", "origin", branch],
        cwd=local_path,
    )
    if not ok:
        raise RuntimeError(f"git push failed: {out}")


def list_modified_files(local_path: str | Path) -> list[str]:
    ok, out = _run_git(["diff", "--name-only"], cwd=local_path)
    if not ok or not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def has_working_tree_changes(local_path: str | Path) -> bool:
    return len(list_modified_files(local_path)) > 0


def commit_all_changes(local_path: str | Path, message: str) -> tuple[bool, str]:
    ok, out = _run_git(["add", "."], cwd=local_path)
    if not ok:
        return False, out
    return _run_git(["commit", "-m", message], cwd=local_path)


def summarize_test_result(log) -> tuple[str, str]:
    try:
        from agent.task import EventType
    except ImportError:
        return ("not available", "not available")

    last_test_command = "not available"
    last_test_result = "not available"
    current_test_tool = None
    for event in log.replay():
        if event.event_type == EventType.ACTION:
            action = event.payload.get("action", {})
            tool_call = action.get("tool_call") or {}
            if tool_call.get("name") == "test":
                current_test_tool = "test"
                params = tool_call.get("params", {})
                path = params.get("path", "")
                args = params.get("args", "")
                if path or args:
                    last_test_command = f"test path={path} args={args}".strip()
                else:
                    last_test_command = "test"
            else:
                current_test_tool = None
        elif event.event_type == EventType.OBSERVATION and current_test_tool == "test":
            observation = event.payload.get("observation", {})
            status = observation.get("status", "unknown")
            output = (observation.get("output") or "").strip()
            short_output = output.splitlines()[-1] if output else status
            last_test_result = f"{status}: {short_output}"
            current_test_tool = None
    return last_test_command, last_test_result


def build_pr_body(
    *,
    issue_number: int,
    issue_title: str,
    task_summary: str,
    modified_files: list[str],
    test_command: str,
    test_result: str,
    event_log_path: str,
) -> str:
    files_block = "\n".join(f"- {path}" for path in modified_files) or "- none"
    return (
        f"Fixes #{issue_number}\n\n"
        f"## Issue\n"
        f"#{issue_number}: {issue_title}\n\n"
        f"## Summary\n"
        f"{task_summary}\n\n"
        f"## Modified Files\n"
        f"{files_block}\n\n"
        f"## Verification\n"
        f"Test command: {test_command}\n"
        f"Test result: {test_result}\n\n"
        f"## Event Log\n"
        f"{event_log_path}\n"
    )


def resolve_local_repo_path(repo_name: str, local_path: str | None) -> tuple[Path, object | None]:
    if local_path:
        return Path(local_path).resolve(), None
    temp_dir = tempfile.TemporaryDirectory(prefix="forge-agent-gh-")
    repo_dir = Path(temp_dir.name) / repo_name.split("/")[-1]
    return repo_dir, temp_dir


def run_on_issue(
    repo_name: str,
    issue_number: int,
    local_path: str | None,
    config_path: str | None = None,
    create_pr: bool = True,
    base_branch: str = "main",
    dry_run: bool = False,
) -> int:
    config = load_config(config_path)
    repo_path, temp_dir = resolve_local_repo_path(repo_name, local_path)

    try:
        click.echo(f"\nFetching issue #{issue_number} from {repo_name} ...")
        title, body, issue_url = fetch_issue(repo_name, issue_number)
        click.echo(f"  Title: {title}")
        description = f"Fix GitHub Issue #{issue_number}: {title}\n\n{body}"

        clone_repo(repo_name, repo_path)

        branch = f"agent/fix-issue-{issue_number}-{int(time.time())}"
        create_branch(repo_path, branch)
        click.echo(f"  Branch: {branch}")

        parts = _build_app_components(
            config,
            repo_path=str(repo_path),
            sandbox=False,
            confirm=False,
            chat_mode=False,
        )
        agent = Agent(
            parts["backend"],
            parts["registry"],
            AgentConfig(
                max_steps=config.agent.max_steps,
                budget_tokens=config.agent.budget_tokens,
            ),
        )
        task = Task(
            description=description,
            repo_path=str(repo_path),
            issue_url=issue_url,
            max_steps=config.agent.max_steps,
            budget_tokens=config.agent.budget_tokens,
        )

        click.echo(f"\nRunning agent on issue #{issue_number} ...")
        t0 = time.time()
        with EventLog.create(task, log_dir=config.agent.log_dir) as log:
            result = agent.run(task, log)
            elapsed = time.time() - t0
            click.echo(f"  Status : {result.status.value}")
            click.echo(f"  Steps  : {result.steps_taken}")
            click.echo(f"  Tokens : {result.total_tokens:,}")
            click.echo(f"  Time   : {elapsed:.1f}s")

            if not result.is_success():
                click.echo("  Agent did not complete the task.", err=True)
                return 1

            modified_files = list_modified_files(repo_path)
            if not modified_files:
                click.echo("  No changes detected. No PR created.")
                return 0

            commit_message = f"[Agent] Fix issue #{issue_number}: {title}"
            ok, commit_output = commit_all_changes(repo_path, commit_message)
            if not ok:
                click.echo(f"Error: git commit failed: {commit_output}", err=True)
                return 1

            test_command, test_result = summarize_test_result(log)
            pr_body = build_pr_body(
                issue_number=issue_number,
                issue_title=title,
                task_summary=result.summary,
                modified_files=modified_files,
                test_command=test_command,
                test_result=test_result,
                event_log_path=str(log.path),
            )

            if dry_run or not create_pr:
                click.echo("  Dry run complete. Changes committed locally. No PR created.")
                return 0

            click.echo("\nPushing branch ...")
            try:
                push_branch(repo_path, branch)
            except RuntimeError as exc:
                click.echo(f"Warning: push failed: {exc}", err=True)
                click.echo("Changes are committed locally. Push manually to create a PR.")
                return 0

            pr_title = f"[Agent] Fix issue #{issue_number}: {title}"
            try:
                pr_url = create_pull_request(
                    repo_name=repo_name,
                    branch=branch,
                    title=pr_title,
                    body=pr_body,
                    base=base_branch,
                )
                click.echo(f"\n[OK] PR created: {pr_url}\n")
            except Exception as exc:
                click.echo(f"Warning: PR creation failed: {exc}", err=True)
                click.echo(f"Branch pushed. Create PR manually from branch: {branch}")

        return 0
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


@click.command()
@click.option("--repo", "-r", required=True, help="GitHub repo (owner/repo)")
@click.option("--issue", "-i", required=True, type=int, help="Issue number")
@click.option(
    "--local-path", "-l", default=None,
    help="Local path to clone/use the repo. If omitted, a temporary directory is used.",
)
@click.option("--config", "-c", default=None, help="Config YAML path")
@click.option("--no-pr", is_flag=True, help="Skip push and PR creation")
@click.option("--dry-run", is_flag=True, help="Run through diff and commit checks without pushing or creating a PR")
@click.option("--base-branch", default="main", help="Base branch for PR (default: main)")
@click.option("--verbose", "-v", is_flag=True)
def main(
    repo: str,
    issue: int,
    local_path: str | None,
    config: str | None,
    no_pr: bool,
    dry_run: bool,
    base_branch: str,
    verbose: bool,
) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-7s %(name)s - %(message)s",
    )
    sys.exit(run_on_issue(
        repo_name=repo,
        issue_number=issue,
        local_path=local_path,
        config_path=config,
        create_pr=not no_pr,
        base_branch=base_branch,
        dry_run=dry_run,
    ))


if __name__ == "__main__":
    main()
