from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_makefile_exposes_single_ci_entrypoint():
    makefile = read_text("Makefile")

    assert ".PHONY: ci compile test migration-smoke" in makefile
    assert "ci: compile test migration-smoke" in makefile
    assert "python -m pytest" not in makefile.lower()
    assert '"$(PYTHON)" -m pytest -q' in makefile
    assert '"$(PYTHON)" -m compileall -q app tests' in makefile
    assert '"$(PYTHON)" scripts/run_migrations.py --dry-run' in makefile


def test_github_actions_runs_the_same_ci_entrypoint():
    workflow = read_text(".github/workflows/ci.yml")

    assert "python-version: \"3.11\"" in workflow
    assert "python -m pip install -e ." in workflow
    assert "make ci PYTHON=python" in workflow
    assert 'DATABASE_URL: "sqlite:///:memory:"' in workflow


def test_runtime_config_files_document_embedding_provider_contract():
    env_example = read_text(".env.example")
    compose = read_text("docker-compose.yml")
    readme = read_text("README.md")

    for key in [
        "EMBEDDING_PROVIDER",
        "EMBEDDING_API_KEY",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_MODEL",
        "EMBEDDING_DIMENSION",
    ]:
        assert key in env_example
        assert key in compose
        assert key in readme

    assert "OPENAI_COMPAT_API_KEY" in env_example
    assert "OPENAI_COMPAT_API_KEY" in compose
    assert "OPENAI_COMPAT_API_KEY" in readme
    assert "HF_ENDPOINT" in env_example
    assert "HF_ENDPOINT" in compose
    assert "OPENWEBUI_RAG_EMBEDDING_MODEL" in env_example


def test_contributing_documents_regression_expectations():
    contributing = read_text("CONTRIBUTING.md")
    testing = read_text("docs/testing.md")

    assert "make ci PYTHON=python" in contributing
    assert "先补回归测试" in contributing
    assert "检索失败可以降级为空记忆" in contributing
    assert "不放宽 `user_id` 和 `project_id`" in contributing
    assert "OpenAI-compatible 接口" in testing
    assert "涉及降级行为的修改，必须同时断言返回值和日志" in testing


def test_smoke_script_documents_runtime_health_checks():
    script = read_text("scripts/smoke_api.sh")

    assert "set -euo pipefail" in script
    assert "/health" in script
    assert "/diagnostics" in script
    assert "/v1/models" in script
    assert "wrong-smoke-key" in script
    assert "/memory/ingest" in script
    assert "/memory/search" in script
    assert "/chat" in script
    assert "SMOKE_RUN_CHAT" in script
    assert "PYTHON_BIN" in script
    assert "smoke-e2e" in script
    assert "OPENAI_COMPAT_API_KEY" in script


def test_embedding_check_script_documents_provider_validation():
    script = read_text("scripts/check_embedding_provider.py")

    assert "build_embedding_provider" in script
    assert "sys.path.insert" in script
    assert "embedding_dimension" in script
    assert "embed_texts" in script
    assert "embedding provider check passed" in script


def test_runtime_config_check_script_is_documented():
    script = read_text("scripts/check_runtime_config.py")
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")

    assert "validate_runtime_config" in script
    assert "--strict" in script
    assert "--json" in script
    assert "check_runtime_config.py" in readme
    assert "check_runtime_config.py" in testing


def test_database_migration_entrypoints_are_documented():
    script = read_text("scripts/run_migrations.py")
    database = read_text("app/db/database.py")
    compose = read_text("docker-compose.yml")
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "apply_migrations" in script
    assert "--dry-run" in script
    assert "--json" in script
    assert "schema_migrations" in script
    assert "run_migrations.py" in readme
    assert "run_migrations.py" in testing
    assert "Run migrations first: python scripts/run_migrations.py" in database
    assert "python scripts/run_migrations.py && exec uvicorn" in compose
    assert "应用启动不再自动 `create_all`" in readme
    assert "应用启动不再调用 `Base.metadata.create_all`" in testing
    assert "Task P0-2" in roadmap
    assert "状态：已完成基础版。" in roadmap


