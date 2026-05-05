import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy.orm import Session

from app.agents.executor import AgentStepResult, ExecutorAgent
from app.agents.planner import AgentPlanValidationError, PlannerAgent, validate_agent_plan
from app.agents.run_store import record_agent_run
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
        planner_mode: str = "deterministic",
        execution_mode: str = "sequential",
        persist_agent_result: bool = False,
    ) -> dict[str, Any]:
        try:
            normalized_execution_mode = _normalize_execution_mode(execution_mode)
            if plan_payload is None:
                plan = self.planner.plan(task, mode=planner_mode, registry=self.registry)
                trace_action = "model_plan" if planner_mode.strip().lower() == "model" else "plan"
            else:
                plan = validate_agent_plan(plan_payload, self.registry)
                trace_action = "validate_plan"
        except (AgentPlanValidationError, ValueError) as exc:
            response = {
                "status": "error",
                "answer": "",
                "error": str(exc),
                "memory_saved": 0,
                "steps": [],
                "agent_trace": [{"agent": "planner", "action": "reject", "error": str(exc)}],
            }
            run = record_agent_run(
                db,
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                task=task,
                status=response["status"],
                error=response["error"],
                answer=response["answer"],
                plan_payload={},
                steps=response["steps"],
                agent_trace=response["agent_trace"],
                memory_saved=response["memory_saved"],
                request_id=request_id,
            )
            response["agent_run_id"] = run.id
            return response

        trace: list[dict[str, Any]] = [
            {"agent": "planner", "action": trace_action, "plan": plan.to_dict()},
        ]
        step_results: list[AgentStepResult] = []

        ordered_steps = _ordered_steps_for_execution(plan)
        if normalized_execution_mode == "parallel":
            _run_parallel_steps(
                ordered_steps,
                db=db,
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                request_id=request_id,
                executor=self.executor,
                registry=self.registry,
                step_results=step_results,
                trace=trace,
            )
        else:
            _run_sequential_steps(
                ordered_steps,
                db=db,
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                request_id=request_id,
                executor=self.executor,
                registry=self.registry,
                step_results=step_results,
                trace=trace,
            )

        failed = next((step for step in step_results if step.status == "error"), None)
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
        response = {
            "status": "error" if failed else "ok",
            "answer": answer,
            "error": failed.error if failed else None,
            "memory_saved": memory_saved,
            "steps": [step.to_dict() for step in step_results],
            "agent_trace": trace,
        }
        run = record_agent_run(
            db,
            user_id=user_id,
            project_id=project_id,
            session_id=session_id,
            task=task,
            status=response["status"],
            error=response["error"],
            answer=response["answer"],
            plan_payload=plan.to_dict(),
            steps=response["steps"],
            agent_trace=response["agent_trace"],
            memory_saved=response["memory_saved"],
            request_id=request_id,
        )
        response["agent_run_id"] = run.id
        return response


def _normalize_execution_mode(execution_mode: str) -> str:
    normalized = execution_mode.strip().lower()
    if normalized not in {"sequential", "parallel"}:
        raise ValueError("execution_mode must be one of: sequential, parallel")
    return normalized


def _ordered_steps_for_execution(plan: Any) -> list[Any]:
    by_id = {step.step_id: step for step in plan.steps}
    ordered: list[Any] = []
    visited: set[str] = set()

    def visit(step: Any) -> None:
        if step.step_id in visited:
            return
        for dependency in _effective_dependencies(step):
            visit(by_id[dependency])
        visited.add(step.step_id)
        ordered.append(step)

    for step in plan.steps:
        visit(step)
    return ordered


def _run_sequential_steps(
    steps: list[Any],
    *,
    db: Session,
    user_id: str,
    project_id: str,
    session_id: str | None,
    request_id: str | None,
    executor: ExecutorAgent,
    registry: ToolRegistry,
    step_results: list[AgentStepResult],
    trace: list[dict[str, Any]],
) -> None:
    results_by_id: dict[str, AgentStepResult] = {}
    for step in steps:
        if _skip_step_if_condition_misses(step, results_by_id, step_results, trace):
            continue
        step_result = _execute_and_record_step(
            step,
            db=db,
            user_id=user_id,
            project_id=project_id,
            session_id=session_id,
            request_id=request_id,
            executor=executor,
            registry=registry,
            trace=trace,
        )
        step_results.append(step_result)
        results_by_id[step.step_id] = step_result
        if step_result.status != "ok":
            break


