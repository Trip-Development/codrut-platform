from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from codrut.api.dependencies import current_principal, db_session
from codrut.core.errors import DomainError
from codrut.main import create_app
from codrut.modules.forms.schemas import QuestionnaireDefinitionResponse
from codrut.modules.forms.service import FormsService
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.service import IdentityService


def _principal(
    role: UserRole,
    *,
    terms_version: str = "privacy-2026-07-16",
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

    class NoOpSession:
        async def commit(self) -> None:
            return None

    async def principal_override() -> SessionPrincipal:
        return _principal(role)

    async def db_override():
        yield NoOpSession()

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


def test_participant_cannot_list_questionnaire_definitions() -> None:
    client = _client_as(UserRole.participant)

    response = client.get("/api/forms/definitions")

    assert response.status_code == 403


def test_participant_can_read_an_assignment_authorized_definition_by_key(
    monkeypatch,
) -> None:
    async def assigned_definition(
        _service,
        _user_id,
        key,
        *,
        version=None,
        participant_profile_id=None,
        project_id=None,
        cycle_id=None,
        allowed_assignment_ids=None,
    ) -> QuestionnaireDefinitionResponse:
        assert key == "lencioni"
        assert version is None
        assert participant_profile_id is None
        assert project_id is None
        assert cycle_id is None
        assert allowed_assignment_ids is None
        return QuestionnaireDefinitionResponse(
            key="lencioni",
            version=3,
            title="Evaluare de echipă",
            description="",
            schema={"schema_version": "questionnaire.v1", "sections": []},
        )

    monkeypatch.setattr(
        FormsService,
        "get_participant_definition_by_key",
        assigned_definition,
    )
    client = _client_as(UserRole.participant)

    response = client.get("/api/forms/definitions/lencioni")

    assert response.status_code == 200
    assert response.json()["key"] == "lencioni"
    assert "scoring" not in response.json()["schema"]


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


def test_assignment_response_routes_require_participant_role() -> None:
    client = _client_as(UserRole.trainer)

    response = client.get(f"/api/forms/assignments/{uuid4()}/response")

    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "http_403"
    assert error["message"] == "Sesiunea activă nu este un cont de participant."
    assert error["request_id"]


def test_secure_assignment_response_routes_require_session() -> None:
    app = create_app()

    async def db_override():
        yield object()

    app.dependency_overrides[db_session] = db_override

    response = TestClient(app).get(
        f"/api/forms/secure-links/not-a-token/assignments/{uuid4()}/response"
    )

    assert response.status_code == 401


SECURE_FORM_ROUTES = (
    ("get", "/api/forms/secure-links/invite-token/assignments/{assignment_id}/response", None),
    (
        "get",
        "/api/forms/secure-links/invite-token/assignments/{assignment_id}/definition",
        None,
    ),
    (
        "put",
        "/api/forms/secure-links/invite-token/assignments/{assignment_id}/response",
        {"answers": {}},
    ),
    (
        "post",
        "/api/forms/secure-links/invite-token/assignments/{assignment_id}/response/submit",
        {"answers": {}},
    ),
)


@pytest.mark.parametrize(("method", "path_template", "payload"), SECURE_FORM_ROUTES)
def test_secure_assignment_routes_require_persisted_consent(
    monkeypatch,
    method: str,
    path_template: str,
    payload: dict | None,
) -> None:
    async def reject_missing_consent(
        _service,
        principal: SessionPrincipal,
        invite_token: str,
    ) -> None:
        assert principal.role == UserRole.participant
        assert invite_token == "invite-token"  # noqa: S105
        raise DomainError("Consent is required.", code="terms_required")

    monkeypatch.setattr(
        IdentityService,
        "require_secure_link_consent",
        reject_missing_consent,
    )
    client = _client_as(UserRole.participant)
    path = path_template.format(assignment_id=uuid4())

    request = getattr(client, method)
    response = request(path) if payload is None else request(path, json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "terms_required"


@pytest.mark.parametrize(("method", "path_template", "payload"), SECURE_FORM_ROUTES)
def test_secure_assignment_routes_require_current_legal_version(
    monkeypatch,
    method: str,
    path_template: str,
    payload: dict | None,
) -> None:
    consent_check = AsyncMock()
    monkeypatch.setattr(
        IdentityService,
        "require_secure_link_consent",
        consent_check,
    )
    app = create_app()

    class NoOpSession:
        async def commit(self) -> None:
            return None

    async def principal_override() -> SessionPrincipal:
        return _principal(UserRole.participant, terms_version="retired-version")

    async def db_override():
        yield NoOpSession()

    app.dependency_overrides[current_principal] = principal_override
    app.dependency_overrides[db_session] = db_override
    client = TestClient(app)
    path = path_template.format(assignment_id=uuid4())

    request = getattr(client, method)
    response = request(path) if payload is None else request(path, json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "terms_required"
    consent_check.assert_not_awaited()
