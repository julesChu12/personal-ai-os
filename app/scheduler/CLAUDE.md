# app.scheduler — 定时任务

导航：[仓库根](../../CLAUDE.md) › [app](../CLAUDE.md) › **scheduler**

## 职责

APScheduler 集成：`scheduler.py` 启动/关闭；`jobs.py` 定义任务。

## 生命周期

在 `app.main` 的 `lifespan` 中 `start_scheduler()`，关闭时 `shutdown(wait=False)`。

## 测试

`tests/test_scheduler_lifecycle.py`、`tests/test_scheduler_jobs.py`。
