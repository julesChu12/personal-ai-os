import json
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from app.config import settings
from app.core.session_identity import SessionIdentity

DEFAULT_API_KEY_PERMISSIONS = frozenset({"chat", "tools", "agents"})


@dataclass(frozen=True)
class ApiPrincipal:
    api_key: str
    user_id: str | None
    project_id: str | None
    permissions: frozenset[str]

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


def authenticate_bearer(
    authorization: str | None,
    settings_obj: Any = settings,
    *,
    required_permission: str | None = None,
) -> ApiPrincipal:
    """Authenticate a bearer token and return its optional scope binding."""
    token = _extract_bearer_token(authorization)
    for principal in load_api_principals(settings_obj):
        if token == principal.api_key:
            if required_permission and not principal.has_permission(required_permission):
                raise HTTPException(status_code=403, detail="API key does not have required permission")
            return principal
    raise HTTPException(status_code=401, detail="invalid bearer token")


def load_api_principals(settings_obj: Any = settings) -> list[ApiPrincipal]:
    principals = _load_structured_principals(settings_obj)
    legacy_key = _normalize(getattr(settings_obj, "openai_compat_api_key", None))
    if legacy_key and all(principal.api_key != legacy_key for principal in principals):
        principals.append(
            ApiPrincipal(
                api_key=legacy_key,
                user_id=None,
                project_id=None,
                permissions=DEFAULT_API_KEY_PERMISSIONS,
            )
        )
    return principals


def count_structured_api_key_bindings(settings_obj: Any = settings) -> int:
    return len(_load_structured_principals(settings_obj))


def enforce_principal_scope(principal: ApiPrincipal, *, user_id: str, project_id: str) -> None:
    if principal.user_id is not None and user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="scope is outside API key binding")
    if principal.project_id is not None and project_id != principal.project_id:
        raise HTTPException(status_code=403, detail="scope is outside API key binding")


def bind_openai_identity_to_principal(
    principal: ApiPrincipal,
    identity: SessionIdentity,
    *,
    requested_user_id: str | None,
    requested_project_id: str | None,
) -> SessionIdentity:
    if principal.user_id is None and principal.project_id is None:
        return identity

    if principal.user_id is not None and requested_user_id is not None and requested_user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="scope is outside API key binding")
    if (
        principal.project_id is not None
        and requested_project_id is not None
        and requested_project_id != principal.project_id
    ):
        raise HTTPException(status_code=403, detail="scope is outside API key binding")

    return SessionIdentity(
        user_id=principal.user_id or identity.user_id,
        project_id=principal.project_id or identity.project_id,
        session_id=identity.session_id,
    )


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    return token


def _load_structured_principals(settings_obj: Any) -> list[ApiPrincipal]:
    raw = _normalize(getattr(settings_obj, "openai_compat_api_keys", None))
    if raw is None:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("openai_compat_api_keys is invalid JSON") from exc
    if not isinstance(payload, list):
        raise ValueError("openai_compat_api_keys must be a JSON list")

    principals: list[ApiPrincipal] = []
    seen: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"openai_compat_api_keys[{index}] must be an object")
        key = _normalize(item.get("key"))
        if key is None:
            raise ValueError(f"openai_compat_api_keys[{index}].key is required")
        if key in seen:
            raise ValueError("openai_compat_api_keys keys must be unique")
        seen.add(key)
        principals.append(
            ApiPrincipal(
                api_key=key,
                user_id=_normalize(item.get("user_id")),
                project_id=_normalize(item.get("project_id")),
                permissions=_normalize_permissions(item.get("permissions")),
            )
        )
    return principals


def _normalize_permissions(value: Any) -> frozenset[str]:
    if value is None:
        return DEFAULT_API_KEY_PERMISSIONS
    if not isinstance(value, list):
        raise ValueError("permissions must be a list")
    permissions = {_normalize(item) for item in value}
    cleaned = frozenset(item for item in permissions if item)
    return cleaned or DEFAULT_API_KEY_PERMISSIONS


def _normalize(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
