from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.request_validation import normalize_optional_string, require_non_blank
from app.agents.planner import PlannerAgent
from app.agents.workflow import AgentWorkflow
from app.agents.run_store import serialize_agent_run
from app.config import settings
from app.core.auth import ApiPrincipal, authenticate_bearer, enforce_principal_scope
from app.core.request_context import REQUEST_ID_HEADER, get_request_id
from app.db.database import get_db
from app.db.models import AgentRun
from app.memory.memory_pipeline import MemoryPipeline
from app.tools.registry import ToolRegistry, build_default_tool_registry

router = APIRouter()


class AgentRunRequest(BaseModel):
    user_id: str
    project_id: str
    session_id: str
    task: str
    agents: list[str] = Field(default_factory=list)
    planner_mode: str = "deterministic"
    execution_mode: str = "sequential"
    plan: dict[str, Any] | None = None


def get_tool_registry() -> ToolRegistry:
    return build_default_tool_registry()


def get_planner_agent() -> PlannerAgent:
    return PlannerAgent()


def get_memory_pipeline() -> MemoryPipeline:
    return MemoryPipeline()


def get_auth_settings():
    return settings


def require_agents_principal(
    authorization: str | None = Header(default=None),
    settings_obj=Depends(get_auth_settings),
) -> ApiPrincipal:
    return authenticate_bearer(authorization, settings_obj, required_permission="agents")


@router.get("/agents")
def agents():
    return {
        "agents": ["planner", "researcher", "coder", "executor", "memory_agent"],
        "note": "Planner / Executor workflow is available at POST /agents/run.",
    }


@router.get("/agents/runs")
def list_agent_runs(
    user_id: str = Query(...),
    project_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: ApiPrincipal = Depends(require_agents_principal),
) -> dict[str, Any]:
    user_id = require_non_blank("user_id", user_id)
    project_id = require_non_blank("project_id", project_id)
    enforce_principal_scope(principal, user_id=user_id, project_id=project_id)
    runs = (
        db.query(AgentRun)
        .filter_by(user_id=user_id, project_id=project_id)
        .order_by(AgentRun.id.desc())
        .limit(limit)
        .all()
    )
    return {"runs": [serialize_agent_run(run) for run in runs]}


@router.post("/agents/run")
def run_agent_workflow(
    payload: AgentRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    planner: PlannerAgent = Depends(get_planner_agent),
    registry: ToolRegistry = Depends(get_tool_registry),
    memory_pipeline: MemoryPipeline = Depends(get_memory_pipeline),
    principal: ApiPrincipal = Depends(require_agents_principal),
) -> dict[str, Any]:
    user_id = require_non_blank("user_id", payload.user_id)
    project_id = require_non_blank("project_id", payload.project_id)
    enforce_principal_scope(principal, user_id=user_id, project_id=project_id)
    workflow = AgentWorkflow(planner=planner, registry=registry, memory_pipeline=memory_pipeline)
    return workflow.run(
        db=db,
        user_id=user_id,
        project_id=project_id,
        session_id=normalize_optional_string(payload.session_id),
        task=payload.task,
        request_id=_request_id_from_request(request),
        plan_payload=payload.plan,
        planner_mode=payload.planner_mode,
        execution_mode=payload.execution_mode,
        persist_agent_result=_should_persist_agent_result(payload.agents),
    )


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get(REQUEST_ID_HEADER) or get_request_id(None)


def _should_persist_agent_result(agents: list[str]) -> bool:
    return "memory_agent" in {agent.strip().lower() for agent in agents}
