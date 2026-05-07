# Testing Strategy

本项目的回归测试重点覆盖能直接影响运行稳定性的合同，而不是只验证实现细节。

## 测试入口

```bash
make ci PYTHON=python
```

该命令执行：

```bash
DATABASE_URL="sqlite:///:memory:" python -m compileall -q app tests
DATABASE_URL="sqlite:///:memory:" python -m pytest -q
DATABASE_URL="sqlite:///:memory:" python scripts/run_migrations.py --dry-run
```

## Docker smoke

当 Docker Compose 栈已启动后，运行：

```bash
bash scripts/smoke_api.sh
```

该脚本会检查：

- `/health`
- `/diagnostics`
- `/v1/models`
- OpenAI-compatible auth 负向路径
- `/memory/ingest`
- `/memory/search`

脚本默认使用：

```bash
API_BASE_URL=http://127.0.0.1:8000
OPENAI_COMPAT_API_KEY=EMPTY
```

如需验证完整聊天写入与记忆检索闭环：

```bash
SMOKE_RUN_CHAT=1 bash scripts/smoke_api.sh
```

该模式会调用 `/chat` 写入一条 smoke 会话，并通过 `/memory/search` 验证同一用户和项目范围内可以召回记忆。

## Diagnostics API

`/health` 用于轻量存活检查，适合 Docker 或负载均衡器探活。

`/diagnostics` 用于人工排障，返回状态为：

```text
ok | degraded | error
```

当前诊断项包括：

- `config`
- `database`
- `qdrant`
- `embedding`
- `model`
- `scheduler`

诊断响应会描述当前 provider、collection、维度和依赖状态，但不得返回 API key、数据库密码或完整连接串。

## API error contract

内部 API 错误响应统一使用：

```text
{error: {code, message, type}}
```

当前覆盖范围包括：

- `HTTPException`：保留业务 message，按 HTTP status 生成稳定 code。
- `RequestValidationError`：返回 `validation_error` 和 `request validation failed`。
- 未捕获异常：统一返回 `internal_error` 和 `internal server error`，响应不得泄露异常原文、API key、数据库密码或完整连接串。

OpenAI-compatible 路由 `/v1/*` 保持兼容格式：

```text
{error: {message, type, code}}
```

例如鉴权失败返回 `authentication_error`，请求格式错误返回 `invalid_request_error`。

## Request id and request logs

每个 HTTP 请求都会通过 middleware 绑定 request id，并在响应头返回：

```text
X-Request-ID
```

调用方传入 `X-Request-ID` 时服务会复用该值；缺失时服务会生成 UUID。业务 handler 和错误处理器可以通过请求上下文读取同一个 request id。

请求完成日志使用 `app.core.request_context` logger，核心字段为：

```text
request_id, path, method, status, duration_ms
```

未捕获异常日志使用 `app.core.errors` logger，核心字段为：

```text
request_id, path, method, status, exception_type
```

异常日志不得记录异常原文、API key、数据库密码或完整连接串。响应错误体仍遵循 API error contract。

## Session and project identity

OpenAI-compatible `/v1/chat/completions` 的身份解析规则：

- `user_id`：优先使用 `metadata.user_id`，其次使用 OpenAI `user` 字段，缺失时默认 `openwebui`。
- `project_id`：优先使用 `metadata.project_id`，缺失时默认 `openwebui`。
- `session_id`：优先使用 `X-Session-Id` header，其次使用 `metadata.session_id`，缺失时生成 UUID。

所有身份字段都会 trim；空字符串会被视为缺失值。推荐 Open WebUI 在请求体中传入：

```json
{
  "metadata": {
    "user_id": "alice",
    "project_id": "personal-ai-os",
    "session_id": "chat-2026-05-01"
  }
}
```

`/sessions` 查询必须同时提供非空 `user_id` 和 `project_id`，服务会按精确 scope 查询，不会跨项目返回 session。空 scope 会返回统一 400 错误，例如 `project_id must not be blank`。

## Memory governance

长期记忆写入采用确定性 update-or-create 策略：

