from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from codrut.api.schemas import StrictRequestModel
from codrut.modules.companies.models import CompanyProjectStatus
from codrut.modules.identity.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    validate_new_password,
)

_EMAIL_ADAPTER = TypeAdapter(EmailStr)


class CompanyCreateRequest(StrictRequestModel):
    name: str = Field(min_length=1, max_length=255)


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class CompanySummaryResponse(CompanyResponse):
    participant_count: int = 0
    project_count: int = 0
    assignment_count: int = 0
    completed_count: int = 0
    scored_count: int = 0
    stage: Literal["setup", "invites", "completion", "reporting"] = "setup"


class CompanyProjectCreateRequest(StrictRequestModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    project_type: str | None = Field(default=None, max_length=120)
    status: CompanyProjectStatus = CompanyProjectStatus.draft
    starts_at: datetime | None = None
    due_at: datetime | None = None
    form_opens_at: datetime | None = None
    form_closes_at: datetime | None = None


class CompanyProjectUpdateRequest(StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    project_type: str | None = Field(default=None, max_length=120)
    status: CompanyProjectStatus | None = None
    starts_at: datetime | None = None
    due_at: datetime | None = None
    form_opens_at: datetime | None = None
    form_closes_at: datetime | None = None


class CompanyProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    name: str
    description: str | None
    project_type: str | None
    status: CompanyProjectStatus
    starts_at: datetime | None
    due_at: datetime | None
    form_opens_at: datetime | None
    form_closes_at: datetime | None
    archived_at: datetime | None = None
    archived_by_user_id: UUID | None = None
    archived_from_status: CompanyProjectStatus | None = None
    created_at: datetime
    updated_at: datetime


class CompanyProjectListItemResponse(CompanyProjectResponse):
    company_name: str


class ProjectPermanentDeleteRequest(StrictRequestModel):
    project_name: str = Field(min_length=1, max_length=255)


class ProjectLifecycleEventResponse(BaseModel):
    id: UUID
    company_id: UUID
    project_id: UUID
    actor_user_id: UUID | None
    actor_email: EmailStr | None
    action: Literal["archived", "restored", "permanently_deleted"]
    project_name: str
    previous_status: CompanyProjectStatus | None
    next_status: CompanyProjectStatus | None
    created_at: datetime


class CompanyAccessCodeCreateRequest(StrictRequestModel):
    label: str | None = Field(default=None, max_length=255)


class CompanyAccessCodeResponse(BaseModel):
    id: UUID
    company_id: UUID
    label: str | None
    code: str


class CompanyAccessCodeRegistrationRequest(StrictRequestModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    access_code: str = Field(min_length=6, max_length=64)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_new_password(value)


class ParticipantCreateRequest(StrictRequestModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    reports_to_name: str | None = Field(default=None, max_length=255)
    position: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    role_group: str | None = Field(default=None, max_length=255)
    pcm_profile: str | None = Field(default=None, max_length=255)
    pcm_base: str | None = Field(default=None, max_length=80)
    pcm_phase: str | None = Field(default=None, max_length=80)


class ParticipantUpdateRequest(StrictRequestModel):
    project_id: UUID | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    reports_to_name: str | None = Field(default=None, max_length=255)
    position: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    role_group: str | None = Field(default=None, max_length=255)


class RosterImportRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    full_name: str = Field(alias="Name", min_length=1, max_length=255)
    reports_to_name: str | None = Field(default=None, alias="Reports To", max_length=255)
    position: str | None = Field(default=None, alias="Position", max_length=255)
    location: str | None = Field(default=None, alias="Location", max_length=255)
    email: str | None = Field(default=None, alias="email", max_length=320)
    role_group: str | None = Field(default=None, alias="Role Group", max_length=255)
    pcm_profile: str | None = Field(default=None, alias="Profil PCM", max_length=255)
    pcm_base: str | None = Field(default=None, alias="PCM Bază", max_length=80)
    pcm_phase: str | None = Field(default=None, alias="PCM Fază", max_length=80)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_roster_email(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip().lower()
        if not cleaned:
            return None
        try:
            return str(_EMAIL_ADAPTER.validate_python(cleaned)).lower()
        except ValidationError:
            return None


class RosterImportRequest(StrictRequestModel):
    rows: list[RosterImportRow] = Field(min_length=1, max_length=1000)
    send_invites: bool = False
    project_id: UUID | None = None


class ReportingRelationshipIssue(BaseModel):
    participant_id: UUID
    participant_name: str
    reports_to_name: str
    code: str
    message: str


class ReportingRelationshipImportResponse(BaseModel):
    created_count: int
    issues: list[ReportingRelationshipIssue]


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    user_id: UUID | None
    account_type: Literal["guest", "registered"] | None = None
    is_shadow_account: bool = False
    full_name: str
    email: EmailStr | None
    reports_to_name: str | None
    position: str | None
    location: str | None
    role_group: str | None
    pcm_profile: str | None
    pcm_base: str | None = None
    pcm_phase: str | None = None
    anonymous_name: str | None = None


class ParticipantAccountSummary(BaseModel):
    user_id: UUID
    email: EmailStr
    role: Literal["trainer", "participant"]
    account_type: Literal["guest", "registered"]
    is_shadow_account: bool


class ParticipantAccountLinkStatusResponse(BaseModel):
    participant_id: UUID
    participant_email: EmailStr
    linked_account: ParticipantAccountSummary | None
    matching_email_account: ParticipantAccountSummary | None
    matching_account_is_linked: bool


class ParticipantAccountLinkRepairRequest(StrictRequestModel):
    action: Literal["link_matching_email", "unlink"]
    confirmation_email: EmailStr
    reason: str = Field(min_length=10, max_length=1000)


class ProjectMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    project_id: UUID
    participant_profile_id: UUID
    reports_to_name: str | None
    position: str | None
    location: str | None
    role_group: str | None
    active: bool
    notes: str | None


class ProjectParticipantResponse(ParticipantResponse):
    project_membership_id: UUID


class RosterImportEmailResult(BaseModel):
    participant_id: UUID
    email: EmailStr | None
    full_name: str
    delivery_mode: Literal["email", "secure_links"] = "email"
    email_sent: bool
    email_queued: bool = False
    error_code: str | None = None
    error: str | None = None
    invite_url: str | None = None


class RosterImportResponse(BaseModel):
    participants: list[ParticipantResponse]
    email_results: list[RosterImportEmailResult]
    total_imported: int
    emails_sent: int
    emails_queued: int = 0
    emails_failed: int


class ParticipantInviteBatchRequest(StrictRequestModel):
    participant_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=1000)
    project_id: UUID | None = None
    assessment_cycle_id: UUID | None = None
    mode: Literal["email", "secure_links"] = "email"
    target_mode: Literal["unsent", "selected", "all"] = "unsent"
    force_rotate: bool = False


class ParticipantInviteBatchResponse(BaseModel):
    results: list[RosterImportEmailResult]
    total: int
    emails_sent: int
    emails_queued: int = 0
    emails_failed: int
    links_generated: int


class ParticipantInvitationStatusResponse(BaseModel):
    participant_id: UUID
    latest_delivery_mode: Literal["email", "secure_links"] | None = None
    latest_email_status: str | None = None
    latest_email_error: str | None = None
    last_sent_at: datetime | None = None
    email_send_count: int = 0
    has_active_secure_link: bool = False
    active_secure_link_expires_at: datetime | None = None
    active_secure_link_url: str | None = None
