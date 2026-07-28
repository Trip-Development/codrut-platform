import smtplib
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from codrut.contracts.emails import (
    EmailAddress,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
    EmailSendResult,
)
from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.assignments import models as assignment_models  # noqa: F401
from codrut.modules.communications.delivery_events import DeliveryEventService
from codrut.modules.communications.email_provider import (
    BrevoEmailProvider,
    SmtpEmailProvider,
    _retry_after_seconds,
    build_email_provider,
)
from codrut.modules.communications.models import (
    Campaign,
    CampaignAsset,
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
    EmailSend,
    EmailSendStatus,
)
from codrut.modules.communications.schemas import (
    BrevoWebhookEvent,
    CampaignCreateRequest,
    CampaignRecipientEventCreateRequest,
    CampaignRecipientUpdateRequest,
    CampaignSendRequest,
    CampaignUpdateRequest,
)
from codrut.modules.communications.service import (
    CommunicationsService,
    EmailOutboxProcessor,
    _bind_campaign_asset,
    _campaign_result_from_existing_send,
    _email_message_from_outbox_payload,
    _email_outbox_assignment_ids,
    _email_outbox_payload,
    _email_outbox_payload_fingerprint,
    _email_outbox_reminder_assignment_ids,
    _email_result_from_existing_send,
    _require_delivery_owner_id,
)
from codrut.modules.companies import models as company_models  # noqa: F401
from codrut.modules.forms import models as form_models  # noqa: F401
from codrut.modules.identity import models as identity_models  # noqa: F401

OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000111")
OTHER_OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000222")
SETTINGS = Settings(
    public_app_url="https://app.example.test",
    email_legal_address="Strada Test 1, Bucuresti",
)


def campaign(
    *,
    status: CampaignStatus = CampaignStatus.ready,
    segment: CampaignRecipientSegment | None = CampaignRecipientSegment.potential_customer,
    owner_id: uuid.UUID | None = OWNER_ID,
) -> Campaign:
    return Campaign(
        id=uuid.uuid4(),
        owner_id=owner_id,
        name="Pilot leadership",
        segment=segment,
        status=status,
        subject="Salut ${first_name}",
        html_body="<p>Mesaj pentru ${organization_name}</p>",
        text_body="Mesaj pentru ${organization_name}",
        recipient_memberships_initialized=True,
    )


def recipient(
    *,
    status: CampaignRecipientStatus = CampaignRecipientStatus.active,
    segment: CampaignRecipientSegment = CampaignRecipientSegment.potential_customer,
    email: str | None = "ana@example.test",
    owner_id: uuid.UUID | None = OWNER_ID,
) -> CampaignRecipient:
    return CampaignRecipient(
        id=uuid.uuid4(),
        owner_id=owner_id,
        email=email,
        contact_name="Ana Popescu",
        organization_name="Exemplu SRL",
        segment=segment,
        status=status,
    )


def email_send(
    *,
    status: EmailSendStatus = EmailSendStatus.queued,
    payload: dict[str, object] | None = None,
) -> EmailSend:
    message_payload = payload or _email_outbox_payload(
        EmailMessage(
            to=EmailAddress("ana@example.test"),
            subject="Salut",
            html_body="<p>Mesaj</p>",
            text_body="Mesaj",
        )
    )
    return EmailSend(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        recipient_email="ana@example.test",
        template_key="campaign",
        template_version=1,
        provider="test",
        idempotency_key=uuid.uuid4().hex,
        payload_fingerprint=_email_outbox_payload_fingerprint(message_payload),
        message_payload=message_payload,
        attempt_count=1,
        max_attempts=5,
        next_attempt_at=datetime.now(UTC),
        lease_token=f"lease-{uuid.uuid4()}",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        status=status,
    )


def service_with(repository: object) -> CommunicationsService:
    service = CommunicationsService()
    service.repository = cast(Any, repository)
    return service


def assert_domain_code(exc_info: pytest.ExceptionInfo[DomainError], code: str) -> None:
    assert exc_info.value.code == code


def test_campaign_delivery_requires_an_owner() -> None:
    with pytest.raises(DomainError) as exc_info:
        _require_delivery_owner_id(None)

    assert_domain_code(exc_info, "email_delivery_owner_required")


async def test_managed_campaign_asset_cannot_cross_owner_or_campaign_boundaries() -> None:
    current_campaign = campaign()
    repository = SimpleNamespace(get_campaign_asset_by_url=AsyncMock(return_value=None))

    with pytest.raises(DomainError) as missing_exc:
        await _bind_campaign_asset(
            cast(Any, repository),
            current_campaign,
            previous_url=None,
            next_url="https://app.example.test/api/campaign-assets/not-owned.png",
            owner_id=OWNER_ID,
            settings=SETTINGS,
        )
    assert_domain_code(missing_exc, "campaign_asset_not_owned")

    foreign_asset = CampaignAsset(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        campaign_id=uuid.uuid4(),
        file_name="foreign.png",
        public_url="https://app.example.test/api/campaign-assets/foreign.png",
        content_type="image/png",
        size_bytes=10,
        status="attached",
    )
    repository.get_campaign_asset_by_url.return_value = foreign_asset
    with pytest.raises(DomainError) as attached_exc:
        await _bind_campaign_asset(
            cast(Any, repository),
            current_campaign,
            previous_url=None,
            next_url=foreign_asset.public_url,
            owner_id=OWNER_ID,
            settings=SETTINGS,
        )
    assert_domain_code(attached_exc, "campaign_asset_already_attached")


