from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.diagnostics import collect_diagnostics, compute_overall_status


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def exec_driver_sql(self, sql: str):
        self.sql = sql


class WorkingEngine:
    def connect(self):
        return FakeConnection()


class BrokenEngine:
    def connect(self):
        raise RuntimeError("database unavailable")


class WorkingQdrantClient:
    def get_collections(self):
        return SimpleNamespace(collections=[SimpleNamespace(name="memories")])


class BrokenQdrantClient:
    def get_collections(self):
        raise RuntimeError("qdrant unavailable")


class WorkingEmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class RealModelRouter:
    provider = "openai"
    model = "gpt-test"


class MockModelRouter:
    provider = "mock"
    model = "mock"


def settings(**overrides):
    defaults = {
        "app_name": "personal-ai-os",
        "app_env": "local",
        "database_url": "postgresql://secret-user:secret-pass@db:5432/app",
        "qdrant_url": "http://qdrant:6333",
        "qdrant_collection": "memories",
        "openai_compat_api_key": "EMPTY",
        "embedding_provider": "mock",
        "embedding_dimension": 3,
        "openai_api_key": None,
        "minimax_api_key": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_compute_overall_status_orders_error_over_degraded():
    assert compute_overall_status([{"status": "ok"}]) == "ok"
    assert compute_overall_status([{"status": "ok"}, {"status": "degraded"}]) == "degraded"
    assert compute_overall_status([{"status": "degraded"}, {"status": "error"}]) == "error"


def test_collect_diagnostics_reports_ok_dependencies_without_leaking_secrets():
    report = collect_diagnostics(
        settings_obj=settings(
            openai_compat_api_key="configured-key",
            openai_api_key="model-key",
            embedding_provider="openai-compatible",
        ),
        db_engine=WorkingEngine(),
        qdrant_client=WorkingQdrantClient(),
        embedding_provider=WorkingEmbeddingProvider(),
        model_router=RealModelRouter(),
        scheduler=SimpleNamespace(running=True),
    )

    assert report["status"] == "ok"
    check_names = {check["name"] for check in report["checks"]}
    assert {"config", "database", "qdrant", "embedding", "model", "scheduler"}.issubset(check_names)
    serialized = str(report)
    assert "configured-key" not in serialized
    assert "model-key" not in serialized
    assert "secret-pass" not in serialized


def test_collect_diagnostics_marks_dependency_failures_as_error():
    report = collect_diagnostics(
        settings_obj=settings(openai_compat_api_key="configured-key", openai_api_key="model-key"),
        db_engine=BrokenEngine(),
        qdrant_client=BrokenQdrantClient(),
        embedding_provider=WorkingEmbeddingProvider(),
        model_router=RealModelRouter(),
        scheduler=SimpleNamespace(running=True),
    )

    assert report["status"] == "error"
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["database"]["status"] == "error"
    assert "database unavailable" in checks["database"]["message"]
    assert checks["qdrant"]["status"] == "error"
    assert "qdrant unavailable" in checks["qdrant"]["message"]


def test_collect_diagnostics_marks_mock_and_default_config_as_degraded():
    report = collect_diagnostics(
        settings_obj=settings(),
        db_engine=WorkingEngine(),
        qdrant_client=WorkingQdrantClient(),
        embedding_provider=WorkingEmbeddingProvider(),
        model_router=MockModelRouter(),
        scheduler=SimpleNamespace(running=False),
    )

    assert report["status"] == "degraded"
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["config"]["status"] == "degraded"
    assert "default OpenAI-compatible API key" in checks["config"]["message"]
    assert checks["model"]["status"] == "degraded"
    assert checks["scheduler"]["status"] == "degraded"


def test_diagnostics_route_returns_report(monkeypatch):
    from app.api import routes_diagnostics

    expected = {"status": "ok", "checks": [{"name": "config", "status": "ok", "message": "ok", "details": {}}]}
    monkeypatch.setattr(routes_diagnostics, "collect_diagnostics", lambda scheduler=None: expected)

    app = FastAPI()
    app.include_router(routes_diagnostics.router)
    response = TestClient(app).get("/diagnostics")

    assert response.status_code == 200
    assert response.json() == expected
