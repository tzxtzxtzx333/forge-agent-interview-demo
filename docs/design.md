# Forge Agent 技术设计文档

如果当前没有合适的项目可以快速理解 Coding Agent 的核心工程链路，可以先看这份文档。它的目标不是做首页介绍，也不是使用教程，而是把项目的架构分层、模块职责、关键设计决策和常见技术问题串起来，帮助自己从工程角度理解一个终端式 AI Coding Agent 是如何落地的。

## 一、项目描述

### 项目概述

Forge Agent 是一个基于大语言模型的终端式 AI Coding Agent 工程化 MVP，能够围绕真实代码仓库完成代码修复、功能开发、测试验证和日志复盘等任务。用户输入自然语言任务后，Agent 会探索代码仓库、调用工具执行操作、根据执行结果继续迭代，直到任务完成、失败退出或触发边界条件。

这个项目的重点不是“让模型生成一段代码”，而是把模型推理、工具执行、上下文管理、测试反馈和执行轨迹记录串成完整闭环。围绕 Coding Agent 的核心工程链路，项目实现了一个可运行、可测试、可复盘的终端式 AI Coding Agent MVP。

### 核心能力

- 支持 5 类模型提供商：Claude / DeepSeek / OpenAI / Groq / Ollama
- 支持三种任务使用路径：持续对话（chat）、一次性任务（run）、`python -m entry.github_issue` 独立入口
- 支持多语言符号级摘要，用于上下文压缩和仓库结构导航
- 支持 JSONL 事件日志、摘要查看与执行轨迹回放
- 支持基础 Shell guardrails 与 Docker demo runtime

### 指标说明

测试结果以当前本地 `pytest -q` 输出为准。

## 二、核心职责与贡献

### 架构设计

项目采用分层架构，把入口层、Agent Core、LLM 层、工具层、上下文层和日志层拆成相对单一职责的模块。不同层之间通过抽象接口通信，新增工具或新增模型后端时，尽量不需要改动核心调度逻辑。

```text
入口层（CLI / Chat / GitHub Issue 独立入口）
    ↓ Task
Agent Core（ReAct 主循环）
    ↓ messages + tools
LLM 层（多 backend 统一抽象）
    ↓ Action
工具层（多工具 + Runtime 抽象）
    ↓ 上下文数据
上下文层（RepoMap + TokenBudget + History）
    ↓ EventLog
日志层（JSONL event log / replay）
```

### ReAct 主循环

这里的 ReAct 指 Reasoning + Acting 的工程范式，即模型在任务执行中交替进行决策、工具调用和结果观察；项目并不是复现某一篇论文的实验设定，而是将这一范式应用到 Coding Agent 场景。

Agent 会在每一步中构建 messages、请求模型输出动作、执行工具、记录 observation，并根据新的环境反馈继续推进。为了让循环可控，项目额外加入了反思、死循环检测和步数熔断机制。

### 多模型路由

项目设计了统一的 `LLMBackend` 抽象接口，用于屏蔽不同模型提供商之间的 API 差异。对于支持 function calling 的后端，优先走原生工具调用；对于不支持 function calling 的模型，则走文本解析 fallback，将结构化动作从模型输出中提取出来。

### 上下文管理

代码仓库任务的核心难点之一是上下文容量有限。项目把上下文管理拆成三个子问题：

- 用 repo-map 生成多语言符号级摘要
- 用 TokenBudget 做上下文预算分配和裁剪
- 用 ConversationHistory 做多轮会话的滑动窗口管理

### 工具层与 Runtime 抽象

工具层负责暴露给 Agent 的实际操作能力，例如文件读写、搜索、Shell、Pytest 和 Git。Runtime 层负责命令如何执行，当前提供本地执行和 Docker demo runtime 两种路径，使工具本身不需要感知运行边界。

### 事件日志与 replay

项目将每次任务执行写入 append-only 的 JSONL 事件日志。日志既可以用于调试，也可以用于摘要统计和执行轨迹回放。这里强调的是执行轨迹回放 / 审计式复盘，不写成确定性重新执行。

### 安全边界

项目包含基础的 Shell guardrails 和 Docker demo runtime。它们的目标是提供可验证的工程边界，而不是更强的隔离承诺。尤其是 Docker runtime，repo 通过 bind mount 挂载到容器中，文件修改会同步回宿主机工作区。

### 工程质量

