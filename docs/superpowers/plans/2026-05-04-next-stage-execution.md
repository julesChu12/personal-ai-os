# Next Stage Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the N1-N10 next-stage roadmap while preserving the current audited ToolRegistry, MemoryPipeline, ToolRun, and AgentRun boundaries.

**Architecture:** Implement each task as an incremental extension of existing modules. Do not add parallel execution, write tools, MCP exposure, or key-scope changes without tests that preserve auditability and scope isolation.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Qdrant, Typer, pytest, Docker Compose, GitHub Actions.

---

## Task N1: retrieval-quality-foundation 规格收尾验证

**Files:**
- Modify: `scripts/evaluate_retrieval_quality.py`
- Modify: `scripts/evaluate_qdrant_retrieval_quality.py`
- Modify: `tests/test_retrieval_quality.py`
- Modify: `tests/test_project_contracts.py`
- Modify: `README.md`
- Modify: `docs/testing.md`

- [x] **Step 1: Write failing tests for `--min-hit-rate`**

Add tests that run evaluator commands with a passing and failing threshold. Expected failing threshold must exit non-zero.

- [x] **Step 2: Add threshold option**

Implement `--min-hit-rate` in both evaluator scripts. Compare against report `hit_rate`.

- [x] **Step 3: Stabilize JSON output contract**

Ensure JSON reports include `hit_rate`, `total`, `hits`, `misses`, and `top_k`.

- [x] **Step 4: Update docs**

Document threshold semantics in README and `docs/testing.md`.

- [x] **Step 5: Verify**

Run:

```bash
make ci PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
DATABASE_URL="sqlite:///:memory:" EMBEDDING_PROVIDER=mock python scripts/evaluate_retrieval_quality.py --min-hit-rate 1.0
```

## Task N2: Planner 模型化

**Files:**
- Modify: `app/agents/planner.py`
- Modify: `app/agents/workflow.py`
- Modify: `app/api/routes_agents.py`
- Modify: `tests/test_agent_plan.py`
- Modify: `tests/test_agent_workflow.py`
- Modify: `tests/test_agents_route.py`
- Modify: `docs/testing.md`
- Modify: `docs/development-roadmap.md`

- [x] **Step 1: Add tests for model-generated plan acceptance and rejection**

Cover valid JSON, invalid JSON, unknown tool, unknown input, step limit, and provider failure.

- [x] **Step 2: Add model planner mode**

Introduce an explicit planner mode so existing deterministic planner remains default unless enabled.

- [x] **Step 3: Parse and validate model output**

Model output must become `raw_plan` and pass `validate_agent_plan(raw_plan, registry)`.

- [x] **Step 4: Preserve audit behavior**

Rejected model plans must not write ToolRun, but must write AgentRun.

- [x] **Step 5: Verify**

Run targeted agent tests and full `make ci`.

## Task N7: 多 API Key 与 user/project 绑定

**Files:**
- Create or modify: `app/core/auth.py`
- Modify: `app/config.py`
- Modify: `app/core/config_validation.py`
- Modify: `app/api/routes_openai_compat.py`
- Modify: `app/api/routes_tools.py`
- Modify: `app/api/routes_agents.py`
- Modify: `tests/test_config_validation.py`
- Modify: `tests/test_openai_compat.py`
- Modify: `tests/test_tools_route.py`
- Modify: `tests/test_agents_route.py`

- [x] **Step 1: Define key config format**

Support local default key plus optional structured key bindings.

- [x] **Step 2: Add auth helper**

Return authenticated principal with default `user_id`, `project_id`, and permissions.

- [x] **Step 3: Enforce scope binding**

Prevent request metadata from overriding a key-bound user/project outside its scope.

- [x] **Step 4: Update diagnostics/config validation**

Strict mode must flag unsafe defaults.

- [x] **Step 5: Verify**

Run auth-related tests, then `make ci`.

## Task N5: MCP Server 适配

Detailed execution plan: `docs/superpowers/plans/2026-05-04-n3-n5-execution-plan.md`.

**Files:**
- Create: `app/tools/mcp_server.py`
- Create or modify: `scripts/run_mcp_server.py`
- Modify: `app/tools/registry.py`
- Create: `tests/test_mcp_server.py`
- Modify: `docs/testing.md`
- Modify: `README.md`

- [x] **Step 1: Add protocol tests for tool list and tool call**

Use a lightweight test double if full MCP client is too heavy for unit tests.

- [x] **Step 2: Map MCP tool list to ToolRegistry definitions**

Do not duplicate tool schema.

- [x] **Step 3: Map MCP tool call to ToolRegistry.invoke**

Preserve ToolRun audit path.

- [x] **Step 4: Keep first version read-only**

Expose only existing low-risk tools.

- [x] **Step 5: Verify**

Run MCP tests, tool tests, and full `make ci`.

## Task N3a: Executor 条件分支与顺序 DAG

Detailed execution plan: `docs/superpowers/plans/2026-05-04-n3-n5-execution-plan.md`.

**Files:**
- Modify: `app/agents/planner.py`
- Modify: `app/agents/workflow.py`
- Modify: `tests/test_agent_plan.py`
- Modify: `tests/test_agent_workflow.py`
- Modify: `tests/test_agents_route.py`

