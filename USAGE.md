# Forge Agent 使用教程

面向代码仓库工作流的终端式 AI Coding Agent 使用说明，覆盖安装、配置、三种使用方式、日志查看、安全机制和常见问题。

---

## 目录

1. [安装](#1-安装)
2. [配置](#2-配置)
3. [三种使用方式](#3-三种使用方式)
4. [chat 模式详解](#4-chat-模式详解)
5. [run 模式详解](#5-run-模式详解)
6. [GitHub Issue 模式](#6-github-issue-模式)
7. [查看运行日志](#7-查看运行日志)
8. [安全机制](#8-安全机制)
9. [Docker 沙箱 / Docker runtime](#9-docker-沙箱--docker-runtime)
10. [写好任务描述的技巧](#10-写好任务描述的技巧)
11. [常见问题](#11-常见问题)
12. [配置参考](#12-配置参考)
13. [快速参考卡](#13-快速参考卡)

---

## 1. 安装

**环境要求：** Python 3.11+、pip

```bash
# 克隆项目
git clone <repo-url>
cd forge-agent-interview-demo

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# 安装
python -m pip install -e ".[dev]"

# 验证安装
agent --help
python -m entry.cli --help
python scripts/smoke_provider.py --help
```

**可选：安装更多语言的代码解析支持**（让 repo-map 对更多语言做更精确的符号级摘要）

```bash
pip install \
    tree-sitter-javascript \
    tree-sitter-typescript \
    tree-sitter-go \
    tree-sitter-rust \
    tree-sitter-java \
    tree-sitter-cpp \
    tree-sitter-c \
    tree-sitter-ruby
```

**可选：安装 tiktoken**（精确 token 计数）

```bash
pip install tiktoken
```

---

## 2. 配置

### 2.1 选择模型提供商

编辑 `config/default.yaml`，根据你使用的服务商填写：

**DeepSeek**

```yaml
llm:
  provider: deepseek
  model: deepseek-v4-flash
  # model: deepseek-v4-pro
  api_key: ${DEEPSEEK_API_KEY}
  base_url: https://api.deepseek.com
```

**Anthropic**

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-5
  api_key: ${ANTHROPIC_API_KEY}
  base_url:
```

**OpenAI**

```yaml
llm:
  provider: openai
  model: gpt-4o
  api_key: ${OPENAI_API_KEY}
  base_url:
```

**Groq**

```yaml
llm:
  provider: groq
  model: llama3-70b-8192
  api_key: ${GROQ_API_KEY}
  base_url: https://api.groq.com/openai/v1
```

**Ollama**

```yaml
llm:
  provider: ollama
  model: llama3
  api_key:
  base_url: http://localhost:11434/v1
```

实际可用模型以 provider 配置和服务商当前支持为准。

### 2.2 设置 API Key

将 API Key 设置为环境变量，不要明文写入 yaml：

```bash
export DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
export OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
export GROQ_API_KEY=sk-xxxxxxxxxxxxxxxx
```

Windows PowerShell：

```powershell
$env:DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxx"
$env:ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxxxxx"
$env:OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxx"
$env:GROQ_API_KEY="sk-xxxxxxxxxxxxxxxx"
```

### 2.3 验证配置

```bash
python -m entry.cli --help
python scripts/smoke_provider.py --help
```

如果你要做最小化的 provider 专项验证，可以运行：

```bash
python scripts/smoke_provider.py --provider deepseek --model deepseek-chat
python scripts/smoke_provider.py --provider anthropic --model claude-sonnet-4-5
python scripts/smoke_provider.py --provider ollama --model llama3
```

---

## 3. 三种使用方式

| 方式 | 命令 | 适合场景 |
| --- | --- | --- |
| **chat** | `agent chat` | 持续对话，围绕真实仓库连续分析、修改和验证 |
| **run** | `agent run --task "..."` | 一次性明确任务，适合批处理或单任务执行 |
| **GitHub Issue** | `python -m entry.github_issue` | 从 Issue 描述驱动修复流程的独立演示入口 |

此外还有 `agent log`，用于查看 JSONL 日志、摘要和 replay，不属于三种任务入口本身。

---

## 4. chat 模式详解

### 基本用法

```bash
cd /path/to/your/project
agent chat

agent chat --repo /path/to/project
agent chat --model deepseek-v4-pro
agent chat --model gpt-4o --provider openai
```

### 交互界面

启动后进入持续对话式 session。你可以先让 Agent 分析项目，再继续让它修 bug、补测试、跑验证；每轮历史会保留给下一轮使用。

### 内置命令

| 命令 | 说明 |
| --- | --- |
| `/exit` 或 `/quit` | 退出 |
| `/stats` | 显示会话统计 |
| `/clear` | 清空当前 history，重新开始 |
| `/help` | 显示命令帮助 |

### 多轮对话示例

```text
you > 先帮我看一下这个项目的模块结构

  Agent working...
  ...输出仓库结构和初步分析...

  Round 1 | steps=2 | status=task_complete | elapsed=5.2s

you > utils.py 里的 parse_date 不能处理空字符串，修一下

  Agent working...
  ...读取文件、修改代码、运行测试...

  Round 2 | steps=4 | status=task_complete | elapsed=12.1s

you > 再给这个修复补一个单元测试

  Round 3 | steps=3 | status=task_complete | elapsed=9.3s
```

关键点：每轮结束后，session 会保留任务摘要和历史上下文，后续轮次不需要从零重新描述。

### 输出结构说明

- 模型文本响应支持流式显示
- 工具调用过程实时展示
- 每轮结束后输出简短 summary，包括 round、steps、status 和 elapsed time

---

## 5. run 模式详解

适合任务描述明确、不需要来回交互的场景。

### 基本用法

```bash
agent run --task "Fix the failing tests"
agent run --repo /path/to/project --task "Refactor api.py into smaller functions"
agent run --task-file task.txt
```

### 所有选项

```text
-r, --repo TEXT       目标 repo 路径（默认当前目录）
-t, --task TEXT       任务描述（自然语言）
-f, --task-file TEXT  从文件读取任务描述
-m, --model TEXT      覆盖模型名
-p, --provider TEXT   覆盖 provider
    --max-steps INT   最大步数
-s, --stream          启用流式输出
    --confirm         危险命令需要确认
    --sandbox         在 Docker demo runtime 中执行
-v, --verbose         显示 debug 日志
```

### 典型使用场景

```bash
# 修复测试
agent run --task "tests/test_api.py::test_auth 报错 KeyError，修复它"

# 添加功能
agent run --task "在 src/api.py 里添加 /health 接口，并补测试"

# 重构代码
agent run --task "把 utils.py 里超过 50 行的函数拆分成更小函数，保持测试通过"

# 需要确认的命令
agent run --task "清理项目中的 .pyc 和 __pycache__" --confirm

# Docker demo runtime
agent run --task "安装依赖并运行测试" --sandbox
```

---

## 6. GitHub Issue 模式

GitHub Issue-to-patch 使用独立入口：

```bash
python -m entry.github_issue --help
```

### 准备工作

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxx
```

### 使用

```bash
python -m entry.github_issue \
    --repo owner/repo-name \
    --issue 42 \
    --local-path /tmp/myrepo
```

### 参数说明

```text
-r, --repo TEXT         GitHub 仓库（owner/repo）
-i, --issue INTEGER     Issue 编号
-l, --local-path TEXT   本地路径
-c, --config TEXT       配置文件路径
    --dry-run           演示流程但不真正推进外部动作
    --no-pr             只修代码，不创建 PR
    --base-branch TEXT  PR 目标分支
-v, --verbose           显示详细日志
```

### 执行流程

1. 拉取 Issue 标题和描述作为任务输入
2. 准备本地 repo 工作区
3. 创建工作分支
4. 调用 Agent 完成任务
5. 根据结果决定是否 commit、push 和创建 PR

---

## 7. 查看运行日志

每次运行都会在 `./logs/` 目录下生成 JSONL 格式的事件日志，记录完整执行过程。

### 列出日志文件

```bash
agent log list
agent log list --dir ./logs
```

### 查看单次运行摘要

```bash
agent log show logs/abc12345_20250525_143022.jsonl
```

### 回放执行轨迹

```bash
agent log replay logs/abc12345_20250525_143022.jsonl
```

请替换为实际运行任务后生成的 JSONL 日志文件路径。

### 日志内容

日志会记录：

- `task_start`
- `action`
- `observation`
- `reflection`
- `task_complete`
- `task_failed`

`show` 用于摘要统计，`replay` 用于顺序查看执行轨迹。

---

## 8. 安全机制

Agent 有多层基础防护，避免误操作。

### 层 1：危险命令硬拦截

以下命令会被直接拒绝：

- `rm -rf /`
- `rm -rf ~`
- `mkfs`
- `dd if=`
- `:(){:|:&};:`
- `chmod -R 777 /`
- `> /dev/sda`

### 层 2：只读或低风险命令直接执行

常见低风险命令例如：

- `pwd`
- `ls`
- `cat`
- `grep`
- `find`
- `git status`
- `git diff`
- `pytest`
- `python -m pytest`

### 层 3：确认模式

在 `--confirm` 模式下，以下命令会要求用户确认：

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
- 覆盖重定向 `>`

### chat 模式中的确认

如当前 session 启用了确认模式，遇到有副作用的命令时也会提示确认。

---

## 9. Docker 沙箱 / Docker runtime

可以保留“Docker 沙箱”作为用户理解用语，但这里的实际实现定位是 Docker demo runtime / 演示级容器执行边界。

### 前提

确保 Docker 已安装并正在运行：

```bash
docker --version
docker info
```

### 使用

```bash
agent run --task "run pytest" --sandbox
agent chat --repo /path/to/project --sandbox
```

### 说明

- repo 目录通过 bind mount 挂载到容器中
- 文件修改会同步到宿主机工作区
- 默认使用断网边界（如 `--network none`）
- 该能力用于演示容器化执行流程，不包装为生产级安全沙箱
- 如果 Docker 不可用，相关命令会明确失败，而不是静默退回本地执行

---

## 10. 写好任务描述的技巧

任务描述的质量会直接影响 Agent 的效果。

### 基本原则：具体优于模糊

```bash
# 不够具体
agent run --task "fix bug"

# 更具体
agent run --task "src/parser.py 的 parse() 在输入空字符串时抛 ValueError，修复它，并在 tests/test_parser.py 里补一个对应 case"
```

### 描述模板

```text
[文件/模块]里的[函数/类]在[什么情况]下出现[什么问题]。
应该改成[预期行为]。
[可选：修复后运行什么测试验证]
```

### 常见任务写法

**修复 Bug**

```text
tests/test_api.py::test_auth_token 报错 KeyError: 'user_id'。
问题可能在 src/auth.py 的 verify_token()。
修复它，并确保相关测试通过。
```

**添加功能**

```text
在 src/api.py 里添加 GET /api/v1/health 接口，
返回 {"status": "ok", "version": "1.0.0"}，
并在 tests/test_api.py 里补测试。
```

**重构代码**

```text
src/utils.py 里的 process_data() 已经超过 200 行。
把它拆分成几个职责更单一的小函数，保持现有测试通过，
不要改外部接口。
```

### 复杂任务建议用文件

```bash
agent run --task-file task.txt
```

---

## 11. 常见问题

**Q：Agent 没有输出或看起来卡住了**

先确认 CLI 和 provider 基础命令存在：

```bash
python -m entry.cli --help
python scripts/smoke_provider.py --help
```

如果 Provider 配置和网络都正常但仍然卡住，可以加 `--verbose`：

```bash
agent chat --verbose
```

**Q：Agent 陷入重复操作怎么办**

系统本身有最大步数、反思和终止分支；如果想人工中断，按 `Ctrl+C`，然后可用 `/clear` 清空当前历史后重新描述任务。

**Q：测试失败后 Agent 怎么处理**

失败会作为 observation 返回给 Agent，模型会基于错误结果继续分析并尝试下一步动作，直到成功、达到步数上限或主动结束。

**Q：改了文件但不满意，怎么撤销**

```bash
git checkout -- .
git checkout -- src/foo.py
```

**Q：Token 消耗太大**

可以尝试：

- 使用更轻量的模型版本
- 降低 `repo_map_budget`
- 降低 `history_window`

**Q：Docker 模式下缺少依赖**

可以把安装依赖也写进任务描述中，例如：

```bash
agent run --task "先运行 pip install -r requirements.txt，再执行 pytest" --sandbox
```

**Q：GitHub Issue 模式创建 PR 失败**

检查 `GITHUB_TOKEN` 权限、本地 git 凭据以及 GitHub 认证状态。若只想演示修复流程，可加 `--no-pr` 或 `--dry-run`。

---

## 12. 配置参考

`config/default.yaml` 示例：

```yaml
llm:
  provider: deepseek
  model: deepseek-v4-flash
  api_key: ${DEEPSEEK_API_KEY}
  base_url: https://api.deepseek.com
  max_tokens: 4096

agent:
  max_steps: 40
  budget_tokens: 80000
  log_dir: ./logs

tools:
  shell:
    timeout: 30
    max_output_tokens: 8000
  file:
    max_view_lines: 100

context:
  repo_map_budget: 8000
  history_window: 20
```

### 多环境配置

可以准备多个配置文件，并通过 `-c` 指定：

```bash
agent chat -c config/dev.yaml
agent run --task "..." -c config/pro.yaml
```

---

## 13. 快速参考卡

```bash
# 安装
python -m pip install -e ".[dev]"

# 设置 Key
export DEEPSEEK_API_KEY=sk-xxx

# 验证命令
python -m entry.cli --help
python scripts/smoke_provider.py --help

# chat
agent chat
agent chat --repo /path/to/project

# run
agent run --task "fix the failing tests"
agent run --task-file task.txt

# 安全选项
agent run --task "..." --confirm
agent run --task "..." --sandbox

# GitHub Issue
python -m entry.github_issue -r owner/repo -i 42 -l /tmp/repo

# 日志
agent log list
agent log show <log-file.jsonl>
agent log replay <log-file.jsonl>

# 对话内命令
# /exit
# /stats
# /clear
# /help
```
