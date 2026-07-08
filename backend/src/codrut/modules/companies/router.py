from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.companies.schemas import (
    CompanyAccessCodeCreateRequest,
    CompanyAccessCodeRegistrationRequest,
    CompanyAccessCodeResponse,
    CompanyCreateRequest,
    CompanyProjectCreateRequest,
    CompanyProjectListItemResponse,
    CompanyProjectResponse,
    CompanyProjectUpdateRequest,
    CompanyResponse,
    CompanySummaryResponse,
    ParticipantCreateRequest,
    ParticipantInvitationStatusResponse,
    ParticipantInviteBatchRequest,
    ParticipantInviteBatchResponse,
    ParticipantResponse,
    ParticipantUpdateRequest,
    ProjectParticipantResponse,
    ReportingRelationshipImportResponse,
    RosterImportRequest,
    RosterImportResponse,
)
from codrut.modules.companies.service import CompanyService
from codrut.modules.identity.schemas import AuthResponse, SessionPrincipal
from codrut.modules.identity.session_cookie import set_session_cookie

router = APIRouter()


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[CompanyResponse]:
    require_trainer_principal(principal)
    return await CompanyService(session).list_companies(principal.user_id)


@router.get("/summary", response_model=list[CompanySummaryResponse])
async def list_company_summaries(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[CompanySummaryResponse]:
    require_trainer_principal(principal)
    return await CompanyService(session).list_company_summaries(principal.user_id)


@router.get("/projects", response_model=list[CompanyProjectListItemResponse])
async def list_all_company_projects(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[CompanyProjectListItemResponse]:
    require_trainer_principal(principal)
    return await CompanyService(session).list_all_projects(principal.user_id)


@router.get("/projects/{project_id}", response_model=CompanyProjectListItemResponse)
async def get_company_project_by_id(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> CompanyProjectListItemResponse:
    require_trainer_principal(principal)
    return await CompanyService(session).get_project_by_id(project_id, user_id=principal.user_id)


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> CompanyResponse:
    require_trainer_principal(principal)
    company = await CompanyService(session).create_company(principal.user_id, payload)
    await session.commit()
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> Response:
    require_trainer_principal(principal)
    await CompanyService(session).delete_company(principal.user_id, company_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{company_id}/projects", response_model=list[CompanyProjectResponse])
async def list_company_projects(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[CompanyProjectResponse]:
    require_trainer_principal(principal)
    return await CompanyService(session).list_projects(principal.user_id, company_id)


@router.post(
    "/{company_id}/projects",
    response_model=CompanyProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_project(
    company_id: UUID,
    payload: CompanyProjectCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> CompanyProjectResponse:
    require_trainer_principal(principal)
    project = await CompanyService(session).create_project(principal.user_id, company_id, payload)
    await session.commit()
    return project


@router.patch("/{company_id}/projects/{project_id}", response_model=CompanyProjectResponse)
async def update_company_project(
    company_id: UUID,
    project_id: UUID,
    payload: CompanyProjectUpdateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> CompanyProjectResponse:
    require_trainer_principal(principal)
    project = await CompanyService(session).update_project(
        principal.user_id,
        company_id,
        project_id,
        payload,
    )
    await session.commit()
    return project


@router.delete("/{company_id}/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_project(
    company_id: UUID,
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> Response:
    require_trainer_principal(principal)
    await CompanyService(session).delete_project(principal.user_id, company_id, project_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{company_id}/participants", response_model=list[ParticipantResponse])
async def list_company_participants(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[ParticipantResponse]:
    require_trainer_principal(principal)
    return await CompanyService(session).list_participants(principal.user_id, company_id)


@router.get(
    "/{company_id}/projects/{project_id}/participants",
    response_model=list[ProjectParticipantResponse],
)
async def list_project_participants(
    company_id: UUID,
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[ProjectParticipantResponse]:
    require_trainer_principal(principal)
    return await CompanyService(session).list_project_participants(
        principal.user_id,
        company_id,
        project_id,
    )


@router.post(
    "/{company_id}/participants",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_participant(
    company_id: UUID,
    payload: ParticipantCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> ParticipantResponse:
    require_trainer_principal(principal)
    participant = await CompanyService(session).create_participant(
        principal.user_id,
        company_id,
        payload,
    )
    await session.commit()
    return participant


@router.patch("/{company_id}/participants/{participant_id}", response_model=ParticipantResponse)
async def update_company_participant(
    company_id: UUID,
    participant_id: UUID,
    payload: ParticipantUpdateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> ParticipantResponse:
    require_trainer_principal(principal)
    participant = await CompanyService(session).update_participant(
        principal.user_id,
        company_id,
        participant_id,
        payload,
    )
    await session.commit()
    return participant


@router.post(
    "/{company_id}/participants/roster",
    response_model=RosterImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_company_roster(
    company_id: UUID,
    payload: RosterImportRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> RosterImportResponse:
    require_trainer_principal(principal)
    result = await CompanyService(session).import_roster(
        principal.user_id,
        company_id,
        payload,
    )
    await session.commit()
    return result


@router.post(
    "/{company_id}/participants/invitations",
    response_model=ParticipantInviteBatchResponse,
    status_code=status.HTTP_200_OK,
)
async def send_participant_invitations(
    company_id: UUID,
    payload: ParticipantInviteBatchRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> ParticipantInviteBatchResponse:
    require_trainer_principal(principal)
    result = await CompanyService(session).send_participant_invites(
        principal.user_id,
        company_id,
        payload,
    )
    await session.commit()
    return result


@router.get(
    "/{company_id}/participants/invitations/status",
    response_model=list[ParticipantInvitationStatusResponse],
)
async def list_participant_invitation_statuses(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    project_id: Annotated[UUID | None, Query()] = None,
) -> list[ParticipantInvitationStatusResponse]:
    require_trainer_principal(principal)
    return await CompanyService(session).list_participant_invitation_statuses(
        principal.user_id,
        company_id,
        project_id,
    )


@router.post(
    "/{company_id}/participants/{participant_id}/resend-invite",
    response_model=RosterImportResponse,
    status_code=status.HTTP_200_OK,
)
async def resend_participant_invite(
    company_id: UUID,
    participant_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    project_id: Annotated[UUID | None, Query()] = None,
) -> RosterImportResponse:
    require_trainer_principal(principal)
    result = await CompanyService(session).resend_invite(
        principal.user_id,
        company_id,
        participant_id,
        project_id,
    )
    await session.commit()
    return result


@router.post(
    "/{company_id}/access-codes",
    response_model=CompanyAccessCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_access_code(
    company_id: UUID,
    payload: CompanyAccessCodeCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> CompanyAccessCodeResponse:
    require_trainer_principal(principal)
    access_code = await CompanyService(session).create_access_code(
        principal.user_id,
        company_id,
        payload,
    )
    await session.commit()
    return access_code


@router.post("/access-code-registration", response_model=AuthResponse)
async def register_with_company_access_code(
    payload: CompanyAccessCodeRegistrationRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session)],
) -> AuthResponse:
    result = await CompanyService(session).register_with_access_code(payload)
    await session.commit()
    _set_session_cookie(response, result.session_token)
    return result.response


@router.post(
    "/{company_id}/participants/reporting-relationships/import",
    response_model=ReportingRelationshipImportResponse,
)
async def import_company_reporting_relationships(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> ReportingRelationshipImportResponse:
    require_trainer_principal(principal)
    result = await CompanyService(session).import_reporting_relationships(
        principal.user_id,
        company_id,
    )
    await session.commit()
    return result


def _set_session_cookie(response: Response, token: str) -> None:
    set_session_cookie(response, token)
