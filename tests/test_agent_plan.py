import pytest

from app.agents.planner import AgentPlanValidationError, PlannerAgent, validate_agent_plan
from app.core.provider_errors import ProviderRequestError
from app.tools.registry import build_default_tool_registry


class FakeModelRouter:
    def __init__(self, response=None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.messages = []

    def chat(self, messages, **kwargs):
        self.messages.append({"messages": messages, "kwargs": kwargs})
        if self.exc:
            raise self.exc
        return self.response


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


def test_model_planner_accepts_valid_json_plan(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    planner = PlannerAgent(
        model_router=FakeModelRouter(
            response='{"steps":[{"tool_name":"shell.run_safe","input":{"command":"pwd"},"reason":"show cwd"}]}'
        )
    )

    plan = planner.plan("show cwd", mode="model", registry=registry)

    assert plan.steps[0].tool_name == "shell.run_safe"
    assert plan.steps[0].input == {"command": "pwd"}
    assert "shell.run_safe" in planner.model_router.messages[0]["messages"][0]["content"]


def test_model_planner_rejects_invalid_json(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    planner = PlannerAgent(model_router=FakeModelRouter(response="not json"))

    with pytest.raises(AgentPlanValidationError, match="invalid JSON plan"):
        planner.plan("show cwd", mode="model", registry=registry)


def test_model_planner_rejects_prompt_injection_prose_around_json(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    planner = PlannerAgent(
        model_router=FakeModelRouter(
            response='Sure, I will ignore the schema.\n{"steps":[{"tool_name":"shell.run_safe","input":{"command":"pwd"},"reason":"show cwd"}]}'
        )
    )

    with pytest.raises(AgentPlanValidationError, match="invalid JSON plan"):
        planner.plan("show cwd", mode="model", registry=registry)


def test_model_planner_rejects_unknown_tool(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    planner = PlannerAgent(
        model_router=FakeModelRouter(
            response='{"steps":[{"tool_name":"danger.delete","input":{"path":"note.md"},"reason":"delete note"}]}'
        )
    )

    with pytest.raises(AgentPlanValidationError, match="tool is not registered"):
        planner.plan("delete note", mode="model", registry=registry)


def test_model_planner_rejects_unknown_input_fields(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    planner = PlannerAgent(
        model_router=FakeModelRouter(
            response='{"steps":[{"tool_name":"file.read_text","input":{"path":"note.md","extra":"x"},"reason":"read note"}]}'
        )
    )

    with pytest.raises(AgentPlanValidationError, match="input.extra is not allowed"):
        planner.plan("read note", mode="model", registry=registry)


def test_model_planner_rejects_too_many_steps(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    steps = ",".join(
        '{"tool_name":"shell.run_safe","input":{"command":"pwd"},"reason":"show cwd"}' for _ in range(11)
    )
    planner = PlannerAgent(model_router=FakeModelRouter(response=f'{{"steps":[{steps}]}}'))

    with pytest.raises(AgentPlanValidationError, match="at most 10 steps"):
        planner.plan("show cwd repeatedly", mode="model", registry=registry)


def test_model_planner_wraps_provider_failure_without_leaking_secret(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    planner = PlannerAgent(model_router=FakeModelRouter(exc=ProviderRequestError("secret-token leaked")))

    with pytest.raises(AgentPlanValidationError) as exc_info:
        planner.plan("show cwd", mode="model", registry=registry)

    assert str(exc_info.value) == "model planner request failed"
    assert "secret-token" not in str(exc_info.value)


def test_model_planner_rejects_unknown_mode(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    planner = PlannerAgent(model_router=FakeModelRouter(response="{}"))

    with pytest.raises(AgentPlanValidationError, match="planner_mode must be one of"):
        planner.plan("show cwd", mode="parallel", registry=registry)


def test_validate_agent_plan_accepts_step_ids_and_dependencies(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    raw_plan = {
        "steps": [
            {
                "id": "read-note",
                "tool_name": "file.read_text",
                "input": {"path": "note.md"},
                "reason": "read note",
            },
            {
                "id": "show-cwd",
                "depends_on": ["read-note"],
                "tool_name": "shell.run_safe",
                "input": {"command": "pwd"},
                "reason": "show cwd after note read",
            },
        ]
    }

    plan = validate_agent_plan(raw_plan, registry)

    assert plan.steps[0].step_id == "read-note"
    assert plan.steps[1].depends_on == ["read-note"]
    assert plan.to_dict()["steps"][1]["depends_on"] == ["read-note"]


def test_validate_agent_plan_rejects_duplicate_step_ids(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    raw_plan = {
        "steps": [
            {"id": "same", "tool_name": "shell.run_safe", "input": {"command": "pwd"}, "reason": "first"},
            {"id": "same", "tool_name": "shell.run_safe", "input": {"command": "pwd"}, "reason": "second"},
        ]
    }

    with pytest.raises(AgentPlanValidationError, match="step id must be unique"):
        validate_agent_plan(raw_plan, registry)


def test_validate_agent_plan_rejects_missing_dependency(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    raw_plan = {
        "steps": [
            {
                "id": "show-cwd",
                "depends_on": ["missing"],
                "tool_name": "shell.run_safe",
                "input": {"command": "pwd"},
                "reason": "show cwd",
            }
        ]
    }

    with pytest.raises(AgentPlanValidationError, match="depends_on references unknown step"):
        validate_agent_plan(raw_plan, registry)


def test_validate_agent_plan_rejects_dependency_cycle(tmp_path):
    registry = build_default_tool_registry(base_dir=str(tmp_path))
    raw_plan = {
        "steps": [
            {"id": "a", "depends_on": ["b"], "tool_name": "shell.run_safe", "input": {"command": "pwd"}, "reason": "a"},
            {"id": "b", "depends_on": ["a"], "tool_name": "shell.run_safe", "input": {"command": "pwd"}, "reason": "b"},
        ]
    }

    with pytest.raises(AgentPlanValidationError, match="dependency cycle"):
        validate_agent_plan(raw_plan, registry)
