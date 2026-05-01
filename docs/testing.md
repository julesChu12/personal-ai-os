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

当前 CI 会执行 `migration-smoke`，使用 `DATABASE_URL=sqlite:///:memory:` 验证 migration 入口可加载。应用启动仍保留 `Base.metadata.create_all` 兼容路径；后续生产部署应优先显式运行 migration，再启动 API。

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

## Tool adapter

P2 工具层的回归重点是工具边界稳定、危险能力默认受控、调用可审计：

- `tests/test_tool_registry.py` 覆盖默认工具枚举、工作目录内文件读取、路径逃逸拒绝、shell allowlist 和未知工具拒绝。
- `tests/test_tools_route.py` 覆盖 `GET /tools`、`POST /tools/{tool_name}/invoke` 和 `GET /tools/runs`。
- `tests/test_db_migrations.py` 覆盖 `tool_runs` 表随 migration 创建。

工具调用必须提供 `user_id` 和 `project_id`，用于审计和后续 Agent 任务归属。`shell.run_safe` 只能执行 allowlist 中的 `pwd`、`ls`、`git status`，不能把任意 shell 命令暴露给 HTTP adapter。

## Retrieval quality

检索质量评估使用固定 golden dataset，默认 fixture 为：

```bash
tests/fixtures/retrieval_quality_cases.json
```

默认 mock provider 可直接运行：

```bash
DATABASE_URL="sqlite:///:memory:" EMBEDDING_PROVIDER=mock python scripts/evaluate_retrieval_quality.py
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

输出 JSON：

```bash
DATABASE_URL="sqlite:///:memory:" \
QDRANT_URL="http://127.0.0.1:6333" \
QDRANT_COLLECTION="personal_ai_os_quality_eval" \
EMBEDDING_PROVIDER=mock \
python scripts/evaluate_qdrant_retrieval_quality.py --json
```

该脚本使用独立的 `user_id` 和 `project_id`，默认均为 `retrieval-quality`，也可以通过 `--user-id` 与 `--project-id` 覆盖。

## 当前回归边界

- OpenAI-compatible 接口：鉴权、模型发现、非流式聊天、流式聊天、消息和记忆持久化。
- 记忆写入：PostgreSQL 记录、Obsidian 路径、Qdrant point id、向量写入失败降级。
- 记忆检索：Qdrant `query_points` 调用、`user_id` / `project_id` 过滤、检索失败日志和空结果降级。
- Embedding provider：mock 确定性、openai-compatible 配置校验、OpenAI 客户端调用。
- Embedding 维度：写入和检索进入 Qdrant 前都会校验向量维度。
- Retrieval quality：固定记忆样本、查询样本、top-k 命中率和 JSON 评估输出。
- Qdrant retrieval quality：把固定样本写入 Qdrant 后，通过 `VectorStore.search` 验证真实检索路径。
- Scheduler：启动注册、生命周期托管、定时摘要任务行为。
- Docker smoke：运行中 API 的健康检查、模型发现和基础检索接口。
- End-to-end smoke：可选验证聊天写入和记忆召回闭环。

## 增加测试的规则

- 修 bug 前先写能失败的回归测试。
- 新增外部服务集成时，优先用 stub 覆盖合同，再按需补 Docker 集成测试。
- 涉及用户、项目或会话隔离的修改，必须覆盖负向用例。
- 涉及降级行为的修改，必须同时断言返回值和日志。
