from app.agents.coder import CoderAgent
from app.agents.executor import AgentStepResult
from app.agents.memory_agent import MemoryAgentAgent
from app.agents.researcher import ResearcherAgent


def test_researcher_builds_bounded_task_notes():
    result = ResearcherAgent().research_task(
        "  read the project note  ",
        [{"name": "file.read_text"}, {"name": "git.status"}],
    )

    assert result["task"] == "read the project note"
    assert result["available_tools"] == ["file.read_text", "git.status"]
    assert "External actions must go through ToolRegistry." in result["notes"]


def test_coder_summarizes_successful_step_outputs():
    answer = CoderAgent().summarize_execution(
        "read notes",
        [
            AgentStepResult(step_id="one", tool_name="file.read_text", input={}, status="ok", output="first"),
            AgentStepResult(step_id="two", tool_name="file.read_text", input={}, status="ok", output="second"),
        ],
    )

    assert "Step summary:" in answer
    assert "- one (file.read_text): first" in answer
    assert "- two (file.read_text): second" in answer


def test_coder_summarizes_errors_when_no_outputs():
    answer = CoderAgent().summarize_execution(
        "read missing note",
        [AgentStepResult(step_id="one", tool_name="file.read_text", input={}, status="error", error="missing")],
    )

    assert answer == "missing"


def test_memory_agent_builds_candidate_only_for_success():
    agent = MemoryAgentAgent()

    candidate = agent.build_result_memory("read file note.md", "done", success=True)
    failed = agent.build_result_memory("read file note.md", "done", success=False)

    assert candidate is not None
    assert candidate.memory_type == "agent_result"
    assert candidate.title == "Agent result: read file note.md"
    assert "Task: read file note.md" in candidate.content
    assert "done" in candidate.content
    assert failed is None
