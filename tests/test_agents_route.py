from fastapi import FastAPI
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace

from app.api import routes_agents
from app.agents.planner import PlannerAgent
from app.core.provider_errors import ProviderRequestError
from app.db.database import Base
from app.db.models import AgentRun, ToolRun
from app.tools.registry import build_default_tool_registry


class FakeModelRouter:
    def __init__(self, response=None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc

    def chat(self, messages, **kwargs):
        if self.exc:
            raise self.exc
        return self.response


class RecordingMemoryPipeline:
    def __init__(self) -> None:
        self.persist_calls = []

    def persist(self, db, user_id, project_id, session_id, candidates):
        self.persist_calls.append(
            {
                "user_id": user_id,
                "project_id": project_id,
                "session_id": session_id,
                "candidates": candidates,
            }
        )
        return candidates


def auth_settings(**overrides):
    defaults = {
        "openai_compat_api_key": "EMPTY",
        "openai_compat_api_keys": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def build_client(tmp_path, *, planner: PlannerAgent | None = None, settings_obj=None) -> TestClient:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def get_test_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(routes_agents.router)
    app.dependency_overrides[routes_agents.get_db] = get_test_db
    app.dependency_overrides[routes_agents.get_tool_registry] = lambda: build_default_tool_registry(base_dir=str(tmp_path))
    if settings_obj is not None:
        app.dependency_overrides[routes_agents.get_auth_settings] = lambda: settings_obj
    if planner is not None:
        app.dependency_overrides[routes_agents.get_planner_agent] = lambda: planner
    memory_pipeline = RecordingMemoryPipeline()
    app.dependency_overrides[routes_agents.get_memory_pipeline] = lambda: memory_pipeline
    app.state.testing_session = testing_session
    app.state.memory_pipeline = memory_pipeline
    return TestClient(app)


def test_agents_run_endpoint_executes_minimal_workflow(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("route agent output", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "read file note.md",
            "agents": ["planner", "executor"],
        },
        headers={"X-Request-ID": "req-agent-route", "Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "route agent output" in payload["answer"]
    assert "Step summary:" in payload["answer"]
    assert [entry["agent"] for entry in payload["agent_trace"]] == ["planner", "executor", "coder"]
    assert payload["steps"][0]["tool_name"] == "file.read_text"
    assert payload["steps"][0]["run_id"] >= 1


def test_agents_run_endpoint_accepts_structured_plan(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("structured route output", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "ignored when plan is supplied",
            "agents": ["planner", "executor"],
            "plan": {
                "steps": [
                    {
                        "tool_name": "file.read_text",
                        "input": {"path": "note.md"},
                        "reason": "read via explicit plan",
                    }
                ]
            },
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "structured route output" in payload["answer"]
    assert payload["agent_trace"][0]["action"] == "validate_plan"


def test_agents_run_endpoint_accepts_parallel_execution_mode(tmp_path):
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("first route output", encoding="utf-8")
    second.write_text("second route output", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "parallel route reads",
            "agents": ["planner", "executor"],
            "execution_mode": "parallel",
            "plan": {
                "steps": [
                    {
                        "id": "first",
                        "tool_name": "file.read_text",
                        "input": {"path": "first.md"},
                        "reason": "read first",
                    },
                    {
                        "id": "second",
                        "tool_name": "file.read_text",
                        "input": {"path": "second.md"},
                        "reason": "read second",
                    },
                ]
            },
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert [step["id"] for step in payload["steps"]] == ["first", "second"]
    assert "first route output" in payload["answer"]
    assert "second route output" in payload["answer"]


def test_agents_run_endpoint_accepts_model_planner_mode(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("model route output", encoding="utf-8")
    planner = PlannerAgent(
        model_router=FakeModelRouter(
            response='{"steps":[{"tool_name":"file.read_text","input":{"path":"note.md"},"reason":"read via model plan"}]}'
        )
    )
    client = build_client(tmp_path, planner=planner)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "read note with model planner",
            "agents": ["planner", "executor"],
            "planner_mode": "model",
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "model route output" in payload["answer"]
    assert payload["agent_trace"][0]["action"] == "model_plan"


def test_agents_run_endpoint_rejects_invalid_model_plan_without_tool_run(tmp_path):
    planner = PlannerAgent(
        model_router=FakeModelRouter(
            response='{"steps":[{"tool_name":"danger.delete","input":{"path":"note.md"},"reason":"delete note"}]}'
        )
    )
    client = build_client(tmp_path, planner=planner)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "delete note with model planner",
            "agents": ["planner", "executor"],
            "planner_mode": "model",
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert "tool is not registered" in payload["error"]
    assert payload["steps"] == []

    db = client.app.state.testing_session()
    try:
        assert db.query(ToolRun).count() == 0
        agent_run = db.query(AgentRun).one()
        assert agent_run.status == "error"
        assert "tool is not registered" in agent_run.error
    finally:
        db.close()


def test_agents_run_endpoint_wraps_model_planner_provider_failure(tmp_path):
    planner = PlannerAgent(model_router=FakeModelRouter(exc=ProviderRequestError("secret-token leaked")))
    client = build_client(tmp_path, planner=planner)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "plan with failing provider",
            "agents": ["planner", "executor"],
            "planner_mode": "model",
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["error"] == "model planner request failed"
    assert "secret-token" not in str(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", " "),
        ("project_id", " "),
    ],
)
def test_agents_run_endpoint_rejects_blank_scope(tmp_path, field, value):
    note = tmp_path / "note.md"
    note.write_text("should not run", encoding="utf-8")
    client = build_client(tmp_path)
    payload = {
        "user_id": "u1",
        "project_id": "p1",
        "session_id": "s1",
        "task": "ignored when plan is supplied",
        "agents": ["planner", "executor"],
        "plan": {
            "steps": [
                {
                    "tool_name": "file.read_text",
                    "input": {"path": "note.md"},
                    "reason": "read via explicit plan",
                }
            ]
        },
    }
    payload[field] = value

    response = client.post("/agents/run", json=payload, headers={"Authorization": "Bearer EMPTY"})

    assert response.status_code == 400
    assert response.json()["detail"] == f"{field} must not be blank"


def test_agents_run_endpoint_normalizes_blank_session_id(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("session normalized", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": " ",
            "task": "read file note.md",
            "agents": ["planner", "executor"],
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"

    db = client.app.state.testing_session()
    try:
        runs = db.query(ToolRun).all()
        assert len(runs) == 1
        assert runs[0].session_id is None
    finally:
        db.close()


def test_agents_run_endpoint_stops_after_failed_plan_step(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "ignored when plan is supplied",
            "agents": ["planner", "executor"],
            "plan": {
                "steps": [
                    {
                        "tool_name": "file.read_text",
                        "input": {"path": "missing.md"},
                        "reason": "read missing note",
                    },
                    {
                        "tool_name": "shell.run_safe",
                        "input": {"command": "pwd"},
                        "reason": "show cwd after failure",
                    },
                ]
            },
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert len(payload["steps"]) == 1
    assert payload["steps"][0]["tool_name"] == "file.read_text"
    assert payload["error"] == "path is not a file"

    db = client.app.state.testing_session()
    try:
        runs = db.query(ToolRun).all()
        assert len(runs) == 1
        assert runs[0].tool_name == "file.read_text"
    finally:
        db.close()


def test_agents_run_endpoint_persists_result_when_memory_agent_requested(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("route memory output", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "read file note.md",
            "agents": ["planner", "executor", "memory_agent"],
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["memory_saved"] == 1
    assert payload["agent_trace"][-1]["agent"] == "memory_agent"
    assert payload["agent_trace"][-1]["status"] == "saved"

    calls = client.app.state.memory_pipeline.persist_calls
    assert len(calls) == 1
    candidate = calls[0]["candidates"][0]
    assert candidate.memory_type == "agent_result"
    assert candidate.title == "Agent result: read file note.md"
    assert "route memory output" in candidate.content


def test_agents_run_endpoint_records_agent_run_and_lists_by_scope(tmp_path):
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("first route run", encoding="utf-8")
    second.write_text("second route run", encoding="utf-8")
    client = build_client(tmp_path)

    first_response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "read file first.md",
            "agents": ["planner", "executor"],
        },
        headers={"X-Request-ID": "req-agent-run-first", "Authorization": "Bearer EMPTY"},
    )
    second_response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s2",
            "task": "read file second.md",
            "agents": ["planner", "executor"],
        },
        headers={"X-Request-ID": "req-agent-run-second", "Authorization": "Bearer EMPTY"},
    )
    client.post(
        "/agents/run",
        json={
            "user_id": "u2",
            "project_id": "p1",
            "session_id": "other",
            "task": "read file second.md",
            "agents": ["planner", "executor"],
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_payload = first_response.json()
    second_payload = second_response.json()
    assert first_payload["agent_run_id"] >= 1
    assert second_payload["agent_run_id"] > first_payload["agent_run_id"]

    response = client.get(
        "/agents/runs",
        params={"user_id": "u1", "project_id": "p1"},
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [run["id"] for run in payload["runs"]] == [second_payload["agent_run_id"], first_payload["agent_run_id"]]
    assert payload["runs"][0]["task"] == "read file second.md"
    assert payload["runs"][0]["status"] == "ok"
    assert "second route run" in payload["runs"][0]["answer"]
    assert payload["runs"][0]["request_id"] == "req-agent-run-second"
    assert payload["runs"][0]["steps"][0]["tool_name"] == "file.read_text"
    assert all(run["user_id"] == "u1" and run["project_id"] == "p1" for run in payload["runs"])


def test_agents_runs_endpoint_rejects_blank_scope(tmp_path):
    client = build_client(tmp_path)

    response = client.get(
        "/agents/runs",
        params={"user_id": " ", "project_id": "p1"},
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "user_id must not be blank"


def test_agents_run_endpoint_does_not_persist_result_without_memory_agent(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("route no memory output", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "read file note.md",
            "agents": ["planner", "executor"],
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["memory_saved"] == 0
    assert client.app.state.memory_pipeline.persist_calls == []


def test_agents_run_endpoint_returns_error_for_unsupported_task(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/agents/run",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "run rm -rf",
            "agents": ["planner", "executor"],
        },
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert "unsupported agent task" in payload["error"]
    assert payload["steps"] == []


def test_agents_run_endpoint_rejects_scope_outside_key_binding(tmp_path):
    client = build_client(
        tmp_path,
        settings_obj=auth_settings(openai_compat_api_keys='[{"key":"project-key","user_id":"alice","project_id":"p1"}]'),
    )

    response = client.post(
        "/agents/run",
        json={
            "user_id": "bob",
            "project_id": "p1",
            "session_id": "s1",
            "task": "git status",
            "agents": ["planner", "executor"],
        },
        headers={"Authorization": "Bearer project-key"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "scope is outside API key binding"
