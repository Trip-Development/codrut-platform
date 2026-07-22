import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.communications.models import (
    CampaignRecipient,
    CampaignRecipientStatus,
    EmailEventType,
    EmailSendStatus,
)
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.schemas import BrevoWebhookEvent, BrevoWebhookResponse

BREVO_EVENT_TYPES: dict[str, EmailEventType] = {
    "request": EmailEventType.accepted,
    "delivered": EmailEventType.delivered,
    "opened": EmailEventType.opened,
    "unique_opened": EmailEventType.opened,
    "proxy_open": EmailEventType.opened,
    "unique_proxy_open": EmailEventType.opened,
    "click": EmailEventType.clicked,
    "hard_bounce": EmailEventType.bounced,
    "soft_bounce": EmailEventType.indeterminate,
    "deferred": EmailEventType.indeterminate,
    "blocked": EmailEventType.bounced,
    "invalid_email": EmailEventType.bounced,
    "error": EmailEventType.failed,
    "unsubscribed": EmailEventType.unsubscribed,
    "spam": EmailEventType.complained,
}
PERMANENT_SUPPRESSION_EVENTS = {
    "hard_bounce",
    "blocked",
    "invalid_email",
    "unsubscribed",
    "spam",
}


class DeliveryEventService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CommunicationsRepository(session)

    async def apply_brevo_event(
        self,
        payload: BrevoWebhookEvent,
    ) -> BrevoWebhookResponse:
        normalized_event = payload.event.strip().casefold()
        event_type = BREVO_EVENT_TYPES.get(normalized_event)
        if event_type is None:
            return BrevoWebhookResponse(status="ignored")

        occurred_at = _event_time(payload)
        provider_event_id = _provider_event_id(payload, normalized_event, occurred_at)
        message_ids = _message_id_candidates(payload.message_id)
        send = await self.repository.get_email_send_by_provider_message_id(
            message_ids,
            for_update=True,
        )
        if send is None:
            return BrevoWebhookResponse(status="ignored")
        if await self.repository.get_email_event_by_provider_event_id(provider_event_id):
            return BrevoWebhookResponse(status="duplicate")

        await self.repository.add_email_event(
            send.id,
            event_type,
            occurred_at=occurred_at,
            provider_event_id=provider_event_id,
        )
        is_latest = _is_latest_provider_event(send.last_event_at, occurred_at)
        send.last_event_at = max(send.last_event_at or occurred_at, occurred_at)

        if is_latest and event_type == EmailEventType.delivered:
            if send.status not in {EmailSendStatus.bounced, EmailSendStatus.cancelled}:
                send.status = EmailSendStatus.delivered
                send.error_details = None
        elif is_latest and event_type == EmailEventType.bounced:
            send.status = EmailSendStatus.bounced
            send.error_details = (payload.reason or "Provider reported a bounce.")[:2000]
        elif is_latest and event_type == EmailEventType.failed:
            if send.status not in {EmailSendStatus.delivered, EmailSendStatus.bounced}:
                send.status = EmailSendStatus.failed
                send.error_details = (payload.reason or "Provider reported an error.")[:2000]

        if normalized_event in PERMANENT_SUPPRESSION_EVENTS:
            recipient = await self._suppress_campaign_recipient(
                send.campaign_recipient_id,
                event_type,
            )
            owner_id = send.owner_id or (recipient.owner_id if recipient is not None else None)
            if owner_id is not None:
                await self.repository.suppress_email(
                    owner_id=owner_id,
                    email=send.recipient_email,
                    reason=normalized_event,
                    source_email_send_id=send.id,
                )

        await self.session.commit()
        return BrevoWebhookResponse(status="applied")

    async def _suppress_campaign_recipient(
        self,
        recipient_id: UUID | None,
        event_type: EmailEventType,
    ) -> CampaignRecipient | None:
        if recipient_id is None:
            return None
        recipient = await self.session.get(CampaignRecipient, recipient_id)
        if recipient is None:
            return None
        recipient.status = (
            CampaignRecipientStatus.unsubscribed
            if event_type == EmailEventType.unsubscribed
            else CampaignRecipientStatus.suppressed
        )
        return recipient


def _event_time(payload: BrevoWebhookEvent) -> datetime:
    timestamp = payload.ts_event if payload.ts_event is not None else payload.ts
    if timestamp is None:
        return datetime.now(UTC)
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _is_latest_provider_event(last_event_at: datetime | None, occurred_at: datetime) -> bool:
    if last_event_at is None:
        return True
    # Brevo webhook timestamps have second precision while local outbox acceptance
    # records microseconds. Treat events in the same provider second as current.
    return occurred_at >= last_event_at.replace(microsecond=0)


def _provider_event_id(
    payload: BrevoWebhookEvent,
    normalized_event: str,
    occurred_at: datetime,
) -> str:
    source = "|".join(
        (
            "brevo",
            payload.message_id.strip(),
            normalized_event,
            payload.email.strip().casefold(),
            occurred_at.isoformat(),
        )
    )
    return f"brevo:{hashlib.sha256(source.encode('utf-8')).hexdigest()}"


def _message_id_candidates(value: str) -> set[str]:
    raw = value.strip()
    unwrapped = raw.removeprefix("<").removesuffix(">")
    return {raw, unwrapped, f"<{unwrapped}>"}
