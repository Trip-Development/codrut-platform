from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.participants.schemas import ParticipantWorkspaceSummary
from codrut.modules.participants.service import ParticipantWorkspaceService

router = APIRouter()


@router.get("/me/workspace", response_model=ParticipantWorkspaceSummary)
async def get_my_workspace(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> ParticipantWorkspaceSummary:
    if principal.role != UserRole.participant:
        from codrut.core.errors import DomainError

        raise DomainError("Participant account required.", code="participant_required")
    return await ParticipantWorkspaceService(session).get_workspace_summary(principal.user_id)
