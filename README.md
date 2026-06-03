# Forge Agent

面向代码仓库工作流的终端式 AI Coding Agent 工程化 MVP。给它一个自然语言任务，它可以探索仓库、调用工具、修改文件、运行测试，并根据 observation 持续迭代，直到完成、失败退出或触发边界条件。

支持 **Anthropic、DeepSeek、OpenAI、Groq、Ollama** 多种模型，提供流式 CLI 输出、ReAct 主循环、`agent run` / `agent chat` / `python -m entry.github_issue` 三种任务使用路径，以及 `agent log` 日志查看与 replay 辅助命令。

---

## 快速开始

```bash
# 克隆并安装
git clone https://github.com/tzxtzxtzx333/forge-agent-interview-demo.git
cd forge-agent-interview-demo
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

# 配置 Provider API Key
export DEEPSEEK_API_KEY=sk-xxx
# 或者使用 ANTHROPIC_API_KEY / OPENAI_API_KEY / GROQ_API_KEY

# 验证 CLI 和 Provider smoke 命令存在
python -m entry.cli --help
python scripts/smoke_provider.py --help

# 开始使用
agent run --repo . --task "Fix the failing tests"
```

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:DEEPSEEK_API_KEY="sk-xxx"
python -m entry.cli --help
python scripts/smoke_provider.py --help
```

---

## 使用方式

### `agent chat`（推荐）

持续对话式终端 Coding Agent 工作流，每轮历史保留，适合围绕真实代码仓库连续完成分析、修改和验证。

```bash
agent chat
agent chat --repo /path/to/project
agent chat --model deepseek-v4-pro
agent chat --sandbox
```

对话内命令：

- `/exit` 或 `/quit`：退出会话
- `/stats`：查看 session 统计
- `/clear`：清空当前 history
- `/help`：查看内置命令说明

### `agent run`

一次性任务执行，适合明确、可收敛的仓库任务。

```bash
agent run --repo . --task "Fix the failing tests"
agent run --repo . --task-file examples/tasks/fix_quicksort.md
agent run --repo . --task "..." --confirm
agent run --repo . --task "..." --sandbox
```

### `python -m entry.github_issue`

GitHub Issue-to-patch 独立演示入口，用于从 Issue 描述构造任务并驱动本地修复流程。它是独立入口，不是 `agent` 根命令下的子命令。

```bash
python -m entry.github_issue --help
python -m entry.github_issue \
  --repo owner/repo \
  --issue 42 \
  --local-path /path/to/repo
```

### `agent log`

日志查看与 replay 的辅助命令，用于检查 JSONL event log、统计工具调用和回放执行轨迹。

```bash
agent log list
agent log show <log-file.jsonl>
agent log replay <log-file.jsonl>
```

其中 `<log-file.jsonl>` 需要替换为实际生成的日志文件路径。

---

## 配置

编辑 `config/default.yaml`：

```yaml
llm:
  provider: deepseek
  model: deepseek-v4-flash
  api_key: ${DEEPSEEK_API_KEY}
  base_url: https://api.deepseek.com

agent:
  max_steps: 40
  budget_tokens: 80000

context:
  repo_map_budget: 8000
  history_window: 20
