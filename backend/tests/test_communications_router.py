from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from codrut.api.dependencies import current_principal
from codrut.main import create_app
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal


def _principal(role: UserRole) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=uuid4(),
        email=f"{role.value}@example.com",
        role=role,
        terms_accepted_at=datetime.now(UTC),
        terms_version="privacy-2026-06-12",
        session_token="test-session",  # noqa: S106
    )


def _client_as(role: UserRole) -> TestClient:
    app = create_app()

    async def principal_override() -> SessionPrincipal:
        return _principal(role)

    app.dependency_overrides[current_principal] = principal_override
    return TestClient(app)


def test_test_email_requires_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.post(
        "/api/communications/test-email",
        json={"to": "recipient@example.com"},
    )

    assert response.status_code == 403


def test_trainer_can_send_manual_test_email_in_non_production() -> None:
    client = _client_as(UserRole.trainer)

    response = client.post(
        "/api/communications/test-email",
        json={"to": "recipient@example.com"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] in {"test", "smtp"}
    assert body["status"] == "accepted"
    assert body["recipient"] == "recipient@example.com"


def test_email_template_reads_require_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.get("/api/communications/templates")

    assert response.status_code == 403
