import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select

from codrut.api.dependencies import db_session
from codrut.core.config import Settings, get_settings
from codrut.core.database import SessionLocal, engine
from codrut.main import create_app
from codrut.modules.communications.delivery_events import DeliveryEventService
from codrut.modules.communications.models import (
    CampaignContactTombstone,
    CampaignDeliveryTombstone,
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    EmailEvent,
    EmailEventType,
    EmailSend,
    EmailSendStatus,
    EmailSuppression,
)
from codrut.modules.communications.schemas import BrevoWebhookEvent
from codrut.modules.communications.suppression import (
    email_suppression_fingerprint,
    provider_message_fingerprint,
)
from codrut.modules.identity.models import User, UserRole

LATE_TOMBSTONE_SECRET = (
    "late-provider-tombstone-secret-at-least-32-characters"  # noqa: S105
)


def _send(
    *,
    message_id: str,
    status: EmailSendStatus = EmailSendStatus.accepted,
    last_event_at: datetime | None = None,
    recipient_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> EmailSend:
    return EmailSend(
        id=uuid.uuid4(),
        owner_id=owner_id,
        campaign_recipient_id=recipient_id,
        recipient_email="ana@example.com",
        template_key="campaign",
        template_version=1,
        provider="brevo",
        provider_message_id=message_id,
        status=status,
        attempt_count=1,
        max_attempts=5,
        last_event_at=last_event_at,
    )


async def _cleanup(
    *,
    send_id: uuid.UUID,
    recipient_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> None:
    async with SessionLocal() as session:
        if owner_id is not None:
            await session.execute(
                delete(EmailSuppression).where(EmailSuppression.owner_id == owner_id)
            )
        await session.execute(delete(EmailSend).where(EmailSend.id == send_id))
        if recipient_id is not None:
            await session.execute(
                delete(CampaignRecipient).where(CampaignRecipient.id == recipient_id)
            )
        if owner_id is not None:
            await session.execute(delete(User).where(User.id == owner_id))
        await session.commit()
    await engine.dispose()


async def test_brevo_delivery_is_applied_once_with_message_id_normalization() -> None:
    occurred_at = datetime.now(UTC).replace(microsecond=0)
    send = _send(message_id="<provider-message>")
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": "delivered",
            "email": "ana@example.com",
            "message-id": "provider-message",
            "ts_event": int(occurred_at.timestamp()),
        }
    )
    try:
        async with SessionLocal() as session:
            session.add(send)
            await session.commit()
            service = DeliveryEventService(session)

            first = await service.apply_brevo_event(payload)
            replay = await service.apply_brevo_event(payload)
            stored = await session.get(EmailSend, send.id)
            events = await session.execute(
                select(EmailEvent).where(
                    EmailEvent.email_send_id == send.id,
                    EmailEvent.event_type == EmailEventType.delivered,
                )
            )

            assert first.status == "applied"
            assert replay.status == "duplicate"
            assert stored is not None
            assert stored.status == EmailSendStatus.delivered
            assert len(list(events.scalars().all())) == 1
    finally:
        await _cleanup(send_id=send.id)


async def test_stale_bounce_is_recorded_without_overwriting_newer_delivery() -> None:
    delivered_at = datetime.now(UTC).replace(microsecond=0)
    send = _send(
        message_id="provider-stale",
        status=EmailSendStatus.delivered,
        last_event_at=delivered_at,
    )
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": "hard_bounce",
            "email": "ana@example.com",
            "message-id": "provider-stale",
            "ts_event": int((delivered_at - timedelta(minutes=5)).timestamp()),
            "reason": "Mailbox unavailable",
        }
    )
    try:
        async with SessionLocal() as session:
            session.add(send)
            await session.commit()

            result = await DeliveryEventService(session).apply_brevo_event(payload)
            stored = await session.get(EmailSend, send.id)

            assert result.status == "applied"
            assert stored is not None
            assert stored.status == EmailSendStatus.delivered
            assert stored.last_event_at == delivered_at
            assert stored.error_details is None
    finally:
        await _cleanup(send_id=send.id)


