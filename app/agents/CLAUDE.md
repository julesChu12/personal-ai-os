# app.agents — 多 Agent

导航：[仓库根](../../CLAUDE.md) › [app](../CLAUDE.md) › **agents**

## 职责

多 Agent 编排相关逻辑：规划（planner）、执行（executor）、研究员/编码/记忆等占位或实现、`workflow` 串联、`run_store` 持久化运行记录。

## 关键文件

| 文件 | 说明 |
|------|------|
| `workflow.py` | Agent 工作流主逻辑 |
| `planner.py` | 规划 |
| `executor.py` | 执行 |
| `run_store.py` | run 存储 |
| `researcher.py` / `coder.py` / `memory_agent.py` | 角色 Agent |

## 依赖

与 `app.core.model_router`、`app.db`（若持久化 run）、工具层协作。

## 测试

`tests/test_agent_workflow.py`、`tests/test_agent_plan.py`、`tests/test_agents_route.py`。