def test_api_error_contract_is_documented():
    errors = read_text("app/core/errors.py")
    main = read_text("app/main.py")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "register_error_handlers" in errors
    assert "request validation failed" in errors
    assert "internal server error" in errors
    assert "authentication_error" in errors
    assert "register_error_handlers(app)" in main
    assert "{error: {code, message, type}}" in testing
    assert "OpenAI-compatible" in testing
    assert "Task P0-3" in roadmap
    assert "API 错误响应标准化" in roadmap
    assert "状态：已完成基础版。" in roadmap


def test_request_context_contract_is_documented():
    request_context = read_text("app/core/request_context.py")
    errors = read_text("app/core/errors.py")
    main = read_text("app/main.py")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "REQUEST_ID_HEADER = \"X-Request-ID\"" in request_context
    assert "request completed" in request_context
    assert "duration_ms" in request_context
    assert "request_id" in errors
    assert "register_request_context_middleware(app)" in main
    assert "X-Request-ID" in testing
    assert "request_id, path, method, status" in testing
    assert "Task P0-4" in roadmap
    assert "请求日志和 request id" in roadmap
    assert "状态：已完成基础版。" in roadmap


def test_session_identity_contract_is_documented():
    auth = read_text("app/core/auth.py")
    session_identity = read_text("app/core/session_identity.py")
    openai_compat = read_text("app/api/routes_openai_compat.py")
    sessions_route = read_text("app/api/routes_sessions.py")
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "resolve_openai_identity" in session_identity
    assert "resolve_project_scope" in session_identity
    assert "class ApiPrincipal" in auth
    assert "authenticate_bearer" in auth
    assert "bind_openai_identity_to_principal" in auth
    assert "OPENAI_COMPAT_API_KEYS" in read_text(".env.example")
    assert "DEFAULT_OPENWEBUI_USER_ID" in session_identity
    assert "resolve_openai_identity" in openai_compat
    assert "bind_openai_identity_to_principal" in openai_compat
    assert "resolve_project_scope" in sessions_route
    assert "metadata.user_id" in readme
    assert "metadata.project_id" in readme
    assert "OPENAI_COMPAT_API_KEYS" in readme
    assert "X-Session-Id" in readme
    assert "Session and project identity" in testing
    assert "`/sessions` 查询必须同时提供非空 `user_id` 和 `project_id`" in testing
    assert "Task P1-1" in roadmap
    assert "Session / Project 语义收紧" in roadmap
    assert "状态：已完成基础版。" in roadmap
    assert "多 API Key 与 user/project 绑定" in roadmap


def test_memory_governance_contract_is_documented():
    memory_identity = read_text("app/memory/memory_identity.py")
    memory_pipeline = read_text("app/memory/memory_pipeline.py")
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "build_memory_identity" in memory_identity
    assert "\"user_id\": user_id" in memory_identity
    assert "\"project_id\": project_id" in memory_identity
    assert "normalize_memory_type(candidate.memory_type)" in memory_identity
    assert "normalize_memory_title(candidate.title)" in memory_identity
    assert "build_memory_identity" in memory_pipeline
    assert "point_id=getattr(existing, \"qdrant_point_id\", None)" in memory_pipeline
    assert "Memory governance" in testing
    assert "user_id, project_id, memory_type, title" in testing
    assert "qdrant_point_id" in readme
    assert "Task P1-2" in roadmap
    assert "记忆治理 v2" in roadmap
    assert "状态：已完成基础版。" in roadmap


def test_provider_reliability_contract_is_documented():
    provider_errors = read_text("app/core/provider_errors.py")
    model_router = read_text("app/core/model_router.py")
    embedding_provider = read_text("app/memory/embedding_provider.py")
    env_example = read_text(".env.example")
    compose = read_text("docker-compose.yml")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "ProviderRequestError" in provider_errors
    assert "retry_provider_call" in provider_errors
    assert "provider_timeout_seconds" in model_router
    assert "provider_retry_attempts" in model_router
    assert "ProviderRequestError" in embedding_provider
    assert "PROVIDER_TIMEOUT_SECONDS" in env_example
    assert "PROVIDER_RETRY_ATTEMPTS" in compose
    assert "Provider reliability" in testing
    assert "Task P1-3" in roadmap
    assert "Provider 可靠性治理" in roadmap
    assert "状态：已完成基础版。" in roadmap


