from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

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
    CampaignAsset,
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
)
from codrut.modules.communications.service import CommunicationsService
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.session_cookie import SESSION_COOKIE_NAME


def _png_bytes(size: tuple[int, int] = (2, 2)) -> bytes:
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Comment", "private upload metadata")
    Image.new("RGB", size, color=(137, 5, 5)).save(
        output,
        format="PNG",
        pnginfo=metadata,
    )
    return output.getvalue()


def _principal(role: UserRole, user_id=None) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=user_id or uuid4(),
        email=f"{role.value}@example.com",
        role=role,
        terms_accepted_at=datetime.now(UTC),
        terms_version="privacy-2026-07-16",
        session_token="test-session",  # noqa: S106
    )


def _client_as(
    role: UserRole,
    settings: Settings | None = None,
    user_id=None,
    session=None,
    raise_server_exceptions: bool = True,
) -> TestClient:
    app = create_app()

    async def principal_override() -> SessionPrincipal:
        return _principal(role, user_id=user_id)

    app.dependency_overrides[current_principal] = principal_override
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    if session is not None:

        async def session_override():
            yield session

        app.dependency_overrides[db_session] = session_override
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def _mock_campaign_asset_repository(monkeypatch) -> dict[str, CampaignAsset]:
    assets: dict[str, CampaignAsset] = {}

    async def add_campaign_asset_override(self, asset: CampaignAsset):
        assets[asset.file_name] = asset
        return asset

    async def get_campaign_asset_override(
        self,
        file_name: str,
        *,
        owner_id,
        for_update: bool = False,
    ):
        del for_update
        asset = assets.get(file_name)
        return asset if asset is not None and asset.owner_id == owner_id else None

    async def delete_campaign_asset_override(self, asset: CampaignAsset):
        assets.pop(asset.file_name, None)

    monkeypatch.setattr(
        "codrut.modules.communications.repository.CommunicationsRepository.add_campaign_asset",
        add_campaign_asset_override,
    )
    monkeypatch.setattr(
        "codrut.modules.communications.repository.CommunicationsRepository.get_campaign_asset_by_file_name",
        get_campaign_asset_override,
    )
    monkeypatch.setattr(
        "codrut.modules.communications.repository.CommunicationsRepository.delete_campaign_asset_record",
        delete_campaign_asset_override,
    )
    return assets


class FakeScalarOneResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


def test_email_send_capacity_is_available_to_trainer() -> None:
    result = MagicMock()
    result.scalar_one.return_value = 375
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    client = _client_as(
        UserRole.trainer,
        settings=Settings(_env_file=None, email_daily_send_cap=2000),
        session=session,
    )

    response = client.get("/api/communications/send-capacity")

    assert response.status_code == 200
    assert response.json() == {
        "daily_cap": 2000,
        "used_today": 375,
        "remaining_today": 1625,
    }


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


def test_campaign_membership_reads_require_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.get(f"/api/communications/campaigns/{uuid4()}/recipients")

    assert response.status_code == 403


