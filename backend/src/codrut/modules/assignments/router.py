from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.modules.assignments.schemas import (
    AssignmentCreateRequest,
    AssignmentResponse,
    AssignmentStatusUpdateRequest,
    TeamCreateRequest,
    TeamMembershipCreateRequest,
    TeamMembershipResponse,
    TeamResponse,
)
from codrut.modules.assignments.service import AssignmentService
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.identity.schemas import SessionPrincipal

router = APIRouter()


@router.get("/companies/{company_id}/teams", response_model=list[TeamResponse])
async def list_company_teams(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[TeamResponse]:
    require_trainer_principal(principal)
    return await AssignmentService(session).list_teams(principal.user_id, company_id)


@router.post(
    "/companies/{company_id}/teams",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_team(
    company_id: UUID,
    payload: TeamCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> TeamResponse:
    require_trainer_principal(principal)
    team = await AssignmentService(session).create_team(principal.user_id, company_id, payload)
    await session.commit()
    return team


@router.post(
    "/companies/{company_id}/teams/{team_id}/memberships",
    response_model=TeamMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_team_membership(
    company_id: UUID,
    team_id: UUID,
    payload: TeamMembershipCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> TeamMembershipResponse:
    require_trainer_principal(principal)
    membership = await AssignmentService(session).add_team_membership(
        principal.user_id,
        company_id,
        team_id,
        payload,
    )
    await session.commit()
    return membership


@router.get("/companies/{company_id}/assignments", response_model=list[AssignmentResponse])
async def list_company_assignments(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[AssignmentResponse]:
    require_trainer_principal(principal)
    return await AssignmentService(session).list_assignments(principal.user_id, company_id)


@router.post(
    "/companies/{company_id}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_assignment(
    company_id: UUID,
    payload: AssignmentCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AssignmentResponse:
    require_trainer_principal(principal)
    assignment = await AssignmentService(session).create_assignment(
        principal.user_id,
        company_id,
        payload,
    )
    await session.commit()
    return assignment


@router.patch(
    "/companies/{company_id}/assignments/{assignment_id}/status",
    response_model=AssignmentResponse,
)
async def update_company_assignment_status(
    company_id: UUID,
    assignment_id: UUID,
    payload: AssignmentStatusUpdateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AssignmentResponse:
    require_trainer_principal(principal)
    assignment = await AssignmentService(session).update_assignment_status(
        principal.user_id,
        company_id,
        assignment_id,
        payload,
    )
    await session.commit()
    return assignment
