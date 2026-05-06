# Personal AI OS Development Roadmap

更新日期：2026-05-04

## 当前阶段判断

项目已经完成“本地可用 + Open WebUI 接入 + 长期记忆基础闭环 + P0 基础服务硬化 + P1 运行质量基础版 + P2 工具层基础版 + P3 Agent 执行、审计与记忆沉淀基础 + 开源工程化基础 + GitHub CI 发布入口”的核心底座。

按完整 Personal AI OS 愿景估算，整体进度约为 85%左右。按当前阶段目标“可本地长期运行、可开源协作、基础服务可信、工具调用可控可审计、最小 Agent 闭环可验证”估算，进度约为 99%左右。

当前不优先推进 Obsidian 双向同步。原因是它会引入文件监听、增量同步、冲突处理和双向一致性，属于功能扩展；当前更应该优先把基础服务打牢。

## 已完成能力

| 模块 | 状态 | 功能摘要 |
| --- | --- | --- |
| Open WebUI 接入 | 已完成基础版 | 通过 OpenAI-compatible `/v1/models` 和 `/v1/chat/completions` 接入 Web UI |
| 聊天持久化 | 已完成基础版 | `/chat` 和 `/v1/chat/completions` 共用消息与记忆持久化逻辑 |
| 长期记忆写入 | 已完成基础版 | 支持 PostgreSQL、Qdrant、Obsidian 三路写入 |
| 记忆检索 | 已完成基础版 | 支持 Qdrant 检索、用户/项目过滤、检索失败降级 |
| Embedding provider | 已完成基础版 | 支持 `mock` 和 `openai-compatible`，并校验向量维度 |
| 检索质量评估 | 已完成基础版 | 支持离线 golden dataset 和 Qdrant 端到端 hit-rate 评估 |
| Scheduler | 已完成基础版 | 支持定时会话摘要任务 |
| Diagnostics API | 已完成基础版 | `/diagnostics` 可检查配置、DB、Qdrant、embedding、model、scheduler |
| Tool Registry | 已完成基础版 | 支持工具枚举、安全调用边界、HTTP adapter 和 tool run 审计 |
| Agent Workflow | 已完成模型化 Planner 基础版 | 支持 deterministic Planner、模型化 JSON plan、Planner / Executor 闭环，工具调用走 Tool Registry 并写入 ToolRun |
| 开源工程化 | 已完成基础版 | Apache-2.0、CI、Makefile、smoke、CONTRIBUTING、测试文档已具备 |

## 下一阶段总目标

下一阶段目标是在当前最小 Agent 闭环上增强真实任务能力，同时补齐外部协议与安全边界，而不是继续横向堆功能：

- 先收口 retrieval-quality-foundation 的规格验证，固定检索质量回归口径。
- Planner 从硬编码确定性规则升级为“模型生成结构化 plan + 严格 schema 校验”。
- MCP 和写类工具实施前已经补齐多 API Key 与 user/project 绑定，避免 scope 只停留在业务字段。
- Executor 从线性 fail-fast 升级为限制版 DAG，先做条件分支和顺序依赖，再做有限并行。
- MCP Server、写类工具、Obsidian 导入都必须复用现有 ToolRegistry、MemoryPipeline、ToolRun/AgentRun 审计边界。
- 普通聊天、记忆写入和 OpenAI-compatible 路径继续不能被多 Agent 改造破坏。

## P0：基础服务硬化

P0 回归状态：已完成基础版，最近一次完整回归通过 `make ci`，覆盖 compile、pytest 和 migration smoke。

| Task | 状态 | 回归覆盖 | 文档状态 |
| --- | --- | --- | --- |
| P0-1 配置校验与启动检查 | 已完成基础版 | `tests/test_config_validation.py`、项目合同测试、脚本 smoke | README、testing docs 已覆盖 |
| P0-2 数据库迁移基础 | 已完成基础版 | `tests/test_db_migrations.py`、`migration-smoke`、项目合同测试 | README、testing docs 已覆盖 |
| P0-3 API 错误响应标准化 | 已完成基础版 | `tests/test_errors.py`、OpenAI-compatible 回归、项目合同测试 | README、testing docs 已覆盖 |
| P0-4 请求日志和 request id | 已完成基础版 | `tests/test_request_context.py`、生命周期回归、项目合同测试 | README、testing docs 已覆盖 |

### Task P0-1：配置校验与启动检查

状态：已完成基础版。

功能摘要：
新增统一配置校验模块和 CLI/script 检查入口，检查数据库、Qdrant、OpenAI-compatible key、embedding provider、模型 provider、危险默认值。

执行原因：
当前 `/diagnostics` 可以在服务运行后发现问题，但启动前还没有明确 gate。开源用户最常见的问题会是配置不完整、key 不一致、embedding 维度错误。这个任务能把问题提前暴露。

主要产出：
- `app/core/config_validation.py`
- `scripts/check_runtime_config.py`
- README 和 testing docs 配置检查说明
- 单元测试覆盖默认危险配置、缺失配置、合法配置

验收标准：
- 本地默认配置返回 `degraded` 但不阻塞开发。
- 部署模式下可检测 `OPENAI_COMPAT_API_KEY=EMPTY` 等危险配置。
- 不输出密钥原文。

依赖：
已完成的 `settings`、`/diagnostics`、embedding 维度校验。

### Task P0-2：数据库迁移基础

状态：已完成基础版。

功能摘要：
引入数据库 migration 管理，替代长期依赖 `create_all` 的隐式建表方式。

执行原因：
当前表结构还简单，但后续 session、memory governance、tool runs、多 Agent 状态都会改表。如果没有 migration，开源用户升级会不可控。

