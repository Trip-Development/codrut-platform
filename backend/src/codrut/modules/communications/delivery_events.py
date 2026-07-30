import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.config import Settings
from codrut.modules.communications.models import (
    CampaignRecipient,
    CampaignRecipientStatus,
    EmailEventType,
    EmailSend,
    EmailSendStatus,
)
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.schemas import BrevoWebhookEvent, BrevoWebhookResponse
from codrut.modules.communications.suppression import (
    email_suppression_fingerprint,
    provider_event_fingerprint,
    provider_message_fingerprint,
)

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
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or Settings()
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
        send, locked_recipient, target_is_consistent = (
            await self._lock_delivery_target(message_ids)
        )
        if not target_is_consistent:
            await self.session.rollback()
            send, locked_recipient, target_is_consistent = (
                await self._lock_delivery_target(message_ids)
            )
        if not target_is_consistent:
            await self.session.rollback()
            return BrevoWebhookResponse(status="ignored")
        if send is None:
            if not hasattr(
                self.repository,
                "get_campaign_delivery_tombstone_by_provider_message_fingerprints",
            ):
                return BrevoWebhookResponse(status="ignored")
            tombstone_lookup = (
                self.repository
                .get_campaign_delivery_tombstone_by_provider_message_fingerprints
            )
            tombstone_match = (
                await tombstone_lookup(
                    {
                        provider_message_fingerprint(
                            message_id=message_id,
                            secret=(
                                self.settings.effective_email_suppression_fingerprint_secret
                            ),
                        )
                        for message_id in message_ids
                    },
                    active_at=datetime.now(UTC),
                    for_update=True,
                )
            )
            if tombstone_match is None:
                return BrevoWebhookResponse(status="ignored")
            delivery_tombstone, contact_tombstone = tombstone_match
            recorded = await self.repository.record_late_campaign_delivery_event(
                delivery_tombstone=delivery_tombstone,
                provider_event_fingerprint=provider_event_fingerprint(
                    provider_event_id=provider_event_id,
                    secret=self.settings.effective_email_suppression_fingerprint_secret,
                ),
            )
            if not recorded:
                return BrevoWebhookResponse(status="duplicate")
            await self.repository.increment_campaign_contact_aggregate(
                owner_id=contact_tombstone.owner_id,
                campaign_id=delivery_tombstone.campaign_id,
                metric=f"provider_event:{event_type.value}",
            )
            if normalized_event in PERMANENT_SUPPRESSION_EVENTS:
                if (
                    contact_tombstone.do_not_contact_reason != "unsubscribed"
                    or normalized_event == "unsubscribed"
                ):
                    contact_tombstone.do_not_contact_reason = normalized_event
                    contact_tombstone.suppressed_at = occurred_at
                contact_tombstone.review_after = datetime.now(UTC) + timedelta(
                    days=self.settings.email_suppression_review_days
                )
            await self.session.commit()
            return BrevoWebhookResponse(status="applied")
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
                owner_id=send.owner_id,
                locked_recipient=locked_recipient,
            )
            owner_id = send.owner_id or (recipient.owner_id if recipient is not None else None)
            if owner_id is not None:
                await self.repository.suppress_email(
                    owner_id=owner_id,
                    email=send.recipient_email,
                    email_fingerprint=email_suppression_fingerprint(
                        owner_id=owner_id,
                        email=send.recipient_email,
                        secret=self.settings.effective_email_suppression_fingerprint_secret,
                    ),
                    reason=normalized_event,
                    source_email_send_id=send.id,
                    review_after=datetime.now(UTC)
                    + timedelta(days=self.settings.email_suppression_review_days),
                )

        await self.session.commit()
        return BrevoWebhookResponse(status="applied")

    async def _lock_delivery_target(
        self,
        message_ids: set[str],
    ) -> tuple[EmailSend | None, CampaignRecipient | None, bool]:
        candidate_send = await self.repository.get_email_send_by_provider_message_id(
            message_ids,
            for_update=False,
        )
        locked_recipient = None
        if (
            candidate_send is not None
            and candidate_send.campaign_recipient_id is not None
            and candidate_send.owner_id is not None
        ):
            locked_recipient = await self.repository.get_campaign_recipient(
                candidate_send.campaign_recipient_id,
                owner_id=candidate_send.owner_id,
                catalog_scope="any",
                for_update=True,
            )
        send = await self.repository.get_email_send_by_provider_message_id(
            message_ids,
            for_update=True,
        )
        if send is None:
            return None, locked_recipient, True
        if candidate_send is None or send.id != candidate_send.id:
            return send, locked_recipient, False
        if send.campaign_recipient_id is None or send.owner_id is None:
            return send, locked_recipient, True
        return (
            send,
            locked_recipient,
            locked_recipient is not None
            and locked_recipient.id == send.campaign_recipient_id
            and locked_recipient.owner_id == send.owner_id,
        )

    async def _suppress_campaign_recipient(
        self,
        recipient_id: UUID | None,
        event_type: EmailEventType,
        *,
        owner_id: UUID | None,
        locked_recipient: CampaignRecipient | None = None,
    ) -> CampaignRecipient | None:
        if recipient_id is None or owner_id is None:
            return None
        recipient = locked_recipient
        if recipient is None:
            recipient = await self.repository.get_campaign_recipient(
                recipient_id,
                owner_id=owner_id,
                catalog_scope="any",
                for_update=True,
            )
        if recipient is None:
            return None
        if event_type == EmailEventType.unsubscribed:
            recipient.status = CampaignRecipientStatus.unsubscribed
            if recipient.archived_at is not None:
                recipient.status_before_archive = CampaignRecipientStatus.unsubscribed
        elif recipient.status != CampaignRecipientStatus.unsubscribed:
            recipient.status = CampaignRecipientStatus.suppressed
            if recipient.archived_at is not None:
                recipient.status_before_archive = CampaignRecipientStatus.suppressed
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
