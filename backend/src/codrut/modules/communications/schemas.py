from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from codrut.contracts.emails import EmailDeliveryStatus, EmailProviderKey


class EmailTestSendRequest(BaseModel):
    to: EmailStr
    subject: str = Field(default="Test Codrut email", min_length=1, max_length=180)
    html_body: str = Field(default="<p>Test email din Codrut.</p>", min_length=1)
    text_body: str = Field(default="Test email din Codrut.", min_length=1)


class EmailTestSendResponse(BaseModel):
    provider: EmailProviderKey
    status: EmailDeliveryStatus
    message_id: str
    recipient: EmailStr


class EmailTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    version: int
    subject: str
    html_body: str
    text_body: str
    variables: list[str]
    audience: str | None = None
    active: bool = True
    owner_id: UUID | None = None


class EmailTemplateCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=255)
    html_body: str = Field(min_length=1)
    text_body: str = Field(min_length=1)
    variables: list[str] = Field(default_factory=list)
    audience: str | None = Field(default=None, max_length=100)
    active: bool = True


class EmailTemplateUpdateRequest(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    html_body: str | None = Field(default=None, min_length=1)
    text_body: str | None = Field(default=None, min_length=1)
    variables: list[str] | None = None
    audience: str | None = Field(default=None, max_length=100)
    active: bool | None = None

