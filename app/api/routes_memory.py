from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.schemas import MemoryIngestRequest
from app.db.database import get_db
from app.memory.memory_schema import MemoryCandidate
from app.memory.memory_pipeline import MemoryPipeline
from app.memory.retriever import Retriever

router = APIRouter()


@router.post("/memory/ingest")
def ingest(req: MemoryIngestRequest, db: Session = Depends(get_db)):
    """手动写入一条长期记忆。"""
    candidate = MemoryCandidate(
        memory_type=req.memory_type,
        title=req.title or "手动记忆",
        content=req.content,
        tags=req.tags,
        importance=req.importance,
    )
    saved = MemoryPipeline().persist(db, req.user_id, req.project_id, req.session_id, [candidate])
    return {"saved": len(saved)}


@router.get("/memory/search")
def search(user_id: str, project_id: str, query: str, top_k: int = 5):
    """按用户和项目范围检索长期记忆。"""
    return {"results": Retriever().search(user_id, project_id, query, top_k)}
