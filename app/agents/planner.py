import json
from dataclasses import dataclass
from typing import Any

from app.core.provider_errors import ProviderError
from app.tools.registry import ToolNotFoundError, ToolRegistry

MAX_AGENT_PLAN_STEPS = 10
PLANNER_MODE_DETERMINISTIC = "deterministic"
PLANNER_MODE_MODEL = "model"


class AgentPlanValidationError(ValueError):
    """结构化 Agent plan 不符合工具 schema 时抛出。"""


@dataclass(frozen=True)
class AgentStep:
    tool_name: str
    input: dict[str, Any]
    reason: str
    step_id: str = "step-1"
    depends_on: list[str] | None = None
    condition: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.step_id,
            "tool_name": self.tool_name,
            "input": self.input,
            "reason": self.reason,
            "depends_on": self.depends_on or [],
        }
        if self.condition is not None:
            payload["condition"] = self.condition
        return payload


@dataclass(frozen=True)
class AgentPlan:
    steps: list[AgentStep]

    def to_dict(self) -> dict[str, Any]:
        return {"steps": [step.to_dict() for step in self.steps]}


def validate_agent_plan(raw_plan: dict[str, Any], registry: ToolRegistry) -> AgentPlan:
    """校验外部结构化 plan，确保步骤只调用已注册工具。"""
    steps_payload = raw_plan.get("steps") if isinstance(raw_plan, dict) else None
    if not isinstance(steps_payload, list) or not steps_payload:
        raise AgentPlanValidationError("steps must be a non-empty list")
    if len(steps_payload) > MAX_AGENT_PLAN_STEPS:
        raise AgentPlanValidationError(f"steps must contain at most {MAX_AGENT_PLAN_STEPS} steps")

    steps: list[AgentStep] = []
    for index, raw_step in enumerate(steps_payload):
        if not isinstance(raw_step, dict):
            raise AgentPlanValidationError(f"steps[{index}] must be an object")

        step_id = _optional_step_id(raw_step, index)
        depends_on = _optional_depends_on(raw_step, index)
        condition = _optional_condition(raw_step, index)
        tool_name = _required_step_string(raw_step, "tool_name", index)
        reason = _required_step_string(raw_step, "reason", index)
        input_payload = raw_step.get("input", {})
        if not isinstance(input_payload, dict):
            raise AgentPlanValidationError(f"steps[{index}].input must be an object")

        try:
            definition = registry.get_definition(tool_name)
        except ToolNotFoundError as exc:
            raise AgentPlanValidationError(f"steps[{index}].tool_name tool is not registered") from exc

        _validate_tool_input(index, definition.input_schema, input_payload)
        steps.append(
            AgentStep(
                step_id=step_id,
                depends_on=depends_on,
                condition=condition,
                tool_name=tool_name,
                input=input_payload,
                reason=reason,
            )
        )

    _validate_step_graph(steps)
    return AgentPlan(steps=steps)


def _required_step_string(raw_step: dict[str, Any], key: str, index: int) -> str:
    value = raw_step.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentPlanValidationError(f"steps[{index}].{key} must be a non-empty string")
    return value.strip()


def _optional_step_id(raw_step: dict[str, Any], index: int) -> str:
    value = raw_step.get("id") or f"step-{index + 1}"
    if not isinstance(value, str) or not value.strip():
        raise AgentPlanValidationError(f"steps[{index}].id must be a non-empty string")
    return value.strip()


def _optional_depends_on(raw_step: dict[str, Any], index: int) -> list[str]:
    value = raw_step.get("depends_on", [])
    if not isinstance(value, list):
        raise AgentPlanValidationError(f"steps[{index}].depends_on must be a list")
    dependencies = []
    for dependency in value:
        if not isinstance(dependency, str) or not dependency.strip():
            raise AgentPlanValidationError(f"steps[{index}].depends_on entries must be non-empty strings")
        dependencies.append(dependency.strip())
    return dependencies


def _optional_condition(raw_step: dict[str, Any], index: int) -> dict[str, Any] | None:
    value = raw_step.get("condition")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise AgentPlanValidationError(f"steps[{index}].condition must be an object")

    step_id = value.get("step_id")
    if not isinstance(step_id, str) or not step_id.strip():
        raise AgentPlanValidationError(f"steps[{index}].condition.step_id must be a non-empty string")

    condition: dict[str, Any] = {"step_id": step_id.strip()}
    if "status" in value:
        status = value["status"]
        if not isinstance(status, str) or not status.strip():
            raise AgentPlanValidationError(f"steps[{index}].condition.status must be a non-empty string")
        condition["status"] = status.strip()
    if "output_contains" in value:
        output_contains = value["output_contains"]
        if not isinstance(output_contains, str):
            raise AgentPlanValidationError(f"steps[{index}].condition.output_contains must be a string")
        condition["output_contains"] = output_contains
    return condition


