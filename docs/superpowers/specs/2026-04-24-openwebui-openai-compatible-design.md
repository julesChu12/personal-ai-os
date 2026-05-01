# Open WebUI OpenAI-Compatible 接入设计

## 背景

当前项目已经有可运行的 FastAPI 后端和自定义聊天接口：

- `POST /chat`
- `GET /health`
- `GET /memory/search`

但仓库内没有内置 Web UI。`README` 明确说明该项目“可接 Open WebUI / AnythingLLM”，同时 roadmap 里将 “Open WebUI function/tool 接入” 标记为未完成。

为了让 Open WebUI 直接作为本项目的聊天前端，最合适的方式不是额外写一个前端，而是为现有后端补一层最小 OpenAI-compatible 协议适配层，让 Open WebUI 把本服务当成一个 OpenAI-compatible provider 来连接。

## 目标

为现有 FastAPI 服务补齐最小 OpenAI-compatible 接口，使 Open WebUI 可以直接完成以下流程：

1. 连接到本服务的 `/v1`
2. 拉取模型列表
3. 发送聊天请求
4. 收到与 OpenAI Chat Completions 兼容的响应

本次只解决“能接入、能聊天、协议闭环”的问题，不扩展到完整 OpenAI API 面。

## 非目标

本次设计明确不做以下内容：

- 不实现完整 Responses API
- 不实现流式输出
- 不实现 tool calling / function calling
- 不实现多模态输入
- 不重写 `Orchestrator` 业务逻辑
- 不在本仓库内新增独立前端工程
- 不要求立即接通 PostgreSQL、Qdrant、真实模型

以上内容都属于后续增强项，不应阻塞最小接入。

## 总体方案

新增一个独立的 OpenAI-compatible 路由层，直接挂载到现有 FastAPI 应用：

- `GET /v1/models`
- `POST /v1/chat/completions`

该路由层只负责协议转换，不直接承载业务编排逻辑。真正的问答仍复用现有：

- `app/core/orchestrator.py`

也就是说，整体结构保持为：

Open WebUI -> OpenAI-compatible route -> Orchestrator -> ModelRouter / Retriever / MemoryPipeline

这样做的好处：

- KISS：只加适配层，不推翻现有实现
- DRY：复用已有 `Orchestrator.chat(...)`
- YAGNI：只做 Open WebUI 连通所需最小接口
- SOLID：把“协议转换”和“业务编排”分离

## 路由设计

### 1. `GET /v1/models`

#### 目的

让 Open WebUI 能发现并选择一个可用模型。

#### 返回策略

返回一个固定的虚拟模型列表，最小实现先提供一个模型：

- `personal-ai-os-chat`

#### 返回示例

```json
{
  "object": "list",
  "data": [
    {
      "id": "personal-ai-os-chat",
      "object": "model",
      "created": 0,
      "owned_by": "personal-ai-os"
    }
  ]
}
```

### 2. `POST /v1/chat/completions`

#### 目的

接收 Open WebUI 发来的 OpenAI 风格聊天请求，并转换为现有 `Orchestrator.chat(...)` 可处理的输入。

#### 最小支持字段

请求中最小只解析这些字段：

- `model`
- `messages`
- `stream`
- `user`

额外字段允许透传但忽略，不作为失败条件。

#### 约束

- `stream=true` 时直接返回明确错误，避免假装支持
- `messages` 不能为空
- 至少要能提取到一条用户消息

#### 消息映射策略

现有 `Orchestrator.chat(...)` 接口签名是：

```python
chat(user_id: str, project_id: str, session_id: str, message: str) -> dict
```

因此兼容层需要把 `messages` 映射到这四个业务字段。

##### `message`

优先取最后一条 `role == "user"` 的消息内容，作为当前用户输入。

##### `user_id`

按以下优先级决定：

1. 请求体里的 `user`
2. 默认值 `openwebui`

##### `project_id`

初版固定使用：

- `openwebui`

后续如果需要多项目隔离，再从 header 或扩展字段提取。

##### `session_id`

按以下优先级决定：

1. 请求头 `X-Session-Id`
2. 请求体扩展字段 `metadata.session_id`（如果存在）
3. 自动生成 UUID

