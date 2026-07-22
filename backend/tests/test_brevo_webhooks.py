import uuid
from datetime import UTC, datetime, timedelta

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
from codrut.modules.identity.models import User, UserRole


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
            assert stored.email == "ana@example.com"
            assert stored.reason == "hard_bounce"
            assert stored.source_email_send_id == send.id
    finally:
        await _cleanup(send_id=send.id, owner_id=owner.id)


async def test_unsubscribe_suppresses_campaign_recipient() -> None:
    recipient = CampaignRecipient(
        id=uuid.uuid4(),
        email="ana@example.com",
        contact_name="Ana",
        segment=CampaignRecipientSegment.past_customer,
        status=CampaignRecipientStatus.active,
    )
    send = _send(message_id="provider-unsubscribe", recipient_id=recipient.id)
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
            session.add_all([recipient, send])
            await session.commit()

            result = await DeliveryEventService(session).apply_brevo_event(payload)
            stored = await session.get(CampaignRecipient, recipient.id)

            assert result.status == "applied"
            assert stored is not None
            assert stored.status == CampaignRecipientStatus.unsubscribed
    finally:
        await _cleanup(send_id=send.id, recipient_id=recipient.id)


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
