# Forge Agent

## 一、项目背景

大语言模型已经能够生成代码，但“生成一段代码”和“自主完成一个编程任务”之间还有明显差距。真实的仓库任务通常不是一次性输出答案，而是一个连续闭环：先理解任务，再观察代码仓库，调用工具读取文件、搜索符号、运行测试、查看 diff，根据失败结果继续修正，最后把整个过程沉淀为可复盘的执行轨迹。

这也是 Coding Agent 的工程复杂度所在。问题不在于模型能不能写出几行代码，而在于如何把模型推理、工具执行、上下文管理、测试反馈、错误恢复和日志审计串成一条稳定的工程链路，让 Agent 真正面向代码仓库工作，而不是停留在一次性的文本生成。

## 二、项目描述

Forge Agent 是一个面向代码仓库工作流的终端式 AI Coding Agent 工程化项目。

用户给出自然语言任务后，Agent 可以在仓库内读取代码、搜索文件、调用 Shell / Pytest / Git 等工具、修改文件、运行验证命令，并根据 observation 持续迭代，直到任务完成、失败退出或触发边界条件。项目的核心目标不是“做一个会回答问题的模型包装器”，而是把 LLM 推理、工具执行、上下文管理、测试反馈和日志复盘组织成一条完整闭环。

当前项目提供三种真实使用入口：

- `agent run`：适合一次性任务执行，也支持 `--task-file` 从任务文件读取较长需求
- `agent chat`：适合持续对话式 coding session，在多轮任务中共享 history
- `python -m entry.github_issue`：适合演示从 GitHub Issue 到本地修复、commit、PR 的 issue 驱动流程

其中 GitHub Issue-to-patch 是独立入口，不是 `agent` 根命令下的同级子命令。

## 三、核心指标

项目不强调未经验证的跑分或包装性数字，重点放在已经实现并可验证的工程能力上。

- 三种使用入口：`run` / `chat` / `GitHub Issue-to-patch`
- 多类仓库工作流工具能力：文件读写、文件查找、文本搜索、符号查找、Shell、Pytest、Git、repo-map 上下文注入、日志回放、任务文件输入、Chat session 状态管理、Runtime 抽象
- 多 Provider 路由：Anthropic / OpenAI / DeepSeek / Groq / Ollama
- 多语言 repo-map 符号摘要
- JSONL event log 与 replay
- Docker demo runtime
- Shell guardrails

测试结果以本地 `pytest -q` 输出为准。

## 四、核心职责与贡献

### 1. 架构设计

项目把终端入口、Agent 主循环、LLM 路由、工具层、上下文层、Runtime 层和 Event Log 层拆成相对清晰的职责边界。这样做的目的，是让“模型推理”和“工程执行”分离：模型负责决策，工具负责对仓库产生真实操作，Runtime 决定这些操作在本地还是容器里运行，Event Log 负责把全过程变成可审计轨迹。

### 2. ReAct 主循环

Agent 采用 ReAct-style 主循环组织执行路径：接收任务、构建 messages、请求模型决策、选择动作、执行工具、读取 observation、根据结果继续迭代。这样模型不是一次性给出最终答案，而是在每轮都根据环境反馈重新判断下一步动作，更适合处理真实仓库任务中的失败恢复、补测试和增量修复。

### 3. 多模型路由

项目将模型厂商能力抽象到 Router / Backend 层，统一 run / chat / issue 流程对模型的调用方式。这样主流程不需要和单一厂商 SDK 强绑定，便于在 Anthropic、OpenAI-compatible 和本地推理类 Provider 之间切换。

### 4. 上下文管理

代码仓库任务的瓶颈通常不是“没有代码”，而是“上下文过长、噪声太多”。项目通过 history、token budget 和 repo-map 进行上下文分层管理：既保留任务连续性，也避免把整个仓库原样塞进 prompt。

### 5. 工具层与 Runtime 抽象

文件读写、Shell、Pytest、Git、搜索和符号查找等能力都做成独立工具，再通过 Runtime 抽象决定命令如何落地执行。这样工具本身关注“做什么”，Runtime 关注“在哪里执行、带什么边界执行”，可以复用到本地运行和 Docker demo runtime。

### 6. 事件日志与 replay

项目把每次任务执行写入 JSONL event log，记录 task、action、observation、reflection 和任务完成状态。这样不仅便于调试，也让面试演示时可以直观说明 Agent 是如何决策、如何失败、如何恢复的。

### 7. 安全边界

项目没有把自己包装成强安全隔离系统，而是保留了可验证的边界：Shell guardrails 负责基础命令拦截与确认机制，Docker runtime 提供 demo-grade execution boundary。这个定位更真实，也更符合当前工程实现。

