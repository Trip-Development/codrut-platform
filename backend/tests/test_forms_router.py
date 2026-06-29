from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from codrut.api.dependencies import current_principal, db_session
from codrut.main import create_app
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal


def _principal(
    role: UserRole,
    *,
    terms_version: str = "privacy-2026-06-12",
) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=uuid4(),
        email=f"{role.value}@example.com",
        role=role,
        terms_accepted_at=datetime.now(UTC),
        terms_version=terms_version,
        session_token="test-session",  # noqa: S106
    )


def _client_as(role: UserRole) -> TestClient:
    app = create_app()

    async def principal_override() -> SessionPrincipal:
        return _principal(role)

    async def db_override():
        yield None

    app.dependency_overrides[current_principal] = principal_override
    app.dependency_overrides[db_session] = db_override
    return TestClient(app)


def test_questionnaire_definition_reads_require_authentication() -> None:
    app = create_app()

    async def db_override():
        yield None

    app.dependency_overrides[db_session] = db_override

    response = TestClient(app).get("/api/forms/definitions")

    assert response.status_code == 401


def test_participant_cannot_list_retired_questionnaire_definitions() -> None:
    client = _client_as(UserRole.participant)

    response = client.get("/api/forms/definitions?include_retired=true")

    assert response.status_code == 403


def test_participant_onboarding_requires_current_terms() -> None:
    app = create_app()

    async def principal_override() -> SessionPrincipal:
        return _principal(UserRole.participant, terms_version="old-terms")

    async def db_override():
        yield None

    app.dependency_overrides[current_principal] = principal_override
    app.dependency_overrides[db_session] = db_override

    response = TestClient(app).get("/api/forms/participant/onboarding")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "terms_required"