async def test_same_second_bounce_overrides_microsecond_acceptance_timestamp() -> None:
    accepted_at = datetime.now(UTC)
    provider_second = accepted_at.replace(microsecond=0)
    send = _send(
        message_id="provider-same-second",
        status=EmailSendStatus.accepted,
        last_event_at=accepted_at,
    )
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": "hard_bounce",
            "email": "ana@example.com",
            "message-id": "provider-same-second",
            "ts_event": int(provider_second.timestamp()),
            "reason": "Mailbox unavailable",
        }
    )
    try:
        async with SessionLocal() as session:
            session.add(send)
            await session.commit()

            result = await DeliveryEventService(session).apply_brevo_event(payload)
            stored = await session.get(EmailSend, send.id)

            assert result.status == "applied"
            assert stored is not None
            assert stored.status == EmailSendStatus.bounced
            assert stored.error_details == "Mailbox unavailable"
    finally:
        await _cleanup(send_id=send.id)


@pytest.mark.parametrize("event_name", ["soft_bounce", "deferred"])
async def test_retryable_provider_event_is_recorded_without_suppressing_recipient(
    event_name: str,
) -> None:
    owner = User(
        id=uuid.uuid4(),
        email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",  # noqa: S106
        role=UserRole.trainer,
    )
    send = _send(message_id=f"provider-{event_name}", owner_id=owner.id)
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": event_name,
            "email": "ana@example.com",
            "message-id": f"provider-{event_name}",
            "ts_event": int(datetime.now(UTC).timestamp()),
            "reason": "Provider will retry delivery",
        }
    )
    try:
        async with SessionLocal() as session:
            session.add(owner)
            await session.flush()
            session.add(send)
            await session.commit()

            result = await DeliveryEventService(session).apply_brevo_event(payload)
            stored_send = await session.get(EmailSend, send.id)
            event = await session.execute(
                select(EmailEvent).where(EmailEvent.email_send_id == send.id)
            )
            suppression = await session.execute(
                select(EmailSuppression).where(EmailSuppression.owner_id == owner.id)
            )

            assert result.status == "applied"
            assert stored_send is not None
            assert stored_send.status == EmailSendStatus.accepted
            assert event.scalar_one().event_type == EmailEventType.indeterminate
            assert suppression.scalar_one_or_none() is None
    finally:
        await _cleanup(send_id=send.id, owner_id=owner.id)


async def test_delivery_after_soft_bounce_recovers_to_delivered() -> None:
    occurred_at = datetime.now(UTC).replace(microsecond=0)
    send = _send(message_id="provider-soft-bounce-recovery")
    soft_bounce = BrevoWebhookEvent.model_validate(
        {
            "event": "soft_bounce",
            "email": "ana@example.com",
            "message-id": "provider-soft-bounce-recovery",
            "ts_event": int(occurred_at.timestamp()),
            "reason": "Temporary mailbox failure",
        }
    )
    delivered = BrevoWebhookEvent.model_validate(
        {
            "event": "delivered",
            "email": "ana@example.com",
            "message-id": "provider-soft-bounce-recovery",
            "ts_event": int((occurred_at + timedelta(minutes=1)).timestamp()),
        }
    )
    try:
        async with SessionLocal() as session:
            session.add(send)
            await session.commit()
            service = DeliveryEventService(session)

            await service.apply_brevo_event(soft_bounce)
            result = await service.apply_brevo_event(delivered)
            stored = await session.get(EmailSend, send.id)

            assert result.status == "applied"
            assert stored is not None
            assert stored.status == EmailSendStatus.delivered
            assert stored.error_details is None
    finally:
        await _cleanup(send_id=send.id)