主要产出：
- Alembic 或最小 migration 框架
- 初始 schema migration
- 本地和 Docker migration 文档
- CI 中的 migration smoke

验收标准：
- 新环境可以通过 migration 创建当前 schema。
- 现有 `create_all` 行为有清晰过渡策略。
- migration 命令在 README 中可复现。

依赖：
当前 SQLAlchemy models。

当前实现说明：
已提供轻量 SQLAlchemy migration runner、初始 schema migration、`scripts/run_migrations.py` 入口、`migration-smoke` CI 目标和文档。应用启动仍保留 `create_all` 兼容路径，生产和开源协作流程应逐步切换为“先显式 migration，再启动服务”。

### Task P0-3：API 错误响应标准化

状态：已完成基础版。

功能摘要：
统一 API 错误结构，让 `/chat`、`/memory/*`、`/v1/*`、`/diagnostics` 的错误返回可预测。

执行原因：
现在部分错误来自 FastAPI 默认 detail，部分来自自定义字符串。Open WebUI 和开源用户排障时，需要稳定的错误结构。

主要产出：
- `app/core/errors.py`
- FastAPI exception handlers
- OpenAI-compatible 路由保持兼容格式
- 回归测试覆盖 400、401、500、依赖失败

验收标准：
- 内部 API 返回统一 `{error: {code, message, type}}` 或约定结构。
- `/v1/*` 不破坏 OpenAI-compatible 错误语义。
- 错误响应不泄露 secret 和连接串。

依赖：
现有 API routes 和 diagnostics。

当前实现说明：
已提供 `app/core/errors.py` 和 FastAPI exception handlers。内部 API 使用 `{error: {code, message, type}}`，OpenAI-compatible `/v1/*` 保持 `{error: {message, type, code}}` 兼容格式。未捕获异常统一降级为 `internal server error`，避免响应泄露 secret 或连接串。

### Task P0-4：请求日志和 request id

状态：已完成基础版。

功能摘要：
增加 request id middleware，并在错误日志中带上 request id、path、method、status。

执行原因：
当前日志已经能记录部分检索和持久化错误，但跨请求排查仍然困难。request id 是服务化运行的基础。

主要产出：
- `app/core/request_context.py`
- FastAPI middleware
- 响应头 `X-Request-ID`
- 日志格式文档

验收标准：
- 每个请求都有 request id。
- 传入 `X-Request-ID` 时复用调用方 id。
- 异常日志包含 request id。

依赖：
API 错误标准化可先可后，建议在 P0-3 之后做。

当前实现说明：
已提供 `app/core/request_context.py` 和 FastAPI middleware。服务会复用调用方传入的 `X-Request-ID`，缺失时生成 UUID，并在响应头返回。请求完成日志包含 `request_id, path, method, status, duration_ms`；未捕获异常日志包含 `request_id, path, method, status, exception_type`，且不记录异常原文。

## P1：数据一致性与运行质量

P1 回归状态：已完成基础版并完成 review 修复，最近一次完整回归通过 `make ci`，覆盖 session identity、memory governance、provider reliability 和服务级 smoke 合同。

| Task | 状态 | 回归覆盖 | 文档状态 |
| --- | --- | --- | --- |
| P1-1 Session / Project 语义收紧 | 已完成基础版 | `tests/test_session_identity.py`、`tests/test_sessions_route.py`、OpenAI-compatible 回归 | README、testing docs 已覆盖 |
| P1-2 记忆治理 v2 | 已完成基础版 | `tests/test_memory_pipeline.py`、项目合同测试 | README、testing docs 已覆盖 |
| P1-3 Provider 可靠性治理 | 已完成基础版 | `tests/test_provider_reliability.py`、embedding provider 回归、diagnostics 回归 | README、testing docs 已覆盖 |
| P1-4 服务级集成测试增强 | 已完成基础版 | `scripts/smoke_api.sh` 合同测试、CI Docker smoke 配置 | README、testing docs 已覆盖 |

### Task P1-1：Session / Project 语义收紧

状态：已完成基础版。

功能摘要：
明确 session、project、user 的来源、默认值、持久化规则和查询规则，避免记忆混项目。

执行原因：
后端已支持 OpenAI-compatible `metadata.user_id/project_id/session_id`，但还需要把语义固化成服务合同。

主要产出：
- session identity helper
- `/sessions` 查询规则补强
- Open WebUI metadata 使用说明
- 回归测试覆盖默认值和 metadata 覆盖

验收标准：
- 同一用户不同项目的消息和记忆不串。
- OpenWebUI 缺 metadata 时仍保持兼容。
- 文档明确推荐 metadata 传参方式。

依赖：
当前 `/v1/chat/completions` metadata 支持。

当前实现说明：
已提供 `app/core/session_identity.py`，统一 OpenAI-compatible 身份解析和 `/sessions` 项目 scope 校验。`metadata.user_id/project_id/session_id` 会 trim，空值视为缺失；`X-Session-Id` 优先于 metadata session；OpenWebUI 缺 metadata 时仍使用 `openwebui` 默认值。`/sessions` 会拒绝空 `user_id` 或 `project_id`，避免跨项目查询。

### Task P1-2：记忆治理 v2

状态：已完成基础版。

功能摘要：
从“精确重复跳过”升级为更实用的记忆治理：同类型同标题更新、重要度策略、记忆类型策略、摘要去噪。

执行原因：
现在只跳过完全相同内容。长期使用后，类似但不完全相同的记忆会膨胀，影响检索质量。