```

Provider 支持：

- `anthropic`
- `openai`
- `deepseek`
- `groq`
- `ollama`

CLI 参数如 `--provider`、`--model`、`--max-steps` 可覆盖默认配置。

---

## 项目结构

```text
forge-agent-interview-demo/
├── agent/                # Agent Core、任务结构、事件日志、prompt 组装
│   ├── core.py
│   ├── task.py
│   ├── event_log.py
│   └── prompt.py
├── llm/                  # Backend、Router、Provider Matrix
│   ├── base.py
│   ├── anthropic_backend.py
│   ├── openai_compat.py
│   ├── provider_matrix.py
│   └── router.py
├── tools/                # File / Shell / Pytest / Git / Search / Runtime
│   ├── file_tool.py
│   ├── shell_tool.py
│   ├── test_tool.py
│   ├── git_tool.py
│   ├── search_tool.py
│   └── runtime.py
├── context/              # RepoMap、TokenBudget、History
│   ├── repo_map.py
│   ├── token_budget.py
│   └── history.py
├── entry/                # CLI、Chat Session、GitHub Issue 独立入口
│   ├── cli.py
│   ├── chat.py
│   └── github_issue.py
├── config/
│   ├── default.yaml
│   └── schema.py
├── examples/             # task-file 演示任务
├── tests/
├── README.md
└── USAGE.md
```

---

## 核心特性

### ReAct 主循环

这里的 ReAct 指 Reasoning + Acting 的工程范式，即模型在任务执行中交替进行决策、工具调用和结果观察；项目并不是复现某一篇论文的实验设定，而是将这一范式应用到 Coding Agent 场景。

### 多 Provider 路由

- Anthropic 原生后端
- OpenAI-compatible 路由：OpenAI / DeepSeek / Groq / Ollama
- 支持在配置文件和 CLI 参数层切换 Provider / Model

### 多语言符号级摘要

`repo-map` 用于上下文压缩和仓库结构导航，不宣称完整语义理解代码库。它负责为模型提供多语言符号级摘要，帮助 Agent 在不展开整个仓库的前提下先定位相关模块和文件。

### 流式输出

模型文本响应支持流式显示，工具调用过程实时展示。

### 工具系统

- 文件读写与文件查看
- Shell 命令执行
- Pytest 测试执行
- Git status / diff / add / commit
- 文本搜索、文件查找、符号查找

### Chat Session 与 Task File

- `chat` 模式支持 history 跨轮保留
- `run` 模式支持 `--task-file` 从 Markdown / txt 文件读取较长任务描述

### JSONL Event Log 与 Replay

- 运行过程写入 append-only JSONL event log
- 支持 `log list`、`log show`、`log replay`
- 用于执行轨迹复盘、摘要查看和工具调用分布检查

### Docker demo runtime

可以保留“Docker 沙箱”作为用户理解用语，但这里的实际实现定位是 Docker demo runtime / 演示级容器执行边界。repo 通过 bind mount 同步，文件修改会影响宿主机工作区；该能力用于演示容器化执行流程，不包装为生产级安全沙箱。

### Shell guardrails

- 危险命令硬拦截
- 常见低风险命令直接放行
- `--confirm` 模式下识别写操作和外部副作用命令

---

## 安全说明

`--confirm` 模式会在执行高风险或有副作用的命令前要求确认。

```text
  Agent wants to run:
    $ git commit -m "fix parser bug"
  Allow? [y/N]
```

`--sandbox` 会切换到 Docker demo runtime。它用于演示容器化执行边界，而不是声明宿主机环境完全隔离；由于 repo 使用 bind mount，同一工作区内的文件修改仍会同步回宿主机。

---

## 开发

```bash
# 安装开发依赖
python -m pip install -e ".[dev]"

# 运行测试
pytest -q
pytest tests/test_task_file_cli.py -q
pytest tests/test_chat.py tests/test_chat_cli.py -q
pytest tests/test_log_cli.py -q
pytest tests/test_shell_guardrails.py -q
pytest tests/test_sandbox.py -q
pytest tests/test_event_replay.py -q
pytest tests/test_provider_matrix.py -q
pytest tests/test_repo_map_languages.py -q
```

测试结果以本地 `pytest -q` 输出为准。

最近一次本地完整验证结果：

```text
502 passed, 17 skipped
```

---

## 命令参考

```bash
# root
agent --help

# chat
agent chat [--repo PATH] [--provider PROVIDER] [--model MODEL]
           [--max-steps N] [--stream|--no-stream] [--confirm] [--sandbox] [-v]

# run
agent run --repo PATH [--task TEXT | --task-file FILE]
          [--provider PROVIDER] [--model MODEL] [--max-steps N]
          [--stream] [--confirm] [--sandbox] [-v]

# log
agent log list [--dir DIR]
agent log show <log-file.jsonl>
agent log replay <log-file.jsonl>

# github issue
python -m entry.github_issue --help
python -m entry.github_issue -r owner/repo -i ISSUE_NUM -l LOCAL_PATH [--no-pr] [-v]
```

---

更完整的使用说明见 [USAGE.md](USAGE.md)。
