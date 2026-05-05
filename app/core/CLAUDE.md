# app.core — 核心领域与横切能力

导航：[仓库根](../../CLAUDE.md) › [app](../CLAUDE.md) › **core**

## 职责

编排（`orchestrator`）、模型路由（`model_router`）、会话身份（`session_identity`）、统一错误（`errors`）、请求上下文与中间件（`request_context`）、诊断（`diagnostics`）、配置校验（`config_validation`）、聊天持久化（`chat_persistence`）、对外 schema（`schemas`）、提供商错误类型（`provider_errors`）。

## 关键入口

- `Orchestrator`：`chat` / `chat_stream` / `task`，组合检索与模型调用。
- `ModelRouter`：对接 OpenAI 兼容、Ollama、Minimax 等（详见源码）。
- `register_error_handlers` / `register_request_context_middleware`：在 `main.py` 注册。

## 依赖

依赖 `app.config`、`app.memory`（检索）、`app.db`（若持久化）等。

## 测试

`tests/test_errors.py`、`tests/test_request_context.py`、`tests/test_session_identity.py`、`tests/test_config_validation.py`、`tests/test_diagnostics.py`、`tests/test_provider_reliability.py`、`tests/test_chat_persistence.py` 等。