- 模块级测试覆盖 Agent Core、Provider Matrix、RepoMap、EventLog、Chat Session、Shell guardrails、Docker runtime 等路径
- CLI 入口可直接验证
- 关键行为尽量通过 MockBackend 或局部集成测试覆盖

## 三、分模块设计

### 3.1 ReAct 主循环（`agent/core.py`）

#### 设计目标

实现 Agent 的决策 - 执行 - 观察循环，聚焦编排逻辑，不直接承载具体工具细节或 Provider 差异。

#### 核心流程

每一步大致包含：

1. `_build_messages()`：组装 system、history、repo-map 和当前任务上下文
2. `_call_with_retry()`：调用 LLM，支持流式响应与重试
3. 解析 Action 类型
   - `TOOL_CALL`：调用 ToolRegistry 执行工具，得到 Observation
   - `FINISH`：收敛任务，返回成功结果
   - `GIVE_UP`：返回放弃结果
4. 检测异常条件：死循环、达到 `max_steps`
5. 写入 EventLog：记录 action / observation
6. 根据条件触发 reflection

#### AgentConfig 关键字段

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `max_steps` | `40` | 每轮最大步数 |
| `reflection_no_edit_steps` | `6` | 连续无编辑时触发反思 |
| `loop_detection_window` | `3` | 死循环检测窗口 |
| `budget_tokens` | `80000` | token 预算 |
| `llm_max_retries` | `3` | LLM 最大重试次数 |
| `llm_retry_delay` | `2.0` | 初始重试间隔 |
| `stream` | `False` | 是否启用流式文本输出 |
| `confirm_dangerous` | `False` | 是否要求确认危险命令 |

#### Reflection 触发逻辑

- 测试工具失败时触发 `test_failed`
- 连续若干步没有产生文件写入时触发 `no_edit`

#### 死循环检测

对最近若干个 `TOOL_CALL` 的 `(tool_name, params)` 进行比较，完全重复则判定为死循环，进入放弃或终止分支。

### 3.2 事件日志（`agent/event_log.py`）

#### 设计目标

记录 Agent 的完整运行轨迹，支持审计、调试、摘要统计和执行轨迹回放。

#### 数据模型

事件类型包括：

- `task_start`
- `action`
- `observation`
- `reflection`
- `task_complete`
- `task_failed`

#### 关键设计决策

- **Append-only**：每条事件写入后不修改
- **及时 flush**：每次写入后立即刷新，避免最近事件丢失
- **JSONL 格式**：每行一个 JSON 对象，便于 `cat`、`tail`、`jq` 等工具处理
- **文件命名**：按任务和时间戳生成，避免多次运行互相覆盖
- **回放支持**：日志文件关闭后，仍可独立加载和 replay

#### 摘要统计

`summarize_run()` 会遍历事件日志，统计工具调用分布、reflection 次数和最终状态，用于辅助调试和演示。

### 3.3 LLM 路由与多模型支持（`llm/`）

#### 设计目标

统一各家 LLM API 差异，Agent Core 只依赖抽象接口。

#### 抽象接口

```python
class LLMBackend(ABC):
    def complete(messages, tools) -> LLMResponse
    def stream(messages, tools, on_text) -> LLMResponse
    def model_name(self) -> str
    def supports_function_calling(self) -> bool
```

#### 两类 Backend

| 类别 | 典型实现 | 特点 |
| --- | --- | --- |
| AnthropicBackend | `anthropic_backend.py` | 使用原生 tool_use、独立 system prompt、流式 SDK |
| OpenAICompatBackend | `openai_compat.py` | 支持 OpenAI / DeepSeek / Groq / Ollama 等 OpenAI-compatible 路径 |

#### Function Calling Fallback

对于不支持原生工具调用的模型：

1. 检测模型是否在“不支持 function calling”列表中
2. 走文本输出路径
3. 在 prompt 中注入 JSON 格式要求
4. 用正则和 JSON 解析提取工具调用
5. 提取失败时返回 `GIVE_UP` 或错误结果

#### Router 设计

`router.py` 负责：

- provider 到 base URL 的映射
- backend 的创建
- API Key 的读取与参数合并

#### 重试机制

对临时性错误做指数退避重试；对认证类错误直接失败，不做无意义重试。

### 3.4 工具层与 Runtime 抽象（`tools/`）

#### 设计目标

让工具即插即用，执行环境可切换，本地与容器执行边界解耦。

#### ToolRegistry

所有工具都注册进统一的 `ToolRegistry`，由 Agent 按名字调用。工具不存在或工具内部异常时，不直接把异常抛到 Agent Core，而是尽量返回失败的 `ToolResult`。

