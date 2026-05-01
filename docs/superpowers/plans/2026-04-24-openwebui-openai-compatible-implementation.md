# Open WebUI OpenAI-Compatible Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有 FastAPI 服务补齐最小 OpenAI-compatible 接口，让 Open WebUI 能把它作为聊天模型提供方接入。

**Architecture:** 新增一个独立的协议适配路由层，只实现 `GET /v1/models` 和 `POST /v1/chat/completions`。该层负责 OpenAI 风格请求/响应转换，真正的聊天业务继续复用 `Orchestrator.chat(...)`，避免重复实现。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、unittest、FastAPI TestClient

---

### Task 1: 先锁定协议层测试

**Files:**
- Create: `tests/test_openai_compat.py`
- Test: `tests/test_openai_compat.py`

- [ ] **Step 1: 写失败测试，定义 `/v1/models` 的最小返回契约**

```python
response = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
assert response.status_code == 200
assert response.json()["data"][0]["id"] == "personal-ai-os-chat"
```

- [ ] **Step 2: 写失败测试，定义 `/v1/chat/completions` 到 `Orchestrator.chat(...)` 的映射**

```python
payload = {
    "model": "personal-ai-os-chat",
    "messages": [
        {"role": "system", "content": "系统指令"},
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "第一答"},
        {"role": "user", "content": "第二问"},
    ],
    "user": "alice",
}
```

- [ ] **Step 3: 写失败测试，锁定错误路径**

```python
assert client.post("/v1/chat/completions", json={"model": "x", "messages": [], "stream": False}).status_code == 400
assert client.post("/v1/chat/completions", json={"model": "x", "messages": [...], "stream": True}).status_code == 400
assert client.get("/v1/models").status_code == 401
```

- [ ] **Step 4: 运行测试并确认是 RED**

```bash
DATABASE_URL="sqlite:///:memory:" "/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m unittest tests.test_openai_compat -v
```

预期：因为路由和 schema 尚未实现而失败。

### Task 2: 实现最小 OpenAI-compatible 路由层

**Files:**
- Create: `app/api/routes_openai_compat.py`
- Modify: `app/core/schemas.py`
- Modify: `app/main.py`
- Test: `tests/test_openai_compat.py`

- [ ] **Step 1: 在 `app/core/schemas.py` 增加最小 OpenAI-compatible 请求/响应模型**

```python
class OpenAICompatMessage(BaseModel):
    role: str
    content: str
```

- [ ] **Step 2: 在 `app/api/routes_openai_compat.py` 实现认证检查、`/v1/models` 和 `/v1/chat/completions`**

```python
@router.get("/v1/models")
def list_models(...):
    ...

@router.post("/v1/chat/completions")
def chat_completions(...):
    ...
```

- [ ] **Step 3: 在 `app/main.py` 注册新的兼容路由**

```python
app.include_router(openai_compat_router)
```

- [ ] **Step 4: 运行测试并确认转绿**

```bash
DATABASE_URL="sqlite:///:memory:" "/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/python" -m unittest tests.test_openai_compat -v
```

预期：`OK`

### Task 3: 做最小回归验证

**Files:**
- Test: `tests/test_openai_compat.py`
- Test: `tests/test_scheduler_jobs.py`
- Test: `tests/test_scheduler_lifecycle.py`

- [ ] **Step 1: 运行相关回归测试**

```bash
DATABASE_URL="sqlite:///:memory:" "/Users/yt/Documents/myself/personal-ai-os/.venv311/bin/pytest" -q
```

- [ ] **Step 2: 如果本地服务可启动，再做一次接口级验证**

```bash
curl -s http://127.0.0.1:8000/v1/models -H "Authorization: Bearer test-key"
```

预期：返回包含 `personal-ai-os-chat` 的模型列表。
