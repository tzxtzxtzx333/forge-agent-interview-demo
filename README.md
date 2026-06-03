# Forge Agent

## 项目概览

Forge Agent 是一个面向终端的 AI 编程智能体 MVP，能够检查代码仓库、调用工具、编辑文件、运行测试、在多个 LLM provider 之间切换、执行 demo-grade 的沙箱命令、处理 GitHub Issue、构建轻量级仓库上下文，并生成可回放的 JSONL 执行轨迹。

这个项目采用更适合简历展示的包装方式，但仍然坚持 claims-backed 原则：强调可验证的实现、可直接运行的命令，以及明确写清楚的能力边界，而不是空泛的产品化承诺。

## 当前项目支持的能力

- 基于 ReAct 风格的编程循环，可探索仓库、调用工具、反思并完成任务
- 仓库边界内的文件读写
- shell、pytest 和 git 工具执行
- `run` 与 `chat` 模式下的流式输出
- Anthropic、OpenAI、DeepSeek、Groq、Ollama 多 provider 路由
- demo-grade Docker 沙箱执行
- GitHub Issue 到本地修复 / commit / PR 的 demo 流程
- 多语言 repo-map 符号提取
- 追加写入式 JSONL event log 与可回放执行轨迹
- Windows-safe 的 ASCII CLI 输出

## Engineering Evidence

| Capability | Implementation | Verification |
|---|---|---|
| ReAct-style coding loop | `agent/core.py`, `agent/task.py` | `pytest tests/test_day2.py tests/test_day7.py -q` |
| Repo-scoped file editing | `tools/file_tool.py` | `pytest tests/test_file_tool_repo_boundary.py -q` |
| Shell / pytest / git tool execution | `tools/shell_tool.py`, `tools/test_tool.py`, `tools/git_tool.py` | `pytest tests/test_day3.py tests/test_sandbox.py -q` |
| Streaming CLI output | `entry/cli.py`, `agent/core.py`, `llm/openai_compat.py`, `llm/anthropic_backend.py` | `pytest tests/test_stream.py -q` |
| Multi-provider routing | `llm/router.py`, `llm/provider_matrix.py`, `scripts/smoke_provider.py` | `pytest tests/test_day4.py tests/test_provider_matrix.py -q` |
| Demo-grade Docker runtime | `tools/runtime.py` | `pytest tests/test_sandbox.py -q` |
| GitHub Issue-to-patch demo flow | `entry/github_issue.py` | `pytest tests/test_day6.py tests/test_github_issue_flow.py -q` |
| Multi-language repo-map | `context/repo_map.py` | `pytest tests/test_day5.py tests/test_repo_map_languages.py -q` |
| Event log replay / auditability | `agent/event_log.py`, `entry/cli.py` | `pytest tests/test_event_replay.py -q` |
| Windows-safe CLI behavior | `entry/cli.py`, CLI scripts | `pytest -q` and `python -m entry.cli --help` |

## 快速开始

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

Provider 配置通过环境变量完成，示例：

```bash
export DEEPSEEK_API_KEY=sk-xxx
# 或者 ANTHROPIC_API_KEY / OPENAI_API_KEY / GROQ_API_KEY
```

运行一个基础任务：

```bash
agent run --repo . --task "Fix the failing tests"
```

## 核心架构

```text
entry (cli/chat/github issue)
  -> agent core
  -> llm backend / router
  -> tool registry + runtime
  -> context helpers
  -> event log / replay
```

关键文件：

- `agent/core.py`：ReAct 循环
- `agent/event_log.py`：追加写入式 JSONL event log 与执行轨迹辅助能力
- `llm/router.py`：provider 选择
- `tools/`：文件、shell、test、git 与 runtime 层
- `context/repo_map.py`：仓库摘要与符号提取

## Provider 支持

当前支持的路由目标：

- Anthropic
- OpenAI
- DeepSeek
- Groq
- Ollama