主要产出：
- memory identity / fingerprint
- update-or-create 策略
- memory_type 策略
- 回归测试覆盖重复、更新、新增

验收标准：
- 完全重复不重复写。
- 同一语义的会话摘要可更新或合并。
- Qdrant point id 与 DB row 保持一致可追踪。

依赖：
当前 `MemoryPipeline.persist()` 去重逻辑。

当前实现说明：
已提供 `app/memory/memory_identity.py`，记忆身份定义为 `user_id + project_id + memory_type + title`，其中 `memory_type` 会 trim 并转小写，`title` 会 trim。`MemoryPipeline.persist()` 已升级为 update-or-create：完全重复内容跳过；同身份内容变化时复用原 `qdrant_point_id` upsert 向量，成功后再更新现有 DB row 和 Obsidian 路径；已有记忆更新时如果向量 upsert 失败，会保留原 DB row 和原 point id；不同用户或不同项目不会互相更新。

### Task P1-3：Provider 可靠性治理

状态：已完成基础版。

功能摘要：
为 model provider 和 embedding provider 增加 timeout、retry、错误分类和诊断信息。

执行原因：
真实 provider 会遇到超时、限流、网络错误、配置错误。当前抽象已经有了，但可靠性策略还比较薄。

主要产出：
- provider error types
- timeout/retry 配置
- diagnostics 中展示 provider 状态
- 回归测试覆盖配置错误、请求失败、维度错误

验收标准：
- embedding 失败能被诊断和日志识别。
- model 失败返回可理解错误。
- 不把检索失败升级成聊天硬失败，除非模型本身不可用。

依赖：
Diagnostics API、embedding provider、ModelRouter。

当前实现说明：
已提供 `app/core/provider_errors.py`，定义 `ProviderRequestError`、`ProviderTimeoutError` 和 `ProviderConfigurationError`。OpenAI-compatible model provider 和 embedding provider 已接入 `PROVIDER_TIMEOUT_SECONDS`、`PROVIDER_RETRY_ATTEMPTS`，并通过项目级 `retry_provider_call` 包装请求失败，SDK 内部 retry 设为 0，避免重试放大。MiniMax stream 会在读取 SSE 前检查 HTTP 状态并包装失败，避免错误消息泄露 API key。`/diagnostics` 会展示 provider timeout/retry 配置。

### Task P1-4：服务级集成测试增强

状态：已完成基础版。

功能摘要：
把当前 smoke 脚本升级为更完整的服务级回归，包括 chat、memory ingest、memory search、diagnostics、OpenAI-compatible auth。

执行原因：
现在 unit tests 很多，smoke 也有，但服务级覆盖还可以更系统。开源项目需要一键证明“这套服务真的可用”。

主要产出：
- `scripts/smoke_api.sh` 增强
- 可选 `tests/integration/`
- CI smoke job 增强
- Docker 运行说明

验收标准：
- Docker 栈启动后，一个命令验证核心 API。
- smoke 不依赖真实模型 key。
- 失败时输出足够排障信息。

依赖：
现有 smoke、diagnostics、Qdrant quality evaluator。

当前实现说明：
`scripts/smoke_api.sh` 已覆盖 `/health`、`/diagnostics`、OpenAI-compatible `/v1/models` 正向鉴权、错误 key 负向鉴权、`/memory/ingest`、`/memory/search`，并保留 `SMOKE_RUN_CHAT=1` 的聊天写入与记忆召回闭环。脚本不依赖真实模型 key，可使用 mock provider 完成服务级回归。

## P2：工具层前置

P2 回归状态：已完成基础版，最近一次完整回归通过 `make ci`，覆盖 Tool Registry、HTTP tool adapter、tool run audit、DB migration 和项目合同测试。

| Task | 状态 | 回归覆盖 | 文档状态 |
| --- | --- | --- | --- |
| P2-1 Tool Registry | 已完成基础版 | `tests/test_tool_registry.py`、项目合同测试 | README、testing docs 已覆盖 |
| P2-2 MCP / Tool Adapter | 已完成基础版 | `tests/test_tools_route.py`、项目合同测试 | README、testing docs 已覆盖 |
| P2-3 Tool Run 审计 | 已完成基础版 | `tests/test_tools_route.py`、`tests/test_db_migrations.py`、项目合同测试 | README、testing docs 已覆盖 |

### Task P2-1：Tool Registry

状态：已完成基础版。

功能摘要：
定义统一 tool registry，把 file、shell、git 等工具纳入可控接口。

执行原因：
多 Agent 真正有价值的前提是能调用工具。先做工具层，后做 Agent 编排，风险更低。

主要产出：
- `app/tools/registry.py`
- tool schema
- 权限边界
- 单元测试

验收标准：
- 工具可以被枚举。
- 工具调用输入输出结构稳定。
- 危险工具默认不可随意执行。

依赖：
API 错误标准化、request id、基础安全策略。

当前实现说明：
已提供 `app/tools/registry.py`，定义 `ToolRegistry`、`ToolDefinition` 和 `ToolInvocationResult`。默认注册 `file.read_text`、`git.status`、`shell.run_safe`：文件读取限制在允许工作目录内，shell 只允许 `pwd`、`ls`、`git status`，未知工具会显式拒绝。

### Task P2-2：MCP / Tool Adapter

状态：已完成基础版。

功能摘要：
把内部 tool registry 暴露为 MCP 或兼容适配层。

执行原因：
这是连接外部工具生态的关键，但必须建立在稳定 tool registry 上。

主要产出：
- MCP adapter 或 tool API
- 工具调用文档
- 最小可运行 demo

