from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.modules.forms.schemas import (
    QuestionnaireDefinitionCreateRequest,
    QuestionnaireDefinitionResponse,
    QuestionnaireDefinitionUpdateRequest,
    QuestionnaireResponseResponse,
    QuestionnaireResponseSaveRequest,
    QuestionnaireSlug,
)
from codrut.modules.forms.service import FormsService
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal

router = APIRouter()


@router.get("/definitions", response_model=list[QuestionnaireDefinitionResponse])
async def list_questionnaire_definitions(
    session: Annotated[AsyncSession, Depends(db_session)],
    include_retired: bool = False,
) -> list[QuestionnaireDefinitionResponse]:
    definitions = await FormsService(session).list_persisted_definitions(
        active_only=not include_retired,
    )
    await session.commit()
    return definitions


@router.get("/definitions/{key}", response_model=QuestionnaireDefinitionResponse)
async def get_questionnaire_definition(
    key: QuestionnaireSlug,
    session: Annotated[AsyncSession, Depends(db_session)],
    version: int | None = None,
) -> QuestionnaireDefinitionResponse:
    definition = await FormsService(session).get_persisted_definition(key, version=version)
    await session.commit()
    return definition


@router.post("/definitions", response_model=QuestionnaireDefinitionResponse)
async def create_questionnaire_definition(
    payload: QuestionnaireDefinitionCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> QuestionnaireDefinitionResponse:
    _require_trainer(principal)
    definition = await FormsService(session).create_definition(payload)
    await session.commit()
    return definition


@router.put("/definitions/{key}", response_model=QuestionnaireDefinitionResponse)
async def update_questionnaire_definition(
    key: QuestionnaireSlug,
    payload: QuestionnaireDefinitionUpdateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    version: int | None = None,
) -> QuestionnaireDefinitionResponse:
    _require_trainer(principal)
    definition = await FormsService(session).update_definition(key, payload, version=version)
    await session.commit()
    return definition


@router.post(
    "/definitions/{key}/versions/{version}/activate",
    response_model=QuestionnaireDefinitionResponse,
)
async def activate_questionnaire_definition(
    key: QuestionnaireSlug,
    version: int,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> QuestionnaireDefinitionResponse:
    _require_trainer(principal)
    definition = await FormsService(session).activate_definition(key, version)
    await session.commit()
    return definition


@router.delete("/definitions/{key}", response_model=QuestionnaireDefinitionResponse)
async def retire_questionnaire_definition(
    key: QuestionnaireSlug,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    version: int | None = None,
) -> QuestionnaireDefinitionResponse:
    _require_trainer(principal)
    definition = await FormsService(session).retire_definition(key, version=version)
    await session.commit()
    return definition


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


def _require_trainer(principal: SessionPrincipal) -> None:
    if principal.role != UserRole.trainer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trainer access is required.",
        )
