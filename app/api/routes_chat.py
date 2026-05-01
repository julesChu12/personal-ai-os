from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.chat_persistence import persist_chat_exchange
from app.core.schemas import ChatRequest, ChatResponse, TaskRequest
from app.core.orchestrator import Orchestrator
from app.db.database import get_db

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    result = Orchestrator().chat(req.user_id, req.project_id, req.session_id, req.message)
    persist_chat_exchange(db, req.user_id, req.project_id, req.session_id, req.message, result["answer"])

    return ChatResponse(answer=result["answer"], session_id=req.session_id, memory_used=result["memory_used"], agent_trace=result["agent_trace"])


@router.post("/task")
def task(req: TaskRequest, db: Session = Depends(get_db)):
    return Orchestrator().task(req.user_id, req.project_id, req.session_id, req.task, req.agents)
