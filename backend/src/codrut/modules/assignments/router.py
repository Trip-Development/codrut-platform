from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.modules.assignments.schemas import (
    AssessmentCycleCloseRequest,
    AssessmentCycleCreateRequest,
    AssessmentCycleResponse,
    AssessmentCycleUpdateRequest,
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
from codrut.modules.scoring.schemas import (
    CompanyReportAggregateResponse,
    CompanyReportComparisonResponse,
    IcareAnswerReviewResponse,
)
from codrut.modules.scoring.service import ScoringService

router = APIRouter()


@router.get(
    "/companies/{company_id}/projects/{project_id}/assessment-cycles",
    response_model=list[AssessmentCycleResponse],
)
async def list_project_assessment_cycles(
    company_id: UUID,
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[AssessmentCycleResponse]:
    require_trainer_principal(principal)
    return await AssignmentService(session).list_assessment_cycles(
        principal.user_id,
        company_id,
        project_id,
    )


@router.post(
    "/companies/{company_id}/projects/{project_id}/assessment-cycles",
    response_model=AssessmentCycleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_assessment_cycle(
    company_id: UUID,
    project_id: UUID,
    payload: AssessmentCycleCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AssessmentCycleResponse:
    require_trainer_principal(principal)
    cycle = await AssignmentService(session).create_assessment_cycle(
        principal.user_id,
        company_id,
        project_id,
        payload,
    )
    await session.commit()
    return cycle


@router.patch(
    "/companies/{company_id}/projects/{project_id}/assessment-cycles/{assessment_cycle_id}",
    response_model=AssessmentCycleResponse,
)
async def update_project_assessment_cycle(
    company_id: UUID,
    project_id: UUID,
    assessment_cycle_id: UUID,
    payload: AssessmentCycleUpdateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AssessmentCycleResponse:
    require_trainer_principal(principal)
    cycle = await AssignmentService(session).update_assessment_cycle(
        principal.user_id,
        company_id,
        project_id,
        assessment_cycle_id,
        payload,
    )
    await session.commit()
    return cycle


@router.delete(
    "/companies/{company_id}/projects/{project_id}/assessment-cycles/{assessment_cycle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_assessment_cycle(
    company_id: UUID,
    project_id: UUID,
    assessment_cycle_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> Response:
    require_trainer_principal(principal)
    await AssignmentService(session).delete_assessment_cycle(
        principal.user_id,
        company_id,
        project_id,
        assessment_cycle_id,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/companies/{company_id}/projects/{project_id}/assessment-cycles/{assessment_cycle_id}/close",
    response_model=AssessmentCycleResponse,
)
async def close_project_assessment_cycle(
    company_id: UUID,
    project_id: UUID,
    assessment_cycle_id: UUID,
    payload: AssessmentCycleCloseRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AssessmentCycleResponse:
    require_trainer_principal(principal)
    cycle = await AssignmentService(session).close_assessment_cycle(
        principal.user_id,
        company_id,
        project_id,
        assessment_cycle_id,
        payload,
    )
    await session.commit()
    return cycle


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


@router.delete(
    "/companies/{company_id}/teams/{team_id}/memberships/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_team_membership(
    company_id: UUID,
    team_id: UUID,
    membership_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> Response:
    require_trainer_principal(principal)
    await AssignmentService(session).remove_team_membership(
        principal.user_id,
        company_id,
        team_id,
        membership_id,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/companies/{company_id}/assignments", response_model=list[AssignmentResponse])
async def list_company_assignments(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    project_id: Annotated[UUID | None, Query()] = None,
    assessment_cycle_id: Annotated[UUID | None, Query()] = None,
) -> list[AssignmentResponse]:
    require_trainer_principal(principal)
    return await AssignmentService(session).list_assignments(
        principal.user_id,
        company_id,
        project_id,
        assessment_cycle_id,
    )


@router.get(
    "/companies/{company_id}/assignments/default-plan",
    response_model=AssignmentPlanResponse,
)
async def get_company_default_assignment_plan(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    project_id: Annotated[UUID | None, Query()] = None,
    assessment_cycle_id: Annotated[UUID | None, Query()] = None,
    source_cycle_id: Annotated[UUID | None, Query()] = None,
) -> AssignmentPlanResponse:
    require_trainer_principal(principal)
    return await AssignmentService(session).build_default_assignment_plan(
        principal.user_id,
        company_id,
        project_id,
        assessment_cycle_id,
        source_cycle_id,
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
    project_id: Annotated[UUID | None, Query()] = None,
    assessment_cycle_id: Annotated[UUID | None, Query()] = None,
) -> AssignmentPlanSaveResponse:
    require_trainer_principal(principal)
    if project_id is not None:
        payload.project_id = project_id
    if assessment_cycle_id is not None:
        payload.assessment_cycle_id = assessment_cycle_id
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
    project_id: Annotated[UUID | None, Query()] = None,
    assessment_cycle_id: Annotated[UUID | None, Query()] = None,
) -> CompanyReportAggregateResponse:
    require_trainer_principal(principal)
    await AssignmentService(session).require_company_manager(principal.user_id, company_id)
    return await ScoringService(session).get_company_report_aggregate(
        company_id,
        project_id,
        assessment_cycle_id,
    )


@router.get(
    "/companies/{company_id}/reports/comparison",
    response_model=CompanyReportComparisonResponse,
)
async def get_company_report_comparison(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    project_id: Annotated[UUID, Query()],
    baseline_cycle_id: Annotated[UUID, Query()],
    comparison_cycle_id: Annotated[UUID, Query()],
) -> CompanyReportComparisonResponse:
    require_trainer_principal(principal)
    await AssignmentService(session).require_company_manager(principal.user_id, company_id)
    return await ScoringService(session).get_company_report_comparison(
        company_id,
        project_id,
        baseline_cycle_id,
        comparison_cycle_id,
    )


@router.get(
    "/companies/{company_id}/reports/icare-answers",
    response_model=IcareAnswerReviewResponse,
)
async def get_company_icare_answer_review(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    project_id: Annotated[UUID | None, Query()] = None,
    assessment_cycle_id: Annotated[UUID | None, Query()] = None,
) -> IcareAnswerReviewResponse:
    require_trainer_principal(principal)
    await AssignmentService(session).require_company_manager(principal.user_id, company_id)
    return await ScoringService(session).get_icare_answer_review(
        company_id,
        project_id,
        assessment_cycle_id,
    )


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
    assignment_service = AssignmentService(session)
    await assignment_service.require_company_manager(principal.user_id, company_id)
    service = IdentityService(session)

    # 1. Generate/get invite
    invite = await service.create_invite(
        company_id=company_id,
        respondent_profile_id=payload.respondent_profile_id,
        assignment_ids=payload.assignment_ids,
        project_id=payload.project_id,
        expires_in_days=payload.expires_in_days,
        force_rotate=payload.force_rotate,
    )

    # 2. Update status of the assignments included in this invite to "invited"
    from codrut.modules.communications.task_links import parse_task_token

    claims = parse_task_token(invite.token, settings)
    from datetime import UTC, datetime

    from sqlalchemy import select

    from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment

    assignments_result = await session.execute(
        select(QuestionnaireAssignment)
        .where(QuestionnaireAssignment.id.in_(claims.assignment_ids))
        .where(QuestionnaireAssignment.company_id == company_id)
        .where(QuestionnaireAssignment.respondent_profile_id == payload.respondent_profile_id)
        .where(QuestionnaireAssignment.status == AssignmentStatus.assigned)
    )
    invited_at = datetime.now(UTC)
    for assignment in assignments_result.scalars().all():
        assignment.status = AssignmentStatus.invited
        assignment.invited_at = invited_at

    await session.commit()

    invite_url = build_task_url(invite.token, settings)
    return InvitationResponse(
        id=invite.id,
        company_id=invite.company_id,
        project_id=invite.project_id,
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
    await AssignmentService(session).require_company_manager(principal.user_id, company_id)
    from codrut.modules.identity.service import IdentityService

    service = IdentityService(session)
    await service.invalidate_invite(company_id, respondent_profile_id)
    await session.commit()
