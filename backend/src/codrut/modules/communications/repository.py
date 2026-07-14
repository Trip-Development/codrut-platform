
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.communications.models import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientEvent,
    CampaignRecipientMembership,
    EmailSend,
    EmailSendStatus,
    EmailTemplate,
)


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
        if version is None:
            stmt = stmt.where(EmailTemplate.active.is_(True)).order_by(
                EmailTemplate.owner_id.is_(None),
                EmailTemplate.version.desc()
            )
        else:
            stmt = stmt.where(EmailTemplate.version == version)
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def get_latest_version(self, key: str) -> int:
        result = await self.session.execute(
            select(func.max(EmailTemplate.version)).where(
                EmailTemplate.key == key,
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
        if owner_id is not None:
            stmt = stmt.where(EmailTemplate.owner_id == owner_id)
        result = await self.session.execute(stmt)
        templates = result.scalars().all()
        for template in templates:
            if template.version != except_version:
                template.active = False

    async def has_sent_emails(self, key: str, version: int) -> bool:
        from codrut.modules.communications.models import EmailSend
        result = await self.session.execute(
            select(EmailSend.id)
            .where(EmailSend.template_key == key)
            .where(EmailSend.template_version == version)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def add_campaign_recipients(self, recipients: list[CampaignRecipient]) -> None:
        self.session.add_all(recipients)
        await self.session.flush()

    async def list_campaign_recipients_by_emails(
        self,
        emails: set[str],
        *,
        owner_id: UUID | None = None,
    ) -> list[CampaignRecipient]:
        if not emails:
            return []
        stmt = select(CampaignRecipient).where(
            CampaignRecipient.email.is_not(None),
            func.lower(CampaignRecipient.email).in_(emails),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_campaign_recipients(
        self,
        *,
        owner_id: UUID | None = None,
    ) -> list[CampaignRecipient]:
        stmt = select(CampaignRecipient).order_by(CampaignRecipient.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_campaign_recipient(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> CampaignRecipient | None:
        stmt = select(CampaignRecipient).where(CampaignRecipient.id == recipient_id)
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def get_campaign_recipient_by_email(
        self,
        email: str,
        *,
        owner_id: UUID | None = None,
    ) -> CampaignRecipient | None:
        stmt = select(CampaignRecipient).where(func.lower(CampaignRecipient.email) == email.lower())
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def list_campaign_recipients_by_ids(
        self,
        recipient_ids: list[UUID],
        *,
        owner_id: UUID | None = None,
    ) -> list[CampaignRecipient]:
        if not recipient_ids:
            return []
        stmt = select(CampaignRecipient).where(CampaignRecipient.id.in_(recipient_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_campaign_recipient_events(self) -> list[CampaignRecipientEvent]:
        stmt = select(CampaignRecipientEvent).order_by(CampaignRecipientEvent.occurred_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_campaign_recipient_event(
        self,
        event: CampaignRecipientEvent,
    ) -> CampaignRecipientEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def add_campaign(self, campaign: Campaign) -> Campaign:
        self.session.add(campaign)
        await self.session.flush()
        return campaign

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

    async def list_accepted_campaign_recipient_ids(self, campaign_id: UUID) -> set[UUID]:
        result = await self.session.execute(
            select(EmailSend.campaign_recipient_id)
            .where(EmailSend.campaign_id == campaign_id)
            .where(EmailSend.campaign_recipient_id.is_not(None))
            .where(EmailSend.status.in_((EmailSendStatus.queued, EmailSendStatus.accepted)))
        )
        return {recipient_id for recipient_id in result.scalars().all() if recipient_id is not None}

    async def list_campaign_member_recipient_ids(
        self,
        campaign_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> list[UUID]:
        stmt = (
            select(CampaignRecipientMembership.recipient_id)
            .join(Campaign, Campaign.id == CampaignRecipientMembership.campaign_id)
            .where(CampaignRecipientMembership.campaign_id == campaign_id)
            .order_by(CampaignRecipientMembership.created_at.asc())
        )
        if owner_id is not None:
            stmt = stmt.where(Campaign.owner_id == owner_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_campaign_member_recipients(
        self,
        campaign_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> list[CampaignRecipient]:
        stmt = (
            select(CampaignRecipient)
            .join(
                CampaignRecipientMembership,
                CampaignRecipientMembership.recipient_id == CampaignRecipient.id,
            )
            .join(Campaign, Campaign.id == CampaignRecipientMembership.campaign_id)
            .where(CampaignRecipientMembership.campaign_id == campaign_id)
            .order_by(CampaignRecipientMembership.created_at.asc())
        )
        if owner_id is not None:
            stmt = stmt.where(Campaign.owner_id == owner_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def replace_campaign_memberships(
        self,
        campaign_id: UUID,
        recipient_ids: list[UUID],
        *,
        source: str = "manual",
        owner_id: UUID | None = None,
    ) -> None:
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
            .where(EmailSend.status == EmailSendStatus.accepted)
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

    async def flush(self) -> None:
        await self.session.flush()
