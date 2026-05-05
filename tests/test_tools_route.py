from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace

from app.api import routes_tools
from app.db.database import Base
from app.tools.registry import build_default_tool_registry


def auth_settings(**overrides):
    defaults = {
        "openai_compat_api_key": "EMPTY",
        "openai_compat_api_keys": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def build_client(tmp_path, *, settings_obj=None) -> TestClient:
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
    if settings_obj is not None:
        app.dependency_overrides[routes_tools.get_auth_settings] = lambda: settings_obj
    return TestClient(app)


def test_tools_route_lists_registered_tools(tmp_path):
    client = build_client(tmp_path)

    response = client.get("/tools", headers={"Authorization": "Bearer EMPTY"})

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
        headers={"X-Request-ID": "req-tool-success", "Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "file.read_text"
    assert payload["status"] == "ok"
    assert payload["output"] == "route tool output"
    assert payload["error"] is None
    assert isinstance(payload["run_id"], int)

    runs_response = client.get(
        "/tools/runs",
        params={"user_id": "u1", "project_id": "p1"},
        headers={"Authorization": "Bearer EMPTY"},
    )
    assert runs_response.status_code == 200
    runs = runs_response.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["tool_name"] == "file.read_text"
    assert runs[0]["status"] == "ok"
    assert runs[0]["request_id"] == "req-tool-success"


def test_tool_invoke_records_file_write_run(tmp_path):
    client = build_client(tmp_path)

    response = client.post(
        "/tools/file.write_text/invoke",
        json={
            "user_id": "u1",
            "project_id": "p1",
            "session_id": "s1",
            "input": {"path": "created.md", "content": "hello"},
        },
        headers={"X-Request-ID": "req-tool-write", "Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert (tmp_path / "created.md").read_text(encoding="utf-8") == "hello"
    runs = client.get(
        "/tools/runs",
        params={"user_id": "u1", "project_id": "p1"},
        headers={"Authorization": "Bearer EMPTY"},
    ).json()["runs"]
    assert runs[0]["tool_name"] == "file.write_text"
    assert runs[0]["status"] == "ok"
    assert runs[0]["request_id"] == "req-tool-write"


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
        headers={"Authorization": "Bearer EMPTY"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "shell.run_safe"
    assert payload["status"] == "error"
    assert "Command not allowed" in payload["error"]

    runs = client.get(
        "/tools/runs",
        params={"user_id": "u1", "project_id": "p1"},
        headers={"Authorization": "Bearer EMPTY"},
    ).json()["runs"]
    assert len(runs) == 1
    assert runs[0]["status"] == "error"
    assert "Command not allowed" in runs[0]["error"]


def test_tool_invoke_rejects_scope_outside_key_binding(tmp_path):
    client = build_client(
        tmp_path,
        settings_obj=auth_settings(openai_compat_api_keys='[{"key":"project-key","user_id":"alice","project_id":"p1"}]'),
    )

    response = client.post(
        "/tools/shell.run_safe/invoke",
        json={
            "user_id": "bob",
            "project_id": "p1",
            "session_id": "s1",
            "input": {"command": "pwd"},
        },
        headers={"Authorization": "Bearer project-key"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "scope is outside API key binding"
