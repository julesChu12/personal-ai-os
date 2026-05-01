from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_sessions
from app.core.errors import register_error_handlers


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filter_kwargs = None

    def filter_by(self, **kwargs):
        self.filter_kwargs = kwargs
        return self

    def distinct(self):
        return self

    def all(self):
        return self.rows


class FakeDb:
    def __init__(self, rows):
        self.query_obj = FakeQuery(rows)

    def query(self, *args):
        return self.query_obj


def build_client(db: FakeDb) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(routes_sessions.router)
    app.dependency_overrides[routes_sessions.get_db] = lambda: db
    return TestClient(app)


def test_sessions_query_trims_scope_and_filters_by_user_and_project():
    db = FakeDb(rows=[("session-a",), ("session-b",)])
    response = build_client(db).get("/sessions", params={"user_id": " alice ", "project_id": " project-a "})

    assert response.status_code == 200
    assert response.json() == {"sessions": ["session-a", "session-b"]}
    assert db.query_obj.filter_kwargs == {"user_id": "alice", "project_id": "project-a"}


def test_sessions_query_rejects_blank_project_scope():
    db = FakeDb(rows=[])
    response = build_client(db).get("/sessions", params={"user_id": "alice", "project_id": " "})

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "bad_request",
            "message": "project_id must not be blank",
            "type": "http_error",
        }
    }