def test_p2_tool_layer_contract_is_documented():
    registry = read_text("app/tools/registry.py")
    routes_tools = read_text("app/api/routes_tools.py")
    mcp_server = read_text("app/tools/mcp_server.py")
    mcp_runner = read_text("scripts/run_mcp_server.py")
    main = read_text("app/main.py")
    models = read_text("app/db/models.py")
    migration = read_text("app/db/migrations/versions/v0002_tool_runs.py")
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "class ToolRegistry" in registry
    assert "build_default_tool_registry" in registry
    assert "file.read_text" in registry
    assert "file.write_text" in registry
    assert "obsidian.append_note" in registry
    assert "shell.run_safe" in registry
    assert "router = APIRouter(prefix=\"/tools\"" in routes_tools
    assert "@router.get(\"\")" in routes_tools
    assert "@router.post(\"/{tool_name}/invoke\")" in routes_tools
    assert "require_tools_principal" in routes_tools
    assert "enforce_principal_scope" in routes_tools
    assert "@router.get(\"/runs\")" in routes_tools
    assert "handle_mcp_request" in mcp_server
    assert "tools/list" in mcp_server
    assert "tools/call" in mcp_server
    assert "run_mcp_server.py" in mcp_runner
    assert "routes_tools_router" in main
    assert "class ToolRun" in models
    assert "tool_runs" in migration
    assert "Tool Registry" in readme
    assert "MCP" in readme
    assert "Tool adapter" in testing
    assert "MCP" in testing
    assert "Task P2-1" in roadmap
    assert "Task P2-2" in roadmap
    assert "Task P2-3" in roadmap
    assert "已完成基础版" in roadmap


def test_p3_agent_workflow_contract_is_documented():
    planner = read_text("app/agents/planner.py")
    executor = read_text("app/agents/executor.py")
    workflow = read_text("app/agents/workflow.py")
    routes_agents = read_text("app/api/routes_agents.py")
    models = read_text("app/db/models.py")
    migration = read_text("app/db/migrations/versions/v0003_agent_runs.py")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "class AgentStep" in planner
    assert "validate_agent_plan" in planner
    assert "AgentPlanValidationError" in planner
    assert "def plan" in planner
    assert "depends_on" in planner
    assert "planner_mode" in workflow
    assert "execution_mode" in workflow
    assert "planner_mode" in routes_agents
    assert "execution_mode" in routes_agents
    assert "require_agents_principal" in routes_agents
    assert "enforce_principal_scope" in routes_agents
    assert "model planner request failed" in planner
    assert "validate_agent_plan(raw_plan, registry)" in planner
    assert "class ExecutorAgent" in executor
    assert "def execute" in executor
    assert "class AgentWorkflow" in workflow
    assert "record_tool_run" in workflow
    assert "record_agent_run" in workflow
    assert "agent_run_id" in workflow
    assert "plan_payload" in workflow
    assert "persist_agent_result" in workflow
    assert "MemoryPipeline" in workflow
    assert "class AgentRun" in models
    assert "agent_runs" in migration
    assert "plan:" in routes_agents
    assert "memory_agent" in routes_agents
    assert "@router.get(\"/agents/runs\")" in routes_agents
    assert "@router.post(\"/agents/run\")" in routes_agents
    assert "Agent workflow" in testing
    assert "模型化 Planner" in testing
    assert "planner_mode=model" in testing
    assert "Structured Agent Plan" in testing
    assert "failure short-circuit" in testing
    assert "agent_result" in testing
    assert "AgentRun" in testing
    assert "Task P3-1" in roadmap
    assert "Task P3-2" in roadmap
    assert "Task P3-3" in roadmap
    assert "Task P3-4" in roadmap
    assert "Task P3-5" in roadmap
    assert "Planner / Executor 最小工作流" in roadmap
    assert "多步骤 Executor 失败短路策略" in roadmap
    assert "Agent 结果按策略进入长期记忆" in roadmap
    assert "Agent Run 持久化与查询" in roadmap
    assert "已完成基础版" in roadmap
    assert "Task N2" in roadmap
    assert "状态：已完成" in roadmap


