from typing import Any


class CoderAgent:
    """Turns raw tool step results into a stable developer-facing answer."""

    name = "coder"

    def run(self, input_text: str) -> str:
        return self.summarize_text(input_text)

    def summarize_text(self, input_text: str) -> str:
        text = input_text.strip()
        return text or "No output."

    def summarize_execution(self, task: str, step_results: list[Any]) -> str:
        successful_steps = [step for step in step_results if step.status == "ok" and step.output is not None]
        if successful_steps:
            lines = [
                f"Task: {' '.join(task.strip().split()) or 'agent task'}",
                "",
                "Step summary:",
            ]
            for step in successful_steps:
                step_id = step.step_id or step.tool_name
                lines.append(f"- {step_id} ({step.tool_name}): {step.output}")
            return "\n".join(lines)

        errors = [str(step.error) for step in step_results if step.error]
        if errors:
            return "\n".join(errors)

        return f"Task completed with no tool output: {task.strip()}"