验收标准：
- 至少一个工具可通过 adapter 调用。
- 权限和错误可控。

依赖：
Tool Registry。

当前实现说明：
已提供 `app/api/routes_tools.py`，以 HTTP adapter 形式暴露 `GET /tools`、`POST /tools/{tool_name}/invoke` 和 `GET /tools/runs`。N5 已补充 `app/tools/mcp_server.py` 与 `scripts/run_mcp_server.py`，MCP `tools/list` / `tools/call` 复用同一个 registry 和 tool run 审计模型，且默认隐藏写工具。

### Task P2-3：Tool Run 审计

状态：已完成基础版。

功能摘要：
为每次工具调用记录用户、项目、会话、工具名、输入、输出、错误、request id 和时间，形成 Agent 编排前的可追踪底座。

执行原因：
多 Agent 能力如果没有工具审计，失败后很难判断是模型规划、工具输入、权限边界还是外部命令出错。先把 tool run 记录打牢，可以降低后续 Planner / Executor 的排障成本。

主要产出：
- `ToolRun` DB model
- `0002_tool_runs` migration
- `/tools/runs` 查询接口
- 成功和失败工具调用的审计回归测试

验收标准：
- 成功工具调用会记录 `status=ok`、输入、输出和 request id。
- 失败工具调用会记录 `status=error` 和错误原因。
- 查询工具记录必须按 `user_id + project_id` scope 过滤。

依赖：
Tool Registry、request id、数据库迁移基础。

当前实现说明：
已提供 `app/db/models.py` 中的 `ToolRun`、`app/db/migrations/versions/v0002_tool_runs.py` 和 `/tools/runs` 查询接口。`POST /tools/{tool_name}/invoke` 会在同步返回工具结果的同时写入审计记录。

## P3：真正多 Agent 编排

P3 回归状态：P3-1、P3-2、P3-3、P3-4 和 P3-5 已完成基础版，最近一次完整回归通过 `make ci`，覆盖 Planner / Executor workflow、Structured Agent Plan、多步骤 failure short-circuit、Agent 结果记忆沉淀、AgentRun 任务级审计、Agent API、ToolRun 审计和项目合同测试。

| Task | 状态 | 回归覆盖 | 文档状态 |
| --- | --- | --- | --- |
| P3-1 Planner / Executor 最小工作流 | 已完成基础版 | `tests/test_agent_workflow.py`、`tests/test_agents_route.py`、项目合同测试 | README、testing docs 已覆盖 |
| P3-2 Structured Agent Plan | 已完成基础版 | `tests/test_agent_plan.py`、`tests/test_agent_workflow.py`、`tests/test_agents_route.py`、项目合同测试 | README、testing docs 已覆盖 |
| P3-3 多步骤 Executor 失败短路策略 | 已完成基础版 | `tests/test_agent_workflow.py`、`tests/test_agents_route.py`、项目合同测试 | testing docs 已覆盖 |
| P3-4 Agent 结果按策略进入长期记忆 | 已完成基础版 | `tests/test_agent_workflow.py`、`tests/test_agents_route.py`、项目合同测试 | testing docs 已覆盖 |
| P3-5 Agent Run 持久化与查询 | 已完成基础版 | `tests/test_db_migrations.py`、`tests/test_agent_workflow.py`、`tests/test_agents_route.py`、项目合同测试 | testing docs 已覆盖 |

### Task P3-1：Planner / Executor 最小工作流

状态：已完成基础版。

功能摘要：
实现最小多 Agent 工作流：Planner 拆任务，Executor 通过 Tool Registry 执行，并用 ToolRun 记录结果。

执行原因：
多 Agent 是项目愿景核心，但需要在检索、工具、诊断、错误处理稳定后再做。

主要产出：
- `app/agents/workflow.py`
- Planner 受控任务规划
- Executor 工具执行
- ToolRun 审计复用
- `/agents/run` API
- 回归测试

验收标准：
- 一个任务能被拆解、执行、记录。
- 失败可追踪。
- 不破坏普通聊天路径。

依赖：
Tool Registry、memory governance、request id。

当前实现说明：
已提供 `AgentWorkflow`、`PlannerAgent.plan()` 和 `ExecutorAgent.execute()`。当前 Planner 仅支持 `read file <path>`、`pwd` / `show cwd`、`git status` 三类确定性任务；unsupported task 返回 `status=error`，不会执行工具或写入 tool run。`POST /agents/run` 会执行最小工作流，并复用 Tool Registry 和 ToolRun 审计。

### Task P3-2：Structured Agent Plan

状态：已完成基础版。

功能摘要：
定义结构化 Agent plan schema，让外部或模型生成的计划在进入 Executor 前先通过工具名、输入字段和 enum 白名单校验。

执行原因：
P3-1 已经有最小 Planner / Executor 闭环，但 Planner 仍以硬编码单步任务为主。下一步如果要接入模型生成计划或多步骤执行，必须先把 plan 结构和安全校验固定下来，否则 Executor 会承担过多防御逻辑。

主要产出：
- `AgentPlanValidationError`
- `validate_agent_plan()`
- ToolRegistry definition 查询
- `/agents/run` 可选 `plan` 输入
- 结构化 plan 回归测试

验收标准：
- 合法 `steps[{tool_name,input,reason}]` 可以转换为 `AgentPlan`。
- 未注册工具会被拒绝。
- 缺少 required input 会被拒绝。
- `shell.run_safe.command` 不在 enum 内会被拒绝。
- plan 超过 10 个步骤会被拒绝。
- input 中出现工具 schema 未声明字段会被拒绝。
- `/agents/run` 会拒绝空 `user_id/project_id`，空 `session_id` 归一为 `null`。
- 被拒绝的 plan 不执行工具，也不写入 tool run。

