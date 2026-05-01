from sqlalchemy.orm import Session

from app.db.models import Message
from app.memory.memory_pipeline import MemoryPipeline


def persist_chat_exchange(
    db: Session,
    user_id: str,
    project_id: str,
    session_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """统一保存一次聊天交换，并从同一份内容派生长期记忆。

    `/chat` 和 `/v1/chat/completions` 都应走这里，避免两个入口在消息
    落库、记忆提取和会话归属上出现行为漂移。
    """
    db.add(Message(user_id=user_id, project_id=project_id, session_id=session_id, role="user", content=user_message))
    db.commit()

    db.add(Message(user_id=user_id, project_id=project_id, session_id=session_id, role="assistant", content=assistant_message))
    db.commit()

    pipeline = MemoryPipeline()
    candidates = pipeline.extract_candidates(
        [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ]
    )
    pipeline.persist(db, user_id, project_id, session_id, candidates)