- 记忆身份由 `user_id, project_id, memory_type, title` 组成。
- `memory_type` 会 trim 并转小写，`title` 会 trim，防止空白或大小写差异产生重复记忆。
- 同身份且内容完全相同的记忆会跳过，不重复写入 Obsidian、Qdrant 或数据库。
- 同身份但内容变化的记忆会复用原 `qdrant_point_id` upsert 向量，成功后再更新现有 DB row，保持 DB 和 Qdrant 可追踪。
- 不同 `project_id` 或不同 `user_id` 的同标题记忆必须保持隔离，不能互相更新。

新增记忆的向量写入失败时仍保留 DB 和 Obsidian 记录；如果是更新已有记忆，则保留原 DB row 和原 `qdrant_point_id`，避免检索返回旧向量但 DB 已变新的不一致状态。

Obsidian 单向导入使用同一套记忆身份和 `MemoryPipeline.persist()`。导入前建议先执行：

```bash
python scripts/import_obsidian_vault.py --vault-path ./data/obsidian --user-id jules --project-id personal-ai-os --dry-run --json
```

报告会区分 `created / updated / unchanged / skipped / failed`，dry-run 不写 DB、Obsidian 或 Qdrant。正式导入仍保持串行执行，便于定位失败文件。

## Runtime config check

启动服务或发布镜像前，可以先运行静态配置检查：

```bash
python scripts/check_runtime_config.py
```

本地默认配置允许返回 `degraded`，用于提醒开发者当前仍在使用 `OPENAI_COMPAT_API_KEY=EMPTY`、mock embedding 或 mock model provider。

部署、CI release gate 或正式环境建议使用严格模式：

```bash
python scripts/check_runtime_config.py --strict
```

严格模式会把危险默认值提升为 `error` 并返回非零退出码。需要机器读取时使用：

```bash
python scripts/check_runtime_config.py --json
```

该脚本只做静态配置检查，不连接数据库、Qdrant 或模型 provider；检查结果不得输出 API key、数据库密码或完整连接串。

## Database migrations

数据库 migration 入口：

```bash
python scripts/run_migrations.py --dry-run
```

`--dry-run` 用于查看已应用和待应用 revision，不创建或修改表。

应用 migration：

```bash
python scripts/run_migrations.py
```

输出 JSON：

```bash
python scripts/run_migrations.py --json
```

当前 CI 会执行 `migration-smoke`，使用 `DATABASE_URL=sqlite:///:memory:` 验证 migration 入口可加载。应用启动不再调用 `Base.metadata.create_all`；`app.db.database.init_db()` 只校验 required tables 是否存在，缺少 schema 时会提示先运行 `python scripts/run_migrations.py` 并失败。Docker Compose 的 API command 会先执行 migration，再启动 Uvicorn。

## Open WebUI startup

Open WebUI 默认通过 Docker 内部网络访问 API：

```env
OPENAI_API_BASE_URL=http://api:8000/v1
OPENAI_API_KEY=EMPTY
```

Open WebUI 首次启动可能会下载 RAG embedding 模型。Compose 默认显式配置：

```env
HF_ENDPOINT=https://hf-mirror.com
HF_TOKEN=
OPENWEBUI_RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
OPENWEBUI_RAG_EMBEDDING_MODEL_AUTO_UPDATE=true
```

如果 `/health` 未 ready 且日志停在 `Fetching ... files`，优先检查 HuggingFace 网络、`HF_TOKEN`、`HF_ENDPOINT` 和 embedding 模型是否已缓存。

## Embedding provider 检查

本地或 Docker 环境切换真实 embedding provider 后，先运行：

```bash
python scripts/check_embedding_provider.py
```

脚本会调用当前配置的 provider 生成测试向量，并校验其维度与 `EMBEDDING_DIMENSION` 一致。

## Provider reliability

真实 model provider 和 embedding provider 共用以下可靠性配置：

```env
PROVIDER_TIMEOUT_SECONDS=120
PROVIDER_RETRY_ATTEMPTS=1
```

`PROVIDER_TIMEOUT_SECONDS` 会传给 OpenAI-compatible client 或 HTTP client；`PROVIDER_RETRY_ATTEMPTS` 表示单次 provider 操作的最大尝试次数，最小为 1。provider 请求失败会被包装为 `ProviderRequestError`，超时会被包装为 `ProviderTimeoutError`，错误消息不得包含 API key、完整连接串或 provider 返回的敏感原文。