依赖：
Tool Registry、P3-1 AgentWorkflow。

当前实现说明：
已提供 `validate_agent_plan(raw_plan, registry)`，基于 Tool Registry 的 `ToolDefinition.input_schema` 做最小 JSON-schema 风格校验。外部 plan 最多 10 个步骤，未知 input 字段默认拒绝，避免单请求工具调用和审计 payload 放大。`AgentWorkflow.run(..., plan_payload=...)` 会优先校验外部 plan；校验失败返回 `status=error` 并跳过工具执行。

### Task P3-3：多步骤 Executor 失败短路策略

状态：已完成基础版。

功能摘要：
为结构化多步骤 plan 补齐顺序执行语义：步骤按顺序执行，任一步失败后立即停止，不再执行后续步骤。

执行原因：
P3-2 已经允许外部 plan 提交最多 10 个步骤。如果失败后继续执行，后续工具可能基于错误前提运行；未来加入写文件、网络或记忆写入工具后，会放大副作用风险。先把 fail-fast 合同固定下来，可以让后续扩展工具和 Agent 编排更安全。

主要产出：
- `AgentWorkflow` failure short-circuit
- 多步骤成功回归测试
- 首步失败短路回归测试
- 后续步骤失败短路回归测试
- `/agents/run` API 多步骤短路回归测试

验收标准：
- 多步骤全部成功时按顺序返回所有已执行步骤和聚合输出。
- 任一步失败时返回 `status=error`。
- 失败步骤会写入 `ToolRun`，保留失败原因。
- 失败后的后续步骤不执行，也不写入 `ToolRun`。
- 响应中的 `steps` 只包含实际执行过的步骤。

依赖：
P3-2 Structured Agent Plan、Tool Registry、ToolRun 审计。

当前实现说明：
`AgentWorkflow.run()` 在每个工具步骤执行并记录审计后检查结果状态；当 `ToolInvocationResult.status != "ok"` 时立即停止循环。响应继续使用第一个失败步骤作为 `error` 来源，`agent_trace` 只记录实际发生的 planner/validator 和 executor 动作。

### Task P3-4：Agent 结果按策略进入长期记忆

状态：已完成基础版。

功能摘要：
在 Agent workflow 成功完成后，按显式策略把最终结果沉淀为长期记忆，复用现有 MemoryPipeline。

执行原因：
多 Agent 的执行结果如果完全不进入长期记忆，系统无法从已完成任务中积累经验；但全量自动写入会污染记忆库，尤其是工具输出可能包含临时路径、状态噪声或失败信息。因此先采用显式 `memory_agent` 策略，只保存调用方明确要求沉淀的成功结果。

主要产出：
- `AgentWorkflow.run(..., persist_agent_result=...)`
- `agent_result` 记忆候选构造
- `/agents/run` 根据 `agents` 中是否包含 `memory_agent` 决定是否沉淀
- workflow 层成功沉淀和失败不沉淀回归测试
- API 层显式沉淀和默认不沉淀回归测试

验收标准：
- 默认 `/agents/run` 不自动写长期记忆。
- `agents` 包含 `memory_agent` 且工作流成功时，写入一条 `agent_result` 记忆候选。
- 失败工作流、空 answer 或缺少有效 session_id 时不写长期记忆。
- 记忆写入复用 `MemoryPipeline.persist()`，不新增并行持久化路径。
- 响应包含 `memory_saved`，用于观察本次沉淀数量。

依赖：
P3-1 AgentWorkflow、P3-2 Structured Agent Plan、P3-3 failure short-circuit、P1 Memory governance。

当前实现说明：
`AgentWorkflow` 支持注入 `MemoryPipeline`，便于测试和后续替换。`POST /agents/run` 通过 `agents` 列表中的 `memory_agent` 启用结果沉淀；成功结果会构造 `MemoryCandidate(memory_type="agent_result")`，标题格式为 `Agent result: <task>`，内容包含 task 和 answer。沉淀失败不会改变主工作流工具执行结果，当前以 `memory_saved=0` 表达未写入。

### Task P3-5：Agent Run 持久化与查询

状态：已完成基础版。

功能摘要：
新增任务级 AgentRun 审计记录，让一次 Agent workflow 的整体状态、plan、steps、trace、错误和记忆沉淀结果可查询。

执行原因：
P2 的 `ToolRun` 能追踪单个工具调用，但不能回答“一次 Agent 任务整体发生了什么”。P3-1 到 P3-4 已具备执行、短路和记忆沉淀能力，下一步必须补任务级运行记录，方便调试、回放和后续 Web UI 展示。

主要产出：
- `AgentRun` DB model
- `0003_agent_runs` migration
- `app/agents/run_store.py`
- `AgentWorkflow` 写入 `AgentRun` 并返回 `agent_run_id`
- `GET /agents/runs` scoped 查询接口
- migration、workflow、API 回归测试

验收标准：
- 每次 `/agents/run` 都写入一条 `AgentRun`，包括成功、工具失败和 planner 拒绝。
- 响应返回 `agent_run_id`，可关联数据库记录。
- `AgentRun` 保存 task、status、error、answer、plan、steps、agent_trace、memory_saved 和 request_id。
- `/agents/runs` 必须按 `user_id + project_id` scope 查询，不跨用户或项目泄露。
- 空 `user_id/project_id` 查询会返回 400。

依赖：
P3-1 AgentWorkflow、P3-2 Structured Agent Plan、P3-3 failure short-circuit、P3-4 memory policy、P2 ToolRun 审计。

