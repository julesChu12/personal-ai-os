from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Callable, Optional


def _candidate_payload(candidate: Any) -> dict[str, Any]:
    """把 Pydantic 或测试替身对象统一转换成可复制的候选记忆 payload。"""
    if hasattr(candidate, "model_dump"):
        return candidate.model_dump()
    if hasattr(candidate, "dict"):
        return candidate.dict()
    return {
        "memory_type": getattr(candidate, "memory_type", "learning"),
        "title": getattr(candidate, "title", "会话沉淀"),
        "content": getattr(candidate, "content", ""),
        "tags": list(getattr(candidate, "tags", []) or []),
        "importance": getattr(candidate, "importance", 5),
    }


def _copy_candidate(candidate: Any, **updates: Any) -> Any:
    """复制候选记忆，并兼容 Pydantic v1/v2 与轻量测试替身。"""
    if hasattr(candidate, "model_copy"):
        return candidate.model_copy(update=updates)
    if hasattr(candidate, "copy"):
        return candidate.copy(update=updates)

    payload = _candidate_payload(candidate)
    payload.update(updates)

    try:
        return candidate.__class__(**payload)
    except TypeError:
        return SimpleNamespace(**payload)


def daily_memory_job(
    db_factory: Optional[Callable[[], Any]] = None,
    pipeline: Optional[Any] = None,
    lookback_hours: int = 24,
) -> dict[str, int]:
    """汇总最近有消息的会话，避免重复生成同一会话摘要。"""
    from app.db.database import SessionLocal
    from app.db.models import Memory, Message
    from app.memory.memory_pipeline import MemoryPipeline

    db_factory = db_factory or SessionLocal
    pipeline = pipeline or MemoryPipeline()

    db = db_factory()
    cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
    stats = {
        "sessions_considered": 0,
        "sessions_summarized": 0,
        "sessions_skipped": 0,
        "memories_saved": 0,
    }

    try:
        recent_sessions = (
            db.query(Message.user_id, Message.project_id, Message.session_id)
            .filter(Message.created_at >= cutoff)
            .distinct()
            .all()
        )

        for user_id, project_id, session_id in recent_sessions:
            stats["sessions_considered"] += 1

            existing_summary = (
                db.query(Memory)
                .filter_by(
                    user_id=user_id,
                    project_id=project_id,
                    session_id=session_id,
                    memory_type="session_summary",
                )
                .first()
            )
            if existing_summary:
                stats["sessions_skipped"] += 1
                continue

            rows = (
                db.query(Message)
                .filter_by(user_id=user_id, project_id=project_id, session_id=session_id)
                .order_by(Message.created_at.asc())
                .all()
            )
            if not rows:
                stats["sessions_skipped"] += 1
                continue

            messages = [{"role": row.role, "content": row.content} for row in rows]
            candidates = pipeline.extract_candidates(messages)
            summary_candidates = []

            for candidate in candidates:
                tags = list(dict.fromkeys([*(getattr(candidate, "tags", []) or []), "scheduler", "session-summary"]))
                summary_candidates.append(
                    _copy_candidate(
                        candidate,
                        memory_type="session_summary",
                        title=f"定时汇总 {session_id}",
                        tags=tags,
                    )
                )

            saved = pipeline.persist(db, user_id, project_id, session_id, summary_candidates)
            stats["sessions_summarized"] += 1
            stats["memories_saved"] += len(saved)

        return stats
    finally:
        db.close()
