from dataclasses import dataclass
from typing import Any

from app.tools.registry import ToolNotFoundError, ToolRegistry

MAX_AGENT_PLAN_STEPS = 10


class AgentPlanValidationError(ValueError):
    """结构化 Agent plan 不符合工具 schema 时抛出。"""


@dataclass(frozen=True)
class AgentStep:
    tool_name: str
    input: dict[str, Any]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "input": self.input,
            "reason": self.reason,
        }


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
        steps.append(AgentStep(tool_name=tool_name, input=input_payload, reason=reason))

    return AgentPlan(steps=steps)


def _required_step_string(raw_step: dict[str, Any], key: str, index: int) -> str:
    value = raw_step.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentPlanValidationError(f"steps[{index}].{key} must be a non-empty string")
    return value.strip()


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


class PlannerAgent:
    name = "planner"

    def run(self, input_text: str) -> str:
        return f"[planner] {input_text}"

    def plan(self, task: str) -> AgentPlan:
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