`/diagnostics` 会展示当前 model/embedding provider 的 timeout 和 retry 配置，便于排查真实 provider 的网络和限流问题。

OpenAI-compatible model provider 和 embedding provider 只使用项目级 `retry_provider_call`，SDK 内部 retry 设为 0。MiniMax stream 在读取 SSE 前会检查 HTTP 状态，失败时包装为统一 provider 错误。

provider 错误响应和日志只能暴露稳定错误摘要，不得拼接 provider 原始异常、HTTP response body、API key 或完整连接串。相关回归由 `tests/test_provider_reliability.py`、`tests/test_errors.py` 和 `tests/test_request_context.py` 覆盖。

OpenAI-compatible 非流式响应在 provider 未提供真实 usage 时会使用本地 deterministic 估算，保证 `prompt_tokens`、`completion_tokens` 和 `total_tokens` 可被客户端稳定消费。相关回归在 `tests/test_openai_compat.py`。

## Tool adapter

P2 工具层的回归重点是工具边界稳定、危险能力默认受控、调用可审计：

- `tests/test_tool_registry.py` 覆盖默认工具枚举、工作目录内文件读取、路径逃逸拒绝、shell allowlist 和未知工具拒绝。
- `tests/test_tools_route.py` 覆盖 `GET /tools`、`POST /tools/{tool_name}/invoke` 和 `GET /tools/runs`。
- `tests/test_db_migrations.py` 覆盖 `tool_runs` 表随 migration 创建。

工具调用必须提供 `user_id` 和 `project_id`，用于审计和后续 Agent 任务归属。`shell.run_safe` 只能执行 allowlist 中的 `pwd`、`ls`、`git status`，不能把任意 shell 命令暴露给 HTTP adapter。

MCP first slice exposes read-safe Tool Registry entries through a JSON-RPC stdio runner. It supports `tools/list` and `tools/call`, maps Tool Registry `input_schema` to MCP `inputSchema`, and records every `tools/call` as a `ToolRun`. Write tools are not exposed through MCP by default.

```bash
python scripts/run_mcp_server.py
```

## Agent workflow

P3-1 最小 Agent 工作流的回归重点是 Planner / Executor 不绕过 Tool Registry：

- `tests/test_agent_workflow.py` 覆盖 `AgentWorkflow` 能把 `read file <path>` 规划为 `file.read_text`，执行后写入 `ToolRun` 审计记录。
- `tests/test_agents_route.py` 覆盖 `POST /agents/run` 的最小 API 合同和 unsupported task 降级。
- `tests/test_task_route.py` 覆盖兼容入口 `POST /task` 也走同一套 AgentWorkflow、ToolRun 和 AgentRun 审计，并支持显式结构化 plan 与有限并行模式。
- `tests/test_project_contracts.py` 锁定 Planner、Executor、Workflow 和文档状态，避免后续改动绕开工具层。

当前 Planner 只支持 `read file <path>`、`pwd` / `show cwd`、`git status` 三类确定性任务。任意 shell、删除、写文件等能力不会被规划，unsupported task 返回 `status=error` 且不写 tool run。

Researcher、Coder、Memory Agent 不再是纯回显 stub。`tests/test_agent_specialists.py` 覆盖 Researcher 的受控 notes、Coder 的工具结果摘要和 Memory Agent 的成功结果候选构造。AgentWorkflow 成功路径会记录 Coder 摘要步骤，失败路径仍保持 fail-fast。

## Structured Agent Plan

P3-2 结构化计划的回归重点是外部或模型生成的 plan 必须先过 schema 校验，再进入 Executor：

- `tests/test_agent_plan.py` 覆盖 `steps[{tool_name,input,reason}]` 的结构校验、未知工具拒绝、required input 校验、enum 校验、step 数量上限和未知 input 字段拒绝。
- `tests/test_agent_workflow.py` 覆盖 `AgentWorkflow.run(..., plan_payload=...)` 的成功执行和失败拒绝。
- `tests/test_agents_route.py` 覆盖 `POST /agents/run` 可接受显式 `plan`，同时拒绝空 `user_id/project_id` 并把空 `session_id` 归一为 `null`。

