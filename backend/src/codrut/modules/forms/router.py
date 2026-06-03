from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.modules.forms.models import QuestionnaireKey
from codrut.modules.forms.schemas import (
    QuestionnaireDefinitionResponse,
    QuestionnaireResponseResponse,
    QuestionnaireResponseSaveRequest,
)
from codrut.modules.forms.service import FormsService
from codrut.modules.identity.schemas import SessionPrincipal

router = APIRouter()


@router.get("/definitions", response_model=list[QuestionnaireDefinitionResponse])
async def list_questionnaire_definitions() -> list[QuestionnaireDefinitionResponse]:
    return FormsService().list_definitions()


@router.get("/definitions/{key}", response_model=QuestionnaireDefinitionResponse)
async def get_questionnaire_definition(
    key: QuestionnaireKey,
) -> QuestionnaireDefinitionResponse:
    return FormsService().get_definition(key)


@router.get(
    "/assignments/{assignment_id}/response",
    response_model=QuestionnaireResponseResponse,
)
async def get_assignment_response(
    assignment_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> QuestionnaireResponseResponse:
    return await FormsService(session).get_assignment_response(principal.user_id, assignment_id)


@router.put(
    "/assignments/{assignment_id}/response",
    response_model=QuestionnaireResponseResponse,
)
async def save_assignment_response(
    assignment_id: UUID,
    payload: QuestionnaireResponseSaveRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> QuestionnaireResponseResponse:
    response = await FormsService(session).save_assignment_response(
        principal.user_id,
        assignment_id,
        payload,
    )
    await session.commit()
    return response


@router.post(
    "/assignments/{assignment_id}/response/submit",
    response_model=QuestionnaireResponseResponse,
)
async def submit_assignment_response(
    assignment_id: UUID,
    payload: QuestionnaireResponseSaveRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> QuestionnaireResponseResponse:
    response = await FormsService(session).save_assignment_response(
        principal.user_id,
        assignment_id,
        payload,
        submit=True,
    )
    await session.commit()
    return response
