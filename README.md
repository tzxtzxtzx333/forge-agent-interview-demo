# Forge Agent

## Project Overview

Forge Agent is a runnable, verifiable, auditable coding agent MVP built on top of the upstream `forge-agent` project. This fork focuses on engineering hardening and claims-backed documentation: repo-scoped file editing, test execution, streaming CLI output, provider routing, Docker sandbox verification, GitHub Issue demo flow, repo-map verification, and execution-trace replay.

This project is not positioned as a Claude Code replacement and it is not documented as a production-grade security sandbox.

## What This Project Supports

- ReAct-style coding loop for exploring a repo, calling tools, reflecting, and finishing a task
- Repo-bound file read/write operations
- Shell, pytest, and git tool execution
- Streaming output in `run` and `chat`
- Multi-provider routing for Anthropic, OpenAI, DeepSeek, Groq, and Ollama
- Demo-grade Docker sandbox execution
- GitHub Issue to local fix / commit / PR demo flow
- Multi-language repo-map symbol extraction
- Append-only JSONL event logs with replayable execution trace
- Windows-safe ASCII CLI output

## Feature Verification Matrix

| Feature | Status | Implementation | Tests | Verify |
|---|---|---|---|---|
| ReAct coding loop | Stable MVP | `agent/core.py`, `agent/task.py` | `tests/test_day2.py`, `tests/test_day7.py` | `pytest tests/test_day2.py tests/test_day7.py -q` |
| Repo-bound file tools | Stable | `tools/file_tool.py` | `tests/test_file_tool_repo_boundary.py` | `pytest tests/test_file_tool_repo_boundary.py -q` |
| Shell / test / git tools | Stable | `tools/shell_tool.py`, `tools/test_tool.py`, `tools/git_tool.py` | `tests/test_day3.py`, `tests/test_sandbox.py` | `pytest tests/test_day3.py tests/test_sandbox.py -q` |
| Streaming output | Stable | `entry/cli.py`, `agent/core.py`, `llm/openai_compat.py`, `llm/anthropic_backend.py` | `tests/test_stream.py` | `pytest tests/test_stream.py -q` |
| Provider routing | Verified | `llm/router.py`, `llm/provider_matrix.py` | `tests/test_day4.py`, `tests/test_provider_matrix.py` | `pytest tests/test_day4.py tests/test_provider_matrix.py -q` |
| Real provider smoke | Environment-dependent | `llm/provider_smoke.py`, `scripts/smoke_provider.py` | `tests/test_provider_matrix.py` | `python scripts/smoke_provider.py --provider ollama --model llama3` |
| Docker sandbox | Demo-grade | `tools/runtime.py` | `tests/test_sandbox.py` | `pytest tests/test_sandbox.py -q` |
| GitHub Issue -> PR flow | Demo-grade | `entry/github_issue.py` | `tests/test_day6.py`, `tests/test_github_issue_flow.py` | `python -m entry.github_issue --repo owner/repo --issue 42 --local-path ./tmp/repo --dry-run` |
| Repo-map multi-language symbols | Verified fixtures | `context/repo_map.py` | `tests/test_day5.py`, `tests/test_repo_map_languages.py` | `pytest tests/test_day5.py tests/test_repo_map_languages.py -q` |
| Event log replay / auditability | Stable MVP | `agent/event_log.py`, `entry/cli.py` | `tests/test_day1.py`, `tests/test_day6.py`, `tests/test_event_replay.py` | `pytest tests/test_event_replay.py -q` |
| Windows-safe CLI output | Stable | `entry/cli.py`, CLI scripts | `pytest -q` | `python -m entry.cli --help` |

## Quick Start

```bash
git clone <repo-url>
cd forge-agent-interview-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional extras:

```bash
pip install tiktoken
pip install tree-sitter-javascript tree-sitter-typescript tree-sitter-go tree-sitter-rust tree-sitter-java
pip install tree-sitter-c tree-sitter-cpp tree-sitter-ruby
```

Provider configuration is environment-variable driven. Example:

```bash
export DEEPSEEK_API_KEY=sk-xxx
# or ANTHROPIC_API_KEY / OPENAI_API_KEY / GROQ_API_KEY
```

Run a basic task:

```bash
agent run --repo . --task "Fix the failing tests"
```

## Core Architecture

```text
entry (cli/chat/github issue)
  -> agent core
  -> llm backend / router
  -> tool registry + runtime
  -> context helpers
  -> event log / replay