async def test_hard_bounce_persists_owner_scoped_suppression() -> None:
    owner = User(
        id=uuid.uuid4(),
        email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",  # noqa: S106
        role=UserRole.trainer,
    )
    send = _send(message_id="provider-suppression", owner_id=owner.id)
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": "hard_bounce",
            "email": "ANA@example.com",
            "message-id": "provider-suppression",
            "ts_event": int(datetime.now(UTC).timestamp()),
            "reason": "Permanent mailbox failure",
        }
    )
    try:
        async with SessionLocal() as session:
            session.add(owner)
            await session.flush()
            session.add(send)
            await session.commit()

            result = await DeliveryEventService(session).apply_brevo_event(payload)
            suppression = await session.execute(
                select(EmailSuppression).where(EmailSuppression.owner_id == owner.id)
            )
            stored = suppression.scalar_one_or_none()

            assert result.status == "applied"
            assert stored is not None
            assert stored.email_fingerprint == email_suppression_fingerprint(
                owner_id=owner.id,
                email="ana@example.com",
                secret=Settings().effective_email_suppression_fingerprint_secret,
            )
            assert stored.reason == "hard_bounce"
            assert stored.source_email_send_id == send.id
            assert stored.review_after > datetime.now(UTC) + timedelta(days=364)
    finally:
        await _cleanup(send_id=send.id, owner_id=owner.id)


async def test_unsubscribe_suppresses_campaign_recipient() -> None:
    owner = User(
        id=uuid.uuid4(),
        email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",  # noqa: S106
        role=UserRole.trainer,
    )
    recipient = CampaignRecipient(
        id=uuid.uuid4(),
        owner_id=owner.id,
        email="ana@example.com",
        contact_name="Ana",
        segment=CampaignRecipientSegment.past_customer,
        status=CampaignRecipientStatus.active,
    )
    send = _send(
        message_id="provider-unsubscribe",
        recipient_id=recipient.id,
        owner_id=owner.id,
    )
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": "unsubscribed",
            "email": "ana@example.com",
            "message-id": "<provider-unsubscribe>",
            "ts_event": int(datetime.now(UTC).timestamp()),
        }
    )
    try:
        async with SessionLocal() as session:
            session.add(owner)
            await session.flush()
            session.add_all([recipient, send])
            await session.commit()

            result = await DeliveryEventService(session).apply_brevo_event(payload)
            stored = await session.get(CampaignRecipient, recipient.id)

            assert result.status == "applied"
            assert stored is not None
            assert stored.status == CampaignRecipientStatus.unsubscribed
    finally:
        await _cleanup(
            send_id=send.id,
            recipient_id=recipient.id,
            owner_id=owner.id,
        )


@pytest.mark.parametrize(
    (
        "initial_status",
        "provider_event",
        "expected_status",
        "expected_status_before_archive",
    ),
    [
        (
            CampaignRecipientStatus.active,
            "hard_bounce",
            CampaignRecipientStatus.suppressed,
            CampaignRecipientStatus.suppressed,
        ),
        (
            CampaignRecipientStatus.active,
            "unsubscribed",
            CampaignRecipientStatus.unsubscribed,
            CampaignRecipientStatus.unsubscribed,
        ),
        (
            CampaignRecipientStatus.unsubscribed,
            "hard_bounce",
            CampaignRecipientStatus.unsubscribed,
            None,
        ),
    ],
)
async def test_permanent_event_updates_archived_contact_without_losing_protection(
    initial_status: CampaignRecipientStatus,
    provider_event: str,
    expected_status: CampaignRecipientStatus,
    expected_status_before_archive: CampaignRecipientStatus | None,
) -> None:
    owner = User(
        id=uuid.uuid4(),
        email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",  # noqa: S106
        role=UserRole.trainer,
    )
    archived_at = datetime.now(UTC) - timedelta(days=2)
    recipient = CampaignRecipient(
        id=uuid.uuid4(),
        owner_id=owner.id,
        email="archived@example.com",
        contact_name="Arhivat",
        segment=CampaignRecipientSegment.potential_customer,
        status=initial_status,
        archived_at=archived_at,
        purge_after=archived_at + timedelta(days=30),
    )
    send = _send(
        message_id=f"provider-archived-{initial_status.value}-{provider_event}",
        recipient_id=recipient.id,
        owner_id=owner.id,
    )
    send.recipient_email = recipient.email
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": provider_event,
            "email": recipient.email,
            "message-id": send.provider_message_id,
            "ts_event": int(datetime.now(UTC).timestamp()),
            "reason": "Permanent mailbox failure",
        }
    )
    try:
        async with SessionLocal() as session:
            session.add(owner)
            await session.flush()
            session.add_all([recipient, send])
            await session.commit()

            result = await DeliveryEventService(session).apply_brevo_event(payload)
            stored = await session.get(CampaignRecipient, recipient.id)

            assert result.status == "applied"
            assert stored is not None
            assert stored.status == expected_status
            assert stored.archived_at == archived_at
            assert stored.purge_after == archived_at + timedelta(days=30)
            assert stored.status_before_archive == expected_status_before_archive
    finally:
        await _cleanup(
            send_id=send.id,
            recipient_id=recipient.id,
            owner_id=owner.id,
        )