def _run_parallel_steps(
    steps: list[Any],
    *,
    db: Session,
    user_id: str,
    project_id: str,
    session_id: str | None,
    request_id: str | None,
    executor: ExecutorAgent,
    registry: ToolRegistry,
    step_results: list[AgentStepResult],
    trace: list[dict[str, Any]],
) -> None:
    results_by_id: dict[str, AgentStepResult] = {}
    for batch in _parallel_batches(steps, registry):
        if len(batch) == 1:
            step = batch[0]
            if _skip_step_if_condition_misses(step, results_by_id, step_results, trace):
                continue
            step_result = _execute_and_record_step(
                step,
                db=db,
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                request_id=request_id,
                executor=executor,
                registry=registry,
                trace=trace,
            )
            step_results.append(step_result)
            results_by_id[step.step_id] = step_result
        else:
            raw_results = _execute_parallel_batch(executor, registry, batch)
            for step in batch:
                step_result = _record_step_result(
                    step,
                    raw_results[step.step_id],
                    db=db,
                    user_id=user_id,
                    project_id=project_id,
                    session_id=session_id,
                    request_id=request_id,
                    trace=trace,
                )
                step_results.append(step_result)
                results_by_id[step.step_id] = step_result

        if any(step.status == "error" for step in step_results):
            break


def _parallel_batches(steps: list[Any], registry: ToolRegistry) -> list[list[Any]]:
    batches: list[list[Any]] = []
    current: list[Any] = []
    for step in steps:
        if _effective_dependencies(step) or not registry.is_parallel_safe(step.tool_name):
            if current:
                batches.append(current)
                current = []
            batches.append([step])
            continue
        current.append(step)
    if current:
        batches.append(current)
    return batches


def _execute_parallel_batch(
    executor: ExecutorAgent,
    registry: ToolRegistry,
    batch: list[Any],
) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [(step, pool.submit(executor.execute, step, registry)) for step in batch]
        return {step.step_id: future.result() for step, future in futures}


def _skip_step_if_condition_misses(
    step: Any,
    results_by_id: dict[str, AgentStepResult],
    step_results: list[AgentStepResult],
    trace: list[dict[str, Any]],
) -> bool:
    if _condition_matches(step, results_by_id):
        return False
    skipped = AgentStepResult(
        step_id=step.step_id,
        tool_name=step.tool_name,
        input=step.input,
        status="skipped",
    )
    step_results.append(skipped)
    results_by_id[step.step_id] = skipped
    trace.append(
        {
            "agent": "executor",
            "action": "skip_tool",
            "tool_name": step.tool_name,
            "step_id": step.step_id,
        }
    )
    return True


def _execute_and_record_step(
    step: Any,
    *,
    db: Session,
    user_id: str,
    project_id: str,
    session_id: str | None,
    request_id: str | None,
    executor: ExecutorAgent,
    registry: ToolRegistry,
    trace: list[dict[str, Any]],
) -> AgentStepResult:
    result = executor.execute(step, registry)
    return _record_step_result(
        step,
        result,
        db=db,
        user_id=user_id,
        project_id=project_id,
        session_id=session_id,
        request_id=request_id,
        trace=trace,
    )


def _record_step_result(
    step: Any,
    result: Any,
    *,
    db: Session,
    user_id: str,
    project_id: str,
    session_id: str | None,
    request_id: str | None,
    trace: list[dict[str, Any]],
) -> AgentStepResult:
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
        step_id=step.step_id,
        tool_name=step.tool_name,
        input=step.input,
        status=result.status,
        output=result.output,
        error=result.error,
        run_id=run.id,
    )
    trace.append(
        {
            "agent": "executor",
            "action": "execute_tool",
            "tool_name": step.tool_name,
            "step_id": step.step_id,
            "status": result.status,
            "run_id": run.id,
        }
    )
    return step_result


def _effective_dependencies(step: Any) -> list[str]:
    dependencies = list(step.depends_on or [])
    if step.condition is not None:
        condition_step_id = step.condition["step_id"]
        if condition_step_id not in dependencies:
            dependencies.append(condition_step_id)
    return dependencies


def _condition_matches(step: Any, results_by_id: dict[str, AgentStepResult]) -> bool:
    if not step.condition:
        return True

    condition = step.condition
    source = results_by_id.get(condition["step_id"])
    if source is None:
        return False
    if "status" in condition and source.status != condition["status"]:
        return False
    if "output_contains" in condition and condition["output_contains"] not in str(source.output or ""):
        return False
    return True


def _build_answer(step_results: list[AgentStepResult]) -> str:
    outputs = [str(step.output) for step in step_results if step.status == "ok" and step.output is not None]
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