结构化计划只允许调用 Tool Registry 已注册的工具。`shell.run_safe.command` 必须匹配工具 schema 中的 enum，例如 `pwd`、`ls`、`git status`；`cat /etc/passwd` 这类命令会在计划校验阶段被拒绝，且不写入 tool run。

外部 plan 当前最多允许 10 个步骤，且 `input` 只能包含工具 schema 声明过的字段。这个限制用于避免单请求工具调用放大，以及避免未声明字段进入 `ToolRun.input_payload` 审计记录。

## Executor failure short-circuit

P3-3 多步骤执行的回归重点是 failure short-circuit：顺序执行的 plan 一旦某个 step 返回 `status=error`，Executor workflow 必须停止后续步骤，避免错误放大或产生不必要副作用。

- `tests/test_agent_workflow.py` 覆盖多步骤全部成功、第一步失败短路、后续步骤失败短路。
- `tests/test_agents_route.py` 覆盖 `POST /agents/run` 入口在显式多步骤 plan 中继承同一短路合同。

失败步骤仍会写入 `ToolRun`，用于审计具体失败原因；被短路跳过的后续步骤不会执行，也不会写入 `ToolRun`。响应保持 `status=error`，`error` 使用第一个失败步骤的错误原因，`steps` 只包含已经实际执行的步骤。

## Agent result memory

P3-4 Agent 结果沉淀采用显式策略，避免普通工具调用污染长期记忆：

- 只有 `POST /agents/run` 的 `agents` 中包含 `memory_agent` 时，才允许成功结果进入长期记忆。
- 只有工作流最终 `status=ok` 且 `answer` 非空时，才构造 `agent_result` 记忆候选。
- 失败工作流、空输出或缺少有效 `session_id` 时不写长期记忆。
- `tests/test_agent_workflow.py` 覆盖 workflow 层成功沉淀和失败不沉淀。
- `tests/test_agents_route.py` 覆盖 API 层 `memory_agent` 显式策略和默认不沉淀策略。

沉淀内容复用 `MemoryPipeline.persist()`，候选类型为 `agent_result`，标题格式为 `Agent result: <task>`，内容包含原始 task 和最终 answer。响应中的 `memory_saved` 表示本次成功写入或复用的记忆数量。

## AgentRun audit

P3-5 AgentRun 持久化用于记录一次 Agent workflow 的任务级结果，补齐 `ToolRun` 只能观察单个工具调用的问题：

- 每次 `POST /agents/run` 都会写入一条 `AgentRun`，包括 planner 拒绝、工具失败和成功完成。
- 响应中的 `agent_run_id` 对应 `agent_runs.id`，便于从 API 响应追踪到持久化记录。
- `AgentRun` 记录 `user_id`、`project_id`、`session_id`、`task`、`status`、`error`、`answer`、`plan_payload`、`steps`、`agent_trace`、`memory_saved`、`request_id` 和 `created_at`。
- `GET /agents/runs` 必须同时提供非空 `user_id` 和 `project_id`，按 scope 返回最近 run，不跨用户或项目泄露。
- `tests/test_db_migrations.py` 覆盖 `agent_runs`、`obsidian_sync_states` 表和 `0003_agent_runs` / `0004_obsidian_sync_states` revision。
- `tests/test_agent_workflow.py` 覆盖 workflow 写入 `AgentRun` 和返回 `agent_run_id`。
- `tests/test_agents_route.py` 覆盖 `/agents/runs` 查询、倒序排序和空 scope 拒绝。

## CLI

CLI 入口是：

```bash
python -m app.cli.main
```

当前覆盖：

- `chat`
- `memory-search`
- `obsidian-import`
- `obsidian-sync`
- `agents run`
- `agents runs`

`chat` 普通输出读取 API 返回的 `answer` 字段，`--json` 模式转发原始 JSON。`agents run` 会打印 `agent_run_id`，`agents runs` 按 `user_id + project_id` scope 查询历史 run。所有命令支持 `--json` 时会转发原始 JSON，HTTP 非 2xx 或网络错误会以非零退出码结束。`tests/test_cli.py` 使用 HTTP stub 覆盖命令参数、JSON 输出和 scoped history 查询。

