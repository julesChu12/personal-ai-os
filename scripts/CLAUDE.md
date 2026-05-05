# scripts — 运维与评估脚本

导航：[仓库根](../CLAUDE.md) › **scripts**

## 职责

仓库根目录下的可执行脚本（非包内模块）：迁移、运行时配置检查、嵌入检查、检索质量评估、`smoke_api.sh` 等。

| 脚本 | 用途 |
|------|------|
| `run_migrations.py` | 执行 DB 迁移 |
| `check_runtime_config.py` | 启动前配置检查（支持 `--strict`、`--json`） |
| `check_embedding_provider.py` | 嵌入提供方自检 |
| `evaluate_retrieval_quality.py` / `evaluate_qdrant_retrieval_quality.py` | 检索质量评估 |
| `smoke_api.sh` | API 冒烟 |

## 说明

这些脚本通过路径或环境变量访问项目；运行前确保 `.env` 与依赖服务可用。
