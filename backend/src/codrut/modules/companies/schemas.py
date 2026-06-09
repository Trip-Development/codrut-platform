from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompanyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


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


class RosterImportRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    full_name: str = Field(alias="Name", min_length=1, max_length=255)
    reports_to_name: str | None = Field(default=None, alias="Reports To", max_length=255)
    position: str | None = Field(default=None, alias="Position", max_length=255)
    location: str | None = Field(default=None, alias="Location", max_length=255)
    email: EmailStr = Field(alias="email")
    pcm_profile: str | None = Field(default=None, alias="Profil PCM", max_length=255)


class RosterImportRequest(BaseModel):
    rows: list[RosterImportRow] = Field(min_length=1, max_length=1000)


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


class RosterImportEmailResult(BaseModel):
    participant_id: UUID
    email: EmailStr
    full_name: str
    email_sent: bool
    error: str | None = None


class RosterImportResponse(BaseModel):
    participants: list[ParticipantResponse]
    email_results: list[RosterImportEmailResult]
    total_imported: int
    emails_sent: int
    emails_failed: int