#### 工具集合

- 文件操作：`FileReadTool` / `FileViewTool` / `FileWriteTool`
- 搜索：`SearchTextTool` / `FindFilesTool` / `FindSymbolTool`
- Shell：`ShellTool`
- 测试：`PytestTool`
- Git：`GitStatusTool` / `GitDiffTool` / `GitAddTool` / `GitCommitTool`

#### ShellTool 约束

ShellTool 包含多层基础防护：

- 危险命令硬拦截
- 低风险命令白名单
- `--confirm` 模式下的写操作确认
- 可选切换到 Docker demo runtime

#### Runtime 抽象

```python
class Runtime(ABC):
    def exec(cmd, cwd, timeout) -> RunResult
```

- `LocalRuntime`：使用本地 `subprocess`
- `DockerRuntime`：把命令路由到容器中执行

### 3.5 上下文管理（`context/`）

#### 设计目标

解决“大型代码仓库无法整体放入上下文窗口”的问题。

#### 3.5.1 RepoMap（`context/repo_map.py`）

##### 问题

一个正常项目可能包含大量文件，总代码量远超单次上下文容量。

##### 解决方案

repo-map 负责生成多语言符号级摘要，而不是直接展开所有文件内容。它解决的是上下文压缩和仓库结构导航问题，不宣称完整语义理解代码库。

##### 实现流程

1. 扫描 repo 中的源文件
2. 用 tree-sitter 做精确解析
3. 缺少语言包时走正则 fallback
4. 提取函数、类、方法等 symbol
5. 按重要性和预算排序裁剪
6. 生成可注入 prompt 的结构化摘要

##### 缓存策略

同一 session 内尽量复用 repo-map；换 repo 或失效条件触发时重新构建。

##### 降级策略

tree-sitter 不可用时回退到正则；正则失败时至少列文件名，不阻断 Agent 主流程。

#### 3.5.2 TokenBudget（`context/token_budget.py`）

##### 问题

system prompt、repo-map、历史记录和 observation 叠加后，容易超过上下文上限。

##### 预算分配

按优先级分配总预算：

- reserve：预留给模型输出
- system_core：系统指令
- repo_map：仓库结构摘要
- observation：当前工具输出
- history：历史消息

##### 裁剪策略

- 永远保留任务描述
- 优先裁剪旧历史
- observation 和 repo-map 在预算压力下做有损缩减
- 插入截断提示，保持调试可解释性

##### token 计数

优先使用 `tiktoken`；不可用时用字符数近似估算。

#### 3.5.3 ConversationHistory（`context/history.py`）

##### 作用

管理多轮消息的滑动窗口，保证最初的任务描述不被普通裁剪逻辑丢掉。

##### 机制

- 新消息追加到尾部
- 达到消息条数上限时，从中间或较旧位置开始裁剪
- 与 TokenBudget 形成“双层裁剪”

### 3.6 多轮会话管理（`entry/chat.py`）

#### 设计目标

让 chat 模式在多轮任务之间保留上下文，使 Agent 能看到之前的任务和结果。

#### 核心挑战

`Agent.run()` 更偏一次性调用，而 chat 需要跨轮共享历史。

#### 解决方案

通过共享 `ConversationHistory` 并注入到 Agent 中，实现：

- 用户输入进入共享 history
- 本轮结果摘要追加回 history
- 下一轮继续复用已有上下文

#### 实时打印

chat 模式会在日志写入时同步做终端展示，让用户看到当前轮次的动作和进度。

#### 跨轮统计

在 session 级别累计 rounds、steps、tool calls 和 elapsed time，供 `/stats` 命令查看。

### 3.7 Streaming（`llm/` + `entry/`）

#### 设计目标

让 CLI 在任务执行时有更明显的反馈，而不是长时间静默。

#### 流式链路

```text
LLM API (stream=True)
  → SDK 迭代 delta
  → on_text 回调
  → stream_callback
  → stdout 实时显示
```

#### 关键说明

- 模型文本响应支持流式显示
- 工具调用过程实时展示
- 不把内部 chain-of-thought 作为承诺能力

#### 与交互输入的共存

由于终端输入与流式输出共用 stdout，需要在轮次边界处理换行和提示符刷新，避免交互界面错位。

## 四、Agent 开发面试题

### Q1：什么是 ReAct 架构？和普通 LLM 调用有什么区别？

