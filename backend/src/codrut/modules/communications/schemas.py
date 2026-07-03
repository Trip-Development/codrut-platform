from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from codrut.contracts.emails import EmailDeliveryStatus, EmailProviderKey

CampaignRecipientEventType = Literal[
    "opened",
    "clicked",
    "video_viewed",
    "calendly_clicked",
    "replied",
]


class EmailTestSendRequest(BaseModel):
    to: EmailStr
    subject: str = Field(default="Test Codruț email", min_length=1, max_length=180)
    html_body: str = Field(default="<p>Test email din Codruț.</p>", min_length=1)
    text_body: str = Field(default="Test email din Codruț.", min_length=1)


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


class EmailDeliveryMetricResponse(BaseModel):
    label: str
    value: str
    detail: str


class AssessmentDeliveryRowResponse(BaseModel):
    id: str
    company_id: str
    participant: str
    email: str
    audience: str  # "leadership_account" | "secure_link"
    project: str
    tasks: str
    delivery: str  # "draft" | "sent" | "delivered" | "opened" | "failed"
    reminder: str  # "today" | "tomorrow" | "paused" | "none"
    completion: str  # "not_started" | "in_progress" | "completed"
    nextAction: str


class CampaignRecipientRowResponse(BaseModel):
    id: str
    company: str
    firstName: str | None = None
    lastName: str | None = None
    email: str
    clientType: str
    status: str
    openRate: str | None = None
    clickRate: str | None = None
    viewRate: str | None = None
    openCount: int = 0
    clickCount: int = 0
    viewCount: int = 0
    replyCount: int = 0
    calendlyClickCount: int = 0
    emailVariant: str | None = None
    outcome: str | None = None


class CampaignOpsSummaryResponse(BaseModel):
    videoHost: dict
    template: dict
    recipients: list[CampaignRecipientRowResponse]
    weeklyReport: dict


class EmailOpsSummaryResponse(BaseModel):
    metrics: list[EmailDeliveryMetricResponse]
    assessmentRows: list[AssessmentDeliveryRowResponse]
    rules: list[str]
    campaign: CampaignOpsSummaryResponse


class CampaignRecipientCreateRequest(BaseModel):
    email: EmailStr
    contact_name: str | None = None
    organization_name: str | None = None
    segment: str  # "past_customer" | "potential_customer"
    source: str | None = None


class CampaignRecipientBulkCreateRequest(BaseModel):
    recipients: list[CampaignRecipientCreateRequest]


class CampaignRecipientUpdateRequest(BaseModel):
    email: EmailStr | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    organization_name: str | None = Field(default=None, max_length=255)
    segment: str | None = None
    status: str | None = None
    source: str | None = Field(default=None, max_length=255)


class CampaignRecipientEventCreateRequest(BaseModel):
    event_type: CampaignRecipientEventType
    variant_key: str | None = Field(default=None, max_length=120)
    occurred_at: datetime | None = None


class CampaignRecipientEventResponse(BaseModel):
    id: UUID
    recipient_id: UUID
    event_type: CampaignRecipientEventType
    variant_key: str | None = None
    occurred_at: datetime


class CampaignSendRequest(BaseModel):
    recipient_ids: list[UUID] | None = None
    dry_run: bool = False


class CampaignSendRecipientResult(BaseModel):
    recipient_id: UUID
    email: EmailStr
    status: str
    message_id: str | None = None
    error: str | None = None


class CampaignSendResponse(BaseModel):
    campaign_id: UUID
    total: int
    sent: int
    failed: int
    skipped: int
    dry_run: bool
    results: list[CampaignSendRecipientResult]


class CampaignAssetUploadResponse(BaseModel):
    url: str
    file_name: str
    content_type: str
    size_bytes: int


class CampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    segment: str
    subject: str = Field(min_length=1, max_length=255)
    html_body: str = Field(min_length=1)
    text_body: str = Field(min_length=1)
    video_url: str | None = Field(default=None, max_length=2048)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    landing_page_url: str | None = Field(default=None, max_length=2048)

    @field_validator("video_url", "thumbnail_url", "landing_page_url", mode="before")
    @classmethod
    def normalize_campaign_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        if not stripped:
            return None
        parsed = urlparse(stripped)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Campaign asset URLs must be absolute HTTP(S) URLs.")
        return stripped

    @model_validator(mode="after")
    def require_video_asset_pair(self) -> "CampaignCreateRequest":
        if self.video_url or self.thumbnail_url:
            missing = [
                label
                for label, value in (
                    ("video_url", self.video_url),
                    ("thumbnail_url", self.thumbnail_url),
                )
                if value is None
            ]
            if missing:
                raise ValueError("Video campaigns require video_url and thumbnail_url.")
        return self
