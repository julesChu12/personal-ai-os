from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes_agents
from app.db.database import Base
from app.tools.registry import build_default_tool_registry


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
    app.include_router(routes_agents.router)
    app.dependency_overrides[routes_agents.get_db] = get_test_db
    app.dependency_overrides[routes_agents.get_tool_registry] = lambda: build_default_tool_registry(base_dir=str(tmp_path))
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
        headers={"X-Request-ID": "req-agent-route"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["answer"] == "route agent output"
    assert [entry["agent"] for entry in payload["agent_trace"]] == ["planner", "executor"]
    assert payload["steps"][0]["tool_name"] == "file.read_text"
    assert payload["steps"][0]["run_id"] >= 1


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
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "error"
    assert "unsupported agent task" in payload["error"]
    assert payload["steps"] == []
