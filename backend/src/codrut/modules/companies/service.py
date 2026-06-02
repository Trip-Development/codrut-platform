from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    ParticipantProfile,
)
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.companies.schemas import CompanyCreateRequest, ParticipantCreateRequest


class CompanyService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = CompanyRepository(session)

    async def list_companies(self, user_id: UUID) -> list[Company]:
        return await self.repository.list_companies_for_user(user_id)

    async def create_company(self, owner_user_id: UUID, payload: CompanyCreateRequest) -> Company:
        name = payload.name.strip()
        existing = await self.repository.get_company_by_name(name)
        if existing is not None:
            raise DomainError("A company with this name already exists.", code="company_exists")
        company = await self.repository.add_company(Company(name=name))
        await self.repository.add_membership(
            CompanyMembership(
                company_id=company.id,
                user_id=owner_user_id,
                role=CompanyMembershipRole.owner,
            )
        )
        return company

    async def list_participants(self, user_id: UUID, company_id: UUID) -> list[ParticipantProfile]:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        return await self.repository.list_participants(company_id)

    async def create_participant(
        self,
        user_id: UUID,
        company_id: UUID,
        payload: ParticipantCreateRequest,
    ) -> ParticipantProfile:
        await self._require_company(company_id)
        await self._require_company_manager(user_id, company_id)
        email = payload.email.lower()
        existing = await self.repository.get_participant_by_company_email(company_id, email)
        if existing is not None:
            raise DomainError(
                "A participant with this email already exists for this company.",
                code="participant_exists",
            )
        return await self.repository.add_participant(
            ParticipantProfile(
                company_id=company_id,
                full_name=payload.full_name.strip(),
                email=email,
                position=_clean_optional(payload.position),
                location=_clean_optional(payload.location),
                role_group=_clean_optional(payload.role_group),
                pcm_profile=_clean_optional(payload.pcm_profile),
            )
        )

    async def _require_company(self, company_id: UUID) -> Company:
        company = await self.repository.get_company(company_id)
        if company is None:
            raise DomainError("Company not found.", code="company_not_found")
        return company

    async def _require_company_manager(self, user_id: UUID, company_id: UUID) -> None:
        membership = await self.repository.get_membership(company_id, user_id)
        if membership is None or membership.role not in {
            CompanyMembershipRole.owner,
            CompanyMembershipRole.trainer,
        }:
            raise DomainError(
                "You do not have access to manage this company.",
                code="company_access_denied",
            )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
