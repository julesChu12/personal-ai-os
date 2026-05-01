from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.workflow import AgentWorkflow
from app.core.request_context import REQUEST_ID_HEADER, get_request_id
from app.db.database import get_db
from app.tools.registry import ToolRegistry, build_default_tool_registry

router = APIRouter()


class AgentRunRequest(BaseModel):
    user_id: str
    project_id: str
    session_id: str
    task: str
    agents: list[str] = Field(default_factory=list)


def get_tool_registry() -> ToolRegistry:
    return build_default_tool_registry()


@router.get("/agents")
def agents():
    return {
        "agents": ["planner", "researcher", "coder", "executor", "memory_agent"],
        "note": "Planner / Executor workflow is available at POST /agents/run.",
    }


@router.post("/agents/run")
def run_agent_workflow(
    payload: AgentRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> dict[str, Any]:
    workflow = AgentWorkflow(registry=registry)
    return workflow.run(
        db=db,
        user_id=payload.user_id.strip(),
        project_id=payload.project_id.strip(),
        session_id=payload.session_id.strip(),
        task=payload.task,
        request_id=_request_id_from_request(request),
    )


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get(REQUEST_ID_HEADER) or get_request_id(None)
