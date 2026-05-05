# app.api — HTTP 路由

导航：[仓库根](../../CLAUDE.md) › [app](../CLAUDE.md) › **api**

## 职责

对外 HTTP API：健康检查、聊天、记忆、sessions、agents、OpenAI 兼容端点、诊断、工具调用等。请求体验证见 `request_validation.py`。

## 路由模块（按文件名）

| 文件 | 用途 |
|------|------|
| `routes_health.py` | 存活检查 |
| `routes_chat.py` | 聊天入口 |
| `routes_memory.py` | 记忆检索/写入相关 |
| `routes_sessions.py` | 会话 |
| `routes_agents.py` | Agent 与任务 |
| `routes_openai_compat.py` | OpenAI 兼容 `/v1/*` |
| `routes_diagnostics.py` | `/diagnostics` 深度诊断 |
| `routes_tools.py` | 工具 HTTP 接口 |

## 依赖

调用 `app.core`（编排、schema、错误）、`app.memory`、`app.agents`、`app.tools` 等。

## 测试

`tests/test_*_route.py`、`tests/test_openai_compat.py`、`tests/test_diagnostics.py` 等。
