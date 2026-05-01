from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes_tools
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
    app.include_router(routes_tools.router)
    app.dependency_overrides[routes_tools.get_db] = get_test_db
    app.dependency_overrides[routes_tools.get_tool_registry] = lambda: build_default_tool_registry(base_dir=str(tmp_path))
    return TestClient(app)


def test_tools_route_lists_registered_tools(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/tools")

    assert response.status_code == 200
    payload = response.json()
    names = {tool["name"] for tool in payload["tools"]}
    assert {"file.read_text", "git.status", "shell.run_safe"}.issubset(names)


def test_tool_invoke_records_successful_run(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("route tool output", encoding="utf-8")
    client = build_client(tmp_path)

    response = client.post(
        "/tools/file.read_text/invoke",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "input": {"path": "note.md"},
        },
        headers={"X-Request-ID": "req-tool-success"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "file.read_text"
    assert payload["status"] == "ok"
    assert payload["output"] == "route tool output"
    assert payload["error"] is None
    assert isinstance(payload["run_id"], int)

    runs_response = client.get("/tools/runs", params={"user_id": "u1", "project_id": "p1"})
    assert runs_response.status_code == 200
    runs = runs_response.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["tool_name"] == "file.read_text"
    assert runs[0]["status"] == "ok"
    assert runs[0]["request_id"] == "req-tool-success"


def test_tool_invoke_records_guarded_tool_failure(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/tools/shell.run_safe/invoke",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "input": {"command": "cat /etc/passwd"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "shell.run_safe"
    assert payload["status"] == "error"
    assert "Command not allowed" in payload["error"]

    runs = client.get("/tools/runs", params={"user_id": "u1", "project_id": "p1"}).json()["runs"]
    assert len(runs) == 1
    assert runs[0]["status"] == "error"
    assert "Command not allowed" in runs[0]["error"]