## Scheduler status

调度器除 `/diagnostics` 外，还提供只读状态接口：

```bash
curl http://127.0.0.1:8000/scheduler/status
```

响应包含 `running` 和 `jobs`，job 项包含 `id`、`next_run_time` 和 `trigger`。`tests/test_scheduler_status.py` 覆盖 scheduler 缺失、job 序列化和路由读取 app state。

## Obsidian import and sync

Obsidian 单向导入可以通过 API、CLI 或脚本触发：

```bash
python scripts/import_obsidian_vault.py --user-id jules --project-id personal-ai-os
python -m app.cli.main obsidian-import --user jules --project personal-ai-os
```

导入器只扫描配置 vault 内的 markdown 文件，跳过隐藏目录，解析简单 YAML frontmatter，并复用 `MemoryPipeline.persist()` 的 update-or-create 语义。重复运行不会重复写入；文件内容变化会更新同身份记忆；文件删除不会自动删除 DB/Qdrant 记录。`tests/test_obsidian_importer.py` 使用 fake vector store 隔离 Qdrant，避免单元测试依赖外部服务。

`MemoryPipeline` 写入 Qdrant payload 时会附带 `source`、`governance_version` 和 `quality_score`，用于后续记忆治理和检索解释。相关回归在 `tests/test_memory_pipeline.py`。

Obsidian 双向同步通过 `/memory/obsidian/sync`、`obsidian-sync` 和 `scripts/sync_obsidian_vault.py` 暴露。默认 dry-run，只返回 `summary/planned/applied/conflicts/skipped/errors` 报告；显式 `--apply` 才会应用变更。同步状态由 `obsidian_sync_states` 记录上次同步时的 file/memory hash，用来区分 `unchanged`、`vault_only`、`db_only`、`vault_changed`、`db_changed`、`both_changed`、`vault_deleted` 和 `path_missing`。默认删除策略非破坏性：删除 vault 文件只报告，不会删除 DB/Qdrant。`tests/test_obsidian_sync.py` 使用临时 vault 和 fake vector store 覆盖 dry-run、双向 apply、冲突、删除默认策略和路径边界。

```bash
python scripts/sync_obsidian_vault.py --user-id jules --project-id personal-ai-os --json
python scripts/sync_obsidian_vault.py --user-id jules --project-id personal-ai-os --apply
python -m app.cli.main obsidian-sync --user jules --project personal-ai-os --json
```

## Retrieval quality

检索质量评估使用固定 golden dataset，默认 fixture 为：

```bash
tests/fixtures/retrieval_quality_cases.json
```

默认 mock provider 可直接运行：

```bash
DATABASE_URL="sqlite:///:memory:" EMBEDDING_PROVIDER=mock python scripts/evaluate_retrieval_quality.py
```

设置最小命中率阈值，低于阈值时返回非零退出码：

```bash
DATABASE_URL="sqlite:///:memory:" EMBEDDING_PROVIDER=mock python scripts/evaluate_retrieval_quality.py --min-hit-rate 1.0
```

输出 JSON 方便 CI 或后续分析：

```bash
DATABASE_URL="sqlite:///:memory:" EMBEDDING_PROVIDER=mock python scripts/evaluate_retrieval_quality.py --json
```

覆盖默认 `top_k`：

```bash
DATABASE_URL="sqlite:///:memory:" EMBEDDING_PROVIDER=mock python scripts/evaluate_retrieval_quality.py --top-k 3
```

切换真实 OpenAI-compatible embeddings 时，复用同一个脚本，并通过环境变量配置 `EMBEDDING_PROVIDER`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、`EMBEDDING_MODEL` 和 `EMBEDDING_DIMENSION`。

## Qdrant retrieval quality

当 Docker Compose 栈已启动后，可以把同一组 golden dataset 写入 Qdrant，并通过真实 `VectorStore.search` 路径评估召回：