当前实现说明：
`AgentWorkflow.run()` 在返回响应前通过 `record_agent_run()` 写入任务级记录。`GET /agents/runs` 复用 `require_non_blank()` 校验 scope，并按 `AgentRun.id desc` 返回最近记录，默认 `limit=20`，最大 `100`。

## P4 / N-series：下一阶段执行计划

P4 目标：沿当前最小 Agent 闭环纵向深化，并在新增外部协议、写工具和并行能力前补齐安全边界。P4 不重写 P0-P3 底座，而是复用 `AgentWorkflow`、`ToolRegistry`、`MemoryPipeline`、`ToolRun` 和 `AgentRun`。

| Task | 优先级 | 状态 | 功能摘要 |
| --- | --- | --- | --- |
| N1 retrieval-quality-foundation 规格收尾验证 | P0 | 已完成 | 固定检索质量评估阈值、输出 schema、失败退出码和文档合同 |
| N2 Planner 模型化 | P0 | 已完成 | 让模型受控生成结构化 plan，继续通过 `validate_agent_plan()` 审核 |
| N7 多 API Key 与 user/project 绑定 | P1 | 已完成 | 替代单一 `OPENAI_COMPAT_API_KEY=EMPTY`，把 key 与默认 scope 绑定 |
| N5 MCP Server 适配 | P1 | 已完成 | 以只读方式把 Tool Registry 暴露为 MCP，复用工具 schema 与审计 |
| N3a Executor 条件分支与顺序 DAG | P1 | 已完成 | 在多步骤 fail-fast 基础上增加条件跳过和依赖顺序 |
| N4 写类工具白名单 | P1 | 已完成 | 增加 `file.write_text`、`obsidian.append_note` 等受控写工具 |
| N3b Executor 有限并行 | P2 | 已完成 | 在 DAG 语义稳定后增加有限并行，并保持失败传播可审计 |
| N6 Obsidian 单向导入 | P2 | 已完成 | vault 到 memories/Qdrant 的幂等导入，可重跑，不做双向冲突解决 |
| N8 真实 embedding 在线质量回归 | P2 | 已完成 | 基于 N1 口径支持手动或定时真实 provider 质量评估 |
| N9 CLI 升级 | P3 | 待执行 | 增加 `agents` 子命令、JSON 输出、错误码和最近 run 查询 |
| N10 移除 `create_all` 兼容路径 | P3 | 待执行 | migration 成为 schema 单一真实来源 |

### Task N1：retrieval-quality-foundation 规格收尾验证

状态：已完成。

功能摘要：
将已有离线 retrieval quality 和 Qdrant retrieval quality 评估从“可运行脚本”收口为稳定规格：固定最小 hit-rate、JSON 输出 schema、失败退出码和 CI/手动运行说明。

执行原因：
检索质量评估已经存在，但还没有被当作明确 release gate。N1 成本低，是后续真实 embedding 回归和记忆治理优化的前置。

主要产出：
- `scripts/evaluate_retrieval_quality.py` 阈值参数和失败退出码。
- `scripts/evaluate_qdrant_retrieval_quality.py` 阈值参数和失败退出码。
- `tests/test_retrieval_quality.py` 和项目合同测试补充输出 schema 与阈值语义。
- README、`docs/testing.md`、SPEC 文档同步评估口径。

验收标准：
- 默认 mock fixture 可稳定通过。
- `--min-hit-rate` 低于实际命中率时退出 0，超过实际命中率时退出非 0。
- JSON 输出字段稳定，包含 hit-rate、total、hits、misses、top-k。
- Qdrant 评估仍使用独立 `user_id/project_id`，可重复运行。

依赖：
已完成的 retrieval quality evaluator、Qdrant evaluator、mock embedding provider。

当前实现说明：
`scripts/evaluate_retrieval_quality.py` 和 `scripts/evaluate_qdrant_retrieval_quality.py` 均支持 `--min-hit-rate`。评估报告保留 `total_queries` 兼容字段，同时新增稳定 summary 字段 `total`、`hits`、`misses`、`hit_rate`、`top_k`。当实际 `hit_rate` 低于阈值时，脚本向 stderr 输出明确失败原因并以退出码 1 结束；默认 mock fixture 和 Qdrant 真实路径均可达到 `hit_rate=1.00`。

### Task N2：Planner 模型化（受控生成结构化 plan）

状态：已完成。

功能摘要：
新增模型化 Planner 路径，让 LLM 根据任务生成结构化 plan，但所有输出必须先通过 `validate_agent_plan()`，再进入 Executor。

执行原因：
当前 Planner 只支持少量硬编码任务，无法承载真实多步骤任务。模型化 Planner 是 Agent 深化的核心，但必须保持“模型只规划，工具边界由代码校验”的原则。

主要产出：
- Planner prompt 和结构化输出解析。
- 模型输出清洗与 JSON 解析错误处理。
- plan 生成失败或 provider 失败时的可理解错误。
- 回归测试覆盖合法 plan、非法工具、未知字段、prompt 注入式输出、provider 失败。

验收标准：
- 默认仍支持现有确定性 Planner，不破坏现有 task。
- 模型生成 plan 必须复用 Tool Registry schema 校验。
- 被拒绝的 plan 不执行工具、不写 ToolRun，但写 AgentRun。
- 错误响应不泄露 provider 原始敏感内容。

依赖：
P3-2 Structured Agent Plan、P1-3 Provider 可靠性治理、P3-5 AgentRun。

