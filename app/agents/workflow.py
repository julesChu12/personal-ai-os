import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.executor import AgentStepResult, ExecutorAgent
from app.agents.planner import AgentPlanValidationError, PlannerAgent, validate_agent_plan
from app.memory.memory_pipeline import MemoryPipeline
from app.memory.memory_schema import MemoryCandidate
from app.tools.audit import record_tool_run
from app.tools.registry import ToolRegistry, build_default_tool_registry

logger = logging.getLogger(__name__)


class AgentWorkflow:
    """最小 Planner / Executor 工作流，所有外部动作必须经过 ToolRegistry。"""

    def __init__(
        self,
        *,
        planner: PlannerAgent | None = None,
        executor: ExecutorAgent | None = None,
        registry: ToolRegistry | None = None,
        memory_pipeline: MemoryPipeline | None = None,
    ) -> None:
        self.planner = planner or PlannerAgent()
        self.executor = executor or ExecutorAgent()
        self.registry = registry or build_default_tool_registry()
        self.memory_pipeline = memory_pipeline

    def run(
        self,
        *,
        db: Session,
        user_id: str,
        project_id: str,
        session_id: str | None,
        task: str,
        request_id: str | None = None,
        plan_payload: dict[str, Any] | None = None,
        persist_agent_result: bool = False,
    ) -> dict[str, Any]:
        try:
            if plan_payload is None:
                plan = self.planner.plan(task)
                trace_action = "plan"
            else:
                plan = validate_agent_plan(plan_payload, self.registry)
                trace_action = "validate_plan"
        except (AgentPlanValidationError, ValueError) as exc:
            return {
                "status": "error",
                "answer": "",
                "error": str(exc),
                "memory_saved": 0,
                "steps": [],
                "agent_trace": [{"agent": "planner", "action": "reject", "error": str(exc)}],
            }

        trace: list[dict[str, Any]] = [
            {"agent": "planner", "action": trace_action, "plan": plan.to_dict()},
        ]
        step_results: list[AgentStepResult] = []

        for step in plan.steps:
            result = self.executor.execute(step, self.registry)
            run = record_tool_run(
                db,
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                result=result,
                input_payload=step.input,
                request_id=request_id,
            )
            step_result = AgentStepResult(
                tool_name=step.tool_name,
                input=step.input,
                status=result.status,
                output=result.output,
                error=result.error,
                run_id=run.id,
            )
            step_results.append(step_result)
            trace.append(
                {
                    "agent": "executor",
                    "action": "execute_tool",
                    "tool_name": step.tool_name,
                    "status": result.status,
                    "run_id": run.id,
                }
            )
            if result.status != "ok":
                break

        failed = next((step for step in step_results if step.status != "ok"), None)
        answer = _build_answer(step_results)
        memory_saved = _persist_agent_result(
            self.memory_pipeline,
            db=db,
            user_id=user_id,
            project_id=project_id,
            session_id=session_id,
            task=task,
            answer=answer,
            should_persist=persist_agent_result and failed is None,
        )
        return {
            "status": "error" if failed else "ok",
            "answer": answer,
            "error": failed.error if failed else None,
            "memory_saved": memory_saved,
            "steps": [step.to_dict() for step in step_results],
            "agent_trace": trace,
        }


def _build_answer(step_results: list[AgentStepResult]) -> str:
    outputs = [str(step.output) for step in step_results if step.output is not None]
    if outputs:
        return "\n".join(outputs)
    errors = [str(step.error) for step in step_results if step.error]
    return "\n".join(errors)


def _persist_agent_result(
    memory_pipeline: MemoryPipeline | None,
    *,
    db: Session,
    user_id: str,
    project_id: str,
    session_id: str | None,
    task: str,
    answer: str,
    should_persist: bool,
) -> int:
    if not should_persist or not session_id or not answer.strip():
        return 0

    pipeline = memory_pipeline or MemoryPipeline()
    candidate = _build_agent_result_memory(task, answer)
    try:
        saved = pipeline.persist(db, user_id, project_id, session_id, [candidate])
    except Exception as exc:
        logger.error(
            "Agent result memory persistence failed user_id=%s project_id=%s session_id=%s: %s",
            user_id,
            project_id,
            session_id,
            exc,
        )
        return 0
    return len(saved)


def _build_agent_result_memory(task: str, answer: str) -> MemoryCandidate:
    normalized_task = " ".join(task.strip().split()) or "agent task"
    title_task = normalized_task[:80].rstrip()
    return MemoryCandidate(
        memory_type="agent_result",
        title=f"Agent result: {title_task}",
        content=f"Task: {normalized_task}\n\nResult:\n{answer.strip()}",
        tags=["personal-ai-os", "agent"],
        importance=6,
    )
