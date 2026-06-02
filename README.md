# Forge Agent

一个面向代码仓库任务的 coding agent 项目。它实现了一个可运行的 ReAct 循环，支持多 LLM backend、工具调用、repo 摘要注入、持续对话、事件日志和 Docker sandbox。

这个项目的目标不是“功能越多越好”，而是把核心 agent 组件做成一个可以解释、可以测试、可以展示工程判断的个人项目。

## What It Demonstrates

- ReAct orchestration: `agent/core.py` 负责消息构建、LLM 调用、工具执行、反思触发和终止条件。
- Tool-driven coding workflow: 文件读写、搜索、shell、pytest、git 都通过统一 `ToolRegistry` 暴露给模型。
- Multi-backend model routing: 支持 Anthropic 与 OpenAI-compatible providers，包括 DeepSeek、Groq、Ollama。
- Context compression: 用 repo-map 和 token budget 控制大仓库上下文。
- Auditable runs: 每次任务写入 append-only JSONL event log，可回放和统计。
- Safer execution defaults: shell 工具提供基础防误操作分类；需要更强隔离时使用 Docker sandbox。

## What It Does Not Claim

- `shell` 不是强安全沙箱。它只做基础分类和确认，不能替代容器隔离。
- Windows 本地运行是可用的，但命令语义仍然偏 POSIX-first；需要更稳定的一致性时优先使用 `--sandbox` 或 WSL。
- “无编辑步数” 是基于受信工具元数据的保守估计，不是文件系统级精确变更检测。
- 这个项目优先展示 agent 架构与工程取舍，不追求生产级 autonomy / security / sandbox hardening。

## Quick Start

```bash
git clone <repo-url>
cd forge-agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

配置 `config/default.yaml`，并通过环境变量提供 API Key：

```bash
export DEEPSEEK_API_KEY=sk-xxx
# or ANTHROPIC_API_KEY / OPENAI_API_KEY / GROQ_API_KEY
```

推荐先跑 smoke test：

```bash
python smoke_test.py
```

## Recommended Verification

仓库内推荐的基础验证命令：

```bash
pytest -q
```

`pyproject.toml` 已固定 `--basetemp=.pytest_tmp`，避免默认系统临时目录在某些 Windows 环境下的权限问题。

## Usage

### Chat mode

```bash
agent chat --repo /path/to/project
agent chat --repo /path/to/project --sandbox
```

适合持续对话、多轮迭代。内置命令：

- `/exit`
- `/stats`
- `/clear`
- `/help`

### Run mode

```bash
agent run --repo /path/to/project --task "Fix the failing tests"
agent run --repo /path/to/project --task-file task.txt
agent run --repo /path/to/project --task "..." --confirm
agent run --repo /path/to/project --task "..." --sandbox
```

## Architecture

```text
entry (cli/chat/github issue)
  -> agent core
  -> llm backend
  -> tool registry + runtime
  -> context helpers
```

Key files:

- `agent/core.py`: ReAct loop
- `agent/event_log.py`: append-only event log
- `llm/router.py`: backend selection
- `tools/`: tool implementations
- `context/repo_map.py`: repo summary generation
- `context/token_budget.py`: token trimming rules

## Safety Model

`tools/shell_tool.py` 将命令分成三类：

- Hard blocked: 明显危险命令直接拒绝。
- Read-only pass-through: 明确只读命令直接执行。
- Confirm-required: 含写风险、shell 拼接、重定向、嵌套 shell、可疑 inline interpreter 命令时要求确认；在 `run` 模式下若未开启 `--confirm`，会跳过人工确认直接执行。

如果你要在面试里回答“它安全吗”，更准确的表述是：

- 本地 shell 只有基础 guardrails。
- 真正可信的隔离边界是 `DockerRuntime`。

## Context Handling

- 首条任务消息始终保留。
- 历史会按 token budget 裁剪。
- tool transcript 以原子块保留：`assistant(tool_call)` 与对应 `tool` observation 不会被拆开。

这能避免长会话下生成不合法的 tool history。

## Logging

每次运行生成一个 JSONL event log，记录：

- task start
- action
- observation
- reflection
- task complete / failed

日志实例显式绑定真实 `task_id`，不会再通过文件名猜测，避免带下划线的 task id 被错误截断。

## Known Trade-offs / Boundaries

- 没有实现多工具并发调用。
- 没有做严格 shell AST 级解析，只做保守规则分类。
- repo-map 仍是轻量实现，适合面试项目，不是大型生产仓库的最终形态。
- 部分能力更偏“可解释的工程样例”，不是生产级 agent platform。

## Why This Is a Better Interview Project Now

相比单纯“能跑”的 demo，这个版本更适合 agent / systems 面试追问：

- 文档承诺与实现更一致。
- 关键边界有测试覆盖。
- 安全、上下文、日志、运行语义的取舍是明确的，而不是隐含的。

## More

更详细的命令示例见 [USAGE.md](/abs/path/C:/Users/DELL/Desktop/forge-agent-main/USAGE.md)。
