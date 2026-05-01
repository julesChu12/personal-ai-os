# Scheduler Memory Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为项目补齐“定时汇总最近会话并沉淀长期记忆”的最小可用实现。

**Architecture:** 保持现有 `Message -> MemoryPipeline -> Memory/Obsidian/Qdrant` 链路不变，仅新增一个批量汇总入口。调度器只负责触发作业与托管生命周期，汇总、去重、落库逻辑集中在 `app/scheduler/jobs.py`，避免职责分散。

**Tech Stack:** Python 3、FastAPI、APScheduler、SQLAlchemy 风格查询接口、标准库 `unittest`

---

### Task 1: 先补作业行为测试

**Files:**
- Create: `tests/test_scheduler_jobs.py`
- Test: `tests/test_scheduler_jobs.py`

- [ ] **Step 1: 写失败测试，定义“有消息会话会被汇总”的目标行为**

```python
def test_daily_memory_job_persists_summary_for_recent_session():
    session_rows = [("u1", "p1", "s1")]
    messages = [
        SimpleNamespace(role="user", content="今天学习了 RAG"),
        SimpleNamespace(role="assistant", content="总结了检索链路"),
    ]
```

- [ ] **Step 2: 运行单测并确认因缺少实现而失败**

```bash
python3 -m unittest tests.test_scheduler_jobs -v
```

预期：至少一个断言失败，说明当前 `daily_memory_job()` 还没有真正汇总消息。

- [ ] **Step 3: 再写一个失败测试，定义“已有定时汇总记忆则跳过”的去重行为**

```python
def test_daily_memory_job_skips_session_when_summary_memory_exists():
    existing_summary = object()
```

- [ ] **Step 4: 再次运行单测并确认失败原因符合预期**

```bash
python3 -m unittest tests.test_scheduler_jobs -v
```

预期：失败集中在作业未筛选/未持久化/未跳过重复会话。

### Task 2: 实现批量汇总作业

**Files:**
- Modify: `app/scheduler/jobs.py`
- Test: `tests/test_scheduler_jobs.py`

- [ ] **Step 1: 为作业增加可注入依赖的实现边界**

```python
def daily_memory_job(
    db_factory: Callable[[], Any] | None = None,
    pipeline: MemoryPipeline | None = None,
    lookback_hours: int = 24,
) -> dict[str, int]:
```

- [ ] **Step 2: 最小实现最近会话筛选、消息组装、去重判断、候选提取与持久化**

```python
messages = db.query(Message).filter_by(
    user_id=user_id,
    project_id=project_id,
    session_id=session_id,
).order_by(Message.created_at.asc()).all()
```

- [ ] **Step 3: 运行单测并确认两个行为都转绿**

```bash
python3 -m unittest tests.test_scheduler_jobs -v
```

预期：`OK`

### Task 3: 接入调度器生命周期

**Files:**
- Modify: `app/scheduler/scheduler.py`
- Modify: `app/main.py`
- Test: `tests/test_scheduler_jobs.py`

- [ ] **Step 1: 在调度器启动时注册每日记忆汇总作业**

```python
scheduler.add_job(daily_memory_job, "interval", hours=24, id="daily_memory_job", replace_existing=True)
```

- [ ] **Step 2: 在 FastAPI 启动/关闭阶段托管 scheduler**

```python
app.state.scheduler = start_scheduler()
app.state.scheduler.shutdown(wait=False)
```

- [ ] **Step 3: 运行回归验证**

```bash
python3 -m unittest tests.test_scheduler_jobs -v
```

预期：`OK`
