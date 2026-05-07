from app.memory.memory_schema import MemoryCandidate


class MemoryAgentAgent:
    """Builds memory candidates from successful agent task results."""

    name = "memory_agent"

    def run(self, input_text: str) -> str:
        return input_text.strip()

    def build_result_memory(self, task: str, answer: str, *, success: bool) -> MemoryCandidate | None:
        if not success or not answer.strip():
            return None

        normalized_task = " ".join(task.strip().split()) or "agent task"
        title_task = normalized_task[:80].rstrip()
        return MemoryCandidate(
            memory_type="agent_result",
            title=f"Agent result: {title_task}",
            content=f"Task: {normalized_task}\n\nResult:\n{answer.strip()}",
            tags=["personal-ai-os", "agent"],
            importance=6,
        )


MemoryAgent = MemoryAgentAgent
