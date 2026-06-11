from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.modules.forms.repository import FormsRepository
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.scoring.schemas import ScoringResultResponse
from codrut.modules.scoring.service import ScoringService

router = APIRouter()


@router.get("/assignments/{assignment_id}/result", response_model=ScoringResultResponse)
async def get_assignment_scoring_result(
    assignment_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> ScoringResultResponse:
    # 1. Authorize: Trainer can see all. Respondent can only see their own.
    is_trainer = principal.role == UserRole.trainer
    if not is_trainer:
        forms_repo = FormsRepository(session)
        assignment = await forms_repo.get_assignment_for_user(assignment_id, principal.user_id)
        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this assignment's result",
            )

    # 2. Get scoring result
    scoring_service = ScoringService(session)
    result = await scoring_service.get_result_by_assignment(assignment_id)

    if result is None:
        # Check if there is a submitted response to compute score on-the-fly
        forms_repo = FormsRepository(session)
        response = await forms_repo.get_response_by_assignment(assignment_id)
        if response is not None:
            definition = await forms_repo.get_definition(
                response.questionnaire_key,
                version=response.questionnaire_version,
            )
            result = await scoring_service.compute_and_save_score(
                assignment_id=assignment_id,
                questionnaire_key=response.questionnaire_key,
                questionnaire_version=response.questionnaire_version,
                answers=response.answers,
                definition_schema=definition.schema if definition is not None else None,
            )
            await session.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scoring result not found or assignment not submitted yet",
            )

    return result
