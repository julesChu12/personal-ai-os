from dataclasses import dataclass
from typing import Any

from app.agents.planner import AgentStep
from app.tools.registry import ToolInvocationResult, ToolRegistry


@dataclass(frozen=True)
class AgentStepResult:
    tool_name: str
    input: dict[str, Any]
    status: str
    output: Any | None = None
    error: str | None = None
    run_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "input": self.input,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "run_id": self.run_id,
        }


class ExecutorAgent:
    name = "executor"

    def run(self, input_text: str) -> str:
        return f"[executor] {input_text}"

    def execute(self, step: AgentStep, registry: ToolRegistry) -> ToolInvocationResult:
        """通过 ToolRegistry 执行单个规划步骤。"""
        return registry.invoke(step.tool_name, step.input)
