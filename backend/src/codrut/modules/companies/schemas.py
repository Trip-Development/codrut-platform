from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from codrut.modules.companies.models import CompanyProjectStatus


class CompanyCreateRequest(BaseModel):
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


class CompanyProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    project_type: str | None = Field(default=None, max_length=120)
    status: CompanyProjectStatus = CompanyProjectStatus.draft
    starts_at: datetime | None = None
    due_at: datetime | None = None
    form_opens_at: datetime | None = None
    form_closes_at: datetime | None = None


class CompanyProjectUpdateRequest(BaseModel):
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
    created_at: datetime
    updated_at: datetime


class CompanyProjectListItemResponse(CompanyProjectResponse):
    company_name: str


class CompanyAccessCodeCreateRequest(BaseModel):
    label: str | None = Field(default=None, max_length=255)


class CompanyAccessCodeResponse(BaseModel):
    id: UUID
    company_id: UUID
    label: str | None
    code: str


class CompanyAccessCodeRegistrationRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    access_code: str = Field(min_length=6, max_length=64)


class ParticipantCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    reports_to_name: str | None = Field(default=None, max_length=255)
    position: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    role_group: str | None = Field(default=None, max_length=255)
    pcm_profile: str | None = Field(default=None, max_length=255)
    pcm_base: str | None = Field(default=None, max_length=80)
    pcm_phase: str | None = Field(default=None, max_length=80)


class ParticipantUpdateRequest(BaseModel):
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
    email: EmailStr = Field(alias="email")
    pcm_profile: str | None = Field(default=None, alias="Profil PCM", max_length=255)
    pcm_base: str | None = Field(default=None, alias="PCM Bază", max_length=80)
    pcm_phase: str | None = Field(default=None, alias="PCM Fază", max_length=80)


class RosterImportRequest(BaseModel):
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
    full_name: str
    email: EmailStr
    reports_to_name: str | None
    position: str | None
    location: str | None
    role_group: str | None
    pcm_profile: str | None
    pcm_base: str | None = None
    pcm_phase: str | None = None
    anonymous_name: str | None = None


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
    email: EmailStr
    full_name: str
    delivery_mode: Literal["email", "secure_links"] = "email"
    email_sent: bool
    error: str | None = None
    invite_url: str | None = None


class RosterImportResponse(BaseModel):
    participants: list[ParticipantResponse]
    email_results: list[RosterImportEmailResult]
    total_imported: int
    emails_sent: int
    emails_failed: int


class ParticipantInviteBatchRequest(BaseModel):
    participant_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=1000)
    project_id: UUID | None = None
    mode: Literal["email", "secure_links"] = "email"
    force_rotate: bool = False


class ParticipantInviteBatchResponse(BaseModel):
    results: list[RosterImportEmailResult]
    total: int
    emails_sent: int
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
