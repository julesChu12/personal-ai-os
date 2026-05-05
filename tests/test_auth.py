import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from app.core.session_identity import SessionIdentity


def settings(**overrides):
    defaults = {
        "openai_compat_api_key": "EMPTY",
        "openai_compat_api_keys": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_auth_accepts_legacy_single_key_without_scope_binding():
    from app.core.auth import authenticate_bearer

    principal = authenticate_bearer("Bearer EMPTY", settings())

    assert principal.api_key == "EMPTY"
    assert principal.user_id is None
    assert principal.project_id is None
    assert "chat" in principal.permissions


def test_auth_accepts_structured_key_binding():
    from app.core.auth import authenticate_bearer

    principal = authenticate_bearer(
        "Bearer project-key",
        settings(
            openai_compat_api_keys=(
                '[{"key":"project-key","user_id":"alice","project_id":"personal",'
                '"permissions":["chat","tools","agents"]}]'
            )
        ),
    )

    assert principal.api_key == "project-key"
    assert principal.user_id == "alice"
    assert principal.project_id == "personal"
    assert principal.has_permission("tools")


def test_auth_rejects_invalid_token_without_leaking_configured_keys():
    from app.core.auth import authenticate_bearer

    with pytest.raises(HTTPException) as exc_info:
        authenticate_bearer(
            "Bearer wrong",
            settings(openai_compat_api_keys='[{"key":"secret-key","user_id":"alice","project_id":"personal"}]'),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "invalid bearer token"
    assert "secret-key" not in str(exc_info.value)


def test_bound_principal_rejects_scope_mismatch():
    from app.core.auth import ApiPrincipal, enforce_principal_scope

    principal = ApiPrincipal(
        api_key="project-key",
        user_id="alice",
        project_id="personal",
        permissions=frozenset({"tools"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        enforce_principal_scope(principal, user_id="bob", project_id="personal")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "scope is outside API key binding"


def test_bound_principal_overrides_openai_default_identity_when_scope_is_absent():
    from app.core.auth import ApiPrincipal, bind_openai_identity_to_principal

    principal = ApiPrincipal(
        api_key="project-key",
        user_id="alice",
        project_id="personal",
        permissions=frozenset({"chat"}),
    )

    identity = bind_openai_identity_to_principal(
        principal,
        SessionIdentity(user_id="openwebui", project_id="openwebui", session_id="s1"),
        requested_user_id=None,
        requested_project_id=None,
    )

    assert identity.user_id == "alice"
    assert identity.project_id == "personal"
    assert identity.session_id == "s1"