### 8. 工程质量与测试

关键能力都对应到 CLI 层、模块层或边界条件测试，包括 task-file 输入、chat session、event log replay、provider matrix、repo-map、多语言解析、Shell guardrails 和 Docker runtime 参数构造。验证重点是“能力是否真实存在并可复现”，而不是仅靠 README 声称。

## 五、系统架构

```text
入口层（CLI / Chat / GitHub Issue 独立入口）
    ↓ Task
Agent Core（ReAct-style coding loop）
    ↓ messages + tools
LLM 层（Backend / Router）
    ↓ Action
工具层（File / Shell / Pytest / Git / Search / Symbol）
    ↓ Observation
上下文层（RepoMap / TokenBudget / History）
    ↓ EventLog
```

这条链路的关键点在于，模型并不直接“完成任务”，而是通过 Agent Core 把推理结果转成动作，再把动作送入工具层执行；工具层返回 observation 后，Agent 再基于新状态进入下一轮推理。上下文层和 EventLog 则分别解决“怎么控制输入”和“怎么保留过程”两个工程问题。

## 六、分模块设计

### 1. Agent Core

- 设计目标：把自然语言任务组织成可持续推进的决策循环，而不是一次性生成结果
- 核心实现：维护 messages、调用 backend、选择动作、执行工具、处理 reflection / finish / give_up，并驱动整轮任务结束条件
- 面试亮点：可以重点讲为什么 ReAct 更适合仓库任务，以及为什么 observation 对持续修复比纯文本生成更关键

### 2. EventLog

- 设计目标：记录完整执行轨迹，支持调试、审计和 replay
- 核心实现：以 JSONL 追加写入事件，并提供 summarize、trace、render replay 等能力；CLI 侧支持 `log list`、`log show`、`log replay`
- 面试亮点：可以讲“Agent 不可观测就很难调试”，event log 是把黑盒过程拆成可解释工程轨迹的关键

### 3. LLM Router

- 设计目标：把主流程从单一模型厂商中解耦出来
- 核心实现：通过 Router 和 Provider Matrix 统一 Anthropic / OpenAI-compatible / Ollama 等入口，屏蔽不同 SDK 或协议差异
- 面试亮点：可以讲为什么工程上要先设计抽象层，而不是直接在核心逻辑里写死一个模型调用

### 4. Tools

- 设计目标：让模型具备操作真实代码仓库的执行手段
- 核心实现：围绕仓库任务封装文件读写、搜索、符号查找、Shell、Pytest、Git 等工具，统一返回结构化结果
- 面试亮点：可以讲“Agent 的上限往往取决于工具设计”，尤其是 observation 结构和失败信息是否足够让模型继续决策

### 5. RepoMap

- 设计目标：在不直接展开整个仓库的前提下，为模型提供结构化上下文
- 核心实现：提取多语言符号与结构摘要，作为 prompt context 注入执行流程
- 面试亮点：可以讲 repo-map 不是完整语义理解，而是一个更轻量、更工程可控的上下文压缩方案

### 6. Chat Session

- 设计目标：支持持续对话式仓库任务推进，而不是每轮都从零开始
- 核心实现：在 session 中共享 history，保留用户任务、Agent 摘要和统计信息，支持 `/exit`、`/quit`、`/help`、`/clear`、`/stats`
- 面试亮点：可以讲为什么 chat 模式本质上是在 run 模式上补一层“跨轮状态管理”

### 7. Docker Runtime

- 设计目标：为命令执行提供更明确的 demo 边界
- 核心实现：通过 `DockerRuntime` 构造容器执行参数，覆盖 `--network none`、repo bind mount、`/workspace` 工作目录和基础 hardening flags
- 面试亮点：可以讲“为什么要做 Runtime 抽象”，以及为什么这里明确定位为 demo-grade execution boundary

### 8. GitHub Issue-to-patch Flow

- 设计目标：把仓库任务接入更接近真实协作场景的入口
- 核心实现：支持从 Issue 描述构造任务、运行本地修复、生成 commit / PR 演示流程，并提供 dry-run 能力
- 面试亮点：可以讲这类入口不是新建一套 Agent，而是复用已有核心链路，把任务来源换成 issue 场景

## 七、使用方式

### 1. 基础帮助命令

```bash
agent --help
agent run --help
agent chat --help
agent log --help
python -m entry.cli --help
python -m entry.github_issue --help
```

### 2. 一次性任务执行

```bash
agent run --repo . --task "Fix the failing tests"
```

### 3. 从任务文件读取需求

```bash
agent run --repo . --task-file examples/tasks/fix_quicksort.md
```

