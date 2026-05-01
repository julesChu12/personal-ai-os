class MemoryAgentAgent:
    name = "memory_agent"

    def run(self, input_text: str) -> str:
        return f"[memory_agent] {input_text}"