def test_campaign_membership_updates_require_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.put(
        f"/api/communications/campaigns/{uuid4()}/recipients",
        json={"recipient_ids": [str(uuid4())]},
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


def test_campaign_recipient_restore_passes_runtime_settings(monkeypatch) -> None:
    trainer_id = uuid4()
    recipient_id = uuid4()
    settings = Settings()
    recipient = CampaignRecipient(
        id=recipient_id,
        owner_id=trainer_id,
        email="ana@example.com",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.active,
    )
    restore = AsyncMock(return_value=recipient)
    monkeypatch.setattr(
        CommunicationsService,
        "restore_campaign_recipient",
        restore,
    )
    session = MagicMock()
    session.commit = AsyncMock()
    client = _client_as(
        UserRole.trainer,
        settings=settings,
        user_id=trainer_id,
        session=session,
    )

    response = client.post(
        f"/api/communications/campaigns/recipients/{recipient_id}/restore"
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(recipient_id),
        "status": "active",
        "archived_at": None,
        "purge_after": None,
    }
    restore.assert_awaited_once_with(
        recipient_id,
        owner_id=trainer_id,
        settings=settings,
    )
    session.commit.assert_awaited_once()


def test_campaign_delete_requires_trainer_role() -> None:
    client = _client_as(UserRole.participant)

    response = client.delete(f"/api/communications/campaigns/{uuid4()}")

    assert response.status_code == 403


def test_trainer_can_list_campaign_membership(monkeypatch) -> None:
    campaign_id = uuid4()
    recipient_id = uuid4()
    trainer_id = uuid4()

    async def list_memberships_override(self, campaign_id_arg, *, owner_id=None):
        assert campaign_id_arg == campaign_id
        assert owner_id == trainer_id
        return [
            {
                "id": str(recipient_id),
                "company": "Demo Co",
                "firstName": "Ana",
                "lastName": "Pop",
                "email": "ana@example.com",
                "clientType": "tip_2",
                "status": "ready",
                "openCount": 0,
                "clickCount": 0,
                "viewCount": 0,
                "replyCount": 0,
                "calendlyClickCount": 0,
                "membershipSource": None,
            }
        ]

    monkeypatch.setattr(
        CommunicationsService,
        "list_campaign_recipient_memberships",
        list_memberships_override,
    )
    client = _client_as(UserRole.trainer, user_id=trainer_id)

    response = client.get(f"/api/communications/campaigns/{campaign_id}/recipients")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(recipient_id)


def test_trainer_can_replace_campaign_membership(monkeypatch) -> None:
    campaign_id = uuid4()
    recipient_id = uuid4()
    trainer_id = uuid4()

    async def replace_memberships_override(self, campaign_id_arg, payload, *, owner_id=None):
        assert campaign_id_arg == campaign_id
        assert payload.recipient_ids == [recipient_id]
        assert owner_id == trainer_id
        return [
            {
                "id": str(recipient_id),
                "company": "Demo Co",
                "firstName": "Ana",
                "lastName": "Pop",
                "email": "ana@example.com",
                "clientType": "tip_2",
                "status": "ready",
                "openCount": 0,
                "clickCount": 0,
                "viewCount": 0,
                "replyCount": 0,
                "calendlyClickCount": 0,
                "membershipSource": "manual",
            }
        ]

    monkeypatch.setattr(
        CommunicationsService,
        "replace_campaign_recipient_memberships",
        replace_memberships_override,
    )
    client = _client_as(UserRole.trainer, user_id=trainer_id)

    response = client.put(
        f"/api/communications/campaigns/{campaign_id}/recipients",
        json={"recipient_ids": [str(recipient_id)]},
    )

    assert response.status_code == 200
    assert response.json()[0]["membershipSource"] == "manual"


def test_trainer_can_list_campaigns(monkeypatch) -> None:
    campaign_id = uuid4()
    trainer_id = uuid4()

    async def list_campaigns_override(self, *, owner_id=None) -> list[Campaign]:
        assert owner_id == trainer_id
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
    client = _client_as(UserRole.trainer, user_id=trainer_id)

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


def test_trainer_can_upload_campaign_asset(tmp_path, monkeypatch) -> None:
    settings = Settings(
        public_app_url="https://codrut.andreivacaru.ro",
        campaign_asset_dir=str(tmp_path),
        campaign_asset_public_path="/api/campaign-assets",
    )
    assets = _mock_campaign_asset_repository(monkeypatch)
    session = AsyncMock()
    client = _client_as(UserRole.trainer, settings, session=session)

    response = client.post(
        "/api/communications/campaign-assets",
        content=_png_bytes(),
        headers={"content-type": "image/png", "x-file-name": "thumbnail.png"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["url"].startswith("https://codrut.andreivacaru.ro/api/campaign-assets/")
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] > 0
    assert body["file_name"].endswith(".png")
    assert assets[body["file_name"]].status == "staged"
    with Image.open(tmp_path / body["file_name"]) as image:
        assert image.size == (2, 2)
        assert "Comment" not in image.info


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


def test_campaign_asset_upload_rejects_oversized_dimensions(tmp_path) -> None:
    settings = Settings(
        campaign_asset_dir=str(tmp_path),
        campaign_asset_max_width=1,
    )
    client = _client_as(UserRole.trainer, settings)

    response = client.post(
        "/api/communications/campaign-assets",
        content=_png_bytes((2, 1)),
        headers={"content-type": "image/png", "x-file-name": "wide.png"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "campaign_asset_dimensions_invalid"


def test_campaign_asset_upload_rejects_corrupt_image_with_valid_signature(tmp_path) -> None:
    settings = Settings(campaign_asset_dir=str(tmp_path))
    client = _client_as(UserRole.trainer, settings)

    response = client.post(
        "/api/communications/campaign-assets",
        content=b"\x89PNG\r\n\x1a\nnot-an-image",
        headers={"content-type": "image/png", "x-file-name": "corrupt.png"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "campaign_asset_decode_invalid"


def test_campaign_asset_upload_cleans_file_when_persistence_fails(
    tmp_path,
    monkeypatch,
) -> None:
    async def fail_asset_persistence(_self, _asset):
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(
        "codrut.modules.communications.repository.CommunicationsRepository.add_campaign_asset",
        fail_asset_persistence,
    )
    session = AsyncMock()
    with _client_as(
        UserRole.trainer,
        Settings(campaign_asset_dir=str(tmp_path)),
        user_id=uuid4(),
        session=session,
        raise_server_exceptions=False,
    ) as client:
        response = client.post(
            "/api/communications/campaign-assets",
            content=_png_bytes(),
            headers={"content-type": "image/png", "x-file-name": "failed.png"},
        )

    assert response.status_code == 500
    assert list(tmp_path.iterdir()) == []
    session.rollback.assert_awaited_once()


def test_trainer_can_delete_owned_campaign_asset(tmp_path, monkeypatch) -> None:
    settings = Settings(campaign_asset_dir=str(tmp_path))
    assets = _mock_campaign_asset_repository(monkeypatch)
    session = AsyncMock()
    with _client_as(
        UserRole.trainer,
        settings,
        user_id=uuid4(),
        session=session,
    ) as client:
        upload = client.post(
            "/api/communications/campaign-assets",
            content=_png_bytes(),
            headers={"content-type": "image/png", "x-file-name": "owned.png"},
        )

        response = client.delete(
            f"/api/communications/campaign-assets/{upload.json()['file_name']}"
        )

    assert response.status_code == 204
    assert not (tmp_path / upload.json()["file_name"]).exists()
    assert assets == {}


def test_trainer_cannot_delete_another_owners_campaign_asset(tmp_path, monkeypatch) -> None:
    settings = Settings(campaign_asset_dir=str(tmp_path))
    assets = _mock_campaign_asset_repository(monkeypatch)
    session = AsyncMock()
    owner_id = uuid4()
    other_owner_id = uuid4()
    with _client_as(
        UserRole.trainer,
        settings,
        user_id=owner_id,
        session=session,
    ) as client:
        upload = client.post(
            "/api/communications/campaign-assets",
            content=_png_bytes(),
            headers={"content-type": "image/png", "x-file-name": "owned.png"},
        )

        async def other_principal_override() -> SessionPrincipal:
            return _principal(UserRole.trainer, user_id=other_owner_id)

        client.app.dependency_overrides[current_principal] = other_principal_override
        response = client.delete(
            f"/api/communications/campaign-assets/{upload.json()['file_name']}"
        )

        assert response.status_code == 404
        assert (tmp_path / upload.json()["file_name"]).exists()

        async def owner_principal_override() -> SessionPrincipal:
            return _principal(UserRole.trainer, user_id=owner_id)

        client.app.dependency_overrides[current_principal] = owner_principal_override
        cleanup = client.delete(
            f"/api/communications/campaign-assets/{upload.json()['file_name']}"
        )

    assert cleanup.status_code == 204
    assert assets == {}


def test_trainer_cannot_delete_attached_campaign_asset(tmp_path, monkeypatch) -> None:
    settings = Settings(campaign_asset_dir=str(tmp_path))
    assets = _mock_campaign_asset_repository(monkeypatch)
    session = AsyncMock()
    owner_id = uuid4()
    with _client_as(
        UserRole.trainer,
        settings,
        user_id=owner_id,
        session=session,
    ) as client:
        upload = client.post(
            "/api/communications/campaign-assets",
            content=_png_bytes(),
            headers={"content-type": "image/png", "x-file-name": "attached.png"},
        )
        file_name = upload.json()["file_name"]
        assets[file_name].campaign_id = uuid4()
        assets[file_name].status = "attached"

        blocked = client.delete(f"/api/communications/campaign-assets/{file_name}")

        assert blocked.status_code == 400
        assert blocked.json()["error"]["code"] == "campaign_asset_attached"
        assert (tmp_path / file_name).exists()

        assets[file_name].campaign_id = None
        assets[file_name].status = "staged"
        cleanup = client.delete(f"/api/communications/campaign-assets/{file_name}")

    assert cleanup.status_code == 204


def test_campaign_event_recording_rejects_unknown_event_type() -> None:
    client = _client_as(UserRole.trainer)

    response = client.post(
        f"/api/communications/campaigns/recipients/{uuid4()}/events",
        json={"event_type": "not_a_real_event"},
    )

    assert response.status_code == 422


def test_campaign_event_recording_requires_csrf_for_session_cookie(monkeypatch) -> None:
    async def record_event_override(self, recipient_id, payload, *, owner_id=None):
        raise AssertionError("CSRF middleware should reject before route execution")

    monkeypatch.setattr(
        CommunicationsService,
        "record_campaign_recipient_event",
        record_event_override,
    )
    client = _client_as(UserRole.trainer)
    client.cookies.set(SESSION_COOKIE_NAME, "test-session")

    response = client.post(
        f"/api/communications/campaigns/recipients/{uuid4()}/events",
        json={"event_type": "replied"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_campaign_calendly_tracking_redirect_is_public_and_records_event() -> None:
    app = create_app()
    recipient_id = uuid4()
    owner_id = uuid4()
    recipient = CampaignRecipient(
        id=recipient_id,
        owner_id=owner_id,
        email="ceo@example.com",
        contact_name="Ana Director",
        organization_name="Compania B",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.active,
    )
    settings = Settings(
        public_app_url="https://codrut.andreivacaru.ro",
        email_from_name="Cody Test",
    )
    session = MagicMock()
    session.execute = AsyncMock(return_value=FakeScalarOneResult(recipient))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    token = create_campaign_tracking_token(
        CampaignTrackingClaims(
            recipient_id=recipient_id,
            owner_id=owner_id,
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
    owner_id = uuid4()
    recipient = CampaignRecipient(
        id=recipient_id,
        owner_id=owner_id,
        email="ceo@example.com",
        contact_name="Ana Director",
        organization_name="Compania B",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.active,
    )
    settings = Settings(
        public_app_url="https://codrut.andreivacaru.ro",
        email_from_name="Cody Test",
    )
    session = MagicMock()
    session.execute = AsyncMock(return_value=FakeScalarOneResult(recipient))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    token = create_campaign_recipient_action_token(
        CampaignRecipientActionClaims(
            recipient_id=recipient_id,
            owner_id=owner_id,
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
    assert "Cody Test" in response.text
    assert "ceo@example.com" in response.text
    assert recipient.status == CampaignRecipientStatus.active
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_campaign_unsubscribe_post_updates_recipient() -> None:
    app = create_app()
    recipient_id = uuid4()
    owner_id = uuid4()
    recipient = CampaignRecipient(
        id=recipient_id,
        owner_id=owner_id,
        email="ceo@example.com",
        contact_name="Ana Director",
        organization_name="Compania B",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.active,
    )
    settings = Settings(
        public_app_url="https://codrut.andreivacaru.ro",
        email_from_name="Cody Test",
    )
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            FakeScalarOneResult(recipient),
            FakeScalarOneResult(None),
            FakeScalarOneResult(None),
            FakeScalarOneResult(None),
        ]
    )
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    token = create_campaign_recipient_action_token(
        CampaignRecipientActionClaims(
            recipient_id=recipient_id,
            owner_id=owner_id,
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
    assert "Cody Test" in response.text
    assert "ceo@example.com" in response.text
    assert recipient.status == CampaignRecipientStatus.unsubscribed
    assert session.flush.await_count == 2
    session.commit.assert_awaited_once()
