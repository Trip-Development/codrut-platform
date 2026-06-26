from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from codrut.modules.identity.models import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    token: str
    terms_accepted: bool = False
    terms_version: str = Field(default="privacy-2026-06-12", max_length=80)


class ConsentRequest(BaseModel):
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
    tasks: list[InviteTask]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=12, max_length=128)


class PasswordResetResponse(BaseModel):
    ok: bool = True


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