当前实现说明：
`AgentRunRequest` 新增 `planner_mode`，默认值为 `deterministic`，因此现有硬编码任务保持兼容。显式传入 `planner_mode=model` 时，`PlannerAgent` 会调用模型生成 JSON plan；输出必须是纯 JSON 对象或完整 fenced JSON，随后统一进入 `validate_agent_plan(raw_plan, registry)`。非法 JSON、未知工具、未知 input 字段、step 超限和 provider 失败都会被拒绝；拒绝路径不写 ToolRun，但会写 AgentRun，provider 失败统一返回 `model planner request failed`，避免泄露底层敏感内容。

### Task N7：多 API Key 与 user/project 绑定

状态：已完成。

功能摘要：
从单一 `OPENAI_COMPAT_API_KEY` 升级为可配置的多 key 体系，每个 key 可绑定默认 `user_id/project_id` 和权限等级。

执行原因：
当前 `user_id/project_id` 是逻辑 scope，不是安全边界。MCP、写工具和远程访问前必须先补认证授权基础。

主要产出：
- API key 配置解析。
- key 到默认 user/project 的绑定规则。
- OpenAI-compatible 和 tools/agents 路由共享认证结果。
- 文档和测试覆盖错误 key、空 key、跨 scope 查询负向路径。

验收标准：
- 本地默认 `EMPTY` 仍可用于开发，但 strict 模式提示风险。
- 多 key 配置可映射不同默认 user/project。
- 请求显式 metadata 不能越权覆盖 key 绑定 scope。
- 错误响应不泄露 key。

依赖：
P1-1 Session/Project 语义、P0-1 配置校验、P0-3 错误标准化。

当前实现说明：
`app/core/auth.py` 提供 `ApiPrincipal`、bearer token 校验、结构化 key 解析、权限检查和 scope 绑定校验。`OPENAI_COMPAT_API_KEYS` 支持 JSON 数组配置，例如 `key/user_id/project_id/permissions`；本地 legacy `OPENAI_COMPAT_API_KEY=EMPTY` 仍保持未绑定开发兼容。OpenAI-compatible 聊天会把绑定 key 收敛到对应 `user_id/project_id`，并拒绝 metadata 越权；`/tools` 和 `/agents` 路由共享同一鉴权 helper，绑定 key 的请求不能写入或查询其他 scope。配置校验会识别结构化 key，strict 模式下不再把已配置绑定 key 视为默认风险，且不会输出 key 明文。

### Task N5：MCP Server 适配（只读 Tool Registry）

状态：已完成。

功能摘要：
新增 MCP Server adapter，先只暴露只读/低风险工具，例如 `file.read_text`、`git.status`、`shell.run_safe` 中的安全命令。

执行原因：
Tool Registry 已经有稳定 schema 和审计，MCP 是外部工具生态的自然协议入口。先只读可以验证协议边界，不提前扩大副作用面。

主要产出：
- MCP server 入口脚本或模块。
- tool list 和 tool call 映射到 ToolRegistry。
- ToolRun 审计复用。
- 最小 MCP 调用 demo 和测试。

验收标准：
- MCP tool list 与 `GET /tools` 暴露的工具合同一致。
- MCP tool call 复用 ToolRegistry 权限边界。
- 每次调用写入 ToolRun。
- 不暴露写文件、删除、任意 shell。

依赖：
P2 Tool Registry、P2 ToolRun 审计、N7 多 API Key。

### Task N3a：Executor 条件分支与顺序 DAG

状态：已完成。

功能摘要：
在现有线性多步骤 plan 上增加 `id`、`depends_on` 和条件跳过能力，但仍按确定性顺序执行。

执行原因：
真实任务需要根据前一步结果决定后续步骤。先做顺序 DAG 能扩展表达力，同时避免并行引入的审计和副作用复杂度。

主要产出：
- plan schema 增加 step id、depends_on、condition。
- Executor 根据依赖拓扑顺序执行。
- 条件不满足时记录 skipped step。
- AgentRun 记录 executed/skipped/failed 状态。

验收标准：
- 循环依赖被拒绝。
- 未满足依赖不执行。
- 条件跳过不写 ToolRun，但 AgentRun 保留 skipped trace。
- 失败仍遵循 fail-fast。

依赖：
P3-2 Structured Agent Plan、P3-3 failure short-circuit、P3-5 AgentRun。

### Task N4：写类工具白名单

状态：已完成。

功能摘要：
增加受控写工具，例如 `file.write_text` 和 `obsidian.append_note`，默认只允许写入配置允许目录。

执行原因：
Agent 如果只能读，真实任务能力有限；但写能力必须有明确路径边界、审计和失败保护。

主要产出：
- `app/tools/file_tool.py` 写入能力。
- Obsidian append note 工具。
- Tool schema enum/path 限制。
- 成功/失败写入审计。

验收标准：
- 不能写出允许目录。
- 默认不支持覆盖敏感文件或删除文件。
- 写入成功和失败都写 ToolRun。
- MCP 默认不暴露写工具，除非显式启用。

依赖：
Tool Registry、ToolRun 审计、N7 多 API Key、N5 MCP read-only adapter。

### Task N3b：Executor 有限并行

状态：已完成。

功能摘要：
在 N3a DAG 语义稳定后，为无依赖且只读的步骤增加有限并行执行。

执行原因：
并行可以提升多工具任务速度，但必须先有依赖图、工具副作用分类和审计顺序规则。

主要产出：
- 工具 side-effect 分类。
- 并行度上限配置。
- 并行结果汇总与失败传播。
- AgentRun trace 保留执行/跳过状态和审计 run_id。

