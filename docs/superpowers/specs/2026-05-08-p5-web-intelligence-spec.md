# P5 Web Intelligence Integration (安全的外部网络接入) SPEC

日期：2026-05-08

## 1. 北极星对齐 (North Star Alignment)

在过去的 P0-P4 阶段，我们成功构建了 Personal AI OS 的“内核”与“本地文件系统”，实现了安全审计、任务编排、双向记忆同步。然而，当前的系统是一个“闭环的孤岛”，其知识边界完全受限于大模型的预训练数据和本地硬盘上的文件。

**P5 的终极目标是为 Personal AI OS 装上“安全的眼睛（Web Intelligence）”。**
只有赋予系统主动查阅最新网络资讯、阅读外部文档的能力，我们架构图中规划的 `Researcher Agent` 才能真正“活”过来，从一个桩代码（Stub）变成一个能辅助用户进行深度行业调研、错误排查的专家。

核心原则：**在赋予网络能力的同时，绝不破坏 P0-P4 建立的安全、防越权和可审计底线。**

---

## 2. 核心能力与工具定义 (Core Capabilities)

我们将在 `ToolRegistry` 中引入两个全新的核心工具，所有外部访问必须且只能通过这两个工具进行，从而保证每一条网络请求都有 `ToolRun` 审计记录。

### 2.1 `web.search` (网络搜索工具)
*   **职责**：给定一个自然语言或关键词 Query，返回搜索结果列表。
*   **输入 Schema**：
    *   `query` (string, required): 搜索关键词。
    *   `limit` (integer, optional): 返回结果数量，默认 5，最大 10。
*   **输出结构**：返回一个 JSON 数组，每项包含 `title`, `url`, `snippet`。
*   **实现建议**：
    *   初期为了降低开源用户的接入成本，默认使用无 Key 限制的免费方案（如 `DuckDuckGo Search API`）。
    *   预留 Provider 接口，后续可配置为 `Tavily`, `Google Custom Search` 等付费高质数据源。

### 2.2 `web.fetch` (安全网页读取工具)
*   **职责**：给定一个外部 URL，抓取网页内容并清洗为适合大模型阅读的纯净 Markdown。
*   **输入 Schema**：
    *   `url` (string, required): 目标网页地址。
*   **输出结构**：清洗后的纯文本/Markdown 正文。
*   **技术要求与安全红线 (Critical Security)**：
    *   **防 SSRF（服务器端请求伪造）**：这是最核心的安全边界。必须在建立 HTTP 连接前，解析域名的 IP 地址，如果解析出的 IP 属于私有局域网或保留地址（如 `127.0.0.0/8`, `10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12` 以及 AWS Metadata IP `169.254.169.254`），必须立刻抛出安全拦截异常。
    *   **反反爬与 Header 伪装**：设置合理的用户代理（User-Agent）和超时时间（Timeout: 10s）。
    *   **内容清洗**：使用如 `readability-lxml` 或 `BeautifulSoup` 去除网页的 `<script>`, `<style>`, `<nav>`, `<footer>` 等噪声，提取正文。

---

## 3. 专家觉醒：ResearcherAgent (Phase 1)

当前 `app/agents/researcher.py` 只是一个返回静态文本的桩代码。在 P5 阶段，它将被接入大模型。

*   **执行逻辑**：
    1.  当 `AgentWorkflow` 将任务分配给 `ResearcherAgent` 且赋予其 `web.search` 和 `web.fetch` 权限时。
    2.  `ResearcherAgent` 会利用内部的“微型 Planner”制定调研策略（比如先搜索关键词，再读取前两个高价值 URL）。
    3.  收集到信息后，内部的大模型会对信息进行去重和提炼。
*   **最终输出**：
    *   返回结构化的 `Research Notes`，包含信息来源（Citations），直接服务于最终用户的提问，或者作为 `CoderAgent` 写代码前的上下文。

---

## 4. MCP Server 同步扩展

由于我们所有的工具都注册在 `ToolRegistry` 中，当 `web.search` 和 `web.fetch` 开发完毕并注册后，我们的 MCP Server (`app/tools/mcp_server.py`) 将自动能够将这些能力暴露给外部（如 Cursor、Claude Desktop 等）。
*   *注意*：网络搜索工具原则上属于只读工具（Read-only），不修改系统状态，因此 MCP 默认暴露它们是安全的。

---

## 5. 验收标准 (Acceptance Criteria)

1.  **安全合规**：测试用例证明 `web.fetch` 工具调用 `http://127.0.0.1:8000/diagnostics` 或 `http://169.254.169.254/latest/meta-data/` 能够被正确且稳定地拦截，不产生实际请求。
2.  **审计闭环**：所有对 `web.search` 和 `web.fetch` 的调用都必须在数据库 `tool_runs` 表中留下请求 URL 和响应长度的审计记录。
3.  **内容清洗**：传入一个包含大量广告的网页 URL，工具能够返回相对纯净的、大模型易读的正文内容。
4.  **端到端协同**：通过 CLI 触发 `agents run "调研一下最新的 FastAPI 版本更新了什么"`，系统能自主搜索并生成摘要，成功记录在 `AgentRun` 中，并（在开启的情况下）持久化到长期记忆中。

---

## 6. 后续延展 (Deferred for P6)

*   在网页读取遇到强力反爬虫（如 Cloudflare 5s 盾）或动态渲染（SPA）页面时，P5 的简单 HTTP 爬取将会失败。基于无头浏览器（Headless Browser / Playwright）的深度抓取将推迟到未来处理。
*   对本地代码的精准修改（AST 级别）及执行沙箱，属于 `CoderAgent` 的范畴，将在 P6 阶段专项攻克。