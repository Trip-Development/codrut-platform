import uuid
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.communications.models import (
    Campaign,
    CampaignAsset,
    CampaignRecipient,
    CampaignRecipientEvent,
    CampaignRecipientMembership,
    CampaignRecipientStatus,
    EmailEvent,
    EmailEventType,
    EmailSend,
    EmailSendStatus,
    EmailSuppression,
    EmailTemplate,
)


def _require_owner_id(owner_id: UUID | None) -> UUID:
    if owner_id is None:
        raise ValueError("owner_id is required for campaign contact access")
    return owner_id


class CommunicationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_templates(
        self,
        *,
        active_only: bool = True,
        owner_id: UUID | None = None,
    ) -> list[EmailTemplate]:
        stmt = select(EmailTemplate).order_by(
            EmailTemplate.key,
            EmailTemplate.version.desc(),
        )
        if owner_id is not None:
            stmt = stmt.where(
                or_(EmailTemplate.owner_id == owner_id, EmailTemplate.owner_id.is_(None))
            )
        else:
            stmt = stmt.where(EmailTemplate.owner_id.is_(None))
        if active_only:
            stmt = stmt.where(EmailTemplate.active.is_(True))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_template(
        self,
        key: str,
        *,
        version: int | None = None,
        owner_id: UUID | None = None,
    ) -> EmailTemplate | None:
        stmt = select(EmailTemplate).where(EmailTemplate.key == key)
        if owner_id is not None:
            stmt = stmt.where(
                or_(EmailTemplate.owner_id == owner_id, EmailTemplate.owner_id.is_(None))
            )
        else:
            stmt = stmt.where(EmailTemplate.owner_id.is_(None))
        if version is None:
            stmt = stmt.where(EmailTemplate.active.is_(True)).order_by(
                EmailTemplate.owner_id.is_(None), EmailTemplate.version.desc()
            )
        else:
            stmt = stmt.where(EmailTemplate.version == version).order_by(
                EmailTemplate.owner_id.is_(None)
            )
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def get_latest_version(self, key: str, *, owner_id: UUID | None = None) -> int:
        result = await self.session.execute(
            select(func.max(EmailTemplate.version)).where(
                EmailTemplate.key == key,
                EmailTemplate.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none() or 0

    async def add_template(
        self,
        template: EmailTemplate,
    ) -> EmailTemplate:
        self.session.add(template)
        await self.session.flush()
        return template

    async def deactivate_templates_for_key(
        self,
        key: str,
        *,
        except_version: int | None = None,
        owner_id: UUID | None = None,
    ) -> None:
        # Fetch all templates for this key to modify them in the session
        stmt = select(EmailTemplate).where(EmailTemplate.key == key)
        stmt = stmt.where(EmailTemplate.owner_id == owner_id)
        result = await self.session.execute(stmt)
        templates = result.scalars().all()
        for template in templates:
            if template.version != except_version:
                template.active = False

    async def has_sent_emails(
        self,
        key: str,
        version: int,
        *,
        owner_id: UUID | None = None,
    ) -> bool:
        result = await self.session.execute(
            select(EmailSend.id)
            .where(EmailSend.template_key == key)
            .where(EmailSend.template_version == version)
            .where(EmailSend.owner_id == owner_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def add_campaign_recipients(
        self,
        recipients: list[CampaignRecipient],
        *,
        owner_id: UUID | None,
    ) -> None:
        owner_id = _require_owner_id(owner_id)
        if any(recipient.owner_id != owner_id for recipient in recipients):
            raise ValueError("campaign contacts must belong to the requested owner")
        self.session.add_all(recipients)
        await self.session.flush()

    async def list_campaign_recipients_by_emails(
        self,
        emails: set[str],
        *,
        owner_id: UUID | None,
    ) -> list[CampaignRecipient]:
        owner_id = _require_owner_id(owner_id)
        if not emails:
            return []
        stmt = (
            select(CampaignRecipient)
            .where(
                CampaignRecipient.owner_id == owner_id,
                CampaignRecipient.email.is_not(None),
                func.lower(CampaignRecipient.email).in_(emails),
            )
            .order_by(CampaignRecipient.created_at.asc(), CampaignRecipient.id.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_campaign_recipients(
        self,
        *,
        owner_id: UUID | None,
    ) -> list[CampaignRecipient]:
        owner_id = _require_owner_id(owner_id)
        stmt = (
            select(CampaignRecipient)
            .where(CampaignRecipient.owner_id == owner_id)
            .order_by(CampaignRecipient.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_campaign_recipient(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID | None,
    ) -> CampaignRecipient | None:
        owner_id = _require_owner_id(owner_id)
        stmt = select(CampaignRecipient).where(
            CampaignRecipient.id == recipient_id,
            CampaignRecipient.owner_id == owner_id,
        )
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def get_campaign_recipient_by_email(
        self,
        email: str,
        *,
        owner_id: UUID | None,
    ) -> CampaignRecipient | None:
        owner_id = _require_owner_id(owner_id)
        stmt = (
            select(CampaignRecipient)
            .where(
                CampaignRecipient.owner_id == owner_id,
                func.lower(CampaignRecipient.email) == email.lower(),
            )
            .order_by(CampaignRecipient.created_at.asc(), CampaignRecipient.id.asc())
        )
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def list_campaign_recipients_by_ids(
        self,
        recipient_ids: list[UUID],
        *,
        owner_id: UUID | None,
    ) -> list[CampaignRecipient]:
        owner_id = _require_owner_id(owner_id)
        if not recipient_ids:
            return []
        stmt = select(CampaignRecipient).where(
            CampaignRecipient.id.in_(recipient_ids),
            CampaignRecipient.owner_id == owner_id,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_campaign_recipient_events(
        self,
        *,
        owner_id: UUID | None,
    ) -> list[CampaignRecipientEvent]:
        _require_owner_id(owner_id)
        stmt = (
            select(CampaignRecipientEvent)
            .join(CampaignRecipient, CampaignRecipient.id == CampaignRecipientEvent.recipient_id)
            .where(CampaignRecipient.owner_id == owner_id)
            .order_by(CampaignRecipientEvent.occurred_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_campaign_recipient_event(
        self,
        event: CampaignRecipientEvent,
        *,
        owner_id: UUID | None,
    ) -> CampaignRecipientEvent:
        _require_owner_id(owner_id)
        self.session.add(event)
        await self.session.flush()
        return event

    async def add_campaign(self, campaign: Campaign) -> Campaign:
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def add_campaign_asset(self, asset: CampaignAsset) -> CampaignAsset:
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def get_campaign_asset_by_url(
        self,
        public_url: str,
        *,
        owner_id: UUID,
        for_update: bool = False,
    ) -> CampaignAsset | None:
        statement = select(CampaignAsset).where(
            CampaignAsset.public_url == public_url,
            CampaignAsset.owner_id == owner_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement.limit(1))
        return result.scalar_one_or_none()

    async def get_campaign_asset_by_file_name(
        self,
        file_name: str,
        *,
        owner_id: UUID,
        for_update: bool = False,
    ) -> CampaignAsset | None:
        statement = select(CampaignAsset).where(
            CampaignAsset.file_name == file_name,
            CampaignAsset.owner_id == owner_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement.limit(1))
        return result.scalar_one_or_none()

    async def delete_campaign_asset_record(self, asset: CampaignAsset) -> None:
        await self.session.delete(asset)

    async def list_campaign_assets_for_campaign(
        self,
        campaign_id: UUID,
        *,
        owner_id: UUID,
    ) -> list[CampaignAsset]:
        result = await self.session.execute(
            select(CampaignAsset).where(
                CampaignAsset.campaign_id == campaign_id,
                CampaignAsset.owner_id == owner_id,
            )
        )
        return list(result.scalars().all())

    async def get_campaign(
        self,
        campaign_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> Campaign | None:
        stmt = select(Campaign).where(Campaign.id == campaign_id)
        if owner_id is not None:
            stmt = stmt.where(Campaign.owner_id == owner_id)
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def list_campaigns(
        self,
        *,
        owner_id: UUID | None = None,
    ) -> list[Campaign]:
        stmt = select(Campaign).order_by(Campaign.created_at.desc())
        if owner_id is not None:
            stmt = stmt.where(Campaign.owner_id == owner_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_accepted_campaign_recipient_ids(
        self,
        campaign_id: UUID,
        *,
        owner_id: UUID | None,
    ) -> set[UUID]:
        owner_id = _require_owner_id(owner_id)
        result = await self.session.execute(
            select(EmailSend.campaign_recipient_id)
            .join(Campaign, Campaign.id == EmailSend.campaign_id)
            .join(CampaignRecipient, CampaignRecipient.id == EmailSend.campaign_recipient_id)
            .where(EmailSend.campaign_id == campaign_id)
            .where(Campaign.owner_id == owner_id)
            .where(CampaignRecipient.owner_id == owner_id)
            .where(EmailSend.owner_id == owner_id)
            .where(EmailSend.campaign_recipient_id.is_not(None))
            .where(
                EmailSend.status.in_(
                    (
                        EmailSendStatus.queued,
                        EmailSendStatus.dispatching,
                        EmailSendStatus.accepted,
                        EmailSendStatus.delivered,
                        EmailSendStatus.bounced,
                    )
                )
            )
        )
        return {recipient_id for recipient_id in result.scalars().all() if recipient_id is not None}

    async def list_campaign_delivery_status_by_recipient_ids(
        self,
        campaign_id: UUID,
        recipient_ids: list[UUID],
        *,
        owner_id: UUID | None,
    ) -> dict[UUID, str]:
        owner_id = _require_owner_id(owner_id)
        if not recipient_ids:
            return {}

        result = await self.session.execute(
            select(EmailSend.campaign_recipient_id, EmailSend.status)
            .join(Campaign, Campaign.id == EmailSend.campaign_id)
            .join(CampaignRecipient, CampaignRecipient.id == EmailSend.campaign_recipient_id)
            .where(EmailSend.campaign_id == campaign_id)
            .where(Campaign.owner_id == owner_id)
            .where(CampaignRecipient.owner_id == owner_id)
            .where(EmailSend.owner_id == owner_id)
            .where(EmailSend.campaign_recipient_id.in_(recipient_ids))
        )
        delivery_statuses: dict[UUID, str] = {}
        status_priority = {
            "failed": 1,
            "queued": 2,
            "sent": 3,
        }
        status_labels = {
            EmailSendStatus.failed: "failed",
            EmailSendStatus.bounced: "failed",
            EmailSendStatus.queued: "queued",
            EmailSendStatus.dispatching: "queued",
            EmailSendStatus.accepted: "sent",
            EmailSendStatus.delivered: "sent",
        }
        for recipient_id, status in result.all():
            if recipient_id is None:
                continue
            next_label = status_labels.get(status, "not_sent")
            next_priority = status_priority.get(next_label, 0)
            current_priority = status_priority.get(
                delivery_statuses.get(recipient_id, "not_sent"),
                0,
            )
            if next_priority > current_priority:
                delivery_statuses[recipient_id] = next_label
        return delivery_statuses

    async def list_campaign_member_recipient_ids(
        self,
        campaign_id: UUID,
        *,
        owner_id: UUID | None,
    ) -> list[UUID]:
        owner_id = _require_owner_id(owner_id)
        stmt = (
            select(CampaignRecipientMembership.recipient_id)
            .join(Campaign, Campaign.id == CampaignRecipientMembership.campaign_id)
            .join(
                CampaignRecipient,
                CampaignRecipient.id == CampaignRecipientMembership.recipient_id,
            )
            .where(CampaignRecipientMembership.campaign_id == campaign_id)
            .where(Campaign.owner_id == owner_id)
            .where(CampaignRecipient.owner_id == owner_id)
            .order_by(CampaignRecipientMembership.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_campaign_member_recipients(
        self,
        campaign_id: UUID,
        *,
        owner_id: UUID | None,
    ) -> list[CampaignRecipient]:
        owner_id = _require_owner_id(owner_id)
        stmt = (
            select(CampaignRecipient)
            .join(
                CampaignRecipientMembership,
                CampaignRecipientMembership.recipient_id == CampaignRecipient.id,
            )
            .join(Campaign, Campaign.id == CampaignRecipientMembership.campaign_id)
            .where(CampaignRecipientMembership.campaign_id == campaign_id)
            .where(Campaign.owner_id == owner_id)
            .where(CampaignRecipient.owner_id == owner_id)
            .order_by(CampaignRecipientMembership.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def replace_campaign_memberships(
        self,
        campaign_id: UUID,
        recipient_ids: list[UUID],
        *,
        source: str = "manual",
        owner_id: UUID | None,
    ) -> None:
        owner_id = _require_owner_id(owner_id)
        campaign = await self.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            raise ValueError("campaign does not belong to the requested owner")
        owned_recipients = await self.list_campaign_recipients_by_ids(
            recipient_ids,
            owner_id=owner_id,
        )
        if (
            {recipient.id for recipient in owned_recipients} != set(recipient_ids)
            or any(recipient.owner_id != owner_id for recipient in owned_recipients)
        ):
            raise ValueError("campaign membership contains contacts owned by another trainer")
        existing_ids = set(
            await self.list_campaign_member_recipient_ids(campaign_id, owner_id=owner_id)
        )
        next_ids = set(recipient_ids)
        delete_ids = existing_ids - next_ids
        if delete_ids:
            await self.session.execute(
                delete(CampaignRecipientMembership)
                .where(CampaignRecipientMembership.campaign_id == campaign_id)
                .where(CampaignRecipientMembership.recipient_id.in_(delete_ids))
            )
        add_ids = next_ids - existing_ids
        if add_ids:
            self.session.add_all(
                [
                    CampaignRecipientMembership(
                        campaign_id=campaign_id,
                        recipient_id=recipient_id,
                        source=source,
                    )
                    for recipient_id in add_ids
                ]
            )
        await self.session.flush()

    async def count_accepted_sends_since(self, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count(EmailSend.id))
            .where(
                EmailSend.status.in_(
                    (
                        EmailSendStatus.queued,
                        EmailSendStatus.dispatching,
                        EmailSendStatus.accepted,
                        EmailSendStatus.delivered,
                    )
                )
            )
            .where(EmailSend.created_at >= since)
        )
        return int(result.scalar_one() or 0)

    async def delete_campaign(self, campaign: Campaign) -> None:
        await self.session.delete(campaign)
        await self.session.flush()

    async def add_email_send(self, send: EmailSend) -> EmailSend:
        self.session.add(send)
        await self.session.flush()
        return send

    async def enqueue_email_send(self, send: EmailSend) -> tuple[EmailSend, bool]:
        if send.idempotency_key is None:
            raise ValueError("durable email outbox rows require an idempotency key")

        existing = await self.get_email_send_by_idempotency_key(send.idempotency_key)
        if existing is not None:
            return existing, False

        try:
            async with self.session.begin_nested():
                self.session.add(send)
                await self.session.flush()
        except IntegrityError:
            existing = await self.get_email_send_by_idempotency_key(send.idempotency_key)
            if existing is None:
                raise
            return existing, False
        await self.add_email_event(send.id, EmailEventType.queued, occurred_at=send.created_at)
        return send, True

    async def add_email_event(
        self,
        email_send_id: UUID,
        event_type: EmailEventType,
        *,
        occurred_at: datetime,
        provider_event_id: str | None = None,
    ) -> EmailEvent:
        event = EmailEvent(
            id=uuid.uuid4(),
            email_send_id=email_send_id,
            event_type=event_type,
            provider_event_id=provider_event_id,
            occurred_at=occurred_at,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_email_event_by_provider_event_id(
        self,
        provider_event_id: str,
    ) -> EmailEvent | None:
        result = await self.session.execute(
            select(EmailEvent)
            .where(EmailEvent.provider_event_id == provider_event_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_email_send_by_provider_message_id(
        self,
        message_ids: set[str],
        *,
        for_update: bool = False,
    ) -> EmailSend | None:
        if not message_ids:
            return None
        statement = (
            select(EmailSend)
            .where(EmailSend.provider_message_id.in_(message_ids))
            .order_by(EmailSend.created_at.desc())
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_email_send_by_idempotency_key(self, key: str) -> EmailSend | None:
        result = await self.session.execute(
            select(EmailSend).where(EmailSend.idempotency_key == key).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_email_suppression(
        self,
        *,
        owner_id: UUID,
        email: str,
    ) -> EmailSuppression | None:
        result = await self.session.execute(
            select(EmailSuppression)
            .where(
                EmailSuppression.owner_id == owner_id,
                func.lower(EmailSuppression.email) == email.strip().casefold(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def suppress_email(
        self,
        *,
        owner_id: UUID,
        email: str,
        reason: str,
        source_email_send_id: UUID | None,
    ) -> EmailSuppression:
        suppression = await self.get_email_suppression(owner_id=owner_id, email=email)
        if suppression is None:
            suppression = EmailSuppression(
                owner_id=owner_id,
                email=email.strip().casefold(),
                reason=reason,
                source_email_send_id=source_email_send_id,
            )
            self.session.add(suppression)
        else:
            suppression.reason = reason
            suppression.source_email_send_id = source_email_send_id
        await self.session.flush()
        return suppression

    async def list_successfully_delivered_assignment_ids(
        self,
        assignment_ids: set[UUID],
    ) -> set[UUID]:
        if not assignment_ids:
            return set()
        result = await self.session.execute(
            select(EmailSend.assignment_id).where(
                EmailSend.assignment_id.in_(assignment_ids),
                EmailSend.status.in_(
                    (EmailSendStatus.accepted, EmailSendStatus.delivered)
                ),
            )
        )
        return {
            assignment_id
            for assignment_id in result.scalars().all()
            if assignment_id is not None
        }

    async def mark_stale_provider_requests_indeterminate(
        self,
        *,
        now: datetime,
    ) -> list[EmailSend]:
        result = await self.session.execute(
            select(EmailSend)
            .where(
                EmailSend.status == EmailSendStatus.dispatching,
                EmailSend.lease_expires_at <= now,
                EmailSend.provider_request_started_at.is_not(None),
            )
            .with_for_update(skip_locked=True)
        )
        sends = list(result.scalars().all())
        for send in sends:
            send.status = EmailSendStatus.indeterminate
            send.error_details = (
                "Provider request outcome requires reconciliation before retry."
            )
            send.lease_token = None
            send.lease_expires_at = None
            send.next_attempt_at = None
            send.last_event_at = now
            await self.add_email_event(send.id, EmailEventType.indeterminate, occurred_at=now)
        return sends

    async def fail_exhausted_stale_email_sends(self, *, now: datetime) -> list[EmailSend]:
        result = await self.session.execute(
            select(EmailSend)
            .where(
                EmailSend.status == EmailSendStatus.dispatching,
                EmailSend.lease_expires_at <= now,
                EmailSend.attempt_count >= EmailSend.max_attempts,
                EmailSend.provider_request_started_at.is_(None),
            )
            .with_for_update(skip_locked=True)
        )
        sends = list(result.scalars().all())
        for send in sends:
            send.status = EmailSendStatus.failed
            send.error_details = "Delivery lease expired after the maximum number of attempts."
            send.lease_token = None
            send.lease_expires_at = None
            send.next_attempt_at = None
            send.last_event_at = now
            await self.add_email_event(send.id, EmailEventType.failed, occurred_at=now)
        return sends

    async def claim_due_email_sends(
        self,
        *,
        now: datetime,
        lease_duration: timedelta,
        limit: int,
    ) -> list[EmailSend]:
        result = await self.session.execute(
            select(EmailSend)
            .where(
                or_(
                    and_(
                        EmailSend.status == EmailSendStatus.queued,
                        EmailSend.next_attempt_at <= now,
                    ),
                    and_(
                        EmailSend.status == EmailSendStatus.dispatching,
                        EmailSend.lease_expires_at <= now,
                        EmailSend.provider_request_started_at.is_(None),
                    ),
                ),
                EmailSend.message_payload.is_not(None),
                EmailSend.attempt_count < EmailSend.max_attempts,
            )
            .order_by(
                EmailSend.next_attempt_at.asc().nullsfirst(),
                EmailSend.created_at.asc(),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        sends = list(result.scalars().all())
        for send in sends:
            send.status = EmailSendStatus.dispatching
            send.attempt_count += 1
            send.lease_token = str(uuid.uuid4())
            send.lease_expires_at = now + lease_duration
            send.last_event_at = now
            send.error_details = None
            await self.add_email_event(send.id, EmailEventType.claimed, occurred_at=now)
        await self.session.flush()
        return sends

    async def begin_email_provider_request(
        self,
        send_id: UUID,
        lease_token: str,
        *,
        provider_idempotency_key: str,
        now: datetime,
    ) -> EmailSend | None:
        send = await self.get_claimed_email_send(send_id, lease_token)
        if send is None:
            return None
        send.provider_idempotency_key = provider_idempotency_key
        send.provider_request_started_at = now
        send.last_event_at = now
        await self.session.flush()
        return send

    async def get_claimed_email_send(
        self,
        send_id: UUID,
        lease_token: str,
    ) -> EmailSend | None:
        result = await self.session.execute(
            select(EmailSend)
            .where(
                EmailSend.id == send_id,
                EmailSend.status == EmailSendStatus.dispatching,
                EmailSend.lease_token == lease_token,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def cancel_queued_campaign_sends(
        self,
        campaign_id: UUID,
        *,
        now: datetime,
    ) -> int:
        result = await self.session.execute(
            select(EmailSend)
            .where(
                EmailSend.campaign_id == campaign_id,
                EmailSend.status == EmailSendStatus.queued,
            )
            .with_for_update(skip_locked=True)
        )
        sends = list(result.scalars().all())
        for send in sends:
            await self.mark_email_send_cancelled(send, now=now)
        return len(sends)

    async def mark_email_send_cancelled(
        self,
        send: EmailSend,
        *,
        now: datetime,
    ) -> None:
        send.status = EmailSendStatus.cancelled
        send.cancelled_at = now
        send.lease_token = None
        send.lease_expires_at = None
        send.next_attempt_at = None
        send.last_event_at = now
        await self.add_email_event(send.id, EmailEventType.cancelled, occurred_at=now)

    async def campaign_recipient_is_active(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID,
    ) -> bool:
        result = await self.session.execute(
            select(CampaignRecipient.status)
            .where(
                CampaignRecipient.id == recipient_id,
                CampaignRecipient.owner_id == owner_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() == CampaignRecipientStatus.active

    async def flush(self) -> None:
        await self.session.flush()
