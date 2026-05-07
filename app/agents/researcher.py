from typing import Any


class ResearcherAgent:
    """Produces small, bounded research notes for an agent task."""

    name = "researcher"

    def run(self, input_text: str) -> str:
        notes = self.research_task(input_text)
        return "\n".join(notes["notes"])

    def research_task(self, task: str, tool_definitions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        normalized_task = " ".join(task.strip().split())
        tools = tool_definitions or []
        tool_names = [str(tool.get("name", "")).strip() for tool in tools if tool.get("name")]
        notes = [
            f"Task: {normalized_task or 'agent task'}",
            "External actions must go through ToolRegistry.",
        ]
        if tool_names:
            notes.append(f"Available tools: {', '.join(sorted(tool_names))}.")
        else:
            notes.append("No tool definitions were provided.")
        return {
            "task": normalized_task,
            "available_tools": sorted(tool_names),
            "notes": notes,
        }