async def test_replacing_a_managed_asset_releases_old_asset_and_attaches_new_one() -> None:
    current_campaign = campaign()
    old_asset = SimpleNamespace(campaign_id=current_campaign.id, status="attached")
    new_asset = SimpleNamespace(campaign_id=None, status="staged")
    repository = SimpleNamespace(
        get_campaign_asset_by_url=AsyncMock(side_effect=[old_asset, new_asset])
    )

    await _bind_campaign_asset(
        cast(Any, repository),
        current_campaign,
        previous_url="https://app.example.test/api/campaign-assets/old.png",
        next_url="https://app.example.test/api/campaign-assets/new.png",
        owner_id=OWNER_ID,
        settings=SETTINGS,
    )

    assert (old_asset.campaign_id, old_asset.status) == (None, "staged")
    assert (new_asset.campaign_id, new_asset.status) == (current_campaign.id, "attached")


async def test_campaign_creation_retains_incomplete_video_as_draft() -> None:
    repository = SimpleNamespace(add_campaign=AsyncMock(side_effect=lambda value: value))
    service = service_with(repository)

    created = await service.create_campaign(
        CampaignCreateRequest(
            name="Video draft",
            segment="potential_customer",
            subject="Salut",
            html_body="<p>Mesaj</p>",
            text_body="Mesaj",
            video_url="https://video.example.test/watch/1",
        ),
        owner_id=OWNER_ID,
        settings=SETTINGS,
    )

    assert created.status == CampaignStatus.draft
    assert created.thumbnail_url is None
    repository.add_campaign.assert_awaited_once()


async def test_campaign_update_rejects_foreign_or_invalid_campaign() -> None:
    repository = SimpleNamespace(get_campaign=AsyncMock(return_value=None))
    service = service_with(repository)

    with pytest.raises(DomainError) as missing_exc:
        await service.update_campaign(
            uuid.uuid4(),
            CampaignUpdateRequest(name="Updated"),
            owner_id=OTHER_OWNER_ID,
        )
    assert_domain_code(missing_exc, "campaign_not_found")
    repository.get_campaign.assert_awaited_once_with(
        repository.get_campaign.await_args.args[0], owner_id=OTHER_OWNER_ID
    )

    current_campaign = campaign()
    repository.get_campaign.return_value = current_campaign
    with pytest.raises(DomainError) as status_exc:
        await service.update_campaign(
            current_campaign.id,
            CampaignUpdateRequest(status="not-a-status"),
            owner_id=OWNER_ID,
        )
    assert_domain_code(status_exc, "campaign_status_invalid")


async def test_campaign_update_applies_explicit_fields_and_flushes() -> None:
    current_campaign = campaign(segment=None)
    repository = SimpleNamespace(
        get_campaign=AsyncMock(return_value=current_campaign),
        flush=AsyncMock(),
    )
    service = service_with(repository)

    updated = await service.update_campaign(
        current_campaign.id,
        CampaignUpdateRequest(
            name="  Campanie actualizata  ",
            segment="past_customer",
            status="paused",
            subject="Subiect nou",
            html_body="<p>Continut nou</p>",
            text_body="Continut nou",
            video_url="https://video.example.test/watch/2",
            thumbnail_url="https://cdn.example.test/thumb.png",
            landing_page_url="https://landing.example.test/pilot",
        ),
        owner_id=OWNER_ID,
        settings=SETTINGS,
    )

    assert updated.name == "Campanie actualizata"
    assert updated.segment == CampaignRecipientSegment.past_customer
    assert updated.status == CampaignStatus.paused
    assert updated.subject == "Subiect nou"
    assert updated.video_url == "https://video.example.test/watch/2"
    repository.flush.assert_awaited_once()


