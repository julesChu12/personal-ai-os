# app.cli — 命令行客户端

导航：[仓库根](../../CLAUDE.md) › [app](../CLAUDE.md) › **cli**

## 职责

基于 Typer 的轻量 CLI，默认请求本机 `http://localhost:8000`（`main.py` 中常量 `API`），提供 `chat` 与 `memory-search` 等命令。

## 依赖

仅依赖已运行的 HTTP API，不直接导入大型应用逻辑。

## 测试

通常以 API 集成测试间接覆盖；若需 CLI 专项测试可后续补充。
