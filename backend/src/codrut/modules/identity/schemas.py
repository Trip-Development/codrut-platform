from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from codrut.api.schemas import StrictRequestModel
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    validate_new_password,
)


class RegisterRequest(StrictRequestModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    token: str
    terms_accepted: bool = False
    terms_version: str = Field(default="privacy-2026-06-12", max_length=80)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_new_password(value)


class ConsentRequest(StrictRequestModel):
    terms_accepted: bool = False
    terms_version: str = Field(default="privacy-2026-06-12", max_length=80)


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


class InviteVerifyResponse(BaseModel):
    email: EmailStr
    full_name: str
    anonymous_name: str | None = None
    is_leadership: bool
    already_registered: bool
    project_id: UUID | None = None
    project_name: str
    expires_at: datetime
    token_status: Literal["active"]
    terms_accepted_at: datetime | None = None
    terms_version: str | None = None
    tasks: list[InviteTask]


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
    terms_accepted_at: datetime | None = None
    terms_version: str | None = None
    session_token: str = Field(exclude=True)


class AuthResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    role: UserRole
    terms_accepted_at: datetime | None = None
    terms_version: str | None = None
