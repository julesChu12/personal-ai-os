# tests — 自动化测试

导航：[仓库根](../CLAUDE.md) › **tests**

## 职责

`pytest` 测试套件：路由契约、编排与 Agent、DB 迁移、内存与向量、工具、调度、OpenAI 兼容层、打包契约等。

## 配置

见根目录 `pyproject.toml` 中 `[tool.pytest.ini_options]`：`testpaths = ["tests"]`，标记 `integration` 用于依赖 Docker 的测试。

## 命名约定

`test_<area>_<aspect>.py`，与 `app/` 下模块大致对应。

## 运行

```bash
pytest
pytest -m "not integration"
```
