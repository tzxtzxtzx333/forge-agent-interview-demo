# Forge Agent Usage

## Install

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

## Configure providers

Edit `config/default.yaml` if you want to change provider or model defaults.

Example:

```yaml
llm:
  provider: deepseek
  model: deepseek-v4-flash
  api_key: ${DEEPSEEK_API_KEY}
  base_url: https://api.deepseek.com
```

Common environment variables:

```bash
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
export DEEPSEEK_API_KEY=...
export GROQ_API_KEY=...
```

Ollama uses a local server instead of an API key.

## Run a basic task

```bash
agent run --repo /path/to/project --task "Fix the failing tests"
```

Run from a task file:

```bash
agent run --repo /path/to/project --task-file task.txt
```

## Chat mode

```bash
agent chat --repo /path/to/project
```

Built-in commands:

- `/exit`
- `/stats`
- `/clear`
- `/help`

## Streaming output

Streaming is enabled by default in `run`.

```bash
agent run --repo /path/to/project --task "Investigate the failing test" --stream
```

## Docker sandbox mode

Use sandbox mode when you want containerized command execution:

```bash
agent run --repo /path/to/project --task "run pytest" --sandbox
agent chat --repo /path/to/project --sandbox
```

Notes:

- Docker sandbox is demo-grade, not production container security.
- If Docker is unavailable, sandboxed commands fail clearly instead of falling back to local execution.

## Provider smoke tests

Use the smoke harness for minimal provider-specific verification:

```bash
python scripts/smoke_provider.py --provider ollama --model llama3
python scripts/smoke_provider.py --provider deepseek --model deepseek-chat
python scripts/smoke_provider.py --provider anthropic --model claude-sonnet-4-5
```

Notes:

- missing API keys produce a clear skip/configuration message
- Ollama requires a running local server

## GitHub Issue dry-run demo

Run the GitHub issue flow locally without creating a PR:

```bash
python -m entry.github_issue --repo owner/repo --issue 42 --local-path ./tmp/repo --dry-run
python -m entry.github_issue --repo owner/repo --issue 42 --local-path ./tmp/repo --no-pr
```

Notes:

- no diff means no PR
- diff requires commit before push / PR
- real PR creation depends on local git credentials and GitHub auth

## Repo-map verification

Run the repo-map verification suite:

```bash
pytest tests/test_day5.py -q
pytest tests/test_repo_map_languages.py -q
```

Notes:

- tree-sitter language packages are optional
- when optional packages are missing, tests use fallback behavior or skip package-specific checks
- `find_symbol` remains Python-only and is not documented as full multi-language search

## Event log replay

List available logs:

```bash
agent log list
```

Show audit summary:

```bash
agent log show logs/<task_id>_<timestamp>.jsonl
```

Replay execution trace:

```bash
agent log replay logs/<task_id>_<timestamp>.jsonl
```

## Running tests

Full test suite:

```bash
pytest -q
```

Selected verification commands:

```bash
pytest tests/test_stream.py -q
pytest tests/test_sandbox.py -q
pytest tests/test_provider_matrix.py -q
pytest tests/test_event_replay.py -q
```

## Troubleshooting

- Local shell guardrails are heuristic. Use `--sandbox` when you want a stronger boundary.
- Docker sandbox behavior depends on Docker being installed and running.
- Real provider smoke depends on API keys or local Ollama.
- Event replay is an execution trace, not deterministic re-execution.
- Windows is supported, but POSIX shell semantics may differ from native Windows shells.
- Pytest temp files use a dedicated user-writable temp root outside the repo, with per-run subdirectories to avoid fixed temp-directory cleanup collisions and system temp-directory permission issues on Windows.
