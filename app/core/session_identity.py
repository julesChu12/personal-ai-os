import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


DEFAULT_OPENWEBUI_USER_ID = "openwebui"
DEFAULT_OPENWEBUI_PROJECT_ID = "openwebui"


class IdentityError(ValueError):
    pass


@dataclass(frozen=True)
class SessionIdentity:
    user_id: str
    project_id: str
    session_id: str


@dataclass(frozen=True)
class ProjectScope:
    user_id: str
    project_id: str


def resolve_openai_identity(
    req: Any,
    x_session_id: str | None,
    new_session_id: Callable[[], str] | None = None,
) -> SessionIdentity:
    """解析 OpenAI-compatible 请求身份，保持 Open WebUI 缺省兼容。"""
    metadata = getattr(req, "metadata", None) or {}
    new_session_id = new_session_id or (lambda: str(uuid.uuid4()))

    user_id = _first_present(_metadata_value(metadata, "user_id"), getattr(req, "user", None), DEFAULT_OPENWEBUI_USER_ID)
    project_id = _first_present(_metadata_value(metadata, "project_id"), DEFAULT_OPENWEBUI_PROJECT_ID)
    session_id = _first_present(x_session_id, _metadata_value(metadata, "session_id"), new_session_id())

    return SessionIdentity(user_id=user_id, project_id=project_id, session_id=session_id)


def resolve_project_scope(user_id: str | None, project_id: str | None) -> ProjectScope:
    normalized_user_id = _normalize_identity_value(user_id)
    normalized_project_id = _normalize_identity_value(project_id)
    if normalized_user_id is None:
        raise IdentityError("user_id must not be blank")
    if normalized_project_id is None:
        raise IdentityError("project_id must not be blank")
    return ProjectScope(user_id=normalized_user_id, project_id=normalized_project_id)


def _metadata_value(metadata: dict[str, Any], key: str) -> str | None:
    return _normalize_identity_value(metadata.get(key))


def _first_present(*values: Any) -> str:
    for value in values:
        normalized = _normalize_identity_value(value)
        if normalized is not None:
            return normalized
    raise IdentityError("identity value must not be blank")


def _normalize_identity_value(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
