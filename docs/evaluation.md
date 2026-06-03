# Forge Agent Evaluation

## 一、评测目标

本评测用于验证 Forge Agent 是否已经具备一个工程化 Coding Agent MVP 的核心闭环能力，即：

自然语言任务理解 → 仓库探索 → 工具调用 → 多文件修改 → `pytest` 验证 → `git diff` / `git status` 检查 → event log 复盘。

这里的重点不是单次代码生成，而是 Agent 是否能够围绕真实仓库持续执行多轮决策，并根据工具反馈推进任务直至完成或暴露边界条件。

## 二、评测环境

- Forge Agent 主项目：`C:\Users\DELL\Desktop\forge-agent-main`
- Level 1 评测仓库：`C:\Users\DELL\Desktop\forge-agent-eval-target`
- Level 2 评测仓库：`C:\Users\DELL\Desktop\forge-agent-eval-app`
- Provider：`deepseek`
- Model：`deepseek-chat`
- Forge Agent 工程基线：最近一次完整 `pytest -q` 验证结果为 `502 passed, 17 skipped`
- 真实任务运行日志保存在 `logs\*.jsonl`

说明：

- 本文档仅记录真实本地运行结果。
- 本评测不是 SWE-bench，也不声称进行过 SWE-bench 跑分。
- 当前 Docker runtime / shell guardrails 仅作为工程边界和演示能力的一部分，不在此文档中表述为强隔离安全方案。

## 三、Level 1：轻量函数级任务

Level 1 使用 `forge-agent-eval-target`，主要验证基础闭环：能否从自然语言任务出发，完成仓库阅读、单文件或轻量多文件修改、测试验证与日志留痕。

| ID | Task | Result | Steps | Tokens | Time | Pytest | Log |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | Bug 修复 | passed | 7 | 9,198 | 13.3s | `5 passed` | `logs\e4217234_20260603_074436.jsonl` |
| T2 | 单元测试补全 | passed | 10 | 15,454 | 21.2s | `8 passed` | `logs\2391d395_20260603_075413.jsonl` |
| T3 | 小功能添加 | passed | 10 | 16,898 | 23.5s | `11 passed` | `logs\e1ea6ca3_20260603_080843.jsonl` |
| T4 | 文档同步 | passed | 9 | 14,340 | 20.2s | `11 passed` | `logs\e78e7259_20260603_081243.jsonl` |
| T5 | 行为保持式重构 | passed | 8 | 15,086 | 17.2s | `11 passed` | `logs\c68bdb08_20260603_081549.jsonl` |

观察：

- Level 1 的 5 个任务均完成。
- 这些任务覆盖了 bug 修复、测试补齐、功能增加、README 同步和不改变行为的重构。
- 从 event log 看，Agent 可以稳定走完读文件、写文件、跑测试、查看 diff 的基础闭环。

## 四、Level 2：项目级多文件任务

Level 2 使用 `forge-agent-eval-app`，仓库中包含 `models`、`config`、`storage`、`service`、`filters`、`cli`、`errors`、`tests`、`docs` 等模块，用于验证 Forge Agent 在项目级多文件任务中的行为。

| ID | Task | Result | Steps | Tokens | Time | Pytest | Log |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L2-T1 | 多文件 bug 修复 | passed | 21 | 98,382 | 47.5s | `19 passed` | `logs\2a0bebed_20260603_083911.jsonl` |
| L2-T2 | priority 支持增强 | passed | 14 | 60,638 | 41.9s | `24 passed` | `logs\85018575_20260603_084400.jsonl` |
| L2-T3 | tags 支持增强 | functionally passed / post-completion provider error | 22 | 131,146 | 59.0s | `33 passed` | `logs\9fa30b29_20260603_084925.jsonl` |
| L2-T4 | README/docs usage 同步 | passed | 9 | 30,030 | 20.7s | `passed` | `logs\40d539d4_20260603_085827.jsonl` |
| L2-T5 | service helpers 重构 | passed | 7 | 21,952 | 18.4s | `passed` | `logs\b14833d5_20260603_090116.jsonl` |
| L2-T6 | Git 状态与测试复盘 | passed | 4 | 7,937 | 9.9s | `passed` | `logs\95294463_20260603_090458.jsonl` |

补充说明：

