import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.communications.models import (
    Campaign,
    CampaignAsset,
    CampaignContactAggregate,
    CampaignContactTombstone,
    CampaignDeliveryEventTombstone,
    CampaignDeliveryTombstone,
    CampaignRecipient,
    CampaignRecipientEvent,
    CampaignRecipientMembership,
    CampaignRecipientStatus,
    EmailEvent,
    EmailEventType,
    EmailSend,
    EmailSendStatus,
    EmailSuppression,
    EmailSuppressionReview,
    EmailTemplate,
)


def _require_owner_id(owner_id: UUID | None) -> UUID:
    if owner_id is None:
        raise ValueError("owner_id is required for campaign contact access")
    return owner_id


class CommunicationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def acquire_email_capacity_lock(self) -> None:
        # One transaction at a time may reserve daily capacity. The lock is
        # released automatically on commit/rollback and carries no user data.
        await self.session.execute(
            text("select pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": 0x434F44525554454D},
        )

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
        include_archived: bool = False,
        for_update: bool = False,
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
        if not include_archived:
            stmt = stmt.where(CampaignRecipient.archived_at.is_(None))
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_campaign_recipients(
        self,
        *,
        owner_id: UUID | None,
        catalog_scope: Literal["active", "archived"] = "active",
    ) -> list[CampaignRecipient]:
        owner_id = _require_owner_id(owner_id)
        archive_clause = (
            CampaignRecipient.archived_at.is_not(None)
            if catalog_scope == "archived"
            else CampaignRecipient.archived_at.is_(None)
        )
        stmt = (
            select(CampaignRecipient)
            .where(
                CampaignRecipient.owner_id == owner_id,
                archive_clause,
            )
            .order_by(CampaignRecipient.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_campaign_recipient(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID | None,
        catalog_scope: Literal["active", "archived", "any"] = "active",
        for_update: bool = False,
    ) -> CampaignRecipient | None:
        owner_id = _require_owner_id(owner_id)
        stmt = select(CampaignRecipient).where(
            CampaignRecipient.id == recipient_id,
            CampaignRecipient.owner_id == owner_id,
        )
        if catalog_scope == "active":
            stmt = stmt.where(CampaignRecipient.archived_at.is_(None))
        elif catalog_scope == "archived":
            stmt = stmt.where(CampaignRecipient.archived_at.is_not(None))
        if for_update:
            stmt = stmt.with_for_update()
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
                CampaignRecipient.archived_at.is_(None),
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
            CampaignRecipient.archived_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def lock_campaign_recipients_for_send(
        self,
        recipient_ids: list[UUID],
        *,
        owner_id: UUID | None,
    ) -> list[CampaignRecipient]:
        owner_id = _require_owner_id(owner_id)
        if not recipient_ids:
            return []
        result = await self.session.execute(
            select(CampaignRecipient)
            .where(
                CampaignRecipient.id.in_(recipient_ids),
                CampaignRecipient.owner_id == owner_id,
                CampaignRecipient.archived_at.is_(None),
            )
            .order_by(CampaignRecipient.id.asc())
            .with_for_update()
        )
        return list(result.scalars().all())

    async def list_campaign_recipient_events(
        self,
        *,
        owner_id: UUID | None,
    ) -> list[CampaignRecipientEvent]:
        _require_owner_id(owner_id)
        stmt = (
            select(CampaignRecipientEvent)
            .outerjoin(
                CampaignRecipient,
                CampaignRecipient.id == CampaignRecipientEvent.recipient_id,
            )
            .where(
                or_(
                    CampaignRecipientEvent.owner_id == owner_id,
                    and_(
                        CampaignRecipientEvent.owner_id.is_(None),
                        CampaignRecipient.owner_id == owner_id,
                    ),
                )
            )
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
        owner_id = _require_owner_id(owner_id)
        if event.owner_id != owner_id:
            raise ValueError("campaign contact events must belong to the requested owner")
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
        for_update: bool = False,
    ) -> Campaign | None:
        stmt = select(Campaign).where(Campaign.id == campaign_id)
        if owner_id is not None:
            stmt = stmt.where(Campaign.owner_id == owner_id)
        if for_update:
            stmt = stmt.with_for_update()
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
        owned_recipients = await self.lock_campaign_recipients_for_send(
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
            # Capacity is reserved by creating an outbox row. Delivery status is
            # mutable: accepted messages may later bounce and uncertain provider
            # requests become indeterminate. Neither transition restores daily
            # capacity. Only work cancelled before delivery is released.
            .where(EmailSend.status != EmailSendStatus.cancelled)
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
        email_fingerprint: str,
        email: str | None = None,
    ) -> EmailSuppression | CampaignContactTombstone | None:
        result = await self.session.execute(
            select(EmailSuppression)
            .where(
                EmailSuppression.owner_id == owner_id,
                EmailSuppression.email_fingerprint == email_fingerprint,
            )
            .limit(1)
        )
        suppression = result.scalar_one_or_none()
        if suppression is not None:
            return suppression
        tombstone_result = await self.session.execute(
            select(CampaignContactTombstone)
            .where(
                CampaignContactTombstone.owner_id == owner_id,
                CampaignContactTombstone.email_fingerprint == email_fingerprint,
                CampaignContactTombstone.do_not_contact_reason.is_not(None),
            )
            .limit(1)
        )
        tombstone = tombstone_result.scalar_one_or_none()
        if tombstone is not None or email is None:
            return tombstone
        legacy_result = await self.session.execute(
            select(EmailSuppression)
            .where(
                EmailSuppression.owner_id == owner_id,
                func.lower(EmailSuppression.legacy_email)
                == email.strip().casefold(),
            )
            .limit(1)
        )
        return legacy_result.scalar_one_or_none()

    async def list_email_suppressions_by_fingerprints(
        self,
        *,
        owner_id: UUID,
        email_fingerprints: set[str],
        normalized_emails: set[str] | None = None,
    ) -> list[EmailSuppression | CampaignContactTombstone]:
        normalized_emails = {
            email.strip().casefold()
            for email in (normalized_emails or set())
            if email.strip()
        }
        if not email_fingerprints and not normalized_emails:
            return []
        suppression_match = EmailSuppression.email_fingerprint.in_(
            email_fingerprints
        )
        if normalized_emails:
            suppression_match = or_(
                suppression_match,
                func.lower(EmailSuppression.legacy_email).in_(
                    normalized_emails
                ),
            )
        result = await self.session.execute(
            select(EmailSuppression).where(
                EmailSuppression.owner_id == owner_id,
                suppression_match,
            )
        )
        tombstone_result = await self.session.execute(
            select(CampaignContactTombstone).where(
                CampaignContactTombstone.owner_id == owner_id,
                CampaignContactTombstone.email_fingerprint.in_(email_fingerprints),
                CampaignContactTombstone.do_not_contact_reason.is_not(None),
            )
        )
        return [*result.scalars().all(), *tombstone_result.scalars().all()]

    async def suppress_email(
        self,
        *,
        owner_id: UUID,
        email: str,
        email_fingerprint: str,
        reason: str,
        source_email_send_id: UUID | None,
        review_after: datetime,
    ) -> EmailSuppression | CampaignContactTombstone:
        suppression = await self.get_email_suppression(
            owner_id=owner_id,
            email_fingerprint=email_fingerprint,
            email=email,
        )
        if isinstance(suppression, CampaignContactTombstone):
            suppression.review_after = max(suppression.review_after, review_after)
            if (
                suppression.do_not_contact_reason != "unsubscribed"
                or reason == "unsubscribed"
            ):
                suppression.do_not_contact_reason = reason
                suppression.suppressed_at = datetime.now(UTC)
            await self.session.flush()
            return suppression
        if suppression is None:
            suppression = EmailSuppression(
                owner_id=owner_id,
                legacy_email=email.strip().casefold(),
                email_fingerprint=email_fingerprint,
                reason=reason,
                source_email_send_id=source_email_send_id,
                review_after=review_after,
            )
            self.session.add(suppression)
        else:
            suppression.email_fingerprint = email_fingerprint
            suppression.review_after = max(
                suppression.review_after or review_after,
                review_after,
            )
            if suppression.reason != "unsubscribed" or reason == "unsubscribed":
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
                CampaignRecipient.archived_at.is_(None),
            )
            .with_for_update()
            .limit(1)
        )
        return result.scalar_one_or_none() == CampaignRecipientStatus.active

    async def campaign_send_ownership_is_valid(
        self,
        send: EmailSend,
    ) -> bool:
        if (
            send.owner_id is None
            or send.campaign_id is None
            or send.campaign_recipient_id is None
        ):
            return False
        result = await self.session.execute(
            select(Campaign.id)
            .join(
                CampaignRecipient,
                CampaignRecipient.id == send.campaign_recipient_id,
            )
            .where(
                Campaign.id == send.campaign_id,
                Campaign.owner_id == send.owner_id,
                CampaignRecipient.owner_id == send.owner_id,
            )
            .with_for_update(of=(Campaign, CampaignRecipient))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def delete_campaign_recipient_memberships(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID,
    ) -> int:
        owned_campaign_ids = select(Campaign.id).where(Campaign.owner_id == owner_id)
        result = await self.session.execute(
            delete(CampaignRecipientMembership).where(
                CampaignRecipientMembership.recipient_id == recipient_id,
                CampaignRecipientMembership.campaign_id.in_(owned_campaign_ids),
            )
        )
        return int(result.rowcount or 0)

    async def cancel_unsent_campaign_recipient_sends(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID,
        now: datetime,
    ) -> tuple[int, int]:
        result = await self.session.execute(
            select(EmailSend)
            .where(
                EmailSend.campaign_recipient_id == recipient_id,
                EmailSend.owner_id == owner_id,
                EmailSend.status.in_(
                    (EmailSendStatus.queued, EmailSendStatus.dispatching)
                ),
            )
            .with_for_update(skip_locked=True)
        )
        cancelled = 0
        in_flight = 0
        for send in result.scalars().all():
            if send.provider_request_started_at is not None:
                in_flight += 1
                continue
            await self.mark_email_send_cancelled(send, now=now)
            cancelled += 1

        indeterminate_result = await self.session.execute(
            select(func.count(EmailSend.id)).where(
                EmailSend.campaign_recipient_id == recipient_id,
                EmailSend.owner_id == owner_id,
                EmailSend.status.in_(
                    (EmailSendStatus.accepted, EmailSendStatus.indeterminate)
                ),
            )
        )
        in_flight += int(indeterminate_result.scalar_one() or 0)
        return cancelled, in_flight

    async def list_unresolved_campaign_recipient_sends(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID,
    ) -> list[EmailSend]:
        result = await self.session.execute(
            select(EmailSend)
            .where(
                EmailSend.campaign_recipient_id == recipient_id,
                EmailSend.owner_id == owner_id,
                EmailSend.status.in_(
                    (
                        EmailSendStatus.queued,
                        EmailSendStatus.dispatching,
                        EmailSendStatus.accepted,
                        EmailSendStatus.indeterminate,
                    )
                ),
            )
            .with_for_update()
        )
        return list(result.scalars().all())

    async def list_campaign_recipient_sends(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID,
    ) -> list[EmailSend]:
        result = await self.session.execute(
            select(EmailSend).where(
                EmailSend.campaign_recipient_id == recipient_id,
                EmailSend.owner_id == owner_id,
            )
        )
        return list(result.scalars().all())

    async def list_campaign_recipient_provider_event_ids(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID,
    ) -> list[tuple[str, str]]:
        result = await self.session.execute(
            select(
                EmailSend.provider_message_id,
                EmailEvent.provider_event_id,
            )
            .join(EmailEvent, EmailEvent.email_send_id == EmailSend.id)
            .where(
                EmailSend.campaign_recipient_id == recipient_id,
                EmailSend.owner_id == owner_id,
                EmailSend.provider_message_id.is_not(None),
                EmailEvent.provider_event_id.is_not(None),
            )
        )
        return [
            (provider_message_id, provider_event_id)
            for provider_message_id, provider_event_id in result.all()
            if provider_message_id is not None and provider_event_id is not None
        ]

    async def create_campaign_contact_tombstones(
        self,
        *,
        owner_id: UUID,
        former_recipient_id: UUID,
        email_fingerprint: str,
        do_not_contact_reason: str | None,
        suppressed_at: datetime | None,
        review_after: datetime,
        delivery_fingerprints: list[tuple[str, UUID | None]],
        delivery_expires_at: datetime,
        provider_event_fingerprints: list[tuple[str, str]],
    ) -> CampaignContactTombstone:
        result = await self.session.execute(
            select(CampaignContactTombstone)
            .where(
                CampaignContactTombstone.owner_id == owner_id,
                CampaignContactTombstone.former_recipient_id == former_recipient_id,
            )
            .with_for_update()
            .limit(1)
        )
        tombstone = result.scalar_one_or_none()
        if tombstone is None:
            tombstone = CampaignContactTombstone(
                owner_id=owner_id,
                former_recipient_id=former_recipient_id,
                email_fingerprint=email_fingerprint,
                do_not_contact_reason=do_not_contact_reason,
                suppressed_at=suppressed_at,
                review_after=review_after,
            )
            self.session.add(tombstone)
            await self.session.flush()
        else:
            tombstone.email_fingerprint = email_fingerprint
            tombstone.review_after = max(tombstone.review_after, review_after)
            if (
                tombstone.do_not_contact_reason != "unsubscribed"
                or do_not_contact_reason == "unsubscribed"
            ):
                tombstone.do_not_contact_reason = (
                    do_not_contact_reason or tombstone.do_not_contact_reason
                )
                tombstone.suppressed_at = suppressed_at or tombstone.suppressed_at

        for provider_fingerprint, campaign_id in delivery_fingerprints:
            statement = pg_insert(CampaignDeliveryTombstone).values(
                id=uuid.uuid4(),
                contact_tombstone_id=tombstone.id,
                campaign_id=campaign_id,
                provider_message_fingerprint=provider_fingerprint,
                expires_at=delivery_expires_at,
            )
            await self.session.execute(
                statement.on_conflict_do_nothing(
                    constraint=(
                        "uq_campaign_delivery_tombstones_provider_message_fingerprint"
                    )
                )
            )
        delivery_by_fingerprint: dict[str, CampaignDeliveryTombstone] = {}
        expected_delivery_fingerprints = {
            provider_fingerprint
            for provider_fingerprint, _ in delivery_fingerprints
        }
        if expected_delivery_fingerprints:
            delivery_result = await self.session.execute(
                select(CampaignDeliveryTombstone).where(
                    CampaignDeliveryTombstone.provider_message_fingerprint.in_(
                        expected_delivery_fingerprints
                    )
                )
            )
            delivery_by_fingerprint = {
                delivery.provider_message_fingerprint: delivery
                for delivery in delivery_result.scalars().all()
            }
            for provider_fingerprint in expected_delivery_fingerprints:
                delivery = delivery_by_fingerprint.get(provider_fingerprint)
                if delivery is None:
                    raise ValueError(
                        "provider message fingerprint has no delivery tombstone"
                    )
                if delivery.contact_tombstone_id != tombstone.id:
                    raise ValueError(
                        "provider message fingerprint belongs to another contact"
                    )
        if provider_event_fingerprints:
            for provider_fingerprint, event_fingerprint in provider_event_fingerprints:
                delivery = delivery_by_fingerprint.get(provider_fingerprint)
                if delivery is None:
                    raise ValueError(
                        "provider event fingerprint has no delivery tombstone"
                    )
                statement = pg_insert(CampaignDeliveryEventTombstone).values(
                    id=uuid.uuid4(),
                    delivery_tombstone_id=delivery.id,
                    provider_event_fingerprint=event_fingerprint,
                )
                await self.session.execute(
                    statement.on_conflict_do_nothing(
                        constraint="uq_delivery_event_tombstone_provider_fingerprint"
                    )
                )
        await self.session.flush()
        return tombstone

    async def get_campaign_contact_tombstone(
        self,
        *,
        owner_id: UUID,
        former_recipient_id: UUID,
        for_update: bool = False,
    ) -> CampaignContactTombstone | None:
        statement = (
            select(CampaignContactTombstone)
            .where(
                CampaignContactTombstone.owner_id == owner_id,
                CampaignContactTombstone.former_recipient_id == former_recipient_id,
            )
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_campaign_delivery_tombstone_by_provider_message_fingerprints(
        self,
        provider_message_fingerprints: set[str],
        *,
        active_at: datetime,
        for_update: bool = False,
    ) -> tuple[CampaignDeliveryTombstone, CampaignContactTombstone] | None:
        if not provider_message_fingerprints:
            return None
        statement = (
            select(CampaignDeliveryTombstone, CampaignContactTombstone)
            .join(
                CampaignContactTombstone,
                CampaignContactTombstone.id
                == CampaignDeliveryTombstone.contact_tombstone_id,
            )
            .where(
                CampaignDeliveryTombstone.provider_message_fingerprint.in_(
                    provider_message_fingerprints
                ),
                CampaignDeliveryTombstone.expires_at > active_at,
            )
            .limit(1)
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    async def record_late_campaign_delivery_event(
        self,
        *,
        delivery_tombstone: CampaignDeliveryTombstone,
        provider_event_fingerprint: str,
    ) -> bool:
        statement = pg_insert(CampaignDeliveryEventTombstone).values(
            id=uuid.uuid4(),
            delivery_tombstone_id=delivery_tombstone.id,
            provider_event_fingerprint=provider_event_fingerprint,
        )
        result = await self.session.execute(
            statement.on_conflict_do_nothing(
                constraint="uq_delivery_event_tombstone_provider_fingerprint"
            )
        )
        return bool(result.rowcount)

    async def increment_campaign_contact_aggregate(
        self,
        *,
        owner_id: UUID,
        campaign_id: UUID | None,
        metric: str,
        count: int = 1,
    ) -> None:
        scope_key = str(campaign_id) if campaign_id is not None else "unattributed"
        statement = pg_insert(CampaignContactAggregate).values(
            owner_id=owner_id,
            scope_key=scope_key,
            campaign_id=campaign_id,
            metric=metric,
            count=count,
        )
        await self.session.execute(
            statement.on_conflict_do_update(
                constraint="uq_campaign_contact_aggregates_owner_scope_metric",
                set_={
                    "count": CampaignContactAggregate.count + count,
                    "updated_at": func.now(),
                },
            )
        )

    async def anonymize_campaign_recipient_history(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID,
        allow_provider_unresolved: bool = False,
    ) -> int:
        result = await self.session.execute(
            select(EmailSend).where(
                EmailSend.campaign_recipient_id == recipient_id,
                EmailSend.owner_id == owner_id,
            )
        )
        sends = list(result.scalars().all())
        non_provider_unresolved = [
            send
            for send in sends
            if send.status
            in {
                EmailSendStatus.queued,
                EmailSendStatus.dispatching,
            }
        ]
        provider_unresolved = [
            send
            for send in sends
            if send.status
            in {
                EmailSendStatus.accepted,
                EmailSendStatus.indeterminate,
            }
        ]
        if non_provider_unresolved or (provider_unresolved and not allow_provider_unresolved):
            raise ValueError("campaign contact still has unresolved email deliveries")

        send_ids = [send.id for send in sends]
        email_event_result = await self.session.execute(
            select(EmailEvent, EmailSend.campaign_id)
            .join(EmailSend, EmailSend.id == EmailEvent.email_send_id)
            .where(EmailEvent.email_send_id.in_(send_ids))
        )
        email_events = list(email_event_result.all()) if send_ids else []
        event_result = await self.session.execute(
            select(CampaignRecipientEvent).where(
                CampaignRecipientEvent.recipient_id == recipient_id,
                or_(
                    CampaignRecipientEvent.owner_id == owner_id,
                    CampaignRecipientEvent.owner_id.is_(None),
                ),
            )
        )
        events = list(event_result.scalars().all())
        aggregate_counts: dict[tuple[UUID | None, str], int] = {}
        for send in sends:
            status = (
                EmailSendStatus.indeterminate
                if allow_provider_unresolved
                and send.status
                in {EmailSendStatus.accepted, EmailSendStatus.indeterminate}
                else send.status
            )
            key = (send.campaign_id, f"send:{status.value}")
            aggregate_counts[key] = aggregate_counts.get(key, 0) + 1
        for email_event, campaign_id in email_events:
            key = (campaign_id, f"provider_event:{email_event.event_type.value}")
            aggregate_counts[key] = aggregate_counts.get(key, 0) + 1
        for event in events:
            key = (event.campaign_id, f"event:{event.event_type}")
            aggregate_counts[key] = aggregate_counts.get(key, 0) + 1
        for (campaign_id, metric), count in aggregate_counts.items():
            await self.increment_campaign_contact_aggregate(
                owner_id=owner_id,
                campaign_id=campaign_id,
                metric=metric,
                count=count,
            )

        for event in events:
            await self.session.delete(event)
        for send in sends:
            await self.session.delete(send)
        await self.session.flush()
        return len(sends)

    async def list_campaign_contact_aggregates(
        self,
        *,
        owner_id: UUID,
    ) -> list[CampaignContactAggregate]:
        result = await self.session.execute(
            select(CampaignContactAggregate)
            .where(CampaignContactAggregate.owner_id == owner_id)
            .order_by(
                CampaignContactAggregate.scope_key,
                CampaignContactAggregate.metric,
            )
        )
        return list(result.scalars().all())

    async def list_due_email_suppressions(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[EmailSuppression]:
        result = await self.session.execute(
            select(EmailSuppression)
            .where(
                EmailSuppression.review_after.is_not(None),
                EmailSuppression.review_after <= now,
            )
            .order_by(EmailSuppression.review_after.asc(), EmailSuppression.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def list_due_campaign_contact_tombstones(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[CampaignContactTombstone]:
        result = await self.session.execute(
            select(CampaignContactTombstone)
            .where(
                CampaignContactTombstone.review_after <= now,
                or_(
                    CampaignContactTombstone.do_not_contact_reason.is_not(None),
                    ~select(CampaignDeliveryTombstone.id)
                    .where(
                        CampaignDeliveryTombstone.contact_tombstone_id
                        == CampaignContactTombstone.id,
                        CampaignDeliveryTombstone.expires_at > now,
                    )
                    .exists(),
                ),
            )
            .order_by(
                CampaignContactTombstone.review_after.asc(),
                CampaignContactTombstone.id.asc(),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def list_due_campaign_delivery_tombstones(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[CampaignDeliveryTombstone]:
        result = await self.session.execute(
            select(CampaignDeliveryTombstone)
            .where(CampaignDeliveryTombstone.expires_at <= now)
            .order_by(CampaignDeliveryTombstone.expires_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def add_email_suppression_review(
        self,
        review: EmailSuppressionReview,
    ) -> None:
        self.session.add(review)
        await self.session.flush()

    async def delete_email_suppression(
        self,
        suppression: EmailSuppression,
    ) -> None:
        await self.session.delete(suppression)
        await self.session.flush()

    async def delete_campaign_contact_tombstone(
        self,
        tombstone: CampaignContactTombstone,
    ) -> None:
        await self.session.delete(tombstone)
        await self.session.flush()

    async def delete_campaign_delivery_tombstone(
        self,
        tombstone: CampaignDeliveryTombstone,
    ) -> None:
        await self.session.delete(tombstone)
        await self.session.flush()

    async def delete_campaign_recipient_record(
        self,
        recipient: CampaignRecipient,
    ) -> None:
        await self.session.delete(recipient)
        await self.session.flush()

    async def list_due_archived_campaign_recipients(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> list[CampaignRecipient]:
        result = await self.session.execute(
            select(CampaignRecipient)
            .where(
                CampaignRecipient.archived_at.is_not(None),
                CampaignRecipient.purge_after <= now,
            )
            .order_by(CampaignRecipient.purge_after.asc(), CampaignRecipient.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def flush(self) -> None:
        await self.session.flush()
