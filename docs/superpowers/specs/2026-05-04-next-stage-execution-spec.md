# Next Stage Execution SPEC

日期：2026-05-04

## 背景

Personal AI OS 当前已经完成 P0-P3 基础底座：服务硬化、运行质量、工具层、最小 Agent 工作流、审计、记忆沉淀、开源工程化和 GitHub CI。项目下一阶段不应重写底座，而应沿既有边界纵向增强真实任务能力。

核心边界保持不变：

- 外部工具调用必须经过 `ToolRegistry`。
- 工具调用必须写入 `ToolRun`。
- Agent 任务必须写入 `AgentRun`。
- 记忆写入必须复用 `MemoryPipeline`。
- 用户、项目和会话 scope 必须显式，不允许跨 scope 泄露。
- 新增 provider、协议或写工具不得破坏 `/chat`、`/v1/chat/completions` 和现有 memory/search 合同。

## 目标

本 SPEC 定义 N1-N10 下一阶段执行主线，用于把项目从“可信最小 Agent 底座”推进到“可接外部协议、可规划真实任务、具备安全前置和质量回归”的模板。

## 非目标

- 不实现完整 UI 产品外壳。
- 不引入微服务、消息队列或 worker 池。
- 不直接做 Obsidian 双向同步。
- 不开放任意 shell、删除文件或无限制写文件。
- 不在默认 CI 中消耗真实 provider key。

## 任务优先级

| 序号 | 任务 | 优先级 | 估算 | 状态 |
| --- | --- | --- | --- | --- |
| N1 | retrieval-quality-foundation 规格收尾验证 | P0 | 0.5-1 天 | 已完成 |
| N2 | Planner 模型化：受控生成结构化 plan | P0 | 2-3 天 | 已完成 |
| N7 | 多 API Key 与 user/project 绑定 | P1 | 2 天 | 已完成 |
| N5 | MCP Server 适配：只读暴露 Tool Registry | P1 | 2 天 | 已完成 |
| N3a | Executor 条件分支与顺序 DAG | P1 | 1-2 天 | 已完成 |
| N4 | 写类工具白名单 | P1 | 1-2 天 | 已完成 |
| N3b | Executor 有限并行 | P2 | 1-2 天 | 已完成 |
| N6 | Obsidian 单向导入 | P2 | 2-3 天 | 已完成 |
| N8 | 真实 embedding 在线质量回归 | P2 | 1 天 | 已完成 |
| N9 | CLI 升级 | P3 | 1 天 | 待执行 |
| N10 | 移除 `create_all` 兼容路径 | P3 | 0.5 天 | 待执行 |

## Requirements

### R1：检索质量回归必须成为稳定规格

系统必须固定 retrieval quality 的评估输入、输出 schema、最小命中率阈值和失败退出码。

验收：

- `scripts/evaluate_retrieval_quality.py` 支持 `--min-hit-rate`。
- `scripts/evaluate_qdrant_retrieval_quality.py` 支持同等阈值语义。
- JSON 输出包含稳定字段：`hit_rate`、`total`、`hits`、`misses`、`top_k`。
- 阈值不满足时命令返回非零退出码。

### R2：模型化 Planner 只能生成计划，不能绕过校验

系统可以让模型生成结构化 plan，但模型输出必须先通过 `validate_agent_plan()`。任何非法工具、未知字段、超限 step 或格式错误都必须被拒绝。

验收：

- 合法模型 plan 能进入 Executor。
- 非法模型 plan 不执行工具、不写 ToolRun。
- 拒绝结果写入 AgentRun。
- provider 失败返回可理解错误，不泄露敏感内容。

### R3：外部访问必须有 key 到 scope 的绑定

系统必须支持多 API key，并能把 key 绑定到默认 `user_id/project_id` 或权限等级。请求 metadata 不得越权覆盖 key 绑定 scope。

验收：

- 本地开发仍支持默认 key，但 strict 模式标记风险。
- 多 key 配置可解析。
- 错误 key 返回稳定鉴权错误。
- 跨 scope 请求被拒绝或按绑定 scope 收敛。

### R4：MCP Server 必须复用 Tool Registry

系统必须通过 MCP 暴露工具，但不能重复实现工具边界。第一版只暴露只读或低风险工具。

验收：

- MCP tool list 与 Tool Registry schema 一致。
- MCP tool call 复用 ToolRegistry。
- MCP 调用写入 ToolRun。
- 默认不暴露写工具。

### R5：Executor DAG 必须先顺序、后并行

系统必须先实现条件分支和顺序 DAG，再实现有限并行。并行只能在依赖图、失败传播和工具副作用分类明确后启用。

验收：

- 循环依赖被拒绝。
- 条件跳过记录到 AgentRun trace。
- 失败仍遵循 fail-fast。
- 并行只允许安全步骤，写工具默认串行。

### R6：写工具必须保守、白名单、可审计

系统可以新增写类工具，但必须限制路径、限制能力、记录审计，并默认不通过 MCP 暴露。

验收：

- 不能写出允许目录。
- 不支持删除或任意覆盖敏感文件。
- 成功和失败都写 ToolRun。
- 写工具 schema 明确 required 字段和边界。

### R7：Obsidian 先做单向导入

系统必须先支持 vault 到 DB/Qdrant 的幂等导入，不做双向同步。

验收：

- 重复运行不重复写入。
- 文件修改可更新记忆。
- 文件删除不自动删除 DB 记录。
- 不引入文件监听。

### R8：真实 embedding 回归必须显式运行

系统必须支持真实 provider 的手动质量回归，但默认 CI 不消耗真实 key。

验收：

- 手动命令可用环境变量切换真实 provider。
- 报告不输出 key。
- 可以复用 N1 的 hit-rate 口径。

### R9：CLI 必须能调试 Agent

CLI 必须支持最小 Agent run 和 run 查询，便于开发者不借助 Web UI 验证系统。

验收：

- `agents run` 返回 `agent_run_id`。
- `agents runs` 支持 user/project scope。
- `--json` 输出可被脚本消费。
- HTTP 错误映射为非零退出码。

### R10：migration 最终成为 schema 单一来源

系统最终必须移除启动时 `create_all`，但必须等前序 schema 变化稳定后执行。

验收：

- 未运行 migration 时服务给出明确错误。
- CI、Docker smoke 和文档都使用 migration-first 流程。

## 执行顺序

1. N1 retrieval-quality-foundation 规格收尾验证
2. N2 Planner 模型化
3. N7 多 API Key 与 user/project 绑定
4. N5 MCP Server 适配
5. N3a Executor 条件分支与顺序 DAG
6. N4 写类工具白名单
7. N3b Executor 有限并行
8. N6 Obsidian 单向导入
9. N8 真实 embedding 在线质量回归
10. N9 CLI 升级
11. N10 移除 `create_all` 兼容路径

## 验证策略

每个任务完成后至少运行：

```bash
make ci PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

涉及运行中服务时额外运行：

```bash
docker compose exec -T api bash scripts/smoke_api.sh
```

涉及检索质量时额外运行：

```bash
DATABASE_URL="sqlite:///:memory:" EMBEDDING_PROVIDER=mock python scripts/evaluate_retrieval_quality.py
DATABASE_URL="sqlite:///:memory:" QDRANT_URL="http://127.0.0.1:6333" QDRANT_COLLECTION="personal_ai_os_quality_eval" EMBEDDING_PROVIDER=mock python scripts/evaluate_qdrant_retrieval_quality.py
```
