from types import SimpleNamespace

import pytest

from app.core.session_identity import IdentityError, resolve_openai_identity, resolve_project_scope


def request(**overrides):
    defaults = {
        "user": None,
        "metadata": {},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_openai_identity_prefers_metadata_and_header_with_trimmed_values():
    identity = resolve_openai_identity(
        request(
            user="openai-user",
            metadata={
                "user_id": " alice ",
                "project_id": " project-a ",
                "session_id": " metadata-session ",
            },
        ),
        x_session_id=" header-session ",
        new_session_id=lambda: "generated-session",
    )

    assert identity.user_id == "alice"
    assert identity.project_id == "project-a"
    assert identity.session_id == "header-session"


def test_openai_identity_uses_openwebui_defaults_when_metadata_is_missing_or_blank():
    identity = resolve_openai_identity(
        request(
            user=" ",
            metadata={
                "user_id": " ",
                "project_id": None,
                "session_id": "",
            },
        ),
        x_session_id=None,
        new_session_id=lambda: "generated-session",
    )

    assert identity.user_id == "openwebui"
    assert identity.project_id == "openwebui"
    assert identity.session_id == "generated-session"


def test_project_scope_requires_non_blank_user_and_project():
    scope = resolve_project_scope(user_id=" alice ", project_id=" project-a ")

    assert scope.user_id == "alice"
    assert scope.project_id == "project-a"

    with pytest.raises(IdentityError, match="project_id must not be blank"):
        resolve_project_scope(user_id="alice", project_id=" ")
