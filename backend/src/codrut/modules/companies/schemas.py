from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompanyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class ParticipantCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    position: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    role_group: str | None = Field(default=None, max_length=255)
    pcm_profile: str | None = Field(default=None, max_length=255)


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    user_id: UUID | None
    full_name: str
    email: EmailStr
    position: str | None
    location: str | None
    role_group: str | None
    pcm_profile: str | None
