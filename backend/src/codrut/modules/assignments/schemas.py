from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from codrut.modules.assignments.models import (
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    ResponseVisibilityPolicy,
    TeamMembershipRole,
    TeamType,
)


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: TeamType


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    name: str
    type: TeamType


class TeamMembershipCreateRequest(BaseModel):
    participant_profile_id: UUID
    role: TeamMembershipRole


class TeamMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    team_id: UUID
    participant_profile_id: UUID
    role: TeamMembershipRole


class AssignmentCreateRequest(BaseModel):
    respondent_profile_id: UUID
    questionnaire_key: str = Field(min_length=1, max_length=120)
    target_type: AssignmentTargetType
    target_person_id: UUID | None = None
    target_team_id: UUID | None = None
    visibility_policy: ResponseVisibilityPolicy = ResponseVisibilityPolicy.trainer_raw_review


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    respondent_profile_id: UUID
    questionnaire_key: str
    target_type: AssignmentTargetType
    target_person_id: UUID | None
    target_team_id: UUID | None
    access_mode: AssignmentAccessMode
    status: AssignmentStatus
    visibility_policy: ResponseVisibilityPolicy
    due_at: datetime | None
    invited_at: datetime | None
    started_at: datetime | None
    submitted_at: datetime | None
    validated_at: datetime | None
    scored_at: datetime | None
    reminder_due_at: datetime | None
    last_reminder_sent_at: datetime | None


class AssignmentStatusUpdateRequest(BaseModel):
    status: AssignmentStatus


class InvitationCreateRequest(BaseModel):
    respondent_profile_id: UUID
    assignment_ids: list[UUID] | None = None
    expires_in_days: int = 14
    force_rotate: bool = False


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    respondent_profile_id: UUID
    token: str
    invite_url: str
    status: str
    expires_at: datetime
