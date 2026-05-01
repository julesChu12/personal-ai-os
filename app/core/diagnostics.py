from typing import Any

from qdrant_client import QdrantClient

from app.config import settings
from app.core.model_router import ModelRouter
from app.db.database import engine
from app.memory.embedding_provider import build_embedding_provider, validate_embedding_dimension


def diagnostic_check(name: str, status: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a normalized diagnostic check result."""
    return {
        "name": name,
        "status": status,
        "message": message,
        "details": details or {},
    }


def compute_overall_status(checks: list[dict[str, Any]]) -> str:
    """Collapse check statuses into the top-level diagnostic status."""
    statuses = {check["status"] for check in checks}
    if "error" in statuses:
        return "error"
    if "degraded" in statuses:
        return "degraded"
    return "ok"


def check_config(settings_obj: Any) -> dict[str, Any]:
    findings: list[str] = []

    if settings_obj.openai_compat_api_key == "EMPTY":
        findings.append("default OpenAI-compatible API key")
    if settings_obj.embedding_provider == "mock":
        findings.append("mock embedding provider")
    if not (settings_obj.openai_api_key or settings_obj.minimax_api_key):
        findings.append("mock model provider")

    if findings:
        return diagnostic_check(
            "config",
            "degraded",
            "; ".join(findings),
            {
                "app_env": settings_obj.app_env,
                "embedding_provider": settings_obj.embedding_provider,
                "embedding_dimension": settings_obj.embedding_dimension,
                "qdrant_collection": settings_obj.qdrant_collection,
            },
        )

    return diagnostic_check(
        "config",
        "ok",
        "configuration is explicit",
        {
            "app_env": settings_obj.app_env,
            "embedding_provider": settings_obj.embedding_provider,
            "embedding_dimension": settings_obj.embedding_dimension,
            "qdrant_collection": settings_obj.qdrant_collection,
        },
    )


def check_database(db_engine: Any) -> dict[str, Any]:
    try:
        with db_engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return diagnostic_check("database", "ok", "database reachable")
    except Exception as exc:
        return diagnostic_check("database", "error", str(exc))


def check_qdrant(qdrant_client: Any, settings_obj: Any) -> dict[str, Any]:
    try:
        collections = qdrant_client.get_collections().collections
        collection_names = [collection.name for collection in collections]
        status = "ok" if settings_obj.qdrant_collection in collection_names else "degraded"
        message = "qdrant reachable" if status == "ok" else "qdrant reachable but configured collection is missing"
        return diagnostic_check(
            "qdrant",
            status,
            message,
            {
                "collection": settings_obj.qdrant_collection,
                "collection_present": settings_obj.qdrant_collection in collection_names,
            },
        )
    except Exception as exc:
        return diagnostic_check("qdrant", "error", str(exc), {"collection": settings_obj.qdrant_collection})


def check_embedding(embedding_provider: Any, settings_obj: Any) -> dict[str, Any]:
    try:
        vector = embedding_provider.embed_texts(["diagnostics embedding probe"])[0]
        validate_embedding_dimension(vector, settings_obj.embedding_dimension)
        return diagnostic_check(
            "embedding",
            "ok",
            "embedding provider returned expected dimension",
            {
                "provider": settings_obj.embedding_provider,
                "dimension": len(vector),
                "timeout_seconds": getattr(settings_obj, "provider_timeout_seconds", None),
                "retry_attempts": getattr(settings_obj, "provider_retry_attempts", None),
            },
        )
    except Exception as exc:
        return diagnostic_check(
            "embedding",
            "error",
            str(exc),
            {
                "provider": settings_obj.embedding_provider,
                "expected_dimension": settings_obj.embedding_dimension,
            },
        )


def check_model(model_router: Any) -> dict[str, Any]:
    if getattr(model_router, "provider", "mock") == "mock":
        return diagnostic_check("model", "degraded", "model provider is mock", {"provider": "mock"})
    return diagnostic_check(
        "model",
        "ok",
        "model provider configured",
        {
            "provider": getattr(model_router, "provider", "unknown"),
            "model": getattr(model_router, "model", "unknown"),
            "timeout_seconds": getattr(model_router, "provider_timeout_seconds", None),
            "retry_attempts": getattr(model_router, "provider_retry_attempts", None),
        },
    )


def check_scheduler(scheduler: Any) -> dict[str, Any]:
    if scheduler is None:
        return diagnostic_check("scheduler", "degraded", "scheduler not available")
    if getattr(scheduler, "running", False):
        return diagnostic_check("scheduler", "ok", "scheduler running")
    return diagnostic_check("scheduler", "degraded", "scheduler not running")


def collect_diagnostics(
    scheduler: Any = None,
    settings_obj: Any = settings,
    db_engine: Any = engine,
    qdrant_client: Any | None = None,
    embedding_provider: Any | None = None,
    model_router: Any | None = None,
) -> dict[str, Any]:
    """Collect read-only runtime diagnostics without exposing secrets."""
    qdrant_client = qdrant_client or QdrantClient(url=settings_obj.qdrant_url)
    embedding_provider = embedding_provider or build_embedding_provider()
    model_router = model_router or ModelRouter()

    checks = [
        check_config(settings_obj),
        check_database(db_engine),
        check_qdrant(qdrant_client, settings_obj),
        check_embedding(embedding_provider, settings_obj),
        check_model(model_router),
        check_scheduler(scheduler),
    ]

    return {
        "status": compute_overall_status(checks),
        "checks": checks,
    }