@pytest.mark.parametrize(
    ("state", "video_url", "thumbnail_url", "expected_code"),
    [
        (None, None, None, "campaign_not_found"),
        (
            CampaignStatus.ready,
            "https://video.example.test/1",
            None,
            "campaign_video_assets_incomplete",
        ),
        (CampaignStatus.draft, None, None, "campaign_not_ready"),
    ],
)
async def test_campaign_send_reports_exact_readiness_failure(
    state: CampaignStatus | None,
    video_url: str | None,
    thumbnail_url: str | None,
    expected_code: str,
) -> None:
    current_campaign = None if state is None else campaign(status=state)
    if current_campaign is not None:
        current_campaign.video_url = video_url
        current_campaign.thumbnail_url = thumbnail_url
    repository = SimpleNamespace(get_campaign=AsyncMock(return_value=current_campaign))
    service = service_with(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.send_campaign(
            uuid.uuid4() if current_campaign is None else current_campaign.id,
            CampaignSendRequest(mode="all"),
            settings=SETTINGS,
            owner_id=OWNER_ID,
        )

    assert_domain_code(exc_info, expected_code)


async def test_campaign_send_requires_matching_recipients() -> None:
    current_campaign = campaign()
    repository = SimpleNamespace(
        get_campaign=AsyncMock(return_value=current_campaign),
        list_campaign_member_recipient_ids=AsyncMock(return_value=[]),
        list_campaign_member_recipients=AsyncMock(return_value=[]),
    )
    service = service_with(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.send_campaign(
            current_campaign.id,
            CampaignSendRequest(mode="all"),
            settings=SETTINGS,
            owner_id=OWNER_ID,
        )

    assert_domain_code(exc_info, "campaign_no_recipients")


async def test_campaign_dry_run_allows_mixed_segments_and_explains_suppression() -> None:
    current_campaign = campaign()
    wrong_segment = recipient(segment=CampaignRecipientSegment.past_customer)
    suppressed = recipient(status=CampaignRecipientStatus.suppressed)
    eligible = recipient(owner_id=None)
    repository = SimpleNamespace(
        get_campaign=AsyncMock(return_value=current_campaign),
        list_campaign_recipients_by_ids=AsyncMock(
            return_value=[wrong_segment, suppressed, eligible]
        ),
        count_accepted_sends_since=AsyncMock(return_value=0),
    )
    service = service_with(repository)

    result = await service.send_campaign(
        current_campaign.id,
        CampaignSendRequest(
            mode="selected",
            recipient_ids=[wrong_segment.id, suppressed.id, eligible.id],
            dry_run=True,
        ),
        settings=SETTINGS,
        owner_id=OWNER_ID,
    )

    assert [item.status for item in result.results] == ["dry_run", "skipped", "dry_run"]
    assert result.skipped == 3
    assert "suppressed" in cast(str, result.results[1].error).lower()


async def test_campaign_dry_run_uses_contacts_created_by_another_trainer() -> None:
    current_campaign = campaign()
    shared_recipient = recipient(owner_id=OTHER_OWNER_ID)
    repository = SimpleNamespace(
        get_campaign=AsyncMock(return_value=current_campaign),
        list_campaign_recipients_by_ids=AsyncMock(return_value=[shared_recipient]),
        count_accepted_sends_since=AsyncMock(return_value=0),
    )
    service = service_with(repository)

    result = await service.send_campaign(
        current_campaign.id,
        CampaignSendRequest(
            mode="selected",
            recipient_ids=[shared_recipient.id],
            dry_run=True,
        ),
        settings=SETTINGS,
        owner_id=OWNER_ID,
    )

    assert [item.status for item in result.results] == ["dry_run"]
    repository.get_campaign.assert_awaited_once_with(
        current_campaign.id,
        owner_id=OWNER_ID,
    )


async def test_campaign_send_preserves_existing_delivery_states_and_daily_cap() -> None:
    current_campaign = campaign(segment=None)
    queued_recipient = recipient()
    accepted_recipient = recipient()
    cancelled_recipient = recipient()
    capped_recipient = recipient()
    existing_by_key: list[EmailSend | None] = [
        email_send(status=EmailSendStatus.queued),
        email_send(status=EmailSendStatus.accepted),
        email_send(status=EmailSendStatus.cancelled),
        None,
    ]
    repository = SimpleNamespace(
        get_campaign=AsyncMock(return_value=current_campaign),
        list_campaign_recipients_by_ids=AsyncMock(
            return_value=[
                queued_recipient,
                accepted_recipient,
                cancelled_recipient,
                capped_recipient,
            ]
        ),
        count_accepted_sends_since=AsyncMock(return_value=SETTINGS.email_daily_send_cap),
        get_email_send_by_idempotency_key=AsyncMock(side_effect=existing_by_key),
    )
    for send in existing_by_key[:3]:
        assert send is not None
        send.payload_fingerprint = None
        # The service recomputes a content fingerprint. Let the contract check pass while
        # still exercising how persisted queue/accepted/cancelled states are reported.
        repository.get_email_send_by_idempotency_key.side_effect = None
    service = service_with(repository)

    fingerprints: list[str] = []

    async def existing_send(_key: str) -> EmailSend | None:
        index = len(fingerprints)
        fingerprints.append(_key)
        if index == 3:
            return None
        stored = cast(EmailSend, existing_by_key[index])
        from codrut.modules.communications.service import _campaign_delivery_payload_fingerprint

        stored.payload_fingerprint = _campaign_delivery_payload_fingerprint(
            current_campaign,
            [queued_recipient, accepted_recipient, cancelled_recipient][index],
            SETTINGS,
        )
        return stored

    repository.get_email_send_by_idempotency_key.side_effect = existing_send

    result = await service.send_campaign(
        current_campaign.id,
        CampaignSendRequest(
            mode="selected",
            recipient_ids=[
                queued_recipient.id,
                accepted_recipient.id,
                cancelled_recipient.id,
                capped_recipient.id,
            ],
        ),
        settings=SETTINGS,
        owner_id=OWNER_ID,
    )

    assert [item.status for item in result.results] == [
        "queued",
        "accepted",
        "cancelled",
        "skipped",
    ]
    assert result.queued == result.sent == 1
    assert result.skipped == 2


async def test_selected_campaign_send_requires_recipient_ids() -> None:
    current_campaign = campaign()
    repository = SimpleNamespace()
    service = service_with(repository)

    with pytest.raises(DomainError) as exc_info:
        await service._campaign_send_recipients(
            current_campaign,
            CampaignSendRequest(mode="selected"),
            owner_id=OWNER_ID,
        )

    assert_domain_code(exc_info, "campaign_selected_recipients_required")


async def test_owner_scoped_campaign_delete_releases_assets_and_cancels_queue() -> None:
    current_campaign = campaign()
    asset = SimpleNamespace(campaign_id=current_campaign.id, status="attached")
    repository = SimpleNamespace(
        get_campaign=AsyncMock(return_value=current_campaign),
        cancel_queued_campaign_sends=AsyncMock(return_value=2),
        list_campaign_assets_for_campaign=AsyncMock(return_value=[asset]),
        delete_campaign=AsyncMock(),
    )
    service = service_with(repository)

    await service.delete_campaign(current_campaign.id, owner_id=OWNER_ID)

    assert (asset.campaign_id, asset.status) == (None, "staged")
    repository.cancel_queued_campaign_sends.assert_awaited_once()
    repository.delete_campaign.assert_awaited_once_with(current_campaign)


def test_communications_service_requires_explicit_persistence_dependencies() -> None:
    service = CommunicationsService()

    with pytest.raises(RuntimeError, match="database session"):
        service._require_repository()
    with pytest.raises(RuntimeError, match="database session"):
        service._require_session()


async def test_contact_edit_preserves_unsubscribe_for_shared_contact() -> None:
    unsubscribed = recipient(
        status=CampaignRecipientStatus.unsubscribed,
        owner_id=OTHER_OWNER_ID,
    )
    repository = SimpleNamespace(
        get_campaign_recipient=AsyncMock(return_value=unsubscribed),
        flush=AsyncMock(),
    )
    service = service_with(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.update_campaign_recipient(
            unsubscribed.id,
            CampaignRecipientUpdateRequest(status="active"),
            owner_id=OWNER_ID,
        )

    assert_domain_code(exc_info, "campaign_recipient_unsubscribe_preserved")
    repository.get_campaign_recipient.assert_awaited_once_with(
        unsubscribed.id,
        owner_id=OWNER_ID,
    )
    repository.flush.assert_not_awaited()


async def test_contact_edit_rejects_duplicate_email_and_active_contact_without_email() -> None:
    current = recipient()
    duplicate = recipient(email="duplicate@example.com")
    repository = SimpleNamespace(
        get_campaign_recipient=AsyncMock(return_value=current),
        get_campaign_recipient_by_email=AsyncMock(return_value=duplicate),
        flush=AsyncMock(),
    )
    service = service_with(repository)

    with pytest.raises(DomainError) as duplicate_exc:
        await service.update_campaign_recipient(
            current.id,
            CampaignRecipientUpdateRequest(email="duplicate@example.com"),
            owner_id=OWNER_ID,
        )
    assert_domain_code(duplicate_exc, "campaign_recipient_email_exists")

    current.email = None
    repository.get_campaign_recipient_by_email.return_value = None
    with pytest.raises(DomainError) as email_exc:
        await service.update_campaign_recipient(
            current.id,
            CampaignRecipientUpdateRequest(contact_name="Ana"),
            owner_id=OWNER_ID,
        )
    assert_domain_code(email_exc, "campaign_recipient_email_required")


async def test_contact_edit_normalizes_fields_and_retains_explicit_status() -> None:
    current = recipient(status=CampaignRecipientStatus.suppressed)
    repository = SimpleNamespace(
        get_campaign_recipient=AsyncMock(return_value=current),
        get_campaign_recipient_by_email=AsyncMock(return_value=current),
        flush=AsyncMock(),
    )
    service = service_with(repository)

    updated = await service.update_campaign_recipient(
        current.id,
        CampaignRecipientUpdateRequest(
            email="ANA@EXAMPLE.COM",
            contact_name="  Ana Actualizata  ",
            organization_name="  Companie  ",
            segment="past_customer",
            status="active",
            source="  import verificat  ",
        ),
        owner_id=OWNER_ID,
    )

    assert updated.email == "ana@example.com"
    assert updated.contact_name == "Ana Actualizata"
    assert updated.organization_name == "Companie"
    assert updated.segment == CampaignRecipientSegment.past_customer
    assert updated.status == CampaignRecipientStatus.active
    assert updated.source == "import verificat"
    repository.flush.assert_awaited_once()


async def test_campaign_membership_backfill_selects_only_sendable_segment_contacts() -> None:
    current_campaign = campaign()
    current_campaign.recipient_memberships_initialized = False
    eligible = recipient()
    repository = SimpleNamespace(
        list_campaign_member_recipient_ids=AsyncMock(return_value=[]),
        list_campaign_recipients=AsyncMock(
            return_value=[
                eligible,
                recipient(status=CampaignRecipientStatus.suppressed),
                recipient(segment=CampaignRecipientSegment.past_customer),
                recipient(email=None),
            ]
        ),
        replace_campaign_memberships=AsyncMock(),
    )
    service = service_with(repository)

    member_ids = await service._ensure_default_campaign_memberships(
        current_campaign,
        owner_id=OWNER_ID,
    )

    assert member_ids == [eligible.id]
    assert current_campaign.recipient_memberships_initialized is True
    repository.replace_campaign_memberships.assert_awaited_once_with(
        current_campaign.id,
        [eligible.id],
        source="segment_backfill",
        owner_id=OWNER_ID,
    )


async def test_campaign_membership_backfill_leaves_empty_audience_uninitialized() -> None:
    current_campaign = campaign()
    current_campaign.recipient_memberships_initialized = False
    repository = SimpleNamespace(
        list_campaign_member_recipient_ids=AsyncMock(return_value=[]),
        list_campaign_recipients=AsyncMock(return_value=[]),
        replace_campaign_memberships=AsyncMock(),
    )
    service = service_with(repository)

    member_ids = await service._ensure_default_campaign_memberships(
        current_campaign,
        owner_id=OWNER_ID,
    )

    assert member_ids == []
    assert current_campaign.recipient_memberships_initialized is False
    repository.replace_campaign_memberships.assert_not_awaited()


async def test_recording_campaign_event_rejects_unknown_recipient() -> None:
    repository = SimpleNamespace(get_campaign_recipient=AsyncMock(return_value=None))
    service = service_with(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.record_campaign_recipient_event(
            uuid.uuid4(),
            CampaignRecipientEventCreateRequest(event_type="opened"),
            owner_id=OTHER_OWNER_ID,
        )

    assert_domain_code(exc_info, "campaign_recipient_not_found")


def test_outbox_payload_validation_rejects_corrupt_or_incomplete_messages() -> None:
    invalid_payloads: list[dict[str, object] | None] = [
        None,
        {"version": 2},
        {"version": 1, "to": "", "subject": "S", "html_body": "H", "text_body": "T"},
        {
            "version": 1,
            "to": "ana@example.test",
            "subject": "S",
            "html_body": "H",
            "text_body": "T",
            "from_address": 123,
        },
        {
            "version": 1,
            "to": "ana@example.test",
            "subject": "S",
            "html_body": "H",
            "text_body": "T",
            "reply_to": [],
        },
    ]

    for payload in invalid_payloads:
        with pytest.raises(DomainError) as exc_info:
            _email_message_from_outbox_payload(payload)
        assert_domain_code(exc_info, "email_outbox_payload_invalid")


def test_outbox_assignment_metadata_ignores_invalid_values() -> None:
    assignment_id = uuid.uuid4()
    assert _email_outbox_assignment_ids(None) == []
    assert _email_outbox_assignment_ids({"assignment_ids": "bad"}) == []
    assert _email_outbox_assignment_ids(
        {"assignment_ids": [str(assignment_id), "invalid"]}
    ) == [assignment_id]
    assert _email_outbox_reminder_assignment_ids(None) == set()
    assert _email_outbox_reminder_assignment_ids({"reminder_assignment_ids": "bad"}) == set()
    assert _email_outbox_reminder_assignment_ids(
        {"reminder_assignment_ids": [str(assignment_id), "invalid"]}
    ) == {assignment_id}


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (EmailSendStatus.dispatching, EmailDeliveryStatus.queued),
        (EmailSendStatus.delivered, EmailDeliveryStatus.accepted),
        (EmailSendStatus.failed, EmailDeliveryStatus.failed),
    ],
)
def test_existing_transactional_send_replays_persisted_state(
    status: EmailSendStatus,
    expected: EmailDeliveryStatus,
) -> None:
    stored = email_send(status=status)
    stored.provider = "unknown-provider"

    result = _email_result_from_existing_send(stored, "ana@example.test")

    assert result.status == expected
    assert result.provider == EmailProviderKey.test


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (EmailSendStatus.dispatching, "queued"),
        (EmailSendStatus.delivered, "accepted"),
        (EmailSendStatus.cancelled, "cancelled"),
        (EmailSendStatus.indeterminate, "failed"),
    ],
)
def test_existing_campaign_send_replays_persisted_state(
    status: EmailSendStatus,
    expected: str,
) -> None:
    result = _campaign_result_from_existing_send(email_send(status=status), recipient())

    assert result.status == expected