```

Key files:

- `agent/core.py`: ReAct loop
- `agent/event_log.py`: append-only JSONL event log and execution trace helpers
- `llm/router.py`: provider selection
- `tools/`: file, shell, test, git, and runtime layers
- `context/repo_map.py`: repo summary and symbol extraction

## Provider Support

Supported routing targets:

- Anthropic
- OpenAI
- DeepSeek
- Groq
- Ollama

Provider verification is backed by:

- `tests/test_day4.py`
- `tests/test_provider_matrix.py`
- `scripts/smoke_provider.py`
- [docs/providers.md](docs/providers.md)

Use the smoke harness for environment-specific checks:

```bash
python scripts/smoke_provider.py --provider ollama --model llama3
python scripts/smoke_provider.py --provider deepseek --model deepseek-chat
```

## Docker Sandbox

The Docker sandbox is documented as a demo-grade container boundary, not a production security product.

Current behavior is backed by:

- `tools/runtime.py`
- `tests/test_sandbox.py`

Verification:

```bash
pytest tests/test_sandbox.py -q
```

Boundary notes:

- local shell guardrails are heuristic
- Docker sandbox defaults to stable limits such as `--network none`
- advanced isolation guarantees are out of scope for this project

## GitHub Issue -> PR Demo Flow

The GitHub entrypoint is intended for demo flow validation, not unattended production automation.

Current behavior is backed by:

- `entry/github_issue.py`
- `tests/test_day6.py`
- `tests/test_github_issue_flow.py`

Verification:

```bash
pytest tests/test_day6.py tests/test_github_issue_flow.py -q
python -m entry.github_issue --repo owner/repo --issue 42 --local-path ./tmp/repo --dry-run
```

Notes:

- no diff means no push and no PR
- diff requires `git add` and `git commit`
- real push / PR creation depends on local git credentials and GitHub auth

## Repo-map

Repo-map is lightweight multi-language symbol extraction for prompt context, not full semantic code intelligence.

Current behavior is backed by:

- `context/repo_map.py`
- `tests/test_day5.py`
- `tests/test_repo_map_languages.py`

Verification:

```bash
pytest tests/test_day5.py tests/test_repo_map_languages.py -q
```

Supported fixture-verified languages:

- Python
- JavaScript
- TypeScript
- Go
- Rust
- Java
- C
- C++
- Ruby

`tools/find_symbol` remains a Python-only regex helper. It is not documented as full multi-language symbol search.

## Event Log / Replay

Each run writes an append-only JSONL log and can be replayed as an execution trace.

Current behavior is backed by:

- `agent/event_log.py`
- `tests/test_day1.py`
- `tests/test_event_replay.py`
- `entry/cli.py`

Verification:

```bash
pytest tests/test_event_replay.py -q
agent log show logs/<task_id>_<timestamp>.jsonl
agent log replay logs/<task_id>_<timestamp>.jsonl
```

Replay is an execution trace for auditability. It is not deterministic re-execution.

## Safety Model and Limitations

- Local shell guardrails are not a strong sandbox.
- Docker sandbox is demo-grade, not production container security.
- Real provider smoke depends on API keys or local Ollama.
- GitHub PR flow depends on local git credentials and GitHub authentication.
- Repo-map is symbol extraction, not full semantic code intelligence.
- Event replay is an execution trace, not deterministic re-execution.
- Windows is supported, but POSIX shell semantics may differ.
- This project is an MVP coding agent, not a production autonomy platform.

## Test and Verification

Primary verification commands:

```bash
pytest -q
python scripts/smoke_provider.py --help
python -m entry.cli --help
python -m entry.cli log --help
```

Latest local verification in this workspace:

- `pytest -q` -> `468 passed, 18 skipped`

Pytest temp files use a dedicated user-writable temp root outside the repo and outside the system temp directory, with pytest-managed per-run subdirectories to avoid Windows cleanup collisions.

For day-to-day operation details, see [USAGE.md](USAGE.md).

## Upstream / Attribution

This project is based on the upstream `forge-agent` repository. This fork does not claim the original framework was built entirely from scratch here.

The V2 work in this fork focuses on:

- engineering hardening
- claims-backed documentation
- provider verification and smoke harnesses
- Docker sandbox verification
- GitHub Issue demo flow verification
- repo-map multi-language verification
- event log replay and auditability
