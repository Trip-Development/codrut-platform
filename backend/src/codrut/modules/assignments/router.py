from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.modules.assignments.schemas import (
    AssignmentCreateRequest,
    AssignmentPlanResponse,
    AssignmentPlanSaveRequest,
    AssignmentPlanSaveResponse,
    AssignmentResponse,
    AssignmentStatusUpdateRequest,
    InvitationCreateRequest,
    InvitationResponse,
    TeamCreateRequest,
    TeamMembershipCreateRequest,
    TeamMembershipResponse,
    TeamResponse,
)
from codrut.modules.assignments.service import AssignmentService
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.scoring.schemas import CompanyReportAggregateResponse
from codrut.modules.scoring.service import ScoringService

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


@router.get(
    "/companies/{company_id}/teams/{team_id}/memberships",
    response_model=list[TeamMembershipResponse],
)
async def list_team_memberships(
    company_id: UUID,
    team_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[TeamMembershipResponse]:
    require_trainer_principal(principal)
    return await AssignmentService(session).list_team_memberships(
        principal.user_id,
        company_id,
        team_id,
    )


@router.get("/companies/{company_id}/assignments", response_model=list[AssignmentResponse])
async def list_company_assignments(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[AssignmentResponse]:
    require_trainer_principal(principal)
    return await AssignmentService(session).list_assignments(principal.user_id, company_id)


@router.get(
    "/companies/{company_id}/assignments/default-plan",
    response_model=AssignmentPlanResponse,
)
async def get_company_default_assignment_plan(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AssignmentPlanResponse:
    require_trainer_principal(principal)
    return await AssignmentService(session).build_default_assignment_plan(
        principal.user_id,
        company_id,
    )


@router.post(
    "/companies/{company_id}/assignments/default-plan",
    response_model=AssignmentPlanSaveResponse,
)
async def save_company_assignment_plan(
    company_id: UUID,
    payload: AssignmentPlanSaveRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AssignmentPlanSaveResponse:
    require_trainer_principal(principal)
    result = await AssignmentService(session).save_assignment_plan(
        principal.user_id,
        company_id,
        payload,
    )
    await session.commit()
    return result


@router.get(
    "/companies/{company_id}/reports/aggregate",
    response_model=CompanyReportAggregateResponse,
)
async def get_company_report_aggregate(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> CompanyReportAggregateResponse:
    require_trainer_principal(principal)
    return await ScoringService(session).get_company_report_aggregate(company_id)


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


@router.post(
    "/companies/{company_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_invitation(
    company_id: UUID,
    payload: InvitationCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> InvitationResponse:
    require_trainer_principal(principal)
    from codrut.core.config import get_settings
    from codrut.modules.communications.task_links import build_task_url
    from codrut.modules.identity.service import IdentityService

    settings = get_settings()
    service = IdentityService(session)

    # 1. Generate/get invite
    invite = await service.create_invite(
        company_id=company_id,
        respondent_profile_id=payload.respondent_profile_id,
        assignment_ids=payload.assignment_ids,
        expires_in_days=payload.expires_in_days,
        force_rotate=payload.force_rotate,
    )

    # 2. Update status of the assignments included in this invite to "invited"
    from codrut.modules.communications.task_links import parse_task_token
    try:
        claims = parse_task_token(invite.token, settings)
        from sqlalchemy import select

        from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
        assignments_result = await session.execute(
            select(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.id.in_(claims.assignment_ids))
            .where(QuestionnaireAssignment.company_id == company_id)
            .where(QuestionnaireAssignment.respondent_profile_id == payload.respondent_profile_id)
            .where(QuestionnaireAssignment.status == AssignmentStatus.assigned)
        )
        assignments = assignments_result.scalars().all()
        for assignment in assignments:
            assignment.status = AssignmentStatus.invited
            # Also update invited_at
            from datetime import UTC, datetime
            assignment.invited_at = datetime.now(UTC)
    except Exception:  # noqa: S110
        pass

    await session.commit()

    invite_url = build_task_url(invite.token, settings)
    return InvitationResponse(
        id=invite.id,
        company_id=invite.company_id,
        respondent_profile_id=invite.respondent_profile_id,
        token=invite.token,
        invite_url=invite_url,
        status=invite.status,
        expires_at=invite.expires_at,
    )


@router.post(
    "/companies/{company_id}/invitations/{respondent_profile_id}/invalidate",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def invalidate_company_invitation(
    company_id: UUID,
    respondent_profile_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> None:
    require_trainer_principal(principal)
    from codrut.modules.identity.service import IdentityService
    service = IdentityService(session)
    await service.invalidate_invite(company_id, respondent_profile_id)
    await session.commit()
