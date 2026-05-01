import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ToolRun
from app.tools.registry import ToolInvocationResult


def record_tool_run(
    db: Session,
    *,
    user_id: str,
    project_id: str,
    session_id: str | None,
    result: ToolInvocationResult,
    input_payload: dict[str, Any],
    request_id: str | None = None,
) -> ToolRun:
    """记录一次工具调用，供 Agent 和 HTTP adapter 共享审计逻辑。"""
    run = ToolRun(
        user_id=user_id,
        project_id=project_id,
        session_id=session_id,
        tool_name=result.tool_name,
        status=result.status,
        input_payload=input_payload,
        output=serialize_tool_output(result.output),
        error=result.error,
        request_id=request_id,
    )
    db.add(run)
    db.commit()
    return run


def serialize_tool_output(output: Any) -> str | None:
    if output is None:
        return None
    if isinstance(output, str):
        return output
    return json.dumps(output, ensure_ascii=False, default=str)
