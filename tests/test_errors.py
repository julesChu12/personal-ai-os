from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers


def build_error_client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/internal/bad-request")
    def bad_request():
        raise HTTPException(status_code=400, detail="invalid request payload")

    @app.get("/internal/broken")
    def broken():
        raise RuntimeError("database password=secret leaked by dependency")

    @app.get("/internal/needs-query")
    def needs_query(query: str):
        return {"query": query}

    @app.get("/v1/protected")
    def openai_protected():
        raise HTTPException(status_code=401, detail="missing bearer token")

    return TestClient(app, raise_server_exceptions=False)


def test_internal_http_exception_uses_standard_error_envelope():
    response = build_error_client().get("/internal/bad-request")

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "bad_request",
            "message": "invalid request payload",
            "type": "http_error",
        }
    }


def test_validation_error_uses_standard_error_envelope():
    response = build_error_client().get("/internal/needs-query")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "request validation failed",
            "type": "request_validation_error",
        }
    }


def test_not_found_uses_standard_error_envelope():
    response = build_error_client().get("/missing-route")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "type": "http_error",
        }
    }


def test_internal_server_error_does_not_leak_exception_details():
    response = build_error_client().get("/internal/broken")

    assert response.status_code == 500
    payload = response.json()
    assert payload == {
        "error": {
            "code": "internal_error",
            "message": "internal server error",
            "type": "internal_error",
        }
    }
    assert "secret" not in str(payload)
    assert "database password" not in str(payload)


def test_openai_compat_http_exception_keeps_openai_error_shape():
    response = build_error_client().get("/v1/protected")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "message": "missing bearer token",
            "type": "authentication_error",
            "code": "unauthorized",
        }
    }
