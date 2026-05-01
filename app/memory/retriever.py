import logging

from app.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """长期记忆检索入口；检索不可用时降级为空记忆。"""

    def search(self, user_id: str, project_id: str, query: str, top_k: int = 5) -> list[dict]:
        """执行范围内向量检索，失败时记录告警并允许聊天继续。"""
        try:
            return VectorStore().search(query=query, user_id=user_id, project_id=project_id, top_k=top_k)
        except Exception as exc:
            logger.warning("Vector search unavailable, fallback to empty memories: %s", exc)
            return []