async def test_smtp_provider_uses_transport_security_login_reply_to_and_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FailingSmtp:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "FailingSmtp":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def starttls(self) -> None:
            calls.append("starttls")

        def login(self, username: str, password: str) -> None:
            calls.append(f"login:{username}:{password}")

        def send_message(self, message: object) -> None:
            assert message["Reply-To"] == "reply@example.test"
            raise smtplib.SMTPException("mailbox unavailable")

    monkeypatch.setattr("codrut.modules.communications.email_provider.smtplib.SMTP", FailingSmtp)
    provider = SmtpEmailProvider(
        Settings(
            email_provider="mailpit",
            email_smtp_username="user",
            email_smtp_password="secret",  # noqa: S106 - inert test credential
            email_smtp_starttls=True,
        )
    )

    result = await provider.send(
        EmailMessage(
            to=EmailAddress("ana@example.test"),
            subject="Salut",
            html_body="<p>Mesaj</p>",
            text_body="Mesaj",
            reply_to=EmailAddress("reply@example.test"),
        )
    )

    assert result.status == EmailDeliveryStatus.failed
    assert "mailbox unavailable" in cast(str, result.error_details)
    assert calls == ["starttls", "login:user:secret"]


async def test_brevo_provider_supports_reply_to_default_client_and_fallback_message_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(202, json={})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*_args: object, **_kwargs: object) -> httpx.AsyncClient:
        return real_client(transport=transport)

    monkeypatch.setattr(
        "codrut.modules.communications.email_provider.httpx.AsyncClient",
        client_factory,
    )
    provider = BrevoEmailProvider(Settings(email_brevo_api_key="secret"))

    result = await provider.send(
        EmailMessage(
            to=EmailAddress("ana@example.test"),
            subject="Salut",
            html_body="<p>Mesaj</p>",
            text_body="Mesaj",
            from_address=EmailAddress("campaign@example.test"),
            reply_to=EmailAddress("reply@example.test"),
        )
    )

    assert result.status == EmailDeliveryStatus.accepted
    assert result.message_id == "brevo:accepted"
    assert b'"replyTo":{"email":"reply@example.test"}' in requests[0].content
    assert b'"campaign@example.test"' in requests[0].content