@pytest.mark.asyncio
async def test_provider_webhook_locks_recipient_before_refetching_send_for_update() -> None:
    owner_id = uuid.uuid4()
    recipient_id = uuid.uuid4()
    send = _send(
        message_id="provider-lock-order",
        recipient_id=recipient_id,
        owner_id=owner_id,
    )
    recipient = CampaignRecipient(
        id=recipient_id,
        owner_id=owner_id,
        email="ana@example.com",
        contact_name="Ana",
        segment=CampaignRecipientSegment.past_customer,
        status=CampaignRecipientStatus.active,
    )
    lock_order: list[str] = []

    async def get_send(
        _message_ids: set[str],
        *,
        for_update: bool,
    ) -> EmailSend:
        lock_order.append("send-lock" if for_update else "send-read")
        return send

    async def get_recipient(
        _recipient_id: uuid.UUID,
        *,
        owner_id: uuid.UUID,
        catalog_scope: str,
        for_update: bool,
    ) -> CampaignRecipient:
        assert owner_id == recipient.owner_id
        assert catalog_scope == "any"
        assert for_update is True
        lock_order.append("recipient-lock")
        return recipient

    repository = SimpleNamespace(
        get_email_send_by_provider_message_id=AsyncMock(side_effect=get_send),
        get_campaign_recipient=AsyncMock(side_effect=get_recipient),
        get_email_event_by_provider_event_id=AsyncMock(return_value=None),
        add_email_event=AsyncMock(),
    )
    session = MagicMock()
    session.commit = AsyncMock()
    service = DeliveryEventService(session)
    service.repository = repository
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": "delivered",
            "email": "ana@example.com",
            "message-id": "provider-lock-order",
            "ts_event": int(datetime.now(UTC).timestamp()),
        }
    )

    result = await service.apply_brevo_event(payload)

    assert result.status == "applied"
    assert lock_order == ["send-read", "recipient-lock", "send-lock"]
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_webhook_retries_send_that_appears_during_locking() -> None:
    owner_id = uuid.uuid4()
    recipient_id = uuid.uuid4()
    send = _send(
        message_id="provider-appeared-during-lock",
        recipient_id=recipient_id,
        owner_id=owner_id,
    )
    recipient = CampaignRecipient(
        id=recipient_id,
        owner_id=owner_id,
        email="ana@example.com",
        contact_name="Ana",
        segment=CampaignRecipientSegment.past_customer,
        status=CampaignRecipientStatus.active,
    )
    repository = SimpleNamespace(
        get_email_send_by_provider_message_id=AsyncMock(
            side_effect=[None, send, send, send]
        ),
        get_campaign_recipient=AsyncMock(return_value=recipient),
        get_email_event_by_provider_event_id=AsyncMock(return_value=None),
        add_email_event=AsyncMock(),
    )
    session = MagicMock()
    session.rollback = AsyncMock()
    session.commit = AsyncMock()
    service = DeliveryEventService(session)
    service.repository = repository
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": "delivered",
            "email": recipient.email,
            "message-id": send.provider_message_id,
            "ts_event": int(datetime.now(UTC).timestamp()),
        }
    )

    result = await service.apply_brevo_event(payload)

    assert result.status == "applied"
    assert send.status == EmailSendStatus.delivered
    assert repository.get_email_send_by_provider_message_id.await_count == 4
    repository.get_campaign_recipient.assert_awaited_once_with(
        recipient_id,
        owner_id=owner_id,
        catalog_scope="any",
        for_update=True,
    )
    session.rollback.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_webhook_rejects_recipient_send_identity_mismatch() -> None:
    owner_id = uuid.uuid4()
    send = _send(
        message_id="provider-recipient-mismatch",
        recipient_id=uuid.uuid4(),
        owner_id=owner_id,
    )
    wrong_recipient = CampaignRecipient(
        id=uuid.uuid4(),
        owner_id=owner_id,
        email="wrong@example.com",
        contact_name="Wrong",
        segment=CampaignRecipientSegment.past_customer,
        status=CampaignRecipientStatus.active,
    )
    repository = SimpleNamespace(
        get_email_send_by_provider_message_id=AsyncMock(return_value=send),
        get_campaign_recipient=AsyncMock(return_value=wrong_recipient),
        get_email_event_by_provider_event_id=AsyncMock(),
        add_email_event=AsyncMock(),
    )
    session = MagicMock()
    session.rollback = AsyncMock()
    session.commit = AsyncMock()
    service = DeliveryEventService(session)
    service.repository = repository
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": "delivered",
            "email": "ana@example.com",
            "message-id": send.provider_message_id,
            "ts_event": int(datetime.now(UTC).timestamp()),
        }
    )

    result = await service.apply_brevo_event(payload)

    assert result.status == "ignored"
    assert repository.get_email_send_by_provider_message_id.await_count == 4
    assert repository.get_campaign_recipient.await_count == 2
    repository.get_email_event_by_provider_event_id.assert_not_awaited()
    repository.add_email_event.assert_not_awaited()
    assert session.rollback.await_count == 2
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initial_reason", "provider_event", "expected_reason"),
    [
        (None, "hard_bounce", "hard_bounce"),
        ("hard_bounce", "unsubscribed", "unsubscribed"),
        ("unsubscribed", "hard_bounce", "unsubscribed"),
    ],
)
async def test_late_permanent_event_updates_pseudonymous_delivery_tombstone(
    initial_reason: str | None,
    provider_event: str,
    expected_reason: str,
) -> None:
    settings = Settings(
        email_suppression_fingerprint_secret=SecretStr(LATE_TOMBSTONE_SECRET)
    )
    occurred_at = datetime.now(UTC).replace(microsecond=0)
    contact_tombstone = CampaignContactTombstone(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        former_recipient_id=uuid.uuid4(),
        email_fingerprint="e" * 64,
        do_not_contact_reason=initial_reason,
        suppressed_at=None,
        review_after=occurred_at,
    )
    delivery_tombstone = CampaignDeliveryTombstone(
        id=uuid.uuid4(),
        contact_tombstone_id=contact_tombstone.id,
        campaign_id=uuid.uuid4(),
        provider_message_fingerprint="f" * 64,
        expires_at=occurred_at + timedelta(days=365),
    )
    repository = SimpleNamespace(
        get_email_send_by_provider_message_id=AsyncMock(return_value=None),
        get_campaign_delivery_tombstone_by_provider_message_fingerprints=AsyncMock(
            return_value=(delivery_tombstone, contact_tombstone)
        ),
        record_late_campaign_delivery_event=AsyncMock(return_value=True),
        increment_campaign_contact_aggregate=AsyncMock(),
    )
    session = MagicMock()
    session.commit = AsyncMock()
    service = DeliveryEventService(session, settings=settings)
    service.repository = repository
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": provider_event,
            "email": "removed-contact@example.com",
            "message-id": "<late-provider-message>",
            "ts_event": int(occurred_at.timestamp()),
        }
    )

    result = await service.apply_brevo_event(payload)

    assert result.status == "applied"
    assert contact_tombstone.do_not_contact_reason == expected_reason
    assert contact_tombstone.review_after > occurred_at + timedelta(days=364)
    expected_event_type = (
        EmailEventType.bounced
        if provider_event == "hard_bounce"
        else EmailEventType.unsubscribed
    )
    repository.get_campaign_delivery_tombstone_by_provider_message_fingerprints.assert_awaited_once_with(
        {
            provider_message_fingerprint(
                message_id="late-provider-message",
                secret=settings.effective_email_suppression_fingerprint_secret,
            )
        },
        active_at=ANY,
        for_update=True,
    )
    repository.increment_campaign_contact_aggregate.assert_awaited_once_with(
        owner_id=contact_tombstone.owner_id,
        campaign_id=delivery_tombstone.campaign_id,
        metric=f"provider_event:{expected_event_type.value}",
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_seeded_provider_event_receipt_prevents_replay_double_count() -> None:
    settings = Settings(
        email_suppression_fingerprint_secret=SecretStr(LATE_TOMBSTONE_SECRET)
    )
    occurred_at = datetime.now(UTC).replace(microsecond=0)
    contact_tombstone = CampaignContactTombstone(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        former_recipient_id=uuid.uuid4(),
        email_fingerprint="a" * 64,
        do_not_contact_reason=None,
        suppressed_at=None,
        review_after=occurred_at + timedelta(days=365),
    )
    delivery_tombstone = CampaignDeliveryTombstone(
        id=uuid.uuid4(),
        contact_tombstone_id=contact_tombstone.id,
        campaign_id=uuid.uuid4(),
        provider_message_fingerprint="b" * 64,
        expires_at=occurred_at + timedelta(days=365),
    )
    repository = SimpleNamespace(
        get_email_send_by_provider_message_id=AsyncMock(return_value=None),
        get_campaign_delivery_tombstone_by_provider_message_fingerprints=AsyncMock(
            return_value=(delivery_tombstone, contact_tombstone)
        ),
        record_late_campaign_delivery_event=AsyncMock(return_value=False),
        increment_campaign_contact_aggregate=AsyncMock(),
    )
    session = MagicMock()
    session.commit = AsyncMock()
    service = DeliveryEventService(session, settings=settings)
    service.repository = repository
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": "opened",
            "email": "removed-contact@example.com",
            "message-id": "<late-provider-message>",
            "ts_event": int(occurred_at.timestamp()),
        }
    )

    result = await service.apply_brevo_event(payload)

    assert result.status == "duplicate"
    repository.increment_campaign_contact_aggregate.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_delivery_tombstone_is_ignored_before_cleanup() -> None:
    settings = Settings(
        email_suppression_fingerprint_secret=SecretStr(LATE_TOMBSTONE_SECRET)
    )
    expired_at = datetime.now(UTC) - timedelta(seconds=1)

    async def lookup_expired(
        _fingerprints: set[str],
        *,
        active_at: datetime,
        for_update: bool,
    ) -> None:
        assert active_at > expired_at
        assert for_update is True
        return None

    repository = SimpleNamespace(
        get_email_send_by_provider_message_id=AsyncMock(return_value=None),
        get_campaign_delivery_tombstone_by_provider_message_fingerprints=AsyncMock(
            side_effect=lookup_expired
        ),
    )
    session = MagicMock()
    session.commit = AsyncMock()
    service = DeliveryEventService(session, settings=settings)
    service.repository = repository
    payload = BrevoWebhookEvent.model_validate(
        {
            "event": "delivered",
            "email": "removed-contact@example.com",
            "message-id": "<expired-provider-message>",
            "ts_event": int(datetime.now(UTC).timestamp()),
        }
    )

    result = await service.apply_brevo_event(payload)

    assert result.status == "ignored"
    repository.get_campaign_delivery_tombstone_by_provider_message_fingerprints.assert_awaited_once()
    session.commit.assert_not_awaited()


def _webhook_client() -> TestClient:
    app = create_app()

    async def database_override():
        yield object()

    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        email_webhook_token=SecretStr("brevo-webhook-token"),
    )
    app.dependency_overrides[db_session] = database_override
    return TestClient(app)


def test_brevo_webhook_rejects_missing_or_invalid_bearer_token() -> None:
    client = _webhook_client()
    payload = {
        "event": "delivered",
        "email": "ana@example.com",
        "message-id": "unknown-message",
    }

    missing = client.post("/api/communications/webhooks/brevo", json=payload)
    invalid = client.post(
        "/api/communications/webhooks/brevo",
        json=payload,
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"


def test_brevo_webhook_accepts_configured_basic_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def apply_event(_service, _payload):
        return {"status": "ignored"}

    monkeypatch.setattr(DeliveryEventService, "apply_brevo_event", apply_event)
    client = _webhook_client()

    response = client.post(
        "/api/communications/webhooks/brevo",
        json={
            "event": "delivered",
            "email": "ana@example.com",
            "message-id": "unknown-message",
        },
        headers={"Authorization": "Bearer brevo-webhook-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
