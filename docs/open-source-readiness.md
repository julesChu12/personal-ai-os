# Open Source Readiness

## 已完成

- License: 项目已声明 Apache-2.0，并提供根目录 `LICENSE` 文件。
- CI: 快速回归入口统一为 `make ci`，GitHub Actions 会运行同一入口。
- Docker smoke: CI 和本地都可通过 `bash scripts/smoke_api.sh` 检查运行中 API，并可用 `SMOKE_RUN_CHAT=1` 验证聊天写入和记忆召回闭环。
- Secrets: 运行密钥通过环境变量配置，`.env` 被 `.gitignore` 排除。
- Runtime data: 本地数据库、向量库、Obsidian 数据和缓存目录被 `.gitignore` 排除。
- Embedding validation: `scripts/check_embedding_provider.py` 可验证当前 embedding provider 和向量维度配置。

## 未决

- Repository URLs: 确认正式 GitHub 仓库地址后，再补 `pyproject.toml` 的 `[project.urls]`。
- Security policy: 开源发布前决定是否新增 `SECURITY.md`。
- Code of conduct: 开源发布前决定是否新增 `CODE_OF_CONDUCT.md`。
- Obsidian sync: 当前支持写入 Obsidian，文件监听、增量同步和冲突处理仍需独立 spec。

## 发布前检查

- Run `make ci PYTHON=python`.
- Run `docker compose up -d --build`.
- Run `bash scripts/smoke_api.sh`.
- Confirm `.env` is not tracked.
- Confirm README startup steps work on a clean machine.
