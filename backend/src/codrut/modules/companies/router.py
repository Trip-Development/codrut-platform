from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.companies.schemas import (
    CompanyCreateRequest,
    CompanyResponse,
    ParticipantCreateRequest,
    ParticipantResponse,
)
from codrut.modules.companies.service import CompanyService
from codrut.modules.identity.schemas import SessionPrincipal

router = APIRouter()


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[CompanyResponse]:
    require_trainer_principal(principal)
    return await CompanyService(session).list_companies(principal.user_id)


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
