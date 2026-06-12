from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from codrut.modules.identity.schemas import InviteTask


class ParticipantWorkspaceCard(BaseModel):
    title: str
    description: str
    meta: str | None = None


class ParticipantWorkspaceSummary(BaseModel):
    participant_profile_id: UUID
    participant_full_name: str
    participant_email: str
    anonymous_name: str | None = None
    company_id: UUID
    company_name: str
    project_id: UUID | None
    project_name: str
    deadline_label: str
    deadline_at: datetime | None = None
    pcm_base: str | None = None
    pcm_phase: str | None = None
    tasks: list[InviteTask]
    cards: list[ParticipantWorkspaceCard]
    empty_state: ParticipantWorkspaceCard
