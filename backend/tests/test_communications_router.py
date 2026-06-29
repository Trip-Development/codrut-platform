from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from codrut.api.dependencies import current_principal, db_session
from codrut.core.config import Settings, get_settings
from codrut.main import create_app
from codrut.modules.communications.campaign_tracking import (
    CampaignRecipientActionClaims,
    CampaignTrackingClaims,
    create_campaign_recipient_action_token,
    create_campaign_tracking_token,
)
from codrut.modules.communications.models import (
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
)
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


def _client_as(role: UserRole, settings: Settings | None = None) -> TestClient:
    app = create_app()

    async def principal_override() -> SessionPrincipal:
        return _principal(role)

    app.dependency_overrides[current_principal] = principal_override
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


class FakeScalarOneResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


def test_test_email_requires_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.post(
        "/api/communications/test-email",
        json={"to": "recipient@example.com"},
    )

    assert response.status_code == 403


def test_trainer_can_send_manual_test_email_in_non_production() -> None:
    client = _client_as(UserRole.trainer, Settings(email_provider="test"))

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


def test_campaign_event_recording_requires_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.post(
        f"/api/communications/campaigns/recipients/{uuid4()}/events",
        json={"event_type": "replied"},
    )

    assert response.status_code == 403


def test_campaign_send_requires_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.post(
        f"/api/communications/campaigns/{uuid4()}/send",
        json={"dry_run": True},
    )

    assert response.status_code == 403


def test_campaign_event_recording_rejects_unknown_event_type() -> None:
    client = _client_as(UserRole.trainer)

    response = client.post(
        f"/api/communications/campaigns/recipients/{uuid4()}/events",
        json={"event_type": "not_a_real_event"},
    )

    assert response.status_code == 422


def test_campaign_calendly_tracking_redirect_is_public_and_records_event() -> None:
    app = create_app()
    recipient_id = uuid4()
    recipient = CampaignRecipient(
        id=recipient_id,
        email="ceo@example.com",
        contact_name="Ana Director",
        organization_name="Compania B",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.active,
    )
    settings = Settings(public_app_url="https://codrut.andreivacaru.ro")
    session = MagicMock()
    session.execute = AsyncMock(return_value=FakeScalarOneResult(recipient))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    token = create_campaign_tracking_token(
        CampaignTrackingClaims(
            recipient_id=recipient_id,
            target_url="https://calendly.com/codrut/demo",
            event_type="calendly_clicked",
            variant_key="variant_a",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        ),
        settings,
    )

    async def principal_override() -> SessionPrincipal:
        raise AssertionError("tracking redirect must not require authenticated session")

    async def db_override():
        yield session

    app.dependency_overrides[current_principal] = principal_override
    app.dependency_overrides[db_session] = db_override
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get(
        f"/api/communications/campaigns/track/calendly/{token}",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "https://calendly.com/codrut/demo"
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    saved_event = session.add.call_args.args[0]
    assert saved_event.recipient_id == recipient_id
    assert saved_event.event_type == "calendly_clicked"
    assert saved_event.variant_key == "variant_a"


def test_campaign_unsubscribe_is_public_and_updates_recipient() -> None:
    app = create_app()
    recipient_id = uuid4()
    recipient = CampaignRecipient(
        id=recipient_id,
        email="ceo@example.com",
        contact_name="Ana Director",
        organization_name="Compania B",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.active,
    )
    settings = Settings(public_app_url="https://codrut.andreivacaru.ro")
    session = MagicMock()
    session.execute = AsyncMock(return_value=FakeScalarOneResult(recipient))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    token = create_campaign_recipient_action_token(
        CampaignRecipientActionClaims(
            recipient_id=recipient_id,
            action="unsubscribe",
        ),
        settings,
    )

    async def principal_override() -> SessionPrincipal:
        raise AssertionError("unsubscribe must not require authenticated session")

    async def db_override():
        yield session

    app.dependency_overrides[current_principal] = principal_override
    app.dependency_overrides[db_session] = db_override
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).get(
        f"/api/communications/campaigns/unsubscribe/{token}",
    )

    assert response.status_code == 200
    assert response.json() == {"status": "unsubscribed", "email": "ceo@example.com"}
    assert recipient.status == CampaignRecipientStatus.unsubscribed
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