- [x] **Step 1: Extend plan schema**

Add step `id`, optional `depends_on`, and optional condition field.

- [x] **Step 2: Reject invalid dependency graphs**

Reject duplicate ids, missing dependencies, and cycles.

- [x] **Step 3: Execute in dependency order**

Keep execution sequential.

- [x] **Step 4: Record skipped steps**

Skipped steps appear in AgentRun trace, not ToolRun.

- [x] **Step 5: Verify**

Run agent tests and full `make ci`.

## Task N4: 写类工具白名单

Detailed execution plan: `docs/superpowers/plans/2026-05-04-n3-n5-execution-plan.md`.

**Files:**
- Modify: `app/tools/file_tool.py`
- Modify: `app/tools/registry.py`
- Create or modify: `app/tools/obsidian_tool.py`
- Modify: `tests/test_tool_registry.py`
- Modify: `tests/test_tools_route.py`
- Modify: `docs/testing.md`

- [x] **Step 1: Add failing tests for path escape and audit**

Write tests before adding write implementations.

- [x] **Step 2: Implement `file.write_text`**

Allow writes only inside configured base directory.

- [x] **Step 3: Implement `obsidian.append_note`**

Append to Obsidian-controlled path only.

- [x] **Step 4: Keep MCP default read-only**

Do not expose write tools through MCP by default.

- [x] **Step 5: Verify**

Run tool tests and full `make ci`.

## Task N3b: Executor 有限并行

Detailed execution plan: `docs/superpowers/plans/2026-05-04-n3-n5-execution-plan.md`.

**Files:**
- Modify: `app/tools/registry.py`
- Modify: `app/agents/workflow.py`
- Modify: `tests/test_agent_workflow.py`
- Modify: `tests/test_agents_route.py`

- [x] **Step 1: Add side-effect classification**

Classify tools as read-only or write.

- [x] **Step 2: Add concurrency limit**

Use a conservative default and config override.

- [x] **Step 3: Parallelize only safe independent steps**

Write steps stay serial.

- [x] **Step 4: Stabilize response ordering**

Return steps in plan order even when executed concurrently.

- [x] **Step 5: Verify**

Run agent workflow tests and full `make ci`.

## Task N6: Obsidian 单向导入

**Files:**
- Create: `app/memory/obsidian_importer.py`
- Create: `scripts/import_obsidian_vault.py`
- Create: `tests/test_obsidian_importer.py`
- Modify: `docs/testing.md`
- Modify: `README.md`

- [x] **Step 1: Add importer fixture tests**

Cover first import, repeat import, and modified file update.

- [x] **Step 2: Implement markdown scanner**

Read only configured vault path.

- [x] **Step 3: Map files to MemoryCandidate**

Use deterministic identity and content hash.

- [x] **Step 4: Reuse MemoryPipeline**

Do not add parallel persistence logic.

- [x] **Step 5: Verify**

Run importer tests, memory tests, and full `make ci`.

## Task N8: 真实 embedding 在线质量回归

**Files:**
- Modify: `scripts/evaluate_retrieval_quality.py`
- Modify: `scripts/evaluate_qdrant_retrieval_quality.py`
- Create or modify: `.github/workflows/retrieval-quality.yml`
- Modify: `docs/testing.md`

- [x] **Step 1: Keep default CI mock-only**

Do not require secrets for normal push CI.

- [x] **Step 2: Add manual workflow or documented command**

Use `workflow_dispatch` if adding GitHub Actions.

- [x] **Step 3: Redact provider details**

Reports must not include API keys.

- [x] **Step 4: Verify**

Run mock mode locally and confirm manual path is opt-in.

## Task N9: CLI 升级

**Files:**
- Modify: `app/cli/main.py`
- Create: `tests/test_cli.py`
- Modify: `README.md`
- Modify: `docs/testing.md`

- [x] **Step 1: Add CLI tests**

Use HTTP stubs or monkeypatch `httpx`.

- [x] **Step 2: Add `agents run`**

Print answer and agent_run_id.

- [x] **Step 3: Add `agents runs`**

Require user/project scope.

- [x] **Step 4: Add `--json` and error codes**

Non-2xx responses exit non-zero.

- [x] **Step 5: Verify**

Run CLI tests and full `make ci`.

## Task N10: 移除 `create_all` 兼容路径

**Files:**
- Modify: `app/db/database.py`
- Modify: `app/main.py`
- Modify: `tests/test_db_migrations.py`
- Modify: `tests/test_scheduler_lifecycle.py`
- Modify: `README.md`
- Modify: `docs/testing.md`

- [x] **Step 1: Add failing startup test**

Service should fail clearly when schema is missing and migrations were not run.

- [x] **Step 2: Remove startup `create_all`**

Keep migration runner as the only schema creation path.

- [x] **Step 3: Update Docker/startup docs**

Document migration-first flow.

- [x] **Step 4: Verify**

Run full `make ci` and Docker smoke.

## Handoff

N1, N2, N7, N5, N3a, N4, N3b, N6, N8, N9, and N10 are complete. Next task candidates should come from the post-P4 backlog: Obsidian 双向同步、最终用户 UI 外壳、真实用户数据治理策略、以及更完整的部署/发布硬化。