验收标准：
- 只读工具可并行，写工具默认串行。
- 任一并行步骤失败后停止后续未开始步骤。
- 响应顺序稳定，不因并发导致审计不可读。

依赖：
N3a、N4、ToolRun/AgentRun 审计。

### Task N6：Obsidian 单向导入

状态：已完成。

功能摘要：
支持从 Obsidian vault 读取 markdown，幂等导入到 DB/Qdrant，形成可检索长期记忆。

执行原因：
当前 Obsidian 已是写入目标，但无法把已有 vault 变成知识源。单向导入收益高，且不引入双向冲突处理。

主要产出：
- vault scanner。
- markdown metadata / hash / mtime 解析。
- 幂等 memory identity。
- 导入脚本和测试 fixture。

验收标准：
- 重复运行不重复写入。
- 修改文件后能更新对应记忆。
- 删除文件不自动删除 DB 记录。
- 不做文件监听和双向同步。

依赖：
MemoryPipeline、memory governance、Qdrant vector store。

### Task N8：真实 embedding 在线质量回归

状态：已完成。

功能摘要：
基于 N1 固定评估口径，支持手动或定时运行真实 embedding provider 的检索质量评估。

执行原因：
mock embedding 只能验证管线稳定，不能代表真实语义检索质量。需要可重复的在线质量回归来发现 provider 或配置退化。

主要产出：
- 手动真实 provider 评估命令。
- 可选 GitHub Actions manual workflow 或本地脚本。
- JSON 报告归档约定。

验收标准：
- 不在默认 CI 中消耗真实 provider key。
- 手动运行需要显式环境变量。
- 报告不输出 API key。

依赖：
N1、embedding provider reliability。

### Task N9：CLI 升级

状态：待执行。

功能摘要：
把当前 demo 级 CLI 扩展为开发者可用入口，支持 agents 子命令、JSON 输出和错误码。

执行原因：
模板项目的第一批用户是开发者。CLI 是验证服务和调试 Agent run 的低成本入口。

主要产出：
- `app.cli.main` 增加 `agents run`、`agents runs`。
- `--json` 输出。
- 非 2xx 映射为非零退出码。
- CLI 专项测试。

验收标准：
- CLI 可运行 agent task 并打印 agent_run_id。
- JSON 输出可被脚本消费。
- 错误响应返回非零退出码。

依赖：
P3 AgentRun、routes_agents。

### Task N10：移除 `create_all` 兼容路径

状态：待执行。

功能摘要：
移除应用启动时的 `Base.metadata.create_all` 兼容路径，让 migration 成为 schema 单一真实来源。

执行原因：
开源协作和生产部署需要可预测 schema 变更。`create_all` 对早期模板友好，但长期会掩盖 migration 缺失。

主要产出：
- `app/db/database.py` 启动路径调整。
- README/testing 更新 migration-first 约定。
- 测试移除对隐式 create_all 的依赖。

验收标准：
- 未运行 migration 的数据库启动时给出明确错误。
- migration dry-run/apply 是唯一建表入口。
- CI 和 Docker smoke 均通过。

依赖：
P0-2 migration 基础、N1-N9 后的 schema 稳定期。

## 暂缓任务

### Obsidian 双向同步

暂缓原因：
当前 Obsidian 已经能作为写入目标，N6 会优先实现 vault 到 memories/Qdrant 的单向导入。双向同步会进一步引入文件监听、冲突处理、删除传播和双向一致性，仍应单独做 spec。

建议触发条件：
- N6 Obsidian 单向导入完成。
- 真实用户开始同时在 Obsidian 和 API 两侧修改同一类记忆。
- 已有明确冲突解决策略和删除传播策略。

## 推荐执行顺序

1. P0-1 配置校验与启动检查
2. P0-2 数据库迁移基础
3. P0-3 API 错误响应标准化
4. P0-4 请求日志和 request id
5. P1-1 Session / Project 语义收紧
6. P1-2 记忆治理 v2
7. P1-3 Provider 可靠性治理
8. P1-4 服务级集成测试增强
9. P2-1 Tool Registry
10. P2-2 MCP / Tool Adapter
11. P2-3 Tool Run 审计
12. P3-1 最小多 Agent 工作流
13. P3-2 Structured Agent Plan
14. P3-3 多步骤 Executor 失败短路策略
15. P3-4 Agent 结果按策略进入长期记忆
16. P3-5 Agent Run 持久化与查询
17. N1 retrieval-quality-foundation 规格收尾验证
18. N2 Planner 模型化：受控生成结构化 plan
19. N7 多 API Key 与 user/project 绑定
20. N5 MCP Server 适配：只读暴露 Tool Registry
21. N3a Executor 条件分支与顺序 DAG
22. N4 写类工具白名单
23. N3b Executor 有限并行
24. N6 Obsidian 单向导入
25. N8 真实 embedding 在线质量回归
26. N9 CLI 升级
27. N10 移除 `create_all` 兼容路径

## 每次任务完成必须验证

每个 task 完成后至少运行：

```bash
make ci PYTHON="/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python"
```

涉及 Docker 服务的 task 还需要运行：

```bash
bash scripts/smoke_api.sh
```

涉及记忆检索的 task 还需要运行：

```bash
DATABASE_URL="sqlite:///:memory:" EMBEDDING_PROVIDER=mock python scripts/evaluate_retrieval_quality.py
DATABASE_URL="sqlite:///:memory:" QDRANT_URL="http://127.0.0.1:6333" QDRANT_COLLECTION="personal_ai_os_quality_eval" EMBEDDING_PROVIDER=mock python scripts/evaluate_qdrant_retrieval_quality.py
```
