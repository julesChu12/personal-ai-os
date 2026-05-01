from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.request_validation import normalize_optional_string, require_non_blank
from app.core.request_context import REQUEST_ID_HEADER, get_request_id
from app.db.database import get_db
from app.db.models import ToolRun
from app.tools.audit import record_tool_run
from app.tools.registry import ToolNotFoundError, ToolRegistry, build_default_tool_registry


router = APIRouter(prefix="/tools", tags=["tools"])


class ToolInvokeRequest(BaseModel):
    user_id: str
    project_id: str
    session_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)


def get_tool_registry() -> ToolRegistry:
    return build_default_tool_registry()


@router.get("")
def list_tools(registry: ToolRegistry = Depends(get_tool_registry)) -> dict[str, Any]:
    return {"tools": [tool.to_dict() for tool in registry.list_tools()]}


@router.get("/runs")
def list_tool_runs(
    user_id: str = Query(...),
    project_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user_id = require_non_blank("user_id", user_id)
    project_id = require_non_blank("project_id", project_id)
    runs = (
        db.query(ToolRun)
        .filter_by(user_id=user_id, project_id=project_id)
        .order_by(ToolRun.id.desc())
        .limit(limit)
        .all()
    )
    return {"runs": [_serialize_run(run) for run in runs]}


@router.post("/{tool_name}/invoke")
def invoke_tool(
    tool_name: str,
    payload: ToolInvokeRequest,
    request: Request,
    db: Session = Depends(get_db),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> dict[str, Any]:
    user_id = require_non_blank("user_id", payload.user_id)
    project_id = require_non_blank("project_id", payload.project_id)
    session_id = normalize_optional_string(payload.session_id)

    try:
        result = registry.invoke(tool_name, payload.input)
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"tool not found: {tool_name}") from exc

    run = record_tool_run(
        db,
        user_id=user_id,
        project_id=project_id,
        session_id=session_id,
        result=result,
        input_payload=payload.input,
        request_id=_request_id_from_request(request),
    )

    return {**result.to_dict(), "run_id": run.id}


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get(REQUEST_ID_HEADER) or get_request_id(None)


def _serialize_run(run: ToolRun) -> dict[str, Any]:
    created_at = getattr(run, "created_at", None)
    return {
        "id": run.id,
        "user_id": run.user_id,
        "project_id": run.project_id,
        "session_id": run.session_id,
        "tool_name": run.tool_name,
        "status": run.status,
        "input": run.input_payload,
        "output": run.output,
        "error": run.error,
        "request_id": run.request_id,
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
    }