@pytest.mark.parametrize(
    ("headers", "minimum", "maximum"),
    [
        ({"Retry-After": "0"}, 1, 1),
        ({"Retry-After": "99999"}, 3600, 3600),
        ({"Retry-After": "invalid", "x-sib-ratelimit-reset": "45"}, 45, 45),
        ({"x-sib-ratelimit-reset": "invalid"}, 0, 0),
        ({}, 0, 0),
    ],
)
def test_brevo_retry_headers_are_bounded_and_invalid_values_are_ignored(
    headers: dict[str, str],
    minimum: int,
    maximum: int,
) -> None:
    value = _retry_after_seconds(httpx.Response(429, headers=headers))

    if minimum == maximum == 0:
        assert value is None
    else:
        assert value is not None
        assert minimum <= value <= maximum


async def test_brevo_duplicate_response_is_indeterminate_not_retried() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            400,
            json={"code": "duplicate_parameter", "message": "Duplicate request"},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await BrevoEmailProvider(
            Settings(email_brevo_api_key="secret"), client=client
        ).send(
            EmailMessage(
                to=EmailAddress("ana@example.test"),
                subject="Salut",
                html_body="<p>Mesaj</p>",
                text_body="Mesaj",
            )
        )

    assert result.delivery_uncertain is True
    assert result.retryable is False


