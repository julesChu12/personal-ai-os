from typing import Any

from sqlalchemy.orm import Session

from app.agents.executor import AgentStepResult, ExecutorAgent
from app.agents.planner import PlannerAgent
from app.tools.audit import record_tool_run
from app.tools.registry import ToolRegistry, build_default_tool_registry


class AgentWorkflow:
    """最小 Planner / Executor 工作流，所有外部动作必须经过 ToolRegistry。"""

    def __init__(
        self,
        *,
        planner: PlannerAgent | None = None,
        executor: ExecutorAgent | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.planner = planner or PlannerAgent()
        self.executor = executor or ExecutorAgent()
        self.registry = registry or build_default_tool_registry()

    def run(
        self,
        *,
        db: Session,
        user_id: str,
        project_id: str,
        session_id: str,
        task: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            plan = self.planner.plan(task)
        except ValueError as exc:
            return {
                "status": "error",
                "answer": "",
                "error": str(exc),
                "steps": [],
                "agent_trace": [{"agent": "planner", "action": "reject", "error": str(exc)}],
            }

        trace: list[dict[str, Any]] = [
            {"agent": "planner", "action": "plan", "plan": plan.to_dict()},
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

        failed = next((step for step in step_results if step.status != "ok"), None)
        answer = _build_answer(step_results)
        return {
            "status": "error" if failed else "ok",
            "answer": answer,
            "error": failed.error if failed else None,
            "steps": [step.to_dict() for step in step_results],
            "agent_trace": trace,
        }


def _build_answer(step_results: list[AgentStepResult]) -> str:
    outputs = [str(step.output) for step in step_results if step.output is not None]
    if outputs:
        return "\n".join(outputs)
    errors = [str(step.error) for step in step_results if step.error]
    return "\n".join(errors)
