# Forge Agent 使用说明

## 安装

```bash
git clone <repo-url>
cd forge-agent-interview-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

可选依赖：

```bash
pip install tiktoken
pip install tree-sitter-javascript tree-sitter-typescript tree-sitter-go tree-sitter-rust tree-sitter-java
pip install tree-sitter-c tree-sitter-cpp tree-sitter-ruby
```

## 配置 provider

如果你想修改默认 provider 或 model，可编辑 `config/default.yaml`。

示例：

```yaml
llm:
  provider: deepseek
  model: deepseek-v4-flash
  api_key: ${DEEPSEEK_API_KEY}
  base_url: https://api.deepseek.com
```

常见环境变量：

```bash
export ANTHROPIC_API_KEY=...
export OPENAI_API_KEY=...
export DEEPSEEK_API_KEY=...
export GROQ_API_KEY=...
```

Ollama 使用本地服务，而不是 API key。

## 运行一个基础任务

```bash
agent run --repo /path/to/project --task "Fix the failing tests"
```

从任务文件运行：

```bash
agent run --repo /path/to/project --task-file task.txt
```

## Chat 模式

```bash
agent chat --repo /path/to/project
```

内置命令：

- `/exit`
- `/stats`
- `/clear`
- `/help`

## 流式输出

`run` 模式默认启用流式输出。

```bash
agent run --repo /path/to/project --task "Investigate the failing test" --stream
```

## Docker 沙箱模式

如果你希望命令在容器中执行，可以使用沙箱模式：

```bash
agent run --repo /path/to/project --task "run pytest" --sandbox
agent chat --repo /path/to/project --sandbox
```

说明：

- Docker 沙箱是 demo-grade，不是 production 级容器安全方案。
- 如果 Docker 不可用，沙箱命令会明确失败，而不是回退到本地执行。

## Provider smoke tests

可使用 smoke harness 做最小化的 provider 专项验证：

```bash
python scripts/smoke_provider.py --provider ollama --model llama3
python scripts/smoke_provider.py --provider deepseek --model deepseek-chat
python scripts/smoke_provider.py --provider anthropic --model claude-sonnet-4-5
```

说明：

- 缺少 API key 时会给出明确的 skip / 配置提示
- Ollama 需要本地服务正在运行

## GitHub Issue dry-run demo

可在本地运行 GitHub issue 流程，而不实际创建 PR：

```bash
python -m entry.github_issue --repo owner/repo --issue 42 --local-path ./tmp/repo --dry-run
python -m entry.github_issue --repo owner/repo --issue 42 --local-path ./tmp/repo --no-pr
```

说明：

- 没有 diff 就不会创建 PR
- 有 diff 时，需要先完成 commit，之后才能 push / 创建 PR
- 实际 PR 创建依赖本地 git 凭据与 GitHub 认证

## Repo-map 验证

运行 repo-map 验证测试：

```bash
pytest tests/test_day5.py -q
pytest tests/test_repo_map_languages.py -q
```

说明：

- tree-sitter 各语言包是可选依赖
- 当可选依赖缺失时，测试会走 fallback 行为，或跳过依赖这些包的检查
- `find_symbol` 仍然是 Python-only，不应理解为完整的多语言搜索能力

## Event log replay

列出可用日志：

```bash
agent log list
```

查看审计摘要：

```bash
agent log show logs/<task_id>_<timestamp>.jsonl
```

回放执行轨迹：

```bash
agent log replay logs/<task_id>_<timestamp>.jsonl
```

## 运行测试

完整测试集：

```bash
pytest -q
```

部分验证命令：

```bash
pytest tests/test_stream.py -q
pytest tests/test_sandbox.py -q
pytest tests/test_provider_matrix.py -q
pytest tests/test_event_replay.py -q
```

## 故障排查

- 本地 shell guardrails 是启发式防护。若你需要更强的边界，请使用 `--sandbox`。
- Docker 沙箱行为依赖 Docker 已安装并正在运行。
- 真实 provider smoke 依赖 API key 或本地 Ollama。
- Event replay 是执行轨迹，不是 deterministic re-execution。
- 支持 Windows，但 POSIX shell 语义可能与原生 Windows shell 不同。
- Pytest 临时文件使用 repo 外的专用用户可写 temp 根目录，并由每次运行创建独立子目录，以避免 Windows 下固定 temp 目录清理冲突以及系统 temp 目录权限问题。
