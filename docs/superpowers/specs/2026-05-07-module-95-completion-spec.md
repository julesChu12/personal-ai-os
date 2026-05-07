# Module 95% Completion SPEC

日期：2026-05-07

## 背景

当前项目已经具备 Personal AI OS 模板的核心底座：FastAPI 服务、OpenAI-compatible 接入、PostgreSQL/Qdrant/Obsidian 长期记忆、Tool Registry、最小 Agent Workflow、Scheduler、CLI、迁移、诊断、测试和 CI。上一轮代码审阅给出的主要缺口集中在：

- Agent 仍偏 Planner/Executor 最小闭环，Researcher/Coder/Memory 专项 Agent 仍为 stub。
- 兼容任务入口 `/task` 仍走旧 Orchestrator task mock，未复用 AgentWorkflow。
- 普通聊天 Orchestrator 仍是简单 RAG 上下文拼接。
- CLI 有已发现的人类输出字段错误。
- Scheduler 只有固定后台任务，没有可观测的运行状态。
- OpenAI-compatible usage 仍为固定 `0`，模型列表也偏静态。
- 记忆治理已有 update-or-create，但缺少更明确的质量分、来源和可解释治理口径。

本阶段目标不是把项目改造成最终用户一体化产品，而是把当前代码中已存在的每个工程模块提升到“模板可复用、行为可验证、缺口可显式 deferred”的 95% 完成度。

## 完成度定义

模块完成度达到 95% 必须同时满足：

- 有可调用的生产代码路径，不只是 stub 或文档声明。
- 有单元或合同测试覆盖成功路径、失败路径和至少一个边界场景。
- 用户/项目/session scope 不发生越权或串数据。
- 对外 API/CLI 输出稳定，可被脚本消费。
- 剩余 5% 是明确 deferred 的增强项，而不是核心功能缺失。

## 范围

### In Scope

- 修复 CLI 与 API 响应字段不一致问题。
- 为 Agent 模块补齐非 stub 的 Researcher、Coder、Memory Agent 基础能力。
- 让 AgentWorkflow 能在受控范围内使用这些 Agent 的能力，但外部动作仍必须经过 ToolRegistry。
- 让兼容 `/task` 入口复用 AgentWorkflow，为后续浏览器、网络搜索、数据库查询和代码执行等开放工具留出统一执行边界。
- 为 OpenAI-compatible 响应增加本地估算 usage，并保持兼容格式。
- 为 Scheduler 暴露只读状态，便于诊断与测试。
- 为 Memory 增加来源/质量治理的可验证 metadata，不破坏现有 schema。
- 更新测试、README/roadmap/testing 文档，使 95% 目标有可追踪证据。

### Out of Scope

- 不实现最终用户 UI 外壳；当前仍以 API/CLI/Open WebUI 为入口。
- 不开放任意 shell、删除文件或无约束文件覆盖。
- 不在本轮直接开放浏览器、网络搜索、数据库查询或任意代码执行工具；本轮只统一执行入口和审计边界。
- 不做 Obsidian 实时文件监听和自动冲突合并。
- 不引入 worker 队列、分布式调度或多租户管理后台。
- 不要求默认 CI 调用真实模型或真实 embedding provider。

## Requirements

### R1：CLI 模块必须正确显示核心 API 响应

Current state：`app.cli.main chat` 普通输出读取 `message` 字段，但 `/chat` 返回 `answer`。

Target state：CLI chat 在普通模式显示 `answer`，并保留兼容 fallback。

Acceptance：

- [x] `tests/test_cli.py` 覆盖 chat 普通输出显示 `answer`。
- [x] `python -m app.cli.main chat ... --json` 行为不变。

### R2：OpenAI-compatible 模块必须提供非零 usage 估算

Current state：非流式 `/v1/chat/completions` 返回 usage 三项固定为 `0`。

Target state：在 provider 未返回真实 usage 时，兼容层基于 prompt 和 answer 做稳定本地估算。

Acceptance：