```bash
DATABASE_URL="sqlite:///:memory:" \
QDRANT_URL="http://127.0.0.1:6333" \
QDRANT_COLLECTION="personal_ai_os_quality_eval" \
EMBEDDING_PROVIDER=mock \
python scripts/evaluate_qdrant_retrieval_quality.py
```

Qdrant 评估同样支持最小命中率阈值：

```bash
DATABASE_URL="sqlite:///:memory:" \
QDRANT_URL="http://127.0.0.1:6333" \
QDRANT_COLLECTION="personal_ai_os_quality_eval" \
EMBEDDING_PROVIDER=mock \
python scripts/evaluate_qdrant_retrieval_quality.py --min-hit-rate 1.0
```

输出 JSON：

```bash
DATABASE_URL="sqlite:///:memory:" \
QDRANT_URL="http://127.0.0.1:6333" \
QDRANT_COLLECTION="personal_ai_os_quality_eval" \
EMBEDDING_PROVIDER=mock \
python scripts/evaluate_qdrant_retrieval_quality.py --json
```

该脚本使用独立的 `user_id` 和 `project_id`，默认均为 `retrieval-quality`，也可以通过 `--user-id` 与 `--project-id` 覆盖。

## Real embedding provider quality regression (N8)

默认情况下，CI 和开发环境使用 `mock` provider 以避免消耗真实 API key。为了确保真实 provider（如 OpenAI、BGE 等）的语义检索质量没有退化，支持手动运行在线质量回归。

运行离线（仅计算 cosine similarity）的真实 provider 回归：

```bash
EMBEDDING_PROVIDER=openai-compatible \
EMBEDDING_API_KEY=your_real_key \
EMBEDDING_BASE_URL=https://api.openai.com/v1 \
EMBEDDING_MODEL=text-embedding-3-small \
EMBEDDING_DIMENSION=1536 \
python scripts/evaluate_retrieval_quality.py --min-hit-rate 0.8
```

运行 Qdrant 端到端的真实 provider 回归：

```bash
DATABASE_URL="sqlite:///:memory:" \
QDRANT_URL="http://127.0.0.1:6333" \
QDRANT_COLLECTION="personal_ai_os_quality_eval_real" \
EMBEDDING_PROVIDER=openai-compatible \
EMBEDDING_API_KEY=your_real_key \
EMBEDDING_BASE_URL=https://api.openai.com/v1 \
EMBEDDING_MODEL=text-embedding-3-small \
EMBEDDING_DIMENSION=1536 \
python scripts/evaluate_qdrant_retrieval_quality.py --min-hit-rate 0.8
```

GitHub Actions 提供手动 workflow：`.github/workflows/retrieval-quality.yml`。默认输入使用 `mock` provider，不消耗真实 key；选择 `openai-compatible` 时必须配置 repository secret `EMBEDDING_API_KEY`，并显式输入 base URL、模型和维度。

**注意：**
1. 报告的 JSON 或控制台输出**不会**泄露 API Key。
2. 建议针对不同的模型使用不同的 `QDRANT_COLLECTION`，因为 Qdrant 集合创建后维度（Dimension）不可更改。
3. 请根据真实的 Golden Dataset 调整 `--min-hit-rate`，避免误报。

## 当前回归边界

截至 2026-05-06，`pytest --collect-only -q` 收集到 197 个测试用例，`make ci` 覆盖 compile、pytest 和 migration dry-run；GitHub Actions 额外运行 Docker smoke，其中 `SMOKE_RUN_CHAT=1` 覆盖聊天写入与记忆召回闭环。

