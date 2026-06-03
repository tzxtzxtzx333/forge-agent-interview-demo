# Forge Agent

一句话介绍：
Forge Agent 是一个面向代码仓库的终端原生 AI Coding Agent 工程化 MVP，支持仓库理解、工具调用、文件修改、测试驱动修复、多模型 Provider 路由、Docker 演示级运行环境、GitHub Issue-to-patch 演示流程、轻量级 repo-map 上下文提取以及可回放的 JSONL 执行轨迹。

## 项目定位

本项目不是单纯的聊天机器人，而是一个围绕“代码仓库自动化修改与验证”构建的工程化 coding agent。它通过 ReAct-style 执行循环，将模型推理、工具调用、文件编辑、命令执行、测试反馈和事件日志串联起来，使 agent 的执行过程可观察、可验证、可复盘。

强调几点：

- 面向真实代码仓库，而不是孤立的代码片段。
- 以工具调用和测试反馈驱动代码修改。
- 支持多模型后端切换。
- 支持演示级 sandbox 和 GitHub Issue 处理流程。
- 通过测试矩阵和执行日志增强可信度。

## 核心能力

1. ReAct-style Coding Loop

   - 支持任务输入、模型决策、工具调用、observation 回写、测试反馈和终止状态管理。
   - 相关实现文件：`agent/core.py`、`agent/task.py`、`agent/prompt.py`

2. 仓库级文件操作

   - 支持在目标 repo 范围内读取、写入和编辑文件。
   - 强调 repo-scoped，不是无限制的文件系统访问。
   - 相关实现文件：`tools/file_tool.py`

3. Shell / Pytest / Git 工具执行

   - 支持命令执行、测试运行、diff 查看、commit 等 coding agent 常用操作。
   - 相关实现文件：`tools/shell_tool.py`、`tools/test_tool.py`、`tools/git_tool.py`

4. 流式 CLI 交互

   - 支持 `run` / `chat` 模式下的流式输出，提升终端交互体验。
   - 相关实现文件：`entry/cli.py`、`agent/core.py`

5. 多模型 Provider 路由

   - 支持 Anthropic 和 OpenAI-compatible provider，覆盖 OpenAI、DeepSeek、Groq、Ollama 等后端接入方式。
   - 相关实现文件：`llm/router.py`、`llm/provider_matrix.py`、`llm/openai_compat.py`、`llm/anthropic_backend.py`

6. Docker 演示级运行环境

   - 采用 demo-grade Docker runtime。
   - 支持容器内命令执行、仓库挂载、默认网络策略和基础资源边界。
   - 不把它表述为 production-grade security sandbox。
   - 相关实现文件：`tools/runtime.py`

7. GitHub Issue-to-patch 演示流程

   - 支持从 GitHub Issue 读取任务，运行 agent，生成本地修改，并在具备本地 GitHub 认证时创建 commit / PR。
   - 不将其表述为 unattended production automation。
   - 相关实现文件：`entry/github_issue.py`

8. 轻量级 repo-map

   - 采用 lightweight multi-language symbol extraction。
   - 支持从多语言项目中提取符号与结构摘要，用作 prompt context。
   - 不将其表述为 full semantic code intelligence。
   - 相关实现文件：`context/repo_map.py`

9. JSONL 执行日志与回放

   - 支持 action / observation / event 的追加式日志记录，并可用于回放执行轨迹。
   - replay 的定位是执行轨迹复盘，不是完全确定性的重新执行。
   - 相关实现文件：`agent/event_log.py`

10. Windows-safe CLI

   - 对 Windows 终端输出、命令帮助和 CLI 入口做了兼容性验证。

## 工程证据

| 能力 | 相关实现 | 验证方式 |
| -- | ---- | ---- |
| ReAct 执行循环 | `agent/core.py`, `agent/task.py`, `agent/prompt.py` | `pytest tests/test_day2.py tests/test_day7.py -q` |
| 仓库级文件边界 | `tools/file_tool.py` | `pytest tests/test_file_tool_repo_boundary.py -q` |
| Shell / Pytest / Git 工具 | `tools/shell_tool.py`, `tools/test_tool.py`, `tools/git_tool.py` | `pytest tests/test_day3.py tests/test_sandbox.py -q` |
| 流式 CLI | `entry/cli.py`, `agent/core.py` | `pytest tests/test_stream.py -q` |
| 多 Provider 路由 | `llm/router.py`, `llm/provider_matrix.py` | `pytest tests/test_day4.py tests/test_provider_matrix.py -q` |
| Provider smoke check | `llm/provider_smoke.py`, `scripts/smoke_provider.py`, `docs/providers.md` | `python scripts/smoke_provider.py --help` |
| Docker 演示运行环境 | `tools/runtime.py` | `pytest tests/test_sandbox.py -q` |
| GitHub Issue 流程 | `entry/github_issue.py` | `pytest tests/test_day6.py tests/test_github_issue_flow.py -q` |
| 多语言 repo-map | `context/repo_map.py` | `pytest tests/test_day5.py tests/test_repo_map_languages.py -q` |
| JSONL event replay | `agent/event_log.py`, `entry/cli.py` | `pytest tests/test_event_replay.py -q` |

## 快速开始

```bash
git clone https://github.com/tzxtzxtzx333/forge-agent-interview-demo.git
cd forge-agent-interview-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Windows PowerShell 示例：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Provider 配置

可以通过环境变量配置模型后端，例如：

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

```bash
agent run --repo . --task "Fix the failing tests"
```

```bash
python -m entry.cli --help
python -m entry.github_issue --help
python scripts/smoke_provider.py --help
```

## 验证命令

```bash
pytest -q
python -m entry.cli --help
python -m entry.github_issue --help
python scripts/smoke_provider.py --help
```

## 项目边界

- 本项目定位为工程化 MVP，而不是生产级商业系统。
- Docker runtime 是 demo-grade 运行环境，不等同于生产级安全沙箱。
- GitHub PR 创建依赖本地 GitHub 凭据和认证状态。
- repo-map 是轻量级符号提取与上下文摘要，不是完整语义级代码理解系统。
- event replay 用于执行轨迹复盘，不保证完全确定性的重执行。
- 多 Provider 能力依赖对应 API Key、网络环境和第三方服务可用性。

## 简历表述参考

Forge Agent 是一个面向代码仓库的 AI Coding Agent 工程化项目，围绕 ReAct 执行循环实现模型推理、工具调用、文件修改、测试反馈和事件日志记录。项目支持 repo-scoped 文件操作、Shell/Pytest/Git 工具执行、多模型 Provider 路由、流式 CLI、Docker 演示运行环境、GitHub Issue-to-patch 演示流程、轻量级 repo-map 和 JSONL 轨迹回放，并通过自动化测试覆盖 provider routing、repo boundary、sandbox、repo-map、event replay 和 GitHub flow 等关键模块。
