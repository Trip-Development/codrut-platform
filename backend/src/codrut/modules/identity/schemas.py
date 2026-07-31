from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from codrut.api.schemas import StrictRequestModel
from codrut.modules.identity.models import UserAccountType, UserRole
from codrut.modules.identity.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    validate_new_password,
)
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION


class RegisterRequest(StrictRequestModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    token: str
    terms_accepted: bool = False
    terms_version: str = Field(default=CURRENT_TERMS_VERSION, max_length=80)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_new_password(value)


class ConsentRequest(StrictRequestModel):
    terms_accepted: bool = False
    terms_version: str = Field(default=CURRENT_TERMS_VERSION, max_length=80)


class InviteTask(BaseModel):
    id: str
    title: str
    status: str
    detail: str
    href: str
    assignmentId: str
    targetLabel: str
    estimatedMinutes: int
    questionnaireKey: str
    questionnaireDefinitionId: UUID | None = None
    projectId: UUID | None = None
    projectName: str | None = None
    assignmentRoundId: UUID | None = None
    assessmentCycleId: UUID | None = None
    cycleName: str | None = None
    cycleSequence: int | None = None
    deadlineLabel: str | None = None
    dueAt: datetime | None = None


class InviteVerifyResponse(BaseModel):
    email: EmailStr
    full_name: str
    anonymous_name: str | None = None
    is_leadership: bool
    already_registered: bool
    account_dashboard_available: bool = False
    account_type: UserAccountType = UserAccountType.guest
    access_mode: Literal["account", "secure_link"] = "secure_link"
    consent_current: bool = False
    project_id: UUID | None = None
    project_name: str
    expires_at: datetime
    token_status: Literal["active"]
    terms_accepted_at: datetime | None = None
    terms_version: str | None = None
    tasks: list[InviteTask]


class InviteExchangeRequest(StrictRequestModel):
    token: str = Field(min_length=1, max_length=2048)
    # Compatibility-only. A link must never replace an authenticated account.
    replace_existing_session: bool = False


class InviteExchangeResponse(BaseModel):
    action: Literal[
        "secure_link_ready",
        "login_required",
        "dashboard_ready",
        "account_switch_required",
    ]
    destination: str | None = None
    participant_profile_id: UUID
    project_id: UUID | None = None
    assessment_cycle_id: UUID | None = None
    account_type: UserAccountType = UserAccountType.guest
    access_mode: Literal["account", "secure_link"] = "secure_link"
    consent_current: bool = False
    terms_accepted_at: datetime | None = None
    terms_version: str | None = None


class LoginRequest(StrictRequestModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequest(StrictRequestModel):
    email: EmailStr


class PasswordResetConfirmRequest(StrictRequestModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_new_password(value)


class PasswordChangeRequest(StrictRequestModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validate_new_password(value)


class PasswordResetResponse(BaseModel):
    ok: bool = True


class CsrfTokenResponse(BaseModel):
    csrf_token: str


class SessionPrincipal(BaseModel):
    user_id: UUID
    email: EmailStr
    role: UserRole
    account_type: UserAccountType = UserAccountType.registered
    available_workspaces: tuple[UserRole, ...] = ()
    default_workspace: UserRole | None = None
    avatar_palette_key: int | None = None
    terms_accepted_at: datetime | None = None
    terms_version: str | None = None
    consent_current: bool = False
    session_token: str = Field(exclude=True)
    assignment_invite_id: UUID | None = Field(default=None, exclude=True)
    assignment_ids: tuple[UUID, ...] | None = Field(default=None, exclude=True)
    project_id: UUID | None = Field(default=None, exclude=True)
    access_mode: Literal["account", "secure_link"] = "account"

    @model_validator(mode="after")
    def normalize_workspace_context(self) -> "SessionPrincipal":
        if not self.available_workspaces:
            self.available_workspaces = (self.role,)
        if self.default_workspace is None:
            self.default_workspace = self.role
        if self.assignment_invite_id is not None:
            self.access_mode = "secure_link"
        return self

    def can_access_workspace(self, workspace: UserRole) -> bool:
        workspaces = self.available_workspaces or (self.role,)
        return workspace in workspaces


class AuthResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    role: UserRole
    account_type: UserAccountType = UserAccountType.registered
    available_workspaces: tuple[UserRole, ...] = ()
    default_workspace: UserRole | None = None
    avatar_palette_key: int | None = None
    terms_accepted_at: datetime | None = None
    terms_version: str | None = None
    consent_current: bool = False
    access_mode: Literal["account", "secure_link"] = "account"