- OpenAI-compatible 接口：鉴权、模型发现、非流式聊天、流式聊天、消息和记忆持久化；多 API key 支持绑定默认 `user_id/project_id`，请求 metadata 不能越权覆盖绑定 scope。
- 记忆写入：PostgreSQL 记录、Obsidian 路径、Qdrant point id、向量写入失败降级。
- 记忆检索：Qdrant `query_points` 调用、`user_id` / `project_id` 过滤、检索失败日志和空结果降级。
- Embedding provider：mock 确定性、openai-compatible 配置校验、OpenAI 客户端调用。
- Embedding 维度：写入和检索进入 Qdrant 前都会校验向量维度。
- Retrieval quality：固定记忆样本、查询样本、top-k 命中率、最小命中率 gate 和 JSON 评估输出。
- Qdrant retrieval quality：把固定样本写入 Qdrant 后，通过 `VectorStore.search` 验证真实检索路径，并支持同样的最小命中率 gate。
- Scheduler：启动注册、生命周期托管、定时摘要任务行为。
- Tool/Agent auth：`/tools` 和 `/agents` 共享兼容层 bearer key，绑定 key 会拒绝跨 `user_id/project_id` 的 tool run 或 agent run。
- Agent workflow：deterministic Planner 保持兼容，模型化 Planner 通过 `planner_mode=model` 生成 JSON plan 后仍强制复用 Tool Registry schema 校验；Executor 通过 Tool Registry 执行，ToolRun 审计记录，AgentRun 任务级审计，unsupported/invalid model plan 不执行工具，多步骤失败短路，DAG 依赖顺序、条件跳过、显式有限并行和 `memory_agent` 结果沉淀均有覆盖。
- Obsidian import：vault markdown 扫描、隐藏目录跳过、frontmatter 解析、重复导入幂等、文件修改更新、dry-run、增量报告、失败报告和 MemoryPipeline 复用。
- CLI：agent run、agent runs scoped 查询、JSON 输出和错误码路径。
- Docker smoke：运行中 API 的健康检查、模型发现和基础检索接口。
- End-to-end smoke：可选验证聊天写入和记忆召回闭环。

## 覆盖审计

当前测试覆盖对 P0-P4 基础合同是充分的，重点覆盖了服务启动前检查、请求上下文、错误规范、身份隔离、记忆治理、provider 可靠性、工具边界、Agent 执行/审计、MCP 只读暴露、DAG/并行执行、写工具白名单、迁移、打包元数据和文档合同。

| 区域 | 覆盖状态 | 主要测试 |
| --- | --- | --- |
| P0 服务硬化 | 充分 | `test_config_validation.py`、`test_db_migrations.py`、`test_errors.py`、`test_request_context.py` |
| P1 运行质量 | 充分 | `test_session_identity.py`、`test_memory_pipeline.py`、`test_provider_reliability.py`、`test_openai_compat.py` |
| P2 / N4 / N5 工具层 | 充分 | `test_tool_registry.py`、`test_tools_route.py`、`test_mcp_server.py`、`test_db_migrations.py` |
| P3 / N2 / N3 / N7 Agent 基础 | 充分 | `test_auth.py`、`test_agent_plan.py`、`test_agent_workflow.py`、`test_agents_route.py` |
| N6 / N9 运维入口 | 充分 | `test_obsidian_importer.py`、`test_cli.py` |
| 检索质量 | 充分 | `test_retrieval_quality.py`、`test_project_contracts.py`、Qdrant 评估脚本 |
| 开源工程化 | 基础充分 | `test_packaging_contracts.py`、`test_project_contracts.py`、GitHub Actions smoke |

N5 / N3 / N4 的新增功能已补齐以下回归覆盖：

- MCP adapter：`tools/list` 和 `tools/call` 复用 Tool Registry schema，默认只暴露 read/guarded 工具，调用写入 ToolRun。
- Executor DAG：plan step id、depends_on、条件跳过、循环依赖拒绝、fail-fast 和 skipped trace 均有测试覆盖。
- 写类工具：`file.write_text` 拒绝路径逃逸和覆盖已有文件，`obsidian.append_note` 限制在 vault 内，成功与失败都走 ToolRun 审计。
- Executor parallel：仅显式 `execution_mode=parallel` 时启用，只有 read 工具可进入并行 batch，响应顺序保持 plan 顺序。
- Obsidian import：首次导入、重复导入、修改更新、dry-run、增量报告和失败报告均有覆盖。

## 增加测试的规则

- 修 bug 前先写能失败的回归测试。
- 新增外部服务集成时，优先用 stub 覆盖合同，再按需补 Docker 集成测试。
- 涉及用户、项目或会话隔离的修改，必须覆盖负向用例。
- 涉及降级行为的修改，必须同时断言返回值和日志。
