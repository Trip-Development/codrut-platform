from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.companies.models import CompanyMembershipRole, CompanyProject, ProjectTrainer
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.identity.models import User
from codrut.modules.identity.schemas import SessionPrincipal


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


async def require_project_trainer(
    session: AsyncSession, principal: SessionPrincipal, project_id: UUID,
) -> CompanyProject:
    """Paza trainerului pe proiect (plicul 242).

    Un trainer vede și schimbă numai proiectele la care e alocat (`project_trainers`);
    proprietarul platformei trece peste alocare. Firma nu mai ajunge.
    """
    require_trainer_principal(principal)
    rezultat = await CompanyRepository(session).get_project_by_id(project_id)
    if rezultat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "project_not_found", "message": "Proiectul nu există."},
        )
    proiect = rezultat[0]
    cont = await session.get(User, principal.user_id)
    if cont is not None and cont.is_platform_owner:
        return proiect
    alocare = (await session.execute(
        select(ProjectTrainer.id).where(
            ProjectTrainer.project_id == project_id,
            ProjectTrainer.user_id == principal.user_id,
        )
    )).scalar_one_or_none()
    if alocare is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "not_project_trainer", "message": "Nu ești trainer pe acest proiect."},
        )
    return proiect
