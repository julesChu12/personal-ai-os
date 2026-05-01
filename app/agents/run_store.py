from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AgentRun


def record_agent_run(
    db: Session,
    *,
    user_id: str,
    project_id: str,
    session_id: str | None,
    task: str,
    status: str,
    error: str | None,
    answer: str,
    plan_payload: dict[str, Any],
    steps: list[dict[str, Any]],
    agent_trace: list[dict[str, Any]],
    memory_saved: int,
    request_id: str | None,
) -> AgentRun:
    run = AgentRun(
        user_id=user_id,
        project_id=project_id,
        session_id=session_id,
        task=task,
        status=status,
        error=error,
        answer=answer,
        plan_payload=plan_payload,
        steps=steps,
        agent_trace=agent_trace,
        memory_saved=memory_saved,
        request_id=request_id,
    )
    db.add(run)
    db.commit()
    return run


def serialize_agent_run(run: AgentRun) -> dict[str, Any]:
    created_at = getattr(run, "created_at", None)
    return {
        "id": run.id,
        "user_id": run.user_id,
        "project_id": run.project_id,
        "session_id": run.session_id,
        "task": run.task,
        "status": run.status,
        "error": run.error,
        "answer": run.answer,
        "plan": run.plan_payload,
        "steps": run.steps or [],
        "agent_trace": run.agent_trace or [],
        "memory_saved": run.memory_saved,
        "request_id": run.request_id,
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
    }
