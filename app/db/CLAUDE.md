# app.db — 数据库与迁移

导航：[仓库根](../../CLAUDE.md) › [app](../CLAUDE.md) › **db**

## 职责

SQLAlchemy 引擎/会话（`database.py`）、ORM 模型（`models.py`）、版本化迁移（`migrations/`）。

## 关键路径

- `migrations/runner.py`：迁移执行逻辑。
- `migrations/versions/v0001_initial_schema.py` 等：递增 schema。
- 启动时仍可能与 `create_all` 兼容路径并存；生产建议使用 `scripts/run_migrations.py`。

## 测试

`tests/test_db_migrations.py`。
