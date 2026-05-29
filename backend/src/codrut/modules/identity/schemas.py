from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from codrut.modules.identity.models import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class SessionPrincipal(BaseModel):
    user_id: UUID
    email: EmailStr
    role: UserRole
    session_token: str = Field(exclude=True)


class AuthResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    role: UserRole
