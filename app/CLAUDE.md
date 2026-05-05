# app 包

导航：[仓库根](../CLAUDE.md) › **app**

## 职责

`personal_ai_os` 主包：FastAPI 应用、领域逻辑与基础设施。入口模块 `main.py` 聚合路由、中间件、错误处理与调度器生命周期。

## 子模块

| 子目录 | 说明 |
|--------|------|
| [api/](api/CLAUDE.md) | HTTP 路由 |
| [agents/](agents/CLAUDE.md) | 多 Agent 与工作流 |
| [core/](core/CLAUDE.md) | 编排、模型、会话、错误、诊断 |
| [db/](db/CLAUDE.md) | 数据库与迁移 |
| [memory/](memory/CLAUDE.md) | RAG、向量、Obsidian、嵌入 |
| [tools/](tools/CLAUDE.md) | 可调用工具注册与实现 |
| [scheduler/](scheduler/CLAUDE.md) | 定时任务 |
| [cli/](cli/CLAUDE.md) | Typer 客户端 |

## 关键文件

- `main.py`：`FastAPI` 实例、`lifespan`（`init_db`、`start_scheduler`）、路由注册。
- `config.py`：`Settings`（`pydantic-settings`），环境变量与默认值。

## 测试

各域测试位于仓库根目录 [`tests/`](../tests/CLAUDE.md)，按路由或模块命名对应。
