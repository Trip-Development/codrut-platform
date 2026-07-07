import re
import unicodedata
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
CampaignSegmentValue = Literal["past_customer", "potential_customer"]


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


class CampaignRecipientMembershipRowResponse(CampaignRecipientRowResponse):
    membershipSource: str | None = None


class CampaignRecipientMembershipUpdateRequest(BaseModel):
    recipient_ids: list[UUID] = Field(default_factory=list)


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
    email: EmailStr | None = None
    contact_name: str | None = None
    organization_name: str | None = None
    segment: CampaignSegmentValue
    status: str | None = None
    source: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def require_email_for_active_recipient(self) -> "CampaignRecipientCreateRequest":
        if (self.status is None or self.status == "active") and self.email is None:
            raise ValueError("Active campaign recipients require an email.")
        return self


CAMPAIGN_RECIPIENT_IMPORT_HEADERS = {
    "de trimis",
    "trimite",
    "send",
    "primul prenume",
    "al doilea prenume",
    "prenume",
    "prenume 1",
    "prenume 2",
    "nume de familie",
    "nume familie",
    "nume",
    "surname",
    "last name",
    "tip client",
    "organizație",
    "organizatie",
    "companie",
    "company",
    "telefon",
    "funcția",
    "functia",
}

FIRST_NAME_KEYS = ["Primul prenume", "Prenume", "Prenume 1", "First name", "first_name"]
MIDDLE_NAME_KEYS = [
    "Al doilea prenume",
    "Prenume 2",
    "Middle name",
    "middle_name",
]
LAST_NAME_KEYS = [
    "Nume de familie",
    "Nume familie",
    "Nume",
    "Familie",
    "Surname",
    "Last name",
    "last_name",
]
FULL_NAME_KEYS = [
    "contact_name",
    "Contact name",
    "Nume contact",
    "Nume complet",
    "Full name",
    "Name",
    "name",
]
FALLBACK_FULL_NAME_KEYS = ["Nume"]
ORGANIZATION_KEYS = [
    "organization_name",
    "Organizație",
    "Organizatie",
    "Organizaţie",
    "Organizația",
    "Organizatia",
    "Companie",
    "company",
    "Company",
]


def _normalize_import_key(value: str) -> str:
    without_marks = "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    return " ".join(without_marks.strip().lower().split())


def _normalize_import_value(value: object) -> str:
    return "" if value is None else str(value).strip()


def _read_import_value(row: dict[str, object], keys: list[str]) -> str:
    wanted_keys = {_normalize_import_key(key) for key in keys}
    for key, value in row.items():
        if _normalize_import_key(str(key)) in wanted_keys:
            normalized_value = _normalize_import_value(value)
            if normalized_value:
                return normalized_value
    return ""


def _is_spreadsheet_import_row(row: dict[str, object]) -> bool:
    return any(
        _normalize_import_key(str(key)) in CAMPAIGN_RECIPIENT_IMPORT_HEADERS
        for key in row
    )


def _is_marked_for_campaign_send(row: dict[str, object]) -> bool:
    send_value = _read_import_value(row, ["De trimis", "Trimite", "Send", "Active"])
    if not send_value:
        return True
    return _normalize_import_key(send_value) in {"da", "yes", "y", "1", "true", "activ"}


def _is_valid_import_email(value: str) -> bool:
    return re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value) is not None


def _campaign_recipient_segment(value: str) -> str:
    normalized = _normalize_import_key(value)
    if (
        "nu e client" in normalized
        or "nu este client" in normalized
        or "non-client" in normalized
        or "potential" in normalized
        or "potențial" in normalized
    ):
        return "potential_customer"
    if "past" in normalized or "client" in normalized:
        return "past_customer"
    return "potential_customer"


def _campaign_recipient_contact_name(row: dict[str, object]) -> str:
    explicit_name = _read_import_value(row, FULL_NAME_KEYS)
    if explicit_name:
        return explicit_name

    composed_name = " ".join(
        value
        for value in [
            _read_import_value(row, FIRST_NAME_KEYS),
            _read_import_value(row, MIDDLE_NAME_KEYS),
            _read_import_value(row, LAST_NAME_KEYS),
        ]
        if value
    )
    if composed_name:
        return composed_name

    return _read_import_value(row, FALLBACK_FULL_NAME_KEYS)


def _normalize_campaign_recipient_import_row(row: dict[str, object]) -> dict[str, object] | None:
    email = _read_import_value(row, ["email", "Email", "EMAIL"])
    is_spreadsheet_row = _is_spreadsheet_import_row(row)
    if not email and not is_spreadsheet_row:
        return row

    marked_for_send = _is_marked_for_campaign_send(row)
    email_is_valid = bool(email) and _is_valid_import_email(email)
    status = "active" if marked_for_send and email_is_valid else "suppressed"

    segment_value = _read_import_value(row, ["segment", "Segment", "Tip Client"])
    return {
        **row,
        "email": email if email_is_valid else None,
        "contact_name": _campaign_recipient_contact_name(row) or None,
        "organization_name": _read_import_value(row, ORGANIZATION_KEYS) or None,
        "segment": _campaign_recipient_segment(segment_value),
        "status": status,
        "source": _read_import_value(row, ["source", "Source"]) or "excel_import",
    }


class CampaignRecipientBulkCreateRequest(BaseModel):
    recipients: list[CampaignRecipientCreateRequest]

    @model_validator(mode="before")
    @classmethod
    def normalize_import_rows(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        recipients = value.get("recipients")
        if not isinstance(recipients, list):
            return value

        normalized_recipients: list[object] = []
        for recipient in recipients:
            if isinstance(recipient, dict):
                normalized = _normalize_campaign_recipient_import_row(recipient)
                if normalized is not None:
                    normalized_recipients.append(normalized)
            else:
                normalized_recipients.append(recipient)
        return {**value, "recipients": normalized_recipients}


class CampaignRecipientUpdateRequest(BaseModel):
    email: EmailStr | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    organization_name: str | None = Field(default=None, max_length=255)
    segment: str | None = None
    status: str | None = None
    source: str | None = Field(default=None, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


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
    mode: Literal["new", "selected", "all"] = "new"
    dry_run: bool = False


class CampaignSendRecipientResult(BaseModel):
    recipient_id: UUID
    email: str
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
    segment: CampaignSegmentValue
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


class CampaignUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    segment: str | None = None
    status: str | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    html_body: str | None = Field(default=None, min_length=1)
    text_body: str | None = Field(default=None, min_length=1)
    video_url: str | None = Field(default=None, max_length=2048)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    landing_page_url: str | None = Field(default=None, max_length=2048)

    @field_validator("video_url", "thumbnail_url", "landing_page_url", mode="before")
    @classmethod
    def normalize_campaign_url(cls, value: str | None) -> str | None:
        return CampaignCreateRequest.normalize_campaign_url(value)