ReAct（Reasoning + Acting）是一种让模型交替进行推理和行动的工程范式。普通 LLM 调用通常是一次输入、一次输出；ReAct 则是多轮循环：模型先决策，再调用工具，再观察结果，再继续调整下一步行动。核心区别在于模型能够“感知”自己行动后的环境反馈。

### Q2：function calling 和让模型输出 JSON 有什么区别？

function calling 是模型厂商在 API 层面的原生结构化工具调用能力，格式稳定，schema 更明确；让模型输出 JSON 更像 prompt 约束，需要自己处理混杂文本、格式错误和解析失败。项目里优先使用 function calling，对不支持的模型再做 JSON fallback。

### Q3：如何处理 LLM 的上下文窗口限制？

关键是分层压缩，而不是硬塞全部内容。项目通过 repo-map 提供结构摘要，通过 TokenBudget 分配预算，通过 ConversationHistory 做滑动窗口，优先保留任务描述和关键 observation，裁剪旧历史和低优先级内容。

### Q4：如何防止 Agent 陷入死循环？

项目结合了多种手段：

- 连续重复动作检测
- `max_steps` 步数熔断
- reflection 机制引导重新规划

这比单纯依赖步数上限更有效。

### Q5：Agent 的工具设计有哪些关键考虑？

1. 接口统一  
2. 错误不直接崩溃主循环  
3. 输出可截断  
4. 有基础安全防护  
5. 尽量返回结构化 observation，方便模型继续决策

### Q6：如何实现工具调用的安全约束？

应用层通过 ShellTool 的危险命令拦截、低风险白名单和确认模式做基础防护；执行层通过 Docker demo runtime 提供演示级容器边界。这里强调的是工程上的可控性，不把它包装成更强的隔离承诺。

### Q7：如何设计 Agent 的状态管理？

项目更接近事件溯源思路：所有关键状态变化都写成事件，事件日志是 append-only 的 JSONL 文件，当前状态可以看作事件序列累计得到的结果。这样更利于调试、审计和回放。

### Q8：怎么做多模型支持？

核心是抽象层正确。先统一 message、tool schema 和 response，再抽象 backend 接口，把 provider 差异限制在 backend 内部，由 router 做集中选择。

### Q9：多轮对话的 history 如何跨轮传递？

chat 模式把共享的 `ConversationHistory` 注入给每轮 `Agent.run()`。本轮用户输入和 Agent 摘要都写回共享 history，下一轮继续复用，从而实现连续任务推进。

### Q10：流式输出时如何处理工具调用？

工具调用阶段不一定总有文本流出，因为模型可能输出的是结构化调用片段。处理方式是分别缓冲文本内容和工具调用参数，最终统一解析成 Action，并在 CLI 中同步展示工具步骤。

### Q11：如何评估 Coding Agent 的质量？

业界通常使用 SWE-bench 这类真实 GitHub issue 基准评估 Coding Agent，但本项目没有声称系统评测 SWE-bench，重点是工程链路实现和模块可验证性。实际评估可以关注任务完成率、步数效率、token 消耗、工具调用稳定性和错误恢复能力。

### Q12：repo-map 的作用是什么？为什么不直接读所有文件？

因为完整仓库通常超出上下文窗口。repo-map 提供的是“结构目录级”理解：有哪些模块、符号和文件值得进一步读，而不是一次把所有内容放进 prompt。这让 Agent 先导航，再按需读取具体文件。

### Q13：如何处理工具执行失败？

工具失败不直接等于任务失败。项目把失败包装成 observation 返还给 Agent，让模型有机会基于错误信息继续调整策略，例如改参数、换工具、补文件或终止任务。

### Q14：如何测试 Agent 的各个组件？

测试策略包括：

- MockBackend：隔离真实 API
- 临时目录 fixture：隔离文件系统副作用
- 真实工具测试：验证文件、Shell、Git 等工具行为
- Docker 相关测试：在不依赖真实 daemon 的路径上覆盖参数构造
- CLI 层测试：验证入口和边界命令

### Q15：Agent 项目的常见坑有哪些？

1. 上下文管理失控，导致 prompt 爆炸  
2. 工具输出不截断，导致 observation 挤占预算  
3. 没有终止条件，Agent 一直重复尝试  
4. 安全边界缺失，工具能力过强但没有防护  
5. 工具异常直接崩溃主循环  
6. 测试依赖真实 API，导致慢且不稳定  
7. prompt 与核心逻辑耦合太紧，难以维护和调试
