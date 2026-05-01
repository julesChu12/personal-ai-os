import pytest

from app.agents.planner import AgentPlanValidationError, validate_agent_plan
from app.tools.registry import build_default_tool_registry


def test_validate_agent_plan_accepts_registered_tool_schema(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    raw_plan = {
        "steps": [
            {
                "tool_name": "file.read_text",
                "input": {"path": "note.md"},
                "reason": "read requested note",
            }
        ]
    }

    plan = validate_agent_plan(raw_plan, registry)

    assert plan.steps[0].tool_name == "file.read_text"
    assert plan.steps[0].input == {"path": "note.md"}
    assert plan.steps[0].reason == "read requested note"


def test_validate_agent_plan_rejects_unknown_tool(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    with pytest.raises(AgentPlanValidationError, match="tool is not registered"):
        validate_agent_plan(
            {
                "steps": [
                    {
                        "tool_name": "danger.delete",
                        "input": {"path": "note.md"},
                        "reason": "delete note",
                    }
                ]
            },
            registry,
        )


def test_validate_agent_plan_rejects_shell_command_outside_schema_enum(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    with pytest.raises(AgentPlanValidationError, match="command must be one of"):
        validate_agent_plan(
            {
                "steps": [
                    {
                        "tool_name": "shell.run_safe",
                        "input": {"command": "cat /etc/passwd"},
                        "reason": "read forbidden file",
                    }
                ]
            },
            registry,
        )


def test_validate_agent_plan_rejects_missing_required_input(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    with pytest.raises(AgentPlanValidationError, match="path is required"):
        validate_agent_plan(
            {
                "steps": [
                    {
                        "tool_name": "file.read_text",
                        "input": {},
                        "reason": "read requested note",
                    }
                ]
            },
            registry,
        )


def test_validate_agent_plan_rejects_too_many_steps(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    with pytest.raises(AgentPlanValidationError, match="at most 10 steps"):
        validate_agent_plan(
            {
                "steps": [
                    {
                        "tool_name": "shell.run_safe",
                        "input": {"command": "pwd"},
                        "reason": "show cwd",
                    }
                    for _ in range(11)
                ]
            },
            registry,
        )


def test_validate_agent_plan_rejects_unknown_input_fields(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))

    with pytest.raises(AgentPlanValidationError, match="input.extra is not allowed"):
        validate_agent_plan(
            {
                "steps": [
                    {
                        "tool_name": "file.read_text",
                        "input": {"path": "note.md", "extra": "not in schema"},
                        "reason": "read requested note",
                    }
                ]
            },
            registry,
        )