def test_retrieval_quality_evaluation_contract_is_documented():
    script = read_text("scripts/evaluate_retrieval_quality.py")
    testing = read_text("docs/testing.md")
    readme = read_text("README.md")

    assert "evaluate_retrieval_quality" in script
    assert "retrieval_quality_cases.json" in script
    assert "--top-k" in script
    assert "--json" in script
    assert "--min-hit-rate" in script
    assert "min_hit_rate_error" in script
    assert "retrieval quality" in testing.lower()
    assert "--min-hit-rate 1.0" in testing
    assert "--min-hit-rate 1.0" in readme
    assert "retrieval-quality.yml" in testing


def test_qdrant_retrieval_quality_evaluation_contract_is_documented():
    script = read_text("scripts/evaluate_qdrant_retrieval_quality.py")
    testing = read_text("docs/testing.md")

    assert "VectorStore" in script
    assert "evaluate_qdrant_retrieval_quality" in script
    assert "retrieval_quality_cases.json" in script
    assert "--user-id" in script
    assert "--project-id" in script
    assert "--min-hit-rate" in script
    assert "min_hit_rate_error" in script
    assert "uuid.uuid5" in script
    assert "qdrant retrieval quality" in testing.lower()


def test_diagnostics_api_is_documented():
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")

    assert "/diagnostics" in readme
    assert "database" in readme.lower()
    assert "qdrant" in readme.lower()
    assert "embedding" in readme.lower()
    assert "scheduler" in readme.lower()
    assert "/health" in testing
    assert "/diagnostics" in testing
    assert "ok | degraded | error" in testing


def test_ci_exposes_docker_smoke_job():
    workflow = read_text(".github/workflows/ci.yml")

    assert "smoke:" in workflow
    assert "SMOKE_RUN_CHAT: \"1\"" in workflow
    assert "docker compose up -d --build" in workflow
    assert "bash scripts/smoke_api.sh" in workflow
    assert "docker compose down -v" in workflow


def test_manual_retrieval_quality_workflow_is_opt_in():
    workflow = read_text(".github/workflows/retrieval-quality.yml")

    assert "workflow_dispatch" in workflow
    assert "provider:" in workflow
    assert "default: \"mock\"" in workflow
    assert "secrets.EMBEDDING_API_KEY" in workflow
    assert "scripts/evaluate_retrieval_quality.py" in workflow
    assert "scripts/evaluate_qdrant_retrieval_quality.py" in workflow


def test_cli_and_obsidian_entrypoints_are_documented():
    cli = read_text("app/cli/main.py")
    cli_tests = read_text("tests/test_cli.py")
    import_script = read_text("scripts/import_obsidian_vault.py")
    sync_script = read_text("scripts/sync_obsidian_vault.py")
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")

    assert 'agents_app.command("runs")' in cli
    assert 'agents_app.command("list-runs", hidden=True)' in cli
    assert "tests/test_cli.py" in testing
    assert "agent_run_id" in cli_tests
    assert "ObsidianImporter" in import_script
    assert "obsidian-sync" in cli
    assert "ObsidianSyncEngine" in sync_script
    assert "scripts/sync_obsidian_vault.py" in readme
    assert "scripts/sync_obsidian_vault.py" in testing
    assert "tests/test_obsidian_sync.py" in testing
    assert "scripts/import_obsidian_vault.py" in readme
    assert "scripts/import_obsidian_vault.py" in testing


def test_open_source_readiness_document_tracks_release_blockers():
    text = read_text("docs/open-source-readiness.md")

    assert "Apache-2.0" in text
    assert "Secrets" in text
    assert "CI" in text
    assert "Docker smoke" in text
    assert "Security policy" in text
    assert "Code of conduct" in text
    assert "Repository URLs" in text
    assert "GitHub Actions" in text
    assert "未决" in text


def test_readme_documents_current_progress_and_next_stage():
    readme = read_text("README.md")

    assert "## 当前项目进度" in readme
    assert "整体进度约为 90%" in readme
    assert "当前阶段目标" in readme
    assert "N1" in readme
    assert "N2" in readme
    assert "N7" in readme
    assert "next-stage-execution-spec.md" in readme
    assert "2026-05-06-obsidian-bidirectional-sync-spec.md" in readme