async def test_brevo_non_json_failure_retains_safe_status_message() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(502, text="upstream details")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await BrevoEmailProvider(
            Settings(email_brevo_api_key="secret"), client=client
        ).send(
            EmailMessage(
                to=EmailAddress("ana@example.test"),
                subject="Salut",
                html_body="<p>Mesaj</p>",
                text_body="Mesaj",
            )
        )

    assert result.retryable is True
    assert result.error_details == "Brevo API error: status 502"


def test_email_provider_factory_blocks_mailpit_in_production() -> None:
    settings = MagicMock()
    settings.email_provider = "mailpit"
    settings.is_production = True

    with pytest.raises(DomainError) as exc_info:
        build_email_provider(settings)

    assert_domain_code(exc_info, "email_provider_not_configured")


def test_email_provider_factory_blocks_test_transport_in_production() -> None:
    settings = MagicMock()
    settings.email_provider = "test"
    settings.is_production = True

    with pytest.raises(DomainError) as exc_info:
        build_email_provider(settings)

    assert_domain_code(exc_info, "email_provider_not_configured")


def brevo_event(*, event: str, timestamp: int | None = None) -> BrevoWebhookEvent:
    return BrevoWebhookEvent.model_validate(
        {
            "event": event,
            "email": "ana@example.com",
            "message-id": "provider-message",
            "ts_event": timestamp,
        }
    )


async def test_delivery_webhook_ignores_unknown_or_unmatched_events() -> None:
    session = SimpleNamespace(commit=AsyncMock())
    service = DeliveryEventService(cast(Any, session))
    repository = SimpleNamespace(
        get_email_send_by_provider_message_id=AsyncMock(return_value=None)
    )
    service.repository = cast(Any, repository)

    unknown = await service.apply_brevo_event(brevo_event(event="unknown"))
    unmatched = await service.apply_brevo_event(brevo_event(event="delivered"))

    assert unknown.status == unmatched.status == "ignored"
    repository.get_email_send_by_provider_message_id.assert_awaited_once()
    session.commit.assert_not_awaited()


async def test_delivery_webhook_deduplicates_provider_event() -> None:
    send = email_send(status=EmailSendStatus.accepted)
    session = SimpleNamespace(commit=AsyncMock())
    service = DeliveryEventService(cast(Any, session))
    repository = SimpleNamespace(
        get_email_send_by_provider_message_id=AsyncMock(return_value=send),
        get_email_event_by_provider_event_id=AsyncMock(return_value=object()),
    )
    service.repository = cast(Any, repository)

    result = await service.apply_brevo_event(brevo_event(event="delivered"))

    assert result.status == "duplicate"
    session.commit.assert_not_awaited()


@pytest.mark.parametrize(
    ("event", "initial_status", "expected_status"),
    [
        ("delivered", EmailSendStatus.bounced, EmailSendStatus.bounced),
        ("error", EmailSendStatus.accepted, EmailSendStatus.failed),
        ("error", EmailSendStatus.delivered, EmailSendStatus.delivered),
        ("hard_bounce", EmailSendStatus.accepted, EmailSendStatus.bounced),
    ],
)
async def test_delivery_webhook_preserves_terminal_ordering_rules(
    event: str,
    initial_status: EmailSendStatus,
    expected_status: EmailSendStatus,
) -> None:
    send = email_send(status=initial_status)
    send.owner_id = None
    send.campaign_recipient_id = None
    send.last_event_at = None
    session = SimpleNamespace(commit=AsyncMock(), get=AsyncMock(return_value=None))
    service = DeliveryEventService(cast(Any, session))
    repository = SimpleNamespace(
        get_email_send_by_provider_message_id=AsyncMock(return_value=send),
        get_email_event_by_provider_event_id=AsyncMock(return_value=None),
        add_email_event=AsyncMock(),
        suppress_email=AsyncMock(),
    )
    service.repository = cast(Any, repository)

    result = await service.apply_brevo_event(brevo_event(event=event))

    assert result.status == "applied"
    assert send.status == expected_status
    repository.add_email_event.assert_awaited_once()
    if event == "hard_bounce":
        repository.suppress_email.assert_not_awaited()


async def test_delivery_webhook_without_timestamp_uses_current_time() -> None:
    before = datetime.now(UTC)
    send = email_send(status=EmailSendStatus.accepted)
    send.last_event_at = None
    session = SimpleNamespace(commit=AsyncMock())
    service = DeliveryEventService(cast(Any, session))
    repository = SimpleNamespace(
        get_email_send_by_provider_message_id=AsyncMock(return_value=send),
        get_email_event_by_provider_event_id=AsyncMock(return_value=None),
        add_email_event=AsyncMock(),
    )
    service.repository = cast(Any, repository)

    await service.apply_brevo_event(brevo_event(event="delivered"))

    assert send.last_event_at is not None
    assert before <= send.last_event_at <= datetime.now(UTC)


