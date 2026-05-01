import logging
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.core.request_context import REQUEST_ID_HEADER, get_request_id, register_request_context_middleware


def build_client(include_error_handlers: bool = False) -> TestClient:
    app = FastAPI()
    register_request_context_middleware(app)
    if include_error_handlers:
        register_error_handlers(app)

    @app.get("/context")
    def context():
        return {"request_id": get_request_id()}

    @app.get("/broken")
    def broken():
        raise RuntimeError("secret should not leak")

    return TestClient(app, raise_server_exceptions=False)


def test_reuses_inbound_request_id_and_exposes_it_to_handlers():
    client = build_client()

    response = client.get("/context", headers={REQUEST_ID_HEADER: "caller-request-1"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "caller-request-1"
    assert response.json() == {"request_id": "caller-request-1"}


def test_generates_request_id_when_header_is_missing():
    response = build_client().get("/context")

    request_id = response.headers[REQUEST_ID_HEADER]
    assert response.status_code == 200
    assert response.json() == {"request_id": request_id}
    assert uuid.UUID(request_id)


def test_request_completion_log_contains_request_context(caplog):
    caplog.set_level(logging.INFO, logger="app.core.request_context")

    response = build_client().get("/context", headers={REQUEST_ID_HEADER: "log-request-1"})

    assert response.status_code == 200
    records = [record for record in caplog.records if record.name == "app.core.request_context"]
    assert len(records) == 1
    record = records[0]
    assert record.message == "request completed"
    assert record.request_id == "log-request-1"
    assert record.method == "GET"
    assert record.path == "/context"
    assert record.status == 200
    assert record.duration_ms >= 0


def test_unhandled_error_log_contains_request_context(caplog):
    caplog.set_level(logging.ERROR, logger="app.core.errors")

    response = build_client(include_error_handlers=True).get("/broken", headers={REQUEST_ID_HEADER: "error-request-1"})

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER] == "error-request-1"
    records = [record for record in caplog.records if record.name == "app.core.errors"]
    assert len(records) == 1
    record = records[0]
    assert record.message == "unhandled request error"
    assert record.request_id == "error-request-1"
    assert record.method == "GET"
    assert record.path == "/broken"
    assert record.status == 500
    assert record.exception_type == "RuntimeError"
    assert "secret should not leak" not in record.getMessage()