- `L2-T3` 在代码与测试层面完成后，生成了提交 `f99a487`，功能上已经通过，但最终总结阶段触发 provider message-history 错误，因此单独标记为 `functionally passed`。
- `L2-T4`、`L2-T5`、`L2-T6` 的日志中可以确认任务完成；其中 `L2-T4` 与 `L2-T5` 的摘要里还保留了 `pytest -q` 通过记录。

## 五、重点案例分析

### L2-T1：多文件 bug 修复

这是一个比较典型的项目级修复任务。初始仓库故意保留了 3 个可修复缺陷：

- `save_tasks()` 不创建父目录
- `get_data_path()` 忽略 `MINIAPP_DATA_DIR`
- `complete_task()` 找不到任务时返回 `None`

Agent 根据 3 个失败测试，首先定位到：

- `src/miniapp/config.py`
- `src/miniapp/storage.py`
- `src/miniapp/service.py`

随后在修复过程中继续发现 CLI 层与异常语义之间存在适配问题：`complete_task()` 改为抛 `TaskNotFoundError` 后，`src/miniapp/cli.py` 也需要同步调整，否则 CLI 仍然按旧的 `None` 返回值路径处理。最终 Agent 继续修改 `cli.py`，把服务层语义和 CLI 层行为对齐，测试全部通过。

这个案例说明 Forge Agent 已经不只是“按失败测试修一行代码”，而是能够：

- 从失败测试反推多个模块
- 在修复主缺陷后继续发现次级影响面
- 把服务层和入口层的行为统一起来
- 用 `pytest` 验证最终结果

### L2-T3：tags 支持增强

`L2-T3` 是一个更接近真实开发的小功能扩展任务。Agent 在该任务中完成了 `tags` 相关能力扩展，并把测试跑到 `33 passed`。同时，仓库还留下了对应提交：

- `f99a487` — `Add tags support to miniapp`

但在任务最后的总结阶段，provider / backend 兼容性边界被触发，导致 run 以错误结束。也就是说：

- 代码结果：通过
- 测试结果：通过
- 提交结果：已生成
- Agent 最终状态：因为 provider 消息历史错误而显示失败

因此，这个任务在本文档中记录为：

`functionally passed / post-completion provider error`

这个案例很重要，因为它反映的是 Provider / backend 协议边界，而不是任务代码本身失败。

## 六、Provider Compatibility Findings

本次真实评测里记录到了两类 Provider / backend 兼容性边界问题。

### 1. `deepseek-v4-flash` thinking mode 触发 `reasoning_content` round-trip 错误

在日志 `logs\2b621e10_20260603_074100.jsonl` 中，记录了如下失败原因：

- `The reasoning_content in the thinking mode must be passed back to the API.`

这说明在 OpenAI-compatible 流式 thinking 路径中，`reasoning_content` 的回传契约需要更严格处理。该问题属于 Provider / backend 兼容性边界，而不是任务仓库代码错误。

### 2. L2-T3 长工具链后触发 tool message history 错误

在日志 `logs\9fa30b29_20260603_084925.jsonl` 中，记录了如下失败原因：

- `Messages with role 'tool' must be a response to a preceding message with 'tool_calls'`

这一错误发生在 `L2-T3` 已经完成代码修改、测试通过并生成提交之后，说明问题出在长链路、多轮工具调用后的消息历史兼容性，而不是 `forge-agent-eval-app` 的功能实现失败。

结论上，这两类问题都应归类为：

- Provider / backend 兼容性边界
- 不是任务代码失败
- 不是仓库逻辑错误

## 七、结论

基于本次本地真实运行结果，可以得出的结论是：

Forge Agent 已经完成工程化 MVP 的核心闭环，能够在真实小型项目中完成：

- 多文件 bug 修复
- 跨文件功能添加
- 文档同步
- 行为保持式重构
- `git status` / `git diff` / 日志复盘

从 Level 1 到 Level 2，Agent 已经展示出稳定的仓库探索、工具调用、测试驱动修复和多文件协同修改能力。

同时，也要明确当前边界：

- 当前评测不是 SWE-bench
- 高级上下文调度仍有继续优化空间
- 断点续跑与更强 replay 能力尚未完成
- 当前不应表述为强安全隔离方案
- 更严格的 provider 消息历史兼容仍是后续优化方向

因此，更准确的表述是：

Forge Agent 已经是一个可运行、可验证、可扩展的 Coding Agent 工程化 MVP，并且在真实小型项目任务上已经证明了核心闭环可用。