async def test_outbox_provider_exception_becomes_indeterminate_without_duplicate_retry() -> None:
    send = email_send(status=EmailSendStatus.dispatching)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    provider = SimpleNamespace(send=AsyncMock(side_effect=RuntimeError("connection lost")))
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, provider))
    processor.repository = cast(
        Any,
        SimpleNamespace(
            campaign_recipient_is_active=AsyncMock(return_value=True),
            get_email_suppression=AsyncMock(return_value=None),
            begin_email_provider_request=AsyncMock(return_value=send),
        ),
    )
    processor._record_indeterminate = AsyncMock(return_value="indeterminate")  # type: ignore[method-assign]

    result = await processor._process_claimed(send)

    assert result == "indeterminate"
    processor._record_indeterminate.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_outbox_invalid_payload_fails_without_contacting_provider() -> None:
    send = email_send(status=EmailSendStatus.dispatching, payload={"version": 2})
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    provider = SimpleNamespace(send=AsyncMock())
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, provider))
    processor.repository = cast(
        Any,
        SimpleNamespace(
            campaign_recipient_is_active=AsyncMock(return_value=True),
            get_email_suppression=AsyncMock(return_value=None),
        ),
    )
    processor._record_failure = AsyncMock(return_value="failed")  # type: ignore[method-assign]

    result = await processor._process_claimed(send)

    assert result == "failed"
    processor._record_failure.assert_awaited_once()
    provider.send.assert_not_awaited()


async def test_outbox_rejects_unleased_job_without_repository_work() -> None:
    send = email_send(status=EmailSendStatus.dispatching)
    send.lease_token = None
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    provider = SimpleNamespace(send=AsyncMock())
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, provider))

    assert await processor._process_claimed(send) == "failed"
    provider.send.assert_not_awaited()


@pytest.mark.parametrize("claimed", [None, "current"])
async def test_outbox_cancels_delivery_when_campaign_recipient_became_inactive(
    claimed: str | None,
) -> None:
    send = email_send(status=EmailSendStatus.dispatching)
    send.campaign_recipient_id = uuid.uuid4()
    current = send if claimed else None
    repository = SimpleNamespace(
        campaign_recipient_is_active=AsyncMock(return_value=False),
        get_claimed_email_send=AsyncMock(return_value=current),
        mark_email_send_cancelled=AsyncMock(),
    )
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    provider = SimpleNamespace(send=AsyncMock())
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, provider))
    processor.repository = cast(Any, repository)

    assert await processor._process_claimed(send) == "cancelled"
    if current is None:
        session.rollback.assert_awaited_once()
        repository.mark_email_send_cancelled.assert_not_awaited()
    else:
        repository.mark_email_send_cancelled.assert_awaited_once()
        session.commit.assert_awaited_once()
    provider.send.assert_not_awaited()


@pytest.mark.parametrize("claimed", [None, "current"])
async def test_outbox_cancels_delivery_for_owner_scoped_suppression(
    claimed: str | None,
) -> None:
    send = email_send(status=EmailSendStatus.dispatching)
    send.campaign_recipient_id = None
    current = send if claimed else None
    repository = SimpleNamespace(
        get_email_suppression=AsyncMock(return_value=object()),
        get_claimed_email_send=AsyncMock(return_value=current),
        mark_email_send_cancelled=AsyncMock(),
    )
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    provider = SimpleNamespace(send=AsyncMock())
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, provider))
    processor.repository = cast(Any, repository)

    assert await processor._process_claimed(send) == "cancelled"
    repository.get_email_suppression.assert_awaited_once_with(
        owner_id=OWNER_ID,
        email=send.recipient_email,
    )
    if current is None:
        session.rollback.assert_awaited_once()
    else:
        assert "permanent delivery failure" in cast(str, current.error_details)
        repository.mark_email_send_cancelled.assert_awaited_once()
    provider.send.assert_not_awaited()


async def test_outbox_stops_when_provider_request_lease_was_lost() -> None:
    send = email_send(status=EmailSendStatus.dispatching)
    repository = SimpleNamespace(
        get_email_suppression=AsyncMock(return_value=None),
        begin_email_provider_request=AsyncMock(return_value=None),
    )
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    provider = SimpleNamespace(send=AsyncMock())
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, provider))
    processor.repository = cast(Any, repository)

    assert await processor._process_claimed(send) == "failed"
    session.rollback.assert_awaited_once()
    provider.send.assert_not_awaited()


