from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes_chat
from app.db.database import Base
from app.db.models import AgentRun, ToolRun
from app.tools.registry import build_default_tool_registry


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


def build_client(tmp_path) -> TestClient:
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
    app.include_router(routes_chat.router)
    app.dependency_overrides[routes_chat.get_db] = get_test_db
    app.dependency_overrides[routes_chat.get_task_tool_registry] = lambda: build_default_tool_registry(
        base_dir=str(tmp_path)
    )
    memory_pipeline = RecordingMemoryPipeline()
    app.dependency_overrides[routes_chat.get_task_memory_pipeline] = lambda: memory_pipeline
    app.state.testing_session = testing_session
    app.state.memory_pipeline = memory_pipeline
    return TestClient(app)


def test_task_route_executes_agent_workflow_and_records_runs(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("task route output", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/task",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "read file note.md",
            "agents": ["planner", "executor"],
        },
        headers={"X-Request-ID": "req-task-route"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "task route output" in payload["answer"]
    assert "Step summary:" in payload["answer"]
    assert [entry["agent"] for entry in payload["agent_trace"]] == ["planner", "executor", "coder"]
    assert payload["steps"][0]["tool_name"] == "file.read_text"

    db = client.app.state.testing_session()
    try:
        agent_run = db.query(AgentRun).one()
        tool_run = db.query(ToolRun).one()
        assert agent_run.request_id == "req-task-route"
        assert tool_run.request_id == "req-task-route"
    finally:
        db.close()


def test_task_route_accepts_structured_parallel_plan(tmp_path):
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("first task route output", encoding="utf-8")
    second.write_text("second task route output", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/task",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "parallel reads through task route",
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
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["agent_trace"][0]["action"] == "validate_plan"
    assert [step["id"] for step in payload["steps"]] == ["first", "second"]
    assert "first task route output" in payload["answer"]
    assert "second task route output" in payload["answer"]


def test_task_route_persists_result_when_memory_agent_requested(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("memory task route output", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/task",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "task": "read file note.md",
            "agents": ["planner", "executor", "memory_agent"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["memory_saved"] == 1
    assert payload["agent_trace"][-1]["agent"] == "memory_agent"
    assert len(client.app.state.memory_pipeline.persist_calls) == 1
