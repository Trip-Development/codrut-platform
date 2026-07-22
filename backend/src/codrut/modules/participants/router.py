from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session, require_current_terms
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.participants.schemas import ParticipantWorkspaceSummary
from codrut.modules.participants.service import ParticipantWorkspaceService

router = APIRouter()


@router.get("/me/workspace", response_model=ParticipantWorkspaceSummary)
async def get_my_workspace(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    participant_profile_id: UUID | None = None,
    project_id: UUID | None = None,
    cycle_id: UUID | None = None,
) -> ParticipantWorkspaceSummary:
    if principal.role != UserRole.participant:
        from codrut.core.errors import DomainError

        raise DomainError("Participant account required.", code="participant_required")
    require_current_terms(principal)
    return await ParticipantWorkspaceService(session).get_workspace_summary(
        principal.user_id,
        participant_profile_id=participant_profile_id,
        project_id=project_id,
        cycle_id=cycle_id,
        allowed_assignment_ids=principal.assignment_ids,
        scoped_project_id=principal.project_id,
    )
