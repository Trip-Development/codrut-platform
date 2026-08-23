from uuid import UUID

from codrut.core.errors import DomainError
from codrut.modules.companies.models import CompanyMembershipRole
from codrut.modules.companies.repository import CompanyRepository


async def require_company_manager(
    company_repository: CompanyRepository,
    user_id: UUID,
    company_id: UUID,
) -> None:
    if await company_repository.get_company(company_id) is None:
        raise DomainError("Company not found.", code="company_not_found")

    membership = await company_repository.get_membership(company_id, user_id)
    if membership is None or membership.role not in {
        CompanyMembershipRole.owner,
        CompanyMembershipRole.trainer,
    }:
        raise DomainError(
            "You do not have access to manage this company.",
            code="company_access_denied",
        )