对应的验证材料：

- `tests/test_day4.py`
- `tests/test_provider_matrix.py`
- `scripts/smoke_provider.py`
- [docs/providers.md](docs/providers.md)

可使用 smoke harness 做环境相关验证：

```bash
python scripts/smoke_provider.py --provider ollama --model llama3
python scripts/smoke_provider.py --provider deepseek --model deepseek-chat
```

## Docker 沙箱

这里的 Docker runtime 被定义为 demo-grade 执行边界，用于受控命令运行。

对应的实现与验证：

- `tools/runtime.py`
- `tests/test_sandbox.py`

验证命令：

```bash
pytest tests/test_sandbox.py -q
```

边界说明：

- 本地 shell guardrails 属于启发式防护
- Docker 沙箱默认启用例如 `--network none` 这样的稳定限制
- 更高级别的隔离保证不在本项目范围内

## GitHub Issue -> PR Demo Flow

GitHub 入口被设计为一个 Issue-to-patch demo flow，用于把一个已跟踪的 Issue 转成一次本地修复、commit，以及可选的 PR 交付。

对应的实现与验证：

- `entry/github_issue.py`
- `tests/test_day6.py`
- `tests/test_github_issue_flow.py`

验证命令：

```bash
pytest tests/test_day6.py tests/test_github_issue_flow.py -q
python -m entry.github_issue --repo owner/repo --issue 42 --local-path ./tmp/repo --dry-run
```

说明：

- 没有 diff 就不会 push，也不会创建 PR
- 有 diff 时需要 `git add` 与 `git commit`
- 实际 push / PR 创建依赖本地 git 凭据与 GitHub 认证

## Repo-map

Repo-map 是面向提示上下文的轻量级多语言符号提取，不是完整语义级代码理解。

对应的实现与验证：

- `context/repo_map.py`
- `tests/test_day5.py`
- `tests/test_repo_map_languages.py`

验证命令：

```bash
pytest tests/test_day5.py tests/test_repo_map_languages.py -q
```

当前通过 fixture 验证的语言：

- Python
- JavaScript
- TypeScript
- Go
- Rust
- Java
- C
- C++
- Ruby

`tools/find_symbol` 仍然只是 Python-only 的正则辅助工具，并没有被表述为完整的多语言符号搜索。

## Event Log / Replay

每次运行都会写入追加式 JSONL 日志，并且可以回放为一条执行轨迹。

对应的实现与验证：

- `agent/event_log.py`
- `tests/test_day1.py`
- `tests/test_event_replay.py`
- `entry/cli.py`

验证命令：

```bash
pytest tests/test_event_replay.py -q
agent log show logs/<task_id>_<timestamp>.jsonl
agent log replay logs/<task_id>_<timestamp>.jsonl
```

Replay 的定位是用于审计的 execution trace，不是 deterministic re-execution。

## 测试与验证

主要验证命令：

```bash
pytest -q
python scripts/smoke_provider.py --help
python -m entry.cli --help
python -m entry.cli log --help
```

当前工作区的 baseline 验证方式：

- 运行 `pytest -q` 来确认当前 baseline。具体的 pass / skip 数字可能会因为可选依赖与本地环境而变化。

Pytest 临时文件使用 repo 外、系统 temp 外的专用用户可写 temp 根目录，并由 pytest 为每次运行管理独立子目录，以避免 Windows 下的清理冲突。

日常使用说明见 [USAGE.md](USAGE.md)。

## Scope & Boundaries

- 这是一个面向工程验证的 MVP，重点是可运行的 agent 工作流与可验证的命令路径。
- Docker runtime 是 demo-grade，不应被理解为 production-grade 的安全沙箱。
- GitHub PR 创建依赖本地 git 凭据与 GitHub 认证。
- Repo-map 是面向提示上下文的轻量级符号提取，不是完整语义级代码理解。