@pytest.mark.parametrize(
    ("result", "recorder", "expected"),
    [
        (
            EmailSendResult(
                provider=EmailProviderKey.brevo,
                status=EmailDeliveryStatus.failed,
                message_id="uncertain",
                recipient=EmailAddress("ana@example.com"),
                delivery_uncertain=True,
            ),
            "indeterminate",
            "indeterminate",
        ),
        (
            EmailSendResult(
                provider=EmailProviderKey.brevo,
                status=EmailDeliveryStatus.failed,
                message_id="rejected",
                recipient=EmailAddress("ana@example.com"),
                retryable=True,
                retry_after_seconds=60,
            ),
            "failure",
            "retried",
        ),
    ],
)
async def test_outbox_distinguishes_uncertain_delivery_from_retryable_rejection(
    result: EmailSendResult,
    recorder: str,
    expected: str,
) -> None:
    send = email_send(status=EmailSendStatus.dispatching)
    repository = SimpleNamespace(
        get_email_suppression=AsyncMock(return_value=None),
        begin_email_provider_request=AsyncMock(return_value=send),
    )
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    provider = SimpleNamespace(send=AsyncMock(return_value=result))
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, provider))
    processor.repository = cast(Any, repository)
    processor._record_indeterminate = AsyncMock(return_value="indeterminate")  # type: ignore[method-assign]
    processor._record_failure = AsyncMock(return_value="retried")  # type: ignore[method-assign]

    assert await processor._process_claimed(send) == expected
    if recorder == "indeterminate":
        processor._record_indeterminate.assert_awaited_once()
        processor._record_failure.assert_not_awaited()
    else:
        processor._record_failure.assert_awaited_once()
        processor._record_indeterminate.assert_not_awaited()


async def test_outbox_does_not_finalize_acceptance_after_lease_loss() -> None:
    send = email_send(status=EmailSendStatus.dispatching)
    result = EmailSendResult(
        provider=EmailProviderKey.brevo,
        status=EmailDeliveryStatus.accepted,
        message_id="accepted",
        recipient=EmailAddress("ana@example.com"),
    )
    repository = SimpleNamespace(
        get_email_suppression=AsyncMock(return_value=None),
        begin_email_provider_request=AsyncMock(return_value=send),
        get_claimed_email_send=AsyncMock(return_value=None),
    )
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    provider = SimpleNamespace(send=AsyncMock(return_value=result))
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, provider))
    processor.repository = cast(Any, repository)

    assert await processor._process_claimed(send) == "failed"
    session.rollback.assert_awaited_once()


async def test_outbox_marks_provider_acceptance_indeterminate_when_local_flush_fails() -> None:
    send = email_send(status=EmailSendStatus.dispatching)
    lease_token = cast(str, send.lease_token)
    result = EmailSendResult(
        provider=EmailProviderKey.brevo,
        status=EmailDeliveryStatus.accepted,
        message_id="accepted-provider-id",
        recipient=EmailAddress("ana@example.com"),
    )
    repository = SimpleNamespace(
        get_email_suppression=AsyncMock(return_value=None),
        begin_email_provider_request=AsyncMock(return_value=send),
        get_claimed_email_send=AsyncMock(return_value=send),
        add_email_event=AsyncMock(),
    )
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        flush=AsyncMock(side_effect=RuntimeError("metadata incomplete")),
    )
    provider = SimpleNamespace(send=AsyncMock(return_value=result))
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, provider))
    processor.repository = cast(Any, repository)
    processor._mark_invitation_assignments_accepted = AsyncMock()  # type: ignore[method-assign]
    processor._complete_campaign_if_idle = AsyncMock()  # type: ignore[method-assign]
    processor._record_indeterminate = AsyncMock(return_value="indeterminate")  # type: ignore[method-assign]

    assert await processor._process_claimed(send) == "indeterminate"

    session.rollback.assert_awaited_once()
    processor._record_indeterminate.assert_awaited_once_with(
        send.id,
        lease_token,
        "Provider accepted the message, but local persistence failed.",
        provider=EmailProviderKey.brevo,
        provider_message_id="accepted-provider-id",
    )


async def test_outbox_failure_records_retry_metadata_then_terminal_failure() -> None:
    send = email_send(status=EmailSendStatus.dispatching)
    repository = SimpleNamespace(
        get_claimed_email_send=AsyncMock(return_value=send),
        add_email_event=AsyncMock(),
    )
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, SimpleNamespace()))
    processor.repository = cast(Any, repository)

    retried = await processor._record_failure(
        send.id,
        cast(str, send.lease_token),
        "temporary",
        retryable=True,
        provider=EmailProviderKey.brevo,
        provider_message_id="provider-id",
        retry_after_seconds=120,
    )

    assert retried == "retried"
    assert send.status == EmailSendStatus.queued
    assert send.provider == "brevo"
    assert send.provider_message_id == "provider-id"
    assert send.next_attempt_at is not None

    send.status = EmailSendStatus.dispatching
    second_lease = f"lease-{uuid.uuid4()}"
    send.lease_token = second_lease
    send.attempt_count = send.max_attempts
    processor._complete_campaign_if_idle = AsyncMock()  # type: ignore[method-assign]
    failed = await processor._record_failure(
        send.id,
        second_lease,
        "permanent",
        retryable=False,
    )

    assert failed == "failed"
    assert send.status == EmailSendStatus.failed
    assert send.attempt_count == send.max_attempts
    processor._complete_campaign_if_idle.assert_awaited_once_with(send.campaign_id)


async def test_outbox_missing_claim_cannot_be_failed_or_marked_indeterminate() -> None:
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        get=AsyncMock(return_value=None),
    )
    repository = SimpleNamespace(get_claimed_email_send=AsyncMock(return_value=None))
    processor = EmailOutboxProcessor(cast(Any, session), cast(Any, SimpleNamespace()))
    processor.repository = cast(Any, repository)
    send_id = uuid.uuid4()

    assert (
        await processor._record_failure(
            send_id,
            "lost-lease",
            "failure",
            retryable=False,
        )
        == "failed"
    )
    assert (
        await processor._record_indeterminate(
            send_id,
            "lost-lease",
            "unknown",
        )
        == "indeterminate"
    )
    assert session.rollback.await_count == 2