def _validate_tool_input(index: int, schema: dict[str, Any], input_payload: dict[str, Any]) -> None:
    properties = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in input_payload:
            raise AgentPlanValidationError(f"steps[{index}].input.{key} is required")

    for key, value in input_payload.items():
        if key not in properties:
            raise AgentPlanValidationError(f"steps[{index}].input.{key} is not allowed")
        property_schema = properties[key]
        expected_type = property_schema.get("type")
        if expected_type == "string" and not isinstance(value, str):
            raise AgentPlanValidationError(f"steps[{index}].input.{key} must be a string")
        enum_values = property_schema.get("enum")
        if enum_values is not None and value not in enum_values:
            allowed = ", ".join(enum_values)
            raise AgentPlanValidationError(f"steps[{index}].input.{key} must be one of: {allowed}")


def _validate_step_graph(steps: list[AgentStep]) -> None:
    seen: set[str] = set()
    for step in steps:
        if step.step_id in seen:
            raise AgentPlanValidationError("step id must be unique")
        seen.add(step.step_id)

    for step in steps:
        for dependency in _effective_dependencies(step):
            if dependency not in seen:
                raise AgentPlanValidationError("depends_on references unknown step")

    visiting: set[str] = set()
    visited: set[str] = set()
    by_id = {step.step_id: step for step in steps}

    def visit(step_id: str) -> None:
        if step_id in visited:
            return
        if step_id in visiting:
            raise AgentPlanValidationError("dependency cycle detected")
        visiting.add(step_id)
        for dependency in _effective_dependencies(by_id[step_id]):
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step in steps:
        visit(step.step_id)


def _effective_dependencies(step: AgentStep) -> list[str]:
    dependencies = list(step.depends_on or [])
    if step.condition is not None:
        condition_step_id = step.condition["step_id"]
        if condition_step_id not in dependencies:
            dependencies.append(condition_step_id)
    return dependencies


class PlannerAgent:
    name = "planner"

    def __init__(self, model_router: Any | None = None) -> None:
        self.model_router = model_router

    def run(self, input_text: str) -> str:
        return f"[planner] {input_text}"

    def plan(
        self,
        task: str,
        *,
        mode: str = PLANNER_MODE_DETERMINISTIC,
        registry: ToolRegistry | None = None,
    ) -> AgentPlan:
        normalized_mode = mode.strip().lower()
        if normalized_mode == PLANNER_MODE_DETERMINISTIC:
            return self._deterministic_plan(task)
        if normalized_mode == PLANNER_MODE_MODEL:
            if registry is None:
                raise AgentPlanValidationError("registry is required for model planner")
            return self._model_plan(task, registry)
        raise AgentPlanValidationError("planner_mode must be one of: deterministic, model")

    def _deterministic_plan(self, task: str) -> AgentPlan:
        """把最小任务转换为受控工具步骤；不生成任意 shell。"""
        normalized = task.strip()
        lowered = normalized.lower()
        if lowered.startswith("read file "):
            path = normalized[len("read file ") :].strip()
            if not path:
                raise ValueError("file path must not be blank")
            return AgentPlan(
                steps=[
                    AgentStep(
                        tool_name="file.read_text",
                        input={"path": path},
                        reason="read requested workspace file",
                    )
                ]
            )
        if lowered in {"pwd", "show cwd"}:
            return AgentPlan(
                steps=[
                    AgentStep(
                        tool_name="shell.run_safe",
                        input={"command": "pwd"},
                        reason="show current workspace directory",
                    )
                ]
            )
        if lowered == "git status":
            return AgentPlan(
                steps=[
                    AgentStep(
                        tool_name="git.status",
                        input={},
                        reason="show repository status",
                    )
                ]
            )
        raise ValueError("unsupported agent task")

    def _model_plan(self, task: str, registry: ToolRegistry) -> AgentPlan:
        messages = _build_model_planner_messages(task, registry)
        try:
            raw_output = self._get_model_router().chat(messages, temperature=0.0)
        except ProviderError as exc:
            raise AgentPlanValidationError("model planner request failed") from exc

        raw_plan = _parse_model_plan_output(raw_output)
        return validate_agent_plan(raw_plan, registry)

    def _get_model_router(self) -> Any:
        if self.model_router is None:
            from app.core.model_router import ModelRouter

            self.model_router = ModelRouter()
        return self.model_router


def _build_model_planner_messages(task: str, registry: ToolRegistry) -> list[dict[str, str]]:
    tools = [definition.to_dict() for definition in registry.list_tools()]
    return [
        {
            "role": "system",
            "content": (
                "You are the Personal AI OS planner. Return JSON only. "
                "The JSON must be an object with a non-empty steps array. "
                "Each step must contain tool_name, input, and reason. "
                "Use only these tool definitions:\n"
                f"{json.dumps(tools, ensure_ascii=False)}"
            ),
        },
        {
            "role": "user",
            "content": task,
        },
    ]


def _parse_model_plan_output(raw_output: Any) -> dict[str, Any]:
    if not isinstance(raw_output, str):
        raise AgentPlanValidationError("model planner returned invalid JSON plan")

    text = raw_output.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AgentPlanValidationError("model planner returned invalid JSON plan") from exc

    if not isinstance(parsed, dict):
        raise AgentPlanValidationError("model planner returned invalid JSON plan")
    return parsed