def test_next_stage_spec_and_plan_are_documented():
    spec = read_text("docs/superpowers/specs/2026-05-04-next-stage-execution-spec.md")
    plan = read_text("docs/superpowers/plans/2026-05-04-next-stage-execution.md")
    roadmap = read_text("docs/development-roadmap.md")
    testing = read_text("docs/testing.md")

    for task_id in ["N1", "N2", "N3a", "N3b", "N4", "N5", "N6", "N7", "N8", "N9", "N10"]:
        assert task_id in spec
        assert task_id in plan
        assert task_id in roadmap

    assert "P4 / N-series" in roadmap
    assert "| N1 retrieval-quality-foundation 规格收尾验证 | P0 | 已完成 |" in roadmap
    assert "| N2 Planner 模型化 | P0 | 已完成 |" in roadmap
    assert "| N7 多 API Key 与 user/project 绑定 | P1 | 已完成 |" in roadmap
    assert "| N5 MCP Server 适配 | P1 | 已完成 |" in roadmap
    assert "| N3a Executor 条件分支与顺序 DAG | P1 | 已完成 |" in roadmap
    assert "| N4 写类工具白名单 | P1 | 已完成 |" in roadmap
    assert "| N3b Executor 有限并行 | P2 | 已完成 |" in roadmap
    assert "| N6 Obsidian 单向导入 | P2 | 已完成 |" in roadmap
    assert "| N11 Obsidian 双向同步基础版 | P2 | 已完成 |" in roadmap
    assert "| N8 真实 embedding 在线质量回归 | P2 | 已完成 |" in roadmap
    assert "| N9 CLI 升级 | P3 | 已完成 |" in roadmap
    assert "| N10 移除 `create_all` 兼容路径 | P3 | 已完成 |" in roadmap
    assert "| N1 | retrieval-quality-foundation 规格收尾验证 | P0 | 0.5-1 天 | 已完成 |" in spec
    assert "| N2 | Planner 模型化：受控生成结构化 plan | P0 | 2-3 天 | 已完成 |" in spec
    assert "| N7 | 多 API Key 与 user/project 绑定 | P1 | 2 天 | 已完成 |" in spec
    assert "| N5 | MCP Server 适配：只读暴露 Tool Registry | P1 | 2 天 | 已完成 |" in spec
    assert "| N3a | Executor 条件分支与顺序 DAG | P1 | 1-2 天 | 已完成 |" in spec
    assert "| N4 | 写类工具白名单 | P1 | 1-2 天 | 已完成 |" in spec
    assert "| N3b | Executor 有限并行 | P2 | 1-2 天 | 已完成 |" in spec
    assert "- [x] **Step 5: Verify**" in plan
    assert "Coverage audit" not in testing
    assert "覆盖审计" in testing
    assert "197 个测试用例" in testing
    assert "N5 / N3 / N4 的新增功能已补齐以下回归覆盖" in testing


def test_obsidian_bidirectional_sync_contract_is_documented():
    models = read_text("app/db/models.py")
    migration = read_text("app/db/migrations/versions/v0004_obsidian_sync_states.py")
    sync_engine = read_text("app/memory/obsidian_sync.py")
    routes = read_text("app/api/routes_memory.py")
    cli = read_text("app/cli/main.py")
    spec = read_text("docs/superpowers/specs/2026-05-06-obsidian-bidirectional-sync-spec.md")
    testing = read_text("docs/testing.md")

    assert "class ObsidianSyncState" in models
    assert "0004_obsidian_sync_states" in migration
    assert "class ObsidianSyncEngine" in sync_engine
    assert "def dry_run" in sync_engine
    assert "def apply" in sync_engine
    assert "both_changed" in sync_engine
    assert "vault_deleted" in sync_engine
    assert "/memory/obsidian/sync" in routes
    assert "obsidian-sync" in cli
    assert "Dry-run first" in spec
    assert "Safe deletion policy" in spec
    assert "tests/test_obsidian_sync.py" in testing
