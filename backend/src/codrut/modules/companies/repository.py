from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.companies.models import (
    Company,
    CompanyAccessCode,
    CompanyMembership,
    ParticipantProfile,
    ParticipantReportingRelationship,
)


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_companies_for_user(self, user_id: UUID) -> list[Company]:
        result = await self.session.execute(
            select(Company)
            .join(CompanyMembership)
            .where(CompanyMembership.user_id == user_id)
            .order_by(Company.name)
        )
        return list(result.scalars().all())

    async def get_company(self, company_id: UUID) -> Company | None:
        result = await self.session.execute(select(Company).where(Company.id == company_id))
        return result.scalar_one_or_none()

    async def get_company_by_name(self, name: str) -> Company | None:
        result = await self.session.execute(select(Company).where(Company.name == name))
        return result.scalar_one_or_none()

    async def add_company(self, company: Company) -> Company:
        self.session.add(company)
        await self.session.flush()
        return company

    async def add_membership(self, membership: CompanyMembership) -> CompanyMembership:
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def get_membership(self, company_id: UUID, user_id: UUID) -> CompanyMembership | None:
        result = await self.session.execute(
            select(CompanyMembership)
            .where(CompanyMembership.company_id == company_id)
            .where(CompanyMembership.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_participants(self, company_id: UUID) -> list[ParticipantProfile]:
        result = await self.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.company_id == company_id)
            .order_by(ParticipantProfile.full_name)
        )
        return list(result.scalars().all())

    async def replace_reporting_relationships(
        self,
        company_id: UUID,
        relationships: list[ParticipantReportingRelationship],
    ) -> list[ParticipantReportingRelationship]:
        existing = await self.session.execute(
            select(ParticipantReportingRelationship).where(
                ParticipantReportingRelationship.company_id == company_id
            )
        )
        for relationship in existing.scalars():
            await self.session.delete(relationship)
        for relationship in relationships:
            self.session.add(relationship)
        await self.session.flush()
        return relationships

    async def get_participant_by_company_email(
        self,
        company_id: UUID,
        email: str,
    ) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.company_id == company_id)
            .where(ParticipantProfile.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def add_participant(self, participant: ParticipantProfile) -> ParticipantProfile:
        self.session.add(participant)
        await self.session.flush()
        return participant

    async def add_access_code(self, access_code: CompanyAccessCode) -> CompanyAccessCode:
        self.session.add(access_code)
        await self.session.flush()
        return access_code

    async def get_active_access_code(self, code_hash: str) -> CompanyAccessCode | None:
        result = await self.session.execute(
            select(CompanyAccessCode)
            .where(CompanyAccessCode.code_hash == code_hash)
            .where(CompanyAccessCode.active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_unclaimed_participant_by_company_email(
        self,
        company_id: UUID,
        email: str,
    ) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile)
            .where(ParticipantProfile.company_id == company_id)
            .where(ParticipantProfile.email == email.lower())
            .where(ParticipantProfile.user_id.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_participant_by_id(self, participant_id: UUID) -> ParticipantProfile | None:
        result = await self.session.execute(
            select(ParticipantProfile).where(ParticipantProfile.id == participant_id)
        )
        return result.scalar_one_or_none()

    async def list_assignments_for_participant(self, participant_id: UUID) -> list:
        from codrut.modules.assignments.models import QuestionnaireAssignment

        result = await self.session.execute(
            select(QuestionnaireAssignment).where(
                QuestionnaireAssignment.respondent_profile_id == participant_id
            )
        )
        return list(result.scalars().all())
