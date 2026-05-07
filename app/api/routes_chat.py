from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.api.request_validation import normalize_optional_string, require_non_blank
from app.agents.planner import PlannerAgent
from app.agents.workflow import AgentWorkflow
from app.core.chat_persistence import persist_chat_exchange
from app.core.request_context import REQUEST_ID_HEADER, get_request_id
from app.core.schemas import ChatRequest, ChatResponse, TaskRequest
from app.core.orchestrator import Orchestrator
from app.db.database import get_db
from app.memory.memory_pipeline import MemoryPipeline
from app.tools.registry import ToolRegistry, build_default_tool_registry

router = APIRouter()


def get_task_tool_registry() -> ToolRegistry:
    return build_default_tool_registry()


def get_task_planner_agent() -> PlannerAgent:
    return PlannerAgent()


def get_task_memory_pipeline() -> MemoryPipeline:
    return MemoryPipeline()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    result = Orchestrator().chat(req.user_id, req.project_id, req.session_id, req.message)
    persist_chat_exchange(db, req.user_id, req.project_id, req.session_id, req.message, result["answer"])

    return ChatResponse(answer=result["answer"], session_id=req.session_id, memory_used=result["memory_used"], agent_trace=result["agent_trace"])


@router.post("/task")
def task(
    req: TaskRequest,
    request: Request,
    db: Session = Depends(get_db),
    planner: PlannerAgent = Depends(get_task_planner_agent),
    registry: ToolRegistry = Depends(get_task_tool_registry),
    memory_pipeline: MemoryPipeline = Depends(get_task_memory_pipeline),
):
    workflow = AgentWorkflow(planner=planner, registry=registry, memory_pipeline=memory_pipeline)
    return workflow.run(
        db=db,
        user_id=require_non_blank("user_id", req.user_id),
        project_id=require_non_blank("project_id", req.project_id),
        session_id=normalize_optional_string(req.session_id),
        task=require_non_blank("task", req.task),
        request_id=_request_id_from_request(request),
        plan_payload=req.plan.model_dump(exclude_unset=True, by_alias=True) if req.plan else None,
        planner_mode=req.planner_mode,
        execution_mode=req.execution_mode,
        persist_agent_result=_should_persist_task_result(req.agents),
    )


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get(REQUEST_ID_HEADER) or get_request_id(None)


def _should_persist_task_result(agents: list[str]) -> bool:
    return "memory_agent" in {agent.strip().lower() for agent in agents}
