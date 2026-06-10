from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.core.config import get_settings
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.companies.schemas import (
    CompanyAccessCodeCreateRequest,
    CompanyAccessCodeRegistrationRequest,
    CompanyAccessCodeResponse,
    CompanyCreateRequest,
    CompanyResponse,
    ParticipantCreateRequest,
    ParticipantInviteBatchRequest,
    ParticipantInviteBatchResponse,
    ParticipantResponse,
    ReportingRelationshipImportResponse,
    RosterImportRequest,
    RosterImportResponse,
)
from codrut.modules.companies.service import CompanyService
from codrut.modules.identity.schemas import AuthResponse, SessionPrincipal

router = APIRouter()


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[CompanyResponse]:
    require_trainer_principal(principal)
    # Trainers see all companies — they are trusted platform operators
    return await CompanyService(session).list_all_companies()


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


@router.get("/{company_id}/participants", response_model=list[ParticipantResponse])
async def list_company_participants(
    company_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[ParticipantResponse]:
    require_trainer_principal(principal)
    return await CompanyService(session).list_participants(principal.user_id, company_id)


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
) -> RosterImportResponse:
    require_trainer_principal(principal)
    result = await CompanyService(session).resend_invite(
        principal.user_id,
        company_id,
        participant_id,
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
    settings = get_settings()
    response.set_cookie(
        "codrut_session",
        token,
        max_age=int(timedelta(days=14).total_seconds()),
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
