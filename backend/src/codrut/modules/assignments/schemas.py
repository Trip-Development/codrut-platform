from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from codrut.api.schemas import StrictRequestModel
from codrut.modules.assignments.models import (
    AssessmentCycleStatus,
    AssignmentAccessMode,
    AssignmentStatus,
    AssignmentTargetType,
    ResponseVisibilityPolicy,
    TeamMembershipRole,
    TeamType,
)


class AssessmentCycleQuestionnaireResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    questionnaire_definition_id: UUID
    questionnaire_key: str
    display_order: int


class AssessmentCycleCreateRequest(StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    source_cycle_id: UUID | None = None
    questionnaire_keys: list[str] | None = None
    starts_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None


class AssessmentCycleUpdateRequest(StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    starts_at: AwareDatetime | None = None
    due_at: AwareDatetime | None = None


class AssessmentCycleCloseRequest(StrictRequestModel):
    cancel_unfinished: bool = False


class AssessmentCycleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    sequence: int
    name: str
    status: AssessmentCycleStatus
    source_cycle_id: UUID | None
    starts_at: datetime | None
    due_at: datetime | None
    closed_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
    questionnaires: list[AssessmentCycleQuestionnaireResponse] = Field(default_factory=list)


class TeamCreateRequest(StrictRequestModel):
    name: str = Field(min_length=1, max_length=255)
    type: TeamType


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    name: str
    type: TeamType


class TeamMembershipCreateRequest(StrictRequestModel):
    participant_profile_id: UUID
    role: TeamMembershipRole


class TeamMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    team_id: UUID
    participant_profile_id: UUID
    role: TeamMembershipRole


class AssignmentCreateRequest(StrictRequestModel):
    project_id: UUID | None = None
    assessment_cycle_id: UUID | None = None
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
    project_id: UUID | None
    assessment_cycle_id: UUID | None
    assignment_round_id: UUID
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
    reminder_count: int


class AssignmentStatusUpdateRequest(StrictRequestModel):
    status: AssignmentStatus


class AssignmentReopenResponse(BaseModel):
    """Ce s-a intamplat la redeschiderea unui chestionar."""

    model_config = ConfigDict(from_attributes=True)

    assignment_id: UUID
    status: AssignmentStatus
    reopen_count: int
    archived_response_id: UUID
    archived_had_score: bool


class InvitationCreateRequest(StrictRequestModel):
    respondent_profile_id: UUID
    project_id: UUID | None = None
    assignment_ids: list[UUID] | None = None
    expires_in_days: int = 3650
    force_rotate: bool = False


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID | None
    respondent_profile_id: UUID
    token: str
    invite_url: str
    status: str
    expires_at: datetime


class AssignmentPlanScopeResponse(BaseModel):
    id: str
    name: str
    type: str
    participant_ids: list[UUID]


class AssignmentPlanItemResponse(BaseModel):
    key: str
    scope_id: str
    scope_name: str
    scope_type: str
    respondent_profile_id: UUID
    respondent_name: str
    questionnaire_key: str
    target_type: AssignmentTargetType
    target_person_id: UUID | None = None
    target_person_name: str | None = None
    target_team_id: UUID | None = None
    target_team_name: str | None = None
    target_team_type: TeamType | None = None
    target_team_member_ids: list[UUID] = Field(default_factory=list)
    target_team_leader_id: UUID | None = None
    visibility_policy: ResponseVisibilityPolicy = ResponseVisibilityPolicy.trainer_raw_review
    selected: bool = True
    existing_assignment_id: UUID | None = None


class AssignmentPlanResponse(BaseModel):
    project_id: UUID | None = None
    assessment_cycle_id: UUID | None = None
    source_cycle_id: UUID | None = None
    scopes: list[AssignmentPlanScopeResponse]
    assignments: list[AssignmentPlanItemResponse]
    suggested_count: int
    existing_count: int


class AssignmentPlanSaveItem(StrictRequestModel):
    respondent_profile_id: UUID
    questionnaire_key: str = Field(min_length=1, max_length=120)
    target_type: AssignmentTargetType
    target_person_id: UUID | None = None
    target_team_id: UUID | None = None
    target_team_name: str | None = Field(default=None, max_length=255)
    target_team_type: TeamType | None = None
    target_team_member_ids: list[UUID] = Field(default_factory=list)
    target_team_leader_id: UUID | None = None
    visibility_policy: ResponseVisibilityPolicy = ResponseVisibilityPolicy.trainer_raw_review

    @model_validator(mode="before")
    @classmethod
    def drop_planner_response_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        response_only_fields = {
            "key",
            "scope_id",
            "scope_name",
            "scope_type",
            "respondent_name",
            "target_person_name",
            "selected",
            "existing_assignment_id",
        }
        return {key: item for key, item in value.items() if key not in response_only_fields}


class AssignmentPlanSaveRequest(StrictRequestModel):
    project_id: UUID | None = None
    assessment_cycle_id: UUID | None = None
    assignments: list[AssignmentPlanSaveItem] = Field(default_factory=list)


class AssignmentPlanSaveResponse(BaseModel):
    assignments: list[AssignmentResponse]
    created_count: int
    existing_count: int
