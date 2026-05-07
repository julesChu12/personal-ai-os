# Module 95% Completion Implementation Plan

日期：2026-05-07

## Goal

把当前代码中的核心模块提升到 95% 模板完成度：核心能力真实可用、测试覆盖完整、剩余缺口明确 deferred。

## Priority Model

优先级按以下顺序排序：

1. 用户直接可见且已有明确 bug 的模块。
2. 会影响系统可信边界的模块。
3. 当前仍为 stub 或“基础版”差距最大的模块。
4. 提升可观测性和长期维护质量的模块。
5. 文档与路线图收口。

## Wave 1：直接缺陷与兼容层可信度

**目标模块：CLI、OpenAI-compatible、测试。**

- [x] 修复 CLI chat 普通输出读取 `answer`。
- [x] 为 CLI chat 增加测试。
- [x] 为 OpenAI-compatible 非流式响应增加 usage 估算。
- [x] 更新 OpenAI-compatible 测试，要求 usage 非零且 total 正确。
- [x] 跑 `uv run pytest tests/test_cli.py tests/test_openai_compat.py`。

## Wave 2：Agent 专项能力去 stub

**目标模块：agents、AgentWorkflow、tests。**

- [x] 实现 `ResearcherAgent.research_task()`，输出结构化 notes。
- [x] 实现 `CoderAgent.summarize_execution()`，输出结构化 answer。
- [x] 实现 `MemoryAgent.build_result_memory()`，返回 `MemoryCandidate | None`。
- [x] 让 `AgentWorkflow` 成功路径使用 CoderAgent 生成 answer。
- [x] 让 `AgentWorkflow` 通过 MemoryAgent 生成可沉淀候选。
- [x] 补直接 Agent 单元测试和 workflow 合同测试。

## Wave 3：Scheduler 可观测性

**目标模块：scheduler、diagnostics/API、tests。**

- [x] 新增 `/scheduler/status` 只读 endpoint。
- [x] 返回 scheduler running 状态、job id、next_run_time。
- [x] 覆盖 scheduler present/absent 测试。
- [x] README/testing 增加状态接口说明。

## Wave 4：Memory 治理 metadata

**目标模块：memory、vector payload、tests。**

- [x] 为 MemoryPipeline 增加治理 metadata builder。
- [x] Qdrant payload 包含 `source`、`governance_version`、`quality_score`。
- [x] tags 中保留来源标签，不破坏原 tag。
- [x] 覆盖新建、更新、向量失败降级测试。

## Wave 5：文档和整体验收

**目标模块：README、development roadmap、testing docs、全量回归。**

- [x] README 增加 95% 模块完成度说明。
- [x] development roadmap 增加本阶段目标和 deferred 5%。
- [x] docs/testing.md 增加新增回归入口。
- [x] 跑 `uv run pytest`。
- [x] 给出最终模块完成度表。

## Wave 6：兼容任务入口统一到 AgentWorkflow

**目标模块：`/task`、AgentWorkflow、开放工具准备、tests。**

- [x] 扩展 `TaskRequest`，支持 `planner_mode`、`execution_mode` 和显式 `plan`。
- [x] 将 `POST /task` 从旧 `Orchestrator.task()` 切换到 `AgentWorkflow.run()`。
- [x] `/task` 复用 ToolRegistry、ToolRun、AgentRun、request id 和 MemoryAgent 显式沉淀策略。
- [x] 增加 `/task` 成功执行、结构化 plan、有限并行和 memory_agent 回归测试。
- [x] 更新文档，说明后续浏览器、网络搜索、数据库查询、代码执行等工具将接入同一执行边界。

## Deferred 5%

- 最终用户 UI 外壳。
- Obsidian 实时监听和自动冲突合并。
- 真实 provider 默认 CI。
- 分布式任务队列和调度后台。
- 高级记忆治理：隐私分级、长期衰减、人工审批工作流。
- 浏览器、网络搜索、数据库查询、任意代码执行等开放工具的具体实现与安全策略。
