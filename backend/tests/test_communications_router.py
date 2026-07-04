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
    Campaign,
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
)
from codrut.modules.communications.service import CommunicationsService
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


def test_campaign_recipient_update_requires_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.patch(
        f"/api/communications/campaigns/recipients/{uuid4()}",
        json={"contact_name": "Ana Director"},
    )

    assert response.status_code == 403


def test_campaign_recipient_delete_requires_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.delete(f"/api/communications/campaigns/recipients/{uuid4()}")

    assert response.status_code == 403


def test_campaign_delete_requires_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.delete(f"/api/communications/campaigns/{uuid4()}")

    assert response.status_code == 403


def test_trainer_can_list_campaigns(monkeypatch) -> None:
    campaign_id = uuid4()

    async def list_campaigns_override(self) -> list[Campaign]:
        return [
            Campaign(
                id=campaign_id,
                name="Campanie pilot",
                segment=CampaignRecipientSegment.potential_customer,
                status=CampaignStatus.ready,
                subject="Salut",
                html_body="<p>Salut</p>",
                text_body="Salut",
            )
        ]

    monkeypatch.setattr(CommunicationsService, "list_campaigns", list_campaigns_override)
    client = _client_as(UserRole.trainer)

    response = client.get("/api/communications/campaigns")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(campaign_id)
    assert response.json()[0]["name"] == "Campanie pilot"


def test_campaign_asset_upload_requires_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.post(
        "/api/communications/campaign-assets",
        content=b"\x89PNG\r\n\x1a\nfake",
        headers={"content-type": "image/png", "x-file-name": "thumb.png"},
    )

    assert response.status_code == 403


def test_trainer_can_upload_campaign_asset(tmp_path) -> None:
    settings = Settings(
        public_app_url="https://codrut.andreivacaru.ro",
        campaign_asset_dir=str(tmp_path),
        campaign_asset_public_path="/api/campaign-assets",
    )
    client = _client_as(UserRole.trainer, settings)

    response = client.post(
        "/api/communications/campaign-assets",
        content=b"\x89PNG\r\n\x1a\nfake",
        headers={"content-type": "image/png", "x-file-name": "thumbnail.png"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["url"].startswith("https://codrut.andreivacaru.ro/api/campaign-assets/")
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == 12
    assert body["file_name"].endswith(".png")
    assert (tmp_path / body["file_name"]).read_bytes() == b"\x89PNG\r\n\x1a\nfake"


def test_campaign_asset_upload_rejects_unsupported_file_type(tmp_path) -> None:
    settings = Settings(campaign_asset_dir=str(tmp_path))
    client = _client_as(UserRole.trainer, settings)

    response = client.post(
        "/api/communications/campaign-assets",
        content=b"<svg></svg>",
        headers={"content-type": "image/svg+xml", "x-file-name": "thumb.svg"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "campaign_asset_type_unsupported"


def test_campaign_asset_upload_rejects_mismatched_signature(tmp_path) -> None:
    settings = Settings(campaign_asset_dir=str(tmp_path))
    client = _client_as(UserRole.trainer, settings)

    response = client.post(
        "/api/communications/campaign-assets",
        content=b"not really a png",
        headers={"content-type": "image/png", "x-file-name": "thumb.png"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "campaign_asset_signature_invalid"


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


def test_campaign_unsubscribe_get_is_public_confirmation_without_mutation() -> None:
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
    assert "Confirmă dezabonarea" in response.text
    assert "ceo@example.com" in response.text
    assert recipient.status == CampaignRecipientStatus.active
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_campaign_unsubscribe_post_updates_recipient() -> None:
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

    async def db_override():
        yield session

    app.dependency_overrides[db_session] = db_override
    app.dependency_overrides[get_settings] = lambda: settings

    response = TestClient(app).post(
        f"/api/communications/campaigns/unsubscribe/{token}",
    )

    assert response.status_code == 200
    assert "Dezabonare confirmată" in response.text
    assert "ceo@example.com" in response.text
    assert recipient.status == CampaignRecipientStatus.unsubscribed
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
