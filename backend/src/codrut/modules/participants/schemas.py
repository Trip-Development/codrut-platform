from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from codrut.modules.identity.schemas import InviteTask


class ParticipantWorkspaceCard(BaseModel):
    title: str
    description: str
    meta: str | None = None


class ParticipantWorkspaceResult(BaseModel):
    assignment_id: UUID
    project_id: UUID | None = None
    project_name: str | None = None
    questionnaire_key: str
    title: str
    target_label: str
    scores: dict
    primary_result: str | None = None


class ParticipantReceivedFeedbackDimension(BaseModel):
    id: str
    label: str
    average_score: float
    completed_count: int


class ParticipantReceivedFeedbackSummary(BaseModel):
    project_id: UUID | None = None
    project_name: str | None = None
    assignment_round_id: UUID
    questionnaire_key: str
    questionnaire_title: str
    completed_count: int
    minimum_completed: int
    scale_max: float
    visible: bool
    overall_average: float | None = None
    dimensions: list[ParticipantReceivedFeedbackDimension] = Field(default_factory=list)


class ParticipantWorkspaceProject(BaseModel):
    id: UUID
    name: str
    deadline_label: str
    deadline_at: datetime | None = None


class ParticipantWorkspaceSummary(BaseModel):
    participant_profile_id: UUID
    participant_full_name: str
    participant_email: str
    anonymous_name: str | None = None
    pcm_base: str | None = None
    pcm_phase: str | None = None
    company_id: UUID
    company_name: str
    project_id: UUID | None
    project_name: str
    projects: list[ParticipantWorkspaceProject] = Field(default_factory=list)
    deadline_label: str
    deadline_at: datetime | None = None
    tasks: list[InviteTask]
    results: list[ParticipantWorkspaceResult] = Field(default_factory=list)
    received_feedback: ParticipantReceivedFeedbackSummary | None = None
    received_feedback_groups: list[ParticipantReceivedFeedbackSummary] = Field(default_factory=list)
    cards: list[ParticipantWorkspaceCard]
    empty_state: ParticipantWorkspaceCard
