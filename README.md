# Forge Agent

Forge Agent 是一个面向代码仓库的终端式 AI Coding Agent 工程化 MVP，支持 run、chat、GitHub Issue-to-patch 三种入口，覆盖 ReAct-style coding loop、工具调用、测试驱动修复、多 Provider 路由、repo-map、JSONL event log、Shell guardrails 和 Docker demo runtime。

## 项目定位

Forge Agent 面向真实代码仓库工作流，而不是单纯的聊天交互。项目将任务输入、模型推理、工具调用、文件修改、测试反馈和事件日志串联起来，使一次 coding agent 执行过程具备可观察、可验证、可复盘的工程属性。

这个项目适合展示以下能力：

- 面向代码仓库的自动化分析、修改与验证
- 基于工具调用和测试反馈的迭代修复
- 多种 CLI 入口与可演示的使用路径
- 多 Provider 路由与可替换模型后端
- JSONL 执行轨迹审计与 replay 能力
- Shell guardrails 与 Docker 演示级执行边界

## 核心能力

### 1. 三种使用方式

项目支持三种主要入口：

- `agent run`：一次性任务执行
- `agent chat`：持续对话式 coding agent session
- `agent log`：查看和回放 JSONL 执行日志

相关实现：

- `entry/cli.py`
- `entry/chat.py`
- `agent/event_log.py`

### 2. ReAct-style Coding Loop

Forge Agent 通过 ReAct-style 执行循环组织 agent 的工作过程，支持任务输入、模型决策、工具调用、observation 回写、测试反馈和终止状态管理。

相关实现：

- `agent/core.py`
- `agent/task.py`
- `agent/prompt.py`

### 3. 仓库级文件操作

项目提供 repo-scoped 文件工具，支持在目标代码仓库范围内读取、写入和编辑文件，避免 agent 对仓库外路径进行不受控访问。

相关实现：

- `tools/file_tool.py`

### 4. run 模式与任务文件输入

`run` 模式既支持直接从命令行传入任务描述，也支持从任务文件读取较长的自然语言任务说明：

- `--task "Fix the failing tests"`
- `--task-file examples/tasks/fix_quicksort.md`

项目已提供可演示任务样例：

- `examples/tasks/fix_quicksort.md`
- `examples/tasks/add_linked_list_tests.md`
- `examples/README.md`

相关实现：

- `entry/cli.py`
- `examples/tasks/`

### 5. chat 持续对话会话

`chat` 模式支持持续对话式 coding agent session。用户可以先让 agent 分析项目，再让它修 bug，再让它补测试。多轮对话之间共享 history，每轮结束后会把结果摘要追加回 history，并输出简短 round summary。

内置命令包括：

- `/exit`
- `/quit`
- `/help`
- `/clear`
- `/stats`

相关实现：

- `entry/chat.py`
- `entry/cli.py`

### 6. Shell / Pytest / Git 工具执行

项目封装了 coding agent 常用的命令执行能力，包括 shell 命令、pytest 测试运行、git diff 查看和 commit 操作，使 agent 能够基于真实执行结果迭代修改。

相关实现：

- `tools/shell_tool.py`
- `tools/test_tool.py`
- `tools/git_tool.py`

### 7. Shell guardrails

Shell 工具有基础安全防护能力，包括危险命令硬拦截、只读命令放行、写操作确认机制，以及 runtime 异常包装。

危险命令硬拦截至少包括：

- `rm -rf /`
- `rm -rf ~`
- `mkfs`
- `dd if=`
- `:(){:|:&};:`
- `chmod -R 777 /`
- `> /dev/sda`

在确认模式下，会识别这些高风险或有副作用的命令并要求确认：

- `rm`
- `mv`
- `pip install`
- `git commit`
- `git push`
- `curl`
- `wget`
- `chmod`
- `sudo`
- `docker`
- 含 `>` 的覆盖重定向

相关实现：

- `tools/shell_tool.py`

### 8. 流式 CLI 交互

项目支持 `run` 和 `chat` 模式下的流式终端输出，使用户能够在命令行中观察 agent 的执行过程和中间状态。

相关实现：

- `entry/cli.py`
- `entry/chat.py`
- `agent/core.py`

### 9. 多 Provider 路由

项目支持 Anthropic 和 OpenAI-compatible provider 的统一路由，可接入 OpenAI、DeepSeek、Groq、Ollama 等后端，便于根据成本、速度和可用性切换模型。

相关实现：

- `llm/router.py`
- `llm/provider_matrix.py`
- `llm/openai_compat.py`
- `llm/anthropic_backend.py`

### 10. Docker 演示级运行环境

项目提供 demo-grade Docker runtime，用于在容器中执行命令、挂载目标仓库，并配置基础网络策略和资源边界。当前测试覆盖了 `--network none`、repo bind mount、`--workdir /workspace`、cwd 到容器路径转换，以及基础 hardening flags。

相关实现：

- `tools/runtime.py`

### 11. GitHub Issue-to-patch 演示流程

项目支持从 GitHub Issue 读取任务，运行 agent 生成本地修改，并在具备本地 GitHub 凭据和认证状态时创建 commit 或 PR。该流程适合展示 coding agent 如何从任务描述进入代码修改链路。

相关实现：

- `entry/github_issue.py`

### 12. 轻量级 repo-map

项目实现了 lightweight multi-language symbol extraction，可以从多语言项目中提取符号和结构摘要，并将其作为 prompt context 注入 agent 执行过程，帮助模型快速理解代码仓库结构。

相关实现：

- `context/repo_map.py`

### 13. JSONL 执行日志与 replay

