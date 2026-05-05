# app.memory — 记忆与 RAG

导航：[仓库根](../../CLAUDE.md) › [app](../CLAUDE.md) › **memory**

## 职责

长期记忆：向量检索（`retriever`、`vector_store`）、嵌入提供（`embedding_provider`）、Obsidian 写入（`obsidian_writer`）、记忆流水线（`memory_pipeline`）、身份与 schema（`memory_identity`、`memory_schema`）、检索质量（`retrieval_quality`）。

## 关键文件

| 文件 | 说明 |
|------|------|
| `retriever.py` | 对外检索入口（被 orchestrator 使用） |
| `vector_store.py` | Qdrant 交互 |
| `memory_pipeline.py` | 记忆处理管线 |
| `embedding_provider.py` | 嵌入后端（含 mock） |

## 测试

`tests/test_retriever.py`、`tests/test_vector_store.py`、`tests/test_memory_pipeline.py`、`tests/test_embedding_provider.py`、`tests/test_retrieval_quality.py`、`tests/test_obsidian_writer.py`。
