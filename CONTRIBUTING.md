# Contributing

感谢你考虑参与 Personal AI OS。这个项目优先保持本地可运行、行为可回归、接口边界清晰。

## 开发环境

推荐使用 Python 3.11：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

本地运行完整回归：

```bash
make ci PYTHON=python
```

如果不使用 `make`，等价命令是：

```bash
DATABASE_URL="sqlite:///:memory:" python -m compileall -q app tests
DATABASE_URL="sqlite:///:memory:" python -m pytest -q
```

## 变更原则

- 先补回归测试，再改生产代码。
- 保持 `/chat` 与 `/v1/chat/completions` 的会话、消息、记忆持久化规则一致。
- 检索失败可以降级为空记忆，但必须保留可诊断日志。
- 不放宽 `user_id` 和 `project_id` 的记忆检索隔离。
- 不引入未使用的抽象、依赖或配置项。

## 配置与密钥

- 不提交 `.env`、本地 vault、数据库或向量库运行数据。
- `OPENAI_COMPAT_API_KEY`、模型密钥和 embedding 密钥必须通过环境变量配置。
- 项目使用 Apache-2.0 许可证，贡献代码默认按同一许可证授权。
- 安全问题请优先按 `SECURITY.md` 私下报告，不要在公开 issue 中粘贴密钥、私有日志或漏洞利用细节。