##### 历史上下文

由于现有 `Orchestrator` 只接收单条 `message`，而不直接接收完整消息数组，因此兼容层采用“拼接上下文”的过渡方案：

- 取最后一条用户消息作为主输入
- 将之前的 `system / user / assistant` 消息按顺序拼接为上下文文本
- 以附加文本形式拼到当前输入前面

拼接格式示例：

```text
[Open WebUI Context]
system: 你是...
user: 第一轮问题
assistant: 第一轮回答

[Current User Message]
第二轮问题
```

这样可以在不改 `Orchestrator` 接口的前提下，保留基本上下文连续性。

## 响应映射

`Orchestrator.chat(...)` 当前返回：

```python
{
    "answer": str,
    "memory_used": list,
    "agent_trace": list,
}
```

兼容层将其映射为 OpenAI Chat Completions 风格响应。

### 返回示例

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1710000000,
  "model": "personal-ai-os-chat",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "这里是回答内容"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

说明：

- `usage` 初版统一返回 0，避免伪造精确 token 统计
- `choices` 固定只返回一条
- `finish_reason` 固定为 `stop`

## 错误处理

初版只做必要错误处理：

- `messages` 为空：返回 `400`
- 没有任何 `user` 消息：返回 `400`
- `stream=true`：返回 `400`
- 内部异常：返回 `500`

错误响应保持简单，兼容 OpenAI 风格即可，例如：

```json
{
  "error": {
    "message": "stream is not supported",
    "type": "invalid_request_error"
  }
}
```

## 认证策略

Open WebUI 连接 OpenAI-compatible provider 时通常要求填写 API Key。

为了降低接入成本，初版认证策略如下：

- 接受 `Authorization: Bearer <token>`
- 不校验 token 内容
- 只要求 header 存在即可

这样可以让 Open WebUI 配任意非空 API Key 即可接通。

后续如果需要，可再补：

- 环境变量配置固定 API Key
- 多租户 token 校验

## 文件变更建议

### 新增文件

- `app/api/routes_openai_compat.py`

职责：

- 定义 `/v1/models`
- 定义 `/v1/chat/completions`
- 处理请求校验与协议转换

### 修改文件

- `app/main.py`

职责：

- 注册新的 OpenAI-compatible router

### 可选新增文件

- `app/core/openai_compat.py`

职责：

- 抽离消息拼接、请求映射、响应映射辅助函数

说明：

若实现规模很小，可以先不拆这个文件，避免过度设计。

## Open WebUI 配置方式

完成后，Open WebUI 侧按 OpenAI-compatible provider 方式接入：

- Base URL: `http://<host>:8000/v1`
- API Key: 任意非空值
- Model: `personal-ai-os-chat`

如果 Open WebUI 跑在 Docker 中，而当前服务跑在宿主机，则 Base URL 通常应使用：

- `http://host.docker.internal:8000/v1`

实际值取决于部署位置。

## 测试策略

本次实现至少覆盖以下测试：

1. `GET /v1/models` 返回固定模型列表
2. `POST /v1/chat/completions` 能把 OpenAI 风格请求映射到 `Orchestrator.chat(...)`
3. 返回体包含 `choices[0].message.content`
4. `stream=true` 返回明确错误
5. `messages=[]` 返回 `400`

测试重点是协议适配行为，而不是底层模型质量。

## 风险与后续演进

### 当前风险

- 上下文通过文本拼接而非结构化消息传递，语义保真度有限
- 没有真实 token usage 统计
- 不支持流式输出，Open WebUI 某些体验会受限
- API Key 仅做存在性检查，安全性较弱

### 后续演进建议

第一阶段完成后，可继续按优先级演进：

1. 支持可配置 API Key
2. 支持 `stream=true`
3. 改造 `Orchestrator` 以原生接收消息数组
4. 支持 tool calling
5. 打通真实模型与向量检索依赖

## 结论

本方案以最小成本把当前项目转换为 Open WebUI 可直接连接的 OpenAI-compatible provider。

它不引入额外前端，不推翻现有后端结构，也不抢跑实现后续复杂能力，适合作为当前阶段最稳妥、最可验证的接入路径。
