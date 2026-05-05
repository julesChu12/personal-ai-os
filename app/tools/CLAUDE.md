# app.tools — 工具注册与实现

导航：[仓库根](../../CLAUDE.md) › [app](../CLAUDE.md) › **tools**

## 职责

可调用工具的注册表（`registry.py`）、审计（`audit.py`），以及 shell、文件、git 等具体工具模块。

## 关键文件

- `registry.py`：工具发现与调用约定。
- `shell_tool.py` / `file_tool.py` / `git_tool.py`：具体能力（注意安全边界）。

## 测试

`tests/test_tool_registry.py`、`tests/test_tools_route.py`。