- [x] 非流式响应包含 `prompt_tokens > 0`、`completion_tokens > 0`、`total_tokens` 为两者之和。
- [x] 估算逻辑不依赖真实 provider，不输出敏感信息。
- [x] 现有 OpenAI-compatible 鉴权、metadata、stream 行为不回退。

### R3：Agent 专项模块不能再是纯 stub

Current state：`ResearcherAgent`、`CoderAgent`、`MemoryAgentAgent` 仅回显输入。

Target state：三个 Agent 都提供可测试的结构化能力：

- Researcher：从任务和可用工具中生成受控 research notes。
- Coder：根据工具执行结果生成面向开发者的实现摘要和风险提示。
- Memory：把成功任务结果转换为 `MemoryCandidate`，交给 `MemoryPipeline` 持久化。

Acceptance：

- [x] 每个 Agent 有直接单元测试。
- [x] AgentWorkflow 的 trace 能体现 planner、executor、coder/memory 的贡献。
- [x] Memory Agent 不在失败任务上写入长期记忆。

### R4：AgentWorkflow 必须更接近真实任务闭环

Current state：AgentWorkflow 已有 Planner/Executor/ToolRun/AgentRun，但 answer 只是拼接工具输出。

Target state：AgentWorkflow 在工具执行后由 CoderAgent 生成结构化 answer，并由 MemoryAgent 决定可沉淀内容。

Acceptance：

- [x] 成功任务 answer 包含 step 摘要，而不是裸输出拼接。
- [x] 失败任务保留 fail-fast 和 AgentRun 审计。
- [x] 非法 plan 仍不写 ToolRun。

### R5：Scheduler 模块必须可观测

Current state：`/diagnostics` 能检查 scheduler 是否存在，但没有独立只读状态。

Target state：新增只读 scheduler status API，返回 job id、next run time、running 状态。

Acceptance：

- [x] 新增 endpoint 不需要写入数据库。
- [x] 测试覆盖 scheduler present 和 absent。
- [x] 不改变现有生命周期启动/关闭行为。

### R6：Memory 模块必须标记来源和治理 metadata

Current state：Memory 表有 `tags/importance/obsidian_path/qdrant_point_id`，但缺少统一来源与治理说明。

Target state：MemoryPipeline 写入 DB 和 Qdrant payload 时，补齐 `source`、`governance_version`、`quality_score` 等 metadata，优先使用现有 JSON 字段，不做破坏性迁移。

Acceptance：

- [x] 新写入 memory 的 tags 或 payload 能反映来源。
- [x] Qdrant payload 包含可解释 metadata。
- [x] 现有检索和 Obsidian 同步不回退。

### R7：文档必须反映真实 95% 状态

Current state：README/roadmap 已描述基础版完成，但没有逐模块 95% gate。

Target state：补充模块 95% SPEC/PLAN，并在 roadmap 中记录本阶段目标和 deferred 5%。

Acceptance：

- [x] SPEC 和 PLAN 文件存在。
- [x] 每个模块有明确 pass/fail 验收项。
- [x] Deferred 项目清楚，不与 95% 核心能力混淆。

### R8：兼容 `/task` 入口必须复用 AgentWorkflow

Current state：`POST /task` 仍调用旧 `Orchestrator.task()` mock，和 `/agents/run` 的 ToolRegistry、ToolRun、AgentRun、结构化 plan 能力割裂。

Target state：`POST /task` 作为兼容入口保留，但执行路径统一进入 `AgentWorkflow.run()`，支持 `planner_mode`、`execution_mode`、显式 `plan` 和 `memory_agent` 结果沉淀策略。

Acceptance：

- [x] `/task` 成功执行时写入 ToolRun 和 AgentRun。
- [x] `/task` 支持显式结构化 plan 和有限并行执行。
- [x] `/task` 只有显式传入 `memory_agent` 时才沉淀成功结果。
- [x] 后续新增浏览器、网络搜索、数据库查询、代码执行等工具时，不需要再为 `/task` 单独建第二套执行链路。

## Ambiguity Report

- Goal Clarity：0.90
- Boundary Clarity：0.85
- Constraint Clarity：0.82
- Acceptance Criteria：0.88
- Ambiguity：0.13

Gate：通过。该阶段可以进入计划与执行。
