# Forge Agent Usage

## Install

```bash
git clone <repo-url>
cd forge-agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional extras:

```bash
pip install tiktoken
pip install tree-sitter-javascript tree-sitter-typescript tree-sitter-go tree-sitter-rust tree-sitter-java
```

## Configure

Edit `config/default.yaml` and set your provider/model. Provide API keys through environment variables.

Example:

```yaml
llm:
  provider: deepseek
  model: deepseek-v4-flash
  api_key: ${DEEPSEEK_API_KEY}
  base_url: https://api.deepseek.com
```

## Verify

Smoke test:

```bash
python smoke_test.py
```

Repository tests:

```bash
pytest -q
```

## Chat Mode

```bash
agent chat --repo /path/to/project
agent chat --repo /path/to/project --sandbox
agent chat --repo /path/to/project --model gpt-4o --provider openai
```

Built-in commands:

- `/exit`
- `/stats`
- `/clear`
- `/help`

Use chat mode when you want multi-round context and iteration.

## Run Mode

```bash
agent run --repo /path/to/project --task "Fix the failing tests"
agent run --repo /path/to/project --task-file task.txt
agent run --repo /path/to/project --task "..." --confirm
agent run --repo /path/to/project --task "..." --sandbox
```

Use run mode for a single well-scoped task.

## Recommended Task Style

Good task prompts are concrete:

```text
src/parser.py 中的 parse() 在空字符串输入时抛出 ValueError。
修复它，让它返回 None，并补上 tests/test_parser.py 的回归测试。
```

Avoid vague prompts like:

```text
fix bug
```

## Safety Notes

- Local shell execution has basic guardrails only.
- Commands with write risk, shell chaining, redirection, nested shells, or suspicious inline interpreters are treated as confirm-required.
- `confirm-required` is a risk classification, not an automatic prompt. In `run` mode, manual confirmation happens only when `--confirm` is enabled; without it, the command may execute directly.
- Use `--sandbox` when you need the stronger isolation boundary.

## Platform Notes

- Local execution is POSIX-first.
- On Windows, prefer `--sandbox` or WSL for more predictable behavior.
- Pytest is configured to use `.pytest_tmp` inside the repo to avoid system temp permission issues on some Windows setups.

## Logs

List logs:

```bash
agent log list
```

Show one log:

```bash
agent log show logs/<task_id>_<timestamp>.jsonl
```

Each run writes an append-only JSONL log with task start, actions, observations, reflections, and final status.
