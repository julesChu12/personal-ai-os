import logging
from collections.abc import Callable

from sqlalchemy.orm import Session
from app.core.model_router import ModelRouter
from app.db.models import Memory
from app.memory.memory_identity import build_memory_identity
from app.memory.memory_schema import MemoryCandidate
from app.memory.obsidian_writer import ObsidianWriter
from app.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


class MemoryPipeline:
    """从对话中提取长期记忆，并写入 Obsidian、Qdrant 和数据库。"""

    def __init__(self, vector_store_factory: Callable[[], VectorStore] | None = None) -> None:
        self.router = ModelRouter()
        self.obsidian = ObsidianWriter()
        self.vector_store_factory = vector_store_factory or VectorStore

    def extract_candidates(self, messages: list[dict]) -> list[MemoryCandidate]:
        """调用模型把一组聊天消息压缩成可持久化的记忆候选。"""
        joined = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        prompt = [
            {"role": "system", "content": "你是个人知识库记忆提取器。请从对话中提取值得长期保存的信息。"},
            {"role": "user", "content": joined},
        ]
        summary = self.router.chat(prompt)
        return [
            MemoryCandidate(
                memory_type="learning",
                title="会话沉淀",
                content=summary,
                tags=["personal-ai-os", "memory"],
                importance=6,
            )
        ]

    def persist(self, db: Session, user_id: str, project_id: str, session_id: str, candidates: list[MemoryCandidate]) -> list[Memory]:
        """持久化记忆；同身份记忆更新，向量写入失败时保留数据库和 Obsidian 记录。"""
        vector_store = self.vector_store_factory()
        saved = []
        has_changes = False

        for c in candidates:
            identity = build_memory_identity(user_id, project_id, c)
            normalized = _normalize_candidate(c, identity)
            existing = db.query(Memory).filter_by(**identity).first()
            if existing is not None:
                if existing.content == normalized.content:
                    logger.info(
                        "Duplicate memory skipped user_id=%s project_id=%s session_id=%s title=%s",
                        user_id,
                        project_id,
                        session_id,
                        normalized.title,
                    )
                    saved.append(existing)
                    continue

                obsidian_path = normalized.obsidian_path or self.obsidian.write_memory(user_id, project_id, session_id, normalized)
                payload = _build_vector_payload(user_id, project_id, session_id, normalized, obsidian_path)
                try:
                    point_id = vector_store.upsert_memory(
                        normalized.content,
                        payload,
                        point_id=getattr(existing, "qdrant_point_id", None),
                    )
                except Exception as exc:
                    logger.error(
                        "Vector persistence failed for memory user_id=%s project_id=%s session_id=%s title=%s: %s",
                        user_id,
                        project_id,
                        session_id,
                        normalized.title,
                        exc,
                    )
                    saved.append(existing)
                    continue

                existing.session_id = session_id
                existing.memory_type = normalized.memory_type
                existing.title = normalized.title
                existing.content = normalized.content
                existing.tags = normalized.tags
                existing.importance = normalized.importance
                existing.obsidian_path = obsidian_path
                existing.qdrant_point_id = point_id
                saved.append(existing)
                has_changes = True
                continue

            obsidian_path = normalized.obsidian_path or self.obsidian.write_memory(user_id, project_id, session_id, normalized)
            payload = _build_vector_payload(user_id, project_id, session_id, normalized, obsidian_path)
            point_id = None
            try:
                point_id = vector_store.upsert_memory(normalized.content, payload)
            except Exception as exc:
                logger.error(
                    "Vector persistence failed for memory user_id=%s project_id=%s session_id=%s title=%s: %s",
                    user_id,
                    project_id,
                    session_id,
                    normalized.title,
                    exc,
                )
            row = Memory(
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                memory_type=normalized.memory_type,
                title=normalized.title,
                content=normalized.content,
                tags=normalized.tags,
                importance=normalized.importance,
                obsidian_path=obsidian_path,
                qdrant_point_id=point_id,
            )
            db.add(row)
            saved.append(row)
            has_changes = True

        if has_changes:
            db.commit()
        return saved


def _normalize_candidate(candidate: MemoryCandidate, identity: dict[str, str]) -> MemoryCandidate:
    return MemoryCandidate(
        memory_type=identity["memory_type"],
        title=identity["title"],
        content=candidate.content,
        tags=candidate.tags,
        importance=candidate.importance,
        obsidian_path=getattr(candidate, "obsidian_path", None),
    )


def _build_vector_payload(
    user_id: str,
    project_id: str,
    session_id: str,
    candidate: MemoryCandidate,
    obsidian_path: str,
) -> dict:
    governance = _build_governance_metadata(candidate, obsidian_path)
    return {
        "user_id": user_id,
        "project_id": project_id,
        "session_id": session_id,
        "memory_type": candidate.memory_type,
        "title": candidate.title,
        "tags": candidate.tags,
        "obsidian_path": obsidian_path,
        **governance,
    }


def _build_governance_metadata(candidate: MemoryCandidate, obsidian_path: str | None) -> dict:
    source = "chat"
    if candidate.memory_type == "agent_result":
        source = "agent"
    elif candidate.memory_type.startswith("obsidian") or candidate.obsidian_path:
        source = "obsidian"

    importance = max(0, min(10, int(candidate.importance or 0)))
    return {
        "source": source,
        "governance_version": "memory-governance-v1",
        "quality_score": round(importance / 10, 2),
    }
