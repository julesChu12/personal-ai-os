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
    assert "DATABASE_URL: sqlite:///:memory:" in workflow


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
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "apply_migrations" in script
    assert "--dry-run" in script
    assert "--json" in script
    assert "schema_migrations" in script
    assert "run_migrations.py" in readme
    assert "run_migrations.py" in testing
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
    session_identity = read_text("app/core/session_identity.py")
    openai_compat = read_text("app/api/routes_openai_compat.py")
    sessions_route = read_text("app/api/routes_sessions.py")
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "resolve_openai_identity" in session_identity
    assert "resolve_project_scope" in session_identity
    assert "DEFAULT_OPENWEBUI_USER_ID" in session_identity
    assert "resolve_openai_identity" in openai_compat
    assert "resolve_project_scope" in sessions_route
    assert "metadata.user_id" in readme
    assert "metadata.project_id" in readme
    assert "X-Session-Id" in readme
    assert "Session and project identity" in testing
    assert "`/sessions` 查询必须同时提供非空 `user_id` 和 `project_id`" in testing
    assert "Task P1-1" in roadmap
    assert "Session / Project 语义收紧" in roadmap
    assert "状态：已完成基础版。" in roadmap


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
    main = read_text("app/main.py")
    models = read_text("app/db/models.py")
    migration = read_text("app/db/migrations/versions/v0002_tool_runs.py")
    readme = read_text("README.md")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "class ToolRegistry" in registry
    assert "build_default_tool_registry" in registry
    assert "file.read_text" in registry
    assert "shell.run_safe" in registry
    assert "router = APIRouter(prefix=\"/tools\"" in routes_tools
    assert "@router.get(\"\")" in routes_tools
    assert "@router.post(\"/{tool_name}/invoke\")" in routes_tools
    assert "@router.get(\"/runs\")" in routes_tools
    assert "routes_tools_router" in main
    assert "class ToolRun" in models
    assert "tool_runs" in migration
    assert "Tool Registry" in readme
    assert "Tool adapter" in testing
    assert "Task P2-1" in roadmap
    assert "Task P2-2" in roadmap
    assert "Task P2-3" in roadmap
    assert "已完成基础版" in roadmap


def test_p3_agent_workflow_contract_is_documented():
    planner = read_text("app/agents/planner.py")
    executor = read_text("app/agents/executor.py")
    workflow = read_text("app/agents/workflow.py")
    routes_agents = read_text("app/api/routes_agents.py")
    testing = read_text("docs/testing.md")
    roadmap = read_text("docs/development-roadmap.md")

    assert "class AgentStep" in planner
    assert "validate_agent_plan" in planner
    assert "AgentPlanValidationError" in planner
    assert "def plan" in planner
    assert "class ExecutorAgent" in executor
    assert "def execute" in executor
    assert "class AgentWorkflow" in workflow
    assert "record_tool_run" in workflow
    assert "plan_payload" in workflow
    assert "persist_agent_result" in workflow
    assert "MemoryPipeline" in workflow
    assert "plan:" in routes_agents
    assert "memory_agent" in routes_agents
    assert "@router.post(\"/agents/run\")" in routes_agents
    assert "Agent workflow" in testing
    assert "Structured Agent Plan" in testing
    assert "failure short-circuit" in testing
    assert "agent_result" in testing
    assert "Task P3-1" in roadmap
    assert "Task P3-2" in roadmap
    assert "Task P3-3" in roadmap
    assert "Task P3-4" in roadmap
    assert "Planner / Executor 最小工作流" in roadmap
    assert "多步骤 Executor 失败短路策略" in roadmap
    assert "Agent 结果按策略进入长期记忆" in roadmap
    assert "已完成基础版" in roadmap


def test_retrieval_quality_evaluation_contract_is_documented():
    script = read_text("scripts/evaluate_retrieval_quality.py")
    testing = read_text("docs/testing.md")

    assert "evaluate_retrieval_quality" in script
    assert "retrieval_quality_cases.json" in script
    assert "--top-k" in script
    assert "--json" in script
    assert "retrieval quality" in testing.lower()


def test_qdrant_retrieval_quality_evaluation_contract_is_documented():
    script = read_text("scripts/evaluate_qdrant_retrieval_quality.py")
    testing = read_text("docs/testing.md")

    assert "VectorStore" in script
    assert "evaluate_qdrant_retrieval_quality" in script
    assert "retrieval_quality_cases.json" in script
    assert "--user-id" in script
    assert "--project-id" in script
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


def test_open_source_readiness_document_tracks_release_blockers():
    text = read_text("docs/open-source-readiness.md")

    assert "Apache-2.0" in text
    assert "Secrets" in text
    assert "CI" in text
    assert "Docker smoke" in text
    assert "未决" in text
