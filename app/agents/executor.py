class ExecutorAgent:
    name = "executor"

    def run(self, input_text: str) -> str:
        return f"[executor] {input_text}"