项目支持 action、observation 和 event 的追加式 JSONL 日志记录，并提供 `log list`、`log show`、`log replay` 三个 CLI 子命令，用于查看日志文件、输出摘要信息，以及按顺序回放执行轨迹。

`log show` 可查看：

- Total events
- Actions
- Observations
- Reflections
- Tool calls 分布
- Final status

`log replay` 可顺序展示：

- `task_start`
- `action`
- `observation`
- `reflection`
- `task_complete`
- `task_failed`

相关实现：

- `agent/event_log.py`
- `entry/cli.py`

### 14. Windows-safe CLI

项目对 Windows 终端输出、命令帮助和 CLI 入口进行了兼容性验证，降低 Windows 环境下运行命令行工具时的编码和输出问题。

## 工程证据

| 能力 | 相关实现 | 验证方式 |
| -- | ---- | ---- |
| ReAct 执行循环 | `agent/core.py`, `agent/task.py`, `agent/prompt.py` | `pytest tests/test_day2.py tests/test_day7.py -q` |
| 仓库级文件边界 | `tools/file_tool.py` | `pytest tests/test_file_tool_repo_boundary.py -q` |
| Shell / Pytest / Git 工具 | `tools/shell_tool.py`, `tools/test_tool.py`, `tools/git_tool.py` | `pytest tests/test_day3.py tests/test_sandbox.py -q` |
| 流式 CLI | `entry/cli.py`, `agent/core.py` | `pytest tests/test_stream.py -q` |
| 多 Provider 路由 | `llm/router.py`, `llm/provider_matrix.py` | `pytest tests/test_day4.py tests/test_provider_matrix.py -q` |
| Task file input | `entry/cli.py`, `examples/tasks` | `pytest tests/test_task_file_cli.py -q` |
| Chat session | `entry/chat.py`, `entry/cli.py` | `pytest tests/test_chat.py tests/test_chat_cli.py -q` |
| Log CLI | `entry/cli.py`, `agent/event_log.py` | `pytest tests/test_log_cli.py tests/test_event_replay.py -q` |
| Shell guardrails | `tools/shell_tool.py` | `pytest tests/test_shell_guardrails.py -q` |
| Docker runtime | `tools/runtime.py` | `pytest tests/test_sandbox.py -q` |
| Provider smoke check | `llm/provider_smoke.py`, `scripts/smoke_provider.py`, `docs/providers.md` | `python scripts/smoke_provider.py --help` |
| GitHub Issue 流程 | `entry/github_issue.py` | `pytest tests/test_day6.py tests/test_github_issue_flow.py -q` |
| 多语言 repo-map | `context/repo_map.py` | `pytest tests/test_day5.py tests/test_repo_map_languages.py -q` |
| JSONL event replay | `agent/event_log.py`, `entry/cli.py` | `pytest tests/test_event_replay.py -q` |

## 快速开始

```bash
git clone https://github.com/tzxtzxtzx333/forge-agent-interview-demo.git
cd forge-agent-interview-demo
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
agent --help
agent run --help
agent chat --help
agent log --help
```

Windows PowerShell 示例：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
agent --help
agent run --help
agent chat --help
agent log --help
```

## Provider 配置

可以通过环境变量配置模型后端：

```bash
export DEEPSEEK_API_KEY=sk-xxx
export OPENAI_API_KEY=sk-xxx
export ANTHROPIC_API_KEY=sk-xxx
export GROQ_API_KEY=sk-xxx
```

Windows PowerShell 示例：

```powershell
$env:DEEPSEEK_API_KEY="sk-xxx"
```

## 运行示例

运行一次性任务：

```bash
agent run --repo . --task "Fix the failing tests"
```

从任务文件读取复杂任务描述：

```bash
agent run --repo . --task-file examples/tasks/fix_quicksort.md
```

启动持续对话式会话：

```bash
agent chat --repo .
```

查看日志列表：

```bash
agent log list
```

查看日志摘要：

```bash
agent log show logs/example.jsonl
```

回放执行轨迹：

```bash
agent log replay logs/example.jsonl
```

## 验证命令

```bash
pytest -q
python -m entry.cli --help
python -m entry.cli run --help
python -m entry.cli chat --help
python -m entry.cli log --help
python scripts/smoke_provider.py --help
```

当前工作区最近一次完整测试结果：

- `502 passed, 17 skipped`

## 示例任务

项目已提供可演示任务样例：

- `examples/tasks/fix_quicksort.md`
- `examples/tasks/add_linked_list_tests.md`
- `examples/README.md`

这些样例用于展示 `run --task-file` 的使用方式，适合在项目演示时直接运行。

## 项目边界

- 这是一个工程化 MVP，不是生产级商业系统。
- Docker runtime 是 demo-grade execution boundary，不是生产级安全沙箱。
- GitHub PR 创建依赖本地 GitHub 凭据。
- repo-map 是轻量级符号提取，不是完整语义级代码理解。
- event replay 是执行轨迹复盘，不保证确定性重执行。
- 多 Provider 能力依赖 API Key、网络环境和第三方服务可用性。

## 简历表述参考

Forge Agent 是一个面向代码仓库的 AI Coding Agent 工程化项目，围绕 ReAct-style 执行循环实现模型推理、工具调用、文件修改、测试反馈和 JSONL 事件日志记录。项目支持 `run`、`chat`、`log` 三类 CLI 使用方式，覆盖任务文件输入、持续对话式代码编辑、执行轨迹回放、Shell guardrails、Docker 演示级运行环境、多 Provider 路由、轻量级 repo-map，以及 GitHub Issue-to-patch 演示流程，并通过自动化测试验证 task-file、chat session、event replay、sandbox、shell guardrails 和 provider routing 等关键模块。