### 4. 持续对话式会话

```bash
agent chat --repo .
```

### 5. 日志查看与回放

```bash
agent log list
agent log show <log-file.jsonl>
agent log replay <log-file.jsonl>
```

其中 `<log-file.jsonl>` 是示例占位路径。需要先运行一次任务生成 JSONL 日志，或替换成实际存在的日志文件路径。

### 6. GitHub Issue-to-patch 独立入口

```bash
python -m entry.github_issue --help
```

这个入口用于 issue 驱动演示流程，不是 `agent` 根命令下的同级子命令。

## 八、测试与验证

项目当前把关键能力的验证聚焦在“功能是否真实存在、边界是否真实覆盖”上。可直接运行的验证命令包括：

```bash
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

这些测试覆盖的重点包括：

- task-file 输入与边界条件
- chat session 的 history 复用与内置命令
- log list / show / replay
- Shell guardrails
- Docker runtime 参数构造
- provider matrix
- repo-map 多语言符号摘要
- event replay

测试结果以本地 `pytest -q` 输出为准。

## 九、安全边界与限制

- 项目定位是工程化 MVP，不是商业级产品
- Docker runtime 是 demo-grade execution boundary，不是强安全隔离沙箱
- Shell guardrails 提供基础防护，但不等同于完整隔离环境
- repo-map 是符号级摘要，不是完整语义理解代码库
- event replay 是执行轨迹回放，不保证确定性重新执行
- GitHub PR 创建依赖本地 GitHub 凭据和认证状态
- 多 Provider 能力依赖 API Key、网络环境和第三方服务可用性

## 十、面试讲解要点

### 1. 为什么这不是普通代码生成项目？

因为核心问题不是“让模型输出一段代码”，而是让模型在真实仓库里完成一段连续工作，包括读代码、调工具、跑测试、看失败、再修复。真正的难点在工程闭环，而不是单次生成。

### 2. 为什么采用 ReAct-style 主循环？

因为仓库任务天然需要多轮决策。模型必须先观察环境，再决定下一步动作；执行动作后又要根据 observation 更新判断。ReAct 比一次性生成更适合这类交互式任务。

### 3. function calling 和 JSON fallback 的区别是什么？

function calling 让模型直接输出结构化工具调用，协议更稳定；JSON fallback 则是在缺少原生工具调用接口时，用约定格式维持同样的动作语义。两者目标一致，都是把“模型输出”变成“可执行动作”。

### 4. repo-map 解决了什么问题？

它解决的是上下文过长和仓库结构不可见的问题。与其把整个仓库原样塞进 prompt，不如先给模型一个轻量级结构摘要，让它知道有哪些模块、符号和文件值得进一步读取。

### 5. 如何防止上下文爆炸？

通过 history、token budget 和 repo-map 分层管理。不是把所有信息都喂给模型，而是保留任务连续性、摘要关键状态，再按需读取文件和符号。

### 6. 工具失败后 Agent 如何恢复？

工具执行结果会变成 observation 返回给 Agent。只要失败信息足够结构化，模型就可以基于错误结果继续决策，例如改命令、补文件、重跑测试，或者在必要时终止任务。

### 7. Shell 工具如何做安全约束？

当前做法是两层：一层是危险命令硬拦截，另一层是确认机制识别写操作或外部副作用命令。目标不是做完全隔离，而是提供基础可验证 guardrails。

### 8. Docker runtime 的边界是什么？

它是 demo-grade execution boundary，重点是限制网络、挂载仓库、约束工作目录和基础资源参数，适合演示命令在容器中执行的边界控制，但不包装成更强安全系统。

### 9. event log 有什么价值？

它让 Agent 从黑盒变成可观察系统。你可以看到任务是怎么开始的、工具是怎么被调用的、为什么失败、为什么继续修复，也能通过 replay 做复盘和演示。

### 10. 多 Provider 路由怎么设计？

核心思想是把模型调用收敛到统一接口，再用 Router 决定具体 Provider / Model。这样上层 Agent 不需要感知底层厂商差异，便于切换和扩展。

### 11. run / chat / GitHub Issue-to-patch 三种入口分别解决什么问题？

- `run`：适合一次性明确任务
- `chat`：适合多轮推进和交互式修复
- `GitHub Issue-to-patch`：适合演示更接近真实协作场景的问题输入和修复链路

### 12. 这个项目最值得讲的工程点是什么？

不是某一个工具，也不是某一个模型，而是把“模型推理 -> 工具执行 -> 测试反馈 -> 上下文管理 -> 日志复盘”真正串成了一个可以运行、可以验证、可以讲清楚的工程闭环。
