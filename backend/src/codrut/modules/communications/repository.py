
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.communications.models import EmailTemplate


class CommunicationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_templates(
        self,
        *,
        active_only: bool = True,
    ) -> list[EmailTemplate]:
        stmt = select(EmailTemplate).order_by(
            EmailTemplate.key,
            EmailTemplate.version.desc(),
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
    ) -> EmailTemplate | None:
        stmt = select(EmailTemplate).where(EmailTemplate.key == key)
        if version is None:
            stmt = stmt.where(EmailTemplate.active.is_(True)).order_by(
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
    ) -> None:
        # Fetch all templates for this key to modify them in the session
        stmt = select(EmailTemplate).where(EmailTemplate.key == key)
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

    async def add_campaign_recipients(self, recipients: list["CampaignRecipient"]) -> None:
        self.session.add_all(recipients)
        await self.session.flush()

    async def list_campaign_recipients(self) -> list["CampaignRecipient"]:
        from codrut.modules.communications.models import CampaignRecipient
        stmt = select(CampaignRecipient).order_by(CampaignRecipient.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_campaign(self, campaign: "Campaign") -> "Campaign":
        self.session.add(campaign)
        await self.session.flush()
        return campaign

    async def list_campaigns(self) -> list["Campaign"]:
        from codrut.modules.communications.models import Campaign
        stmt = select(Campaign).order_by(Campaign.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
