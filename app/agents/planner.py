from dataclasses import dataclass
from typing import Any


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
