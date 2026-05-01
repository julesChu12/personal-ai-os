from typing import Any

from app.config import settings


LOCAL_ENVS = {"local", "dev", "development", "test"}
SUPPORTED_EMBEDDING_PROVIDERS = {"mock", "openai-compatible"}


def validation_check(name: str, status: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a normalized static configuration check result."""
    return {
        "name": name,
        "status": status,
        "message": message,
        "details": details or {},
    }


def compute_overall_status(checks: list[dict[str, Any]]) -> str:
    """Collapse check statuses into the top-level validation status."""
    statuses = {check["status"] for check in checks}
    if "error" in statuses:
        return "error"
    if "degraded" in statuses:
        return "degraded"
    return "ok"


def validate_runtime_config(settings_obj: Any = settings, strict: bool | None = None) -> dict[str, Any]:
    """Validate runtime configuration without contacting external services or exposing secrets."""
    strict_mode = _is_strict(settings_obj, strict)
    checks = [
        _check_database_url(settings_obj),
        _check_qdrant(settings_obj),
        _check_openai_compat_api_key(settings_obj, strict_mode),
        _check_embedding(settings_obj, strict_mode),
        _check_model(settings_obj, strict_mode),
    ]

    return {
        "status": compute_overall_status(checks),
        "strict": strict_mode,
        "checks": checks,
    }


def _is_strict(settings_obj: Any, strict: bool | None) -> bool:
    if strict is not None:
        return strict
    app_env = str(getattr(settings_obj, "app_env", "")).strip().lower()
    return app_env not in LOCAL_ENVS


def _configured(value: Any) -> bool:
    if value is None:
        return False
    return bool(str(value).strip())


def _danger_status(strict_mode: bool) -> str:
    return "error" if strict_mode else "degraded"


def _check_database_url(settings_obj: Any) -> dict[str, Any]:
    configured = _configured(getattr(settings_obj, "database_url", None))
    if not configured:
        return validation_check(
            "database_url",
            "error",
            "database_url is required",
            {"configured": False},
        )
    return validation_check("database_url", "ok", "database_url is configured", {"configured": True})


def _check_qdrant(settings_obj: Any) -> dict[str, Any]:
    url_configured = _configured(getattr(settings_obj, "qdrant_url", None))
    collection = getattr(settings_obj, "qdrant_collection", None)
    collection_configured = _configured(collection)
    if not (url_configured and collection_configured):
        return validation_check(
            "qdrant",
            "error",
            "qdrant_url and qdrant_collection are required",
            {
                "url_configured": url_configured,
                "collection_configured": collection_configured,
            },
        )
    return validation_check(
        "qdrant",
        "ok",
        "qdrant configuration is present",
        {
            "url_configured": True,
            "collection": collection,
        },
    )


def _check_openai_compat_api_key(settings_obj: Any, strict_mode: bool) -> dict[str, Any]:
    key = getattr(settings_obj, "openai_compat_api_key", None)
    uses_default = not _configured(key) or key == "EMPTY"
    if uses_default:
        return validation_check(
            "openai_compat_api_key",
            _danger_status(strict_mode),
            "openai-compatible API key uses an unsafe default",
            {
                "configured": _configured(key),
                "default": True,
            },
        )
    return validation_check(
        "openai_compat_api_key",
        "ok",
        "openai-compatible API key is explicit",
        {
            "configured": True,
            "default": False,
        },
    )


def _check_embedding(settings_obj: Any, strict_mode: bool) -> dict[str, Any]:
    provider = str(getattr(settings_obj, "embedding_provider", "")).strip()
    dimension = getattr(settings_obj, "embedding_dimension", None)
    if provider not in SUPPORTED_EMBEDDING_PROVIDERS:
        return validation_check(
            "embedding",
            "error",
            "unsupported embedding provider",
            {
                "provider": provider,
                "supported_providers": sorted(SUPPORTED_EMBEDDING_PROVIDERS),
            },
        )

    if not isinstance(dimension, int) or dimension <= 0:
        return validation_check(
            "embedding",
            "error",
            "embedding_dimension must be a positive integer",
            {
                "provider": provider,
                "dimension": dimension,
            },
        )

    if provider == "mock":
        return validation_check(
            "embedding",
            _danger_status(strict_mode),
            "mock embedding provider is suitable for local development only",
            {
                "provider": provider,
                "dimension": dimension,
            },
        )

    api_key_configured = _configured(getattr(settings_obj, "embedding_api_key", None))
    base_url_configured = _configured(getattr(settings_obj, "embedding_base_url", None))
    model_configured = _configured(getattr(settings_obj, "embedding_model", None))
    if not (api_key_configured and base_url_configured and model_configured):
        return validation_check(
            "embedding",
            "error",
            "openai-compatible embedding configuration is incomplete",
            {
                "provider": provider,
                "api_key_configured": api_key_configured,
                "base_url_configured": base_url_configured,
                "model_configured": model_configured,
                "dimension": dimension,
            },
        )

    return validation_check(
        "embedding",
        "ok",
        "embedding provider is explicit",
        {
            "provider": provider,
            "api_key_configured": True,
            "base_url_configured": True,
            "model_configured": True,
            "dimension": dimension,
        },
    )


def _check_model(settings_obj: Any, strict_mode: bool) -> dict[str, Any]:
    provider_configured = _configured(getattr(settings_obj, "openai_api_key", None)) or _configured(
        getattr(settings_obj, "minimax_api_key", None)
    )
    if not provider_configured:
        return validation_check(
            "model",
            _danger_status(strict_mode),
            "model provider is not configured; runtime will use mock responses",
            {"provider_configured": False},
        )
    return validation_check("model", "ok", "model provider is configured", {"provider_configured": True})
