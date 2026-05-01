from types import SimpleNamespace

from app.core.config_validation import validate_runtime_config


def settings(**overrides):
    defaults = {
        "app_env": "local",
        "database_url": "postgresql://secret-user:secret-pass@db:5432/app",
        "qdrant_url": "http://qdrant:6333",
        "qdrant_collection": "memories",
        "openai_compat_api_key": "EMPTY",
        "embedding_provider": "mock",
        "embedding_api_key": None,
        "embedding_base_url": None,
        "embedding_model": None,
        "embedding_dimension": 384,
        "openai_api_key": None,
        "minimax_api_key": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def check_by_name(report, name: str):
    return {check["name"]: check for check in report["checks"]}[name]


def test_local_defaults_are_degraded_but_not_error():
    report = validate_runtime_config(settings())

    assert report["status"] == "degraded"
    assert check_by_name(report, "openai_compat_api_key")["status"] == "degraded"
    assert check_by_name(report, "embedding")["status"] == "degraded"
    assert check_by_name(report, "model")["status"] == "degraded"


def test_strict_mode_turns_dangerous_defaults_into_errors():
    report = validate_runtime_config(settings(app_env="production"), strict=True)

    assert report["status"] == "error"
    assert check_by_name(report, "openai_compat_api_key")["status"] == "error"
    assert check_by_name(report, "embedding")["status"] == "error"
    assert check_by_name(report, "model")["status"] == "error"


def test_openai_compatible_embedding_requires_complete_config():
    report = validate_runtime_config(
        settings(
            embedding_provider="openai-compatible",
            embedding_api_key="embedding-secret",
            embedding_base_url=None,
            embedding_model="text-embedding-3-small",
        )
    )

    assert report["status"] == "error"
    embedding = check_by_name(report, "embedding")
    assert embedding["status"] == "error"
    assert "incomplete" in embedding["message"]


def test_explicit_runtime_config_is_ok():
    report = validate_runtime_config(
        settings(
            app_env="production",
            openai_compat_api_key="compat-secret",
            embedding_provider="openai-compatible",
            embedding_api_key="embedding-secret",
            embedding_base_url="https://example.com/v1",
            embedding_model="text-embedding-3-small",
            openai_api_key="model-secret",
        ),
        strict=True,
    )

    assert report["status"] == "ok"
    assert all(check["status"] == "ok" for check in report["checks"])


def test_validation_report_does_not_leak_secret_values():
    report = validate_runtime_config(
        settings(
            openai_compat_api_key="compat-secret",
            embedding_api_key="embedding-secret",
            openai_api_key="model-secret",
        )
    )

    serialized = str(report)
    assert "compat-secret" not in serialized
    assert "embedding-secret" not in serialized
    assert "model-secret" not in serialized
    assert "secret-pass" not in serialized
