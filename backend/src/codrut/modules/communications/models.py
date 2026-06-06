import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from codrut.core.database import Base, TimestampMixin


class EmailSendStatus(StrEnum):
    queued = "queued"
    accepted = "accepted"
    failed = "failed"
    delivered = "delivered"
    bounced = "bounced"


class EmailEventType(StrEnum):
    accepted = "accepted"
    failed = "failed"
    delivered = "delivered"
    bounced = "bounced"
    opened = "opened"
    clicked = "clicked"


class CampaignRecipientSegment(StrEnum):
    past_customer = "past_customer"
    potential_customer = "potential_customer"


class CampaignRecipientStatus(StrEnum):
    active = "active"
    suppressed = "suppressed"
    unsubscribed = "unsubscribed"


class CampaignStatus(StrEnum):
    draft = "draft"
    ready = "ready"
    paused = "paused"
    completed = "completed"


class EmailSend(TimestampMixin, Base):
    __tablename__ = "email_sends"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("questionnaire_assignments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    template_key: Mapped[str] = mapped_column(String(120), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[EmailSendStatus] = mapped_column(
        Enum(EmailSendStatus),
        nullable=False,
        default=EmailSendStatus.queued,
    )
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailEvent(TimestampMixin, Base):
    __tablename__ = "email_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email_send_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_sends.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[EmailEventType] = mapped_column(Enum(EmailEventType), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CampaignRecipient(TimestampMixin, Base):
    __tablename__ = "campaign_recipients"
    __table_args__ = (UniqueConstraint("email"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    segment: Mapped[CampaignRecipientSegment] = mapped_column(
        Enum(CampaignRecipientSegment),
        nullable=False,
    )
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CampaignRecipientStatus] = mapped_column(
        Enum(CampaignRecipientStatus),
        nullable=False,
        default=CampaignRecipientStatus.active,
    )


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    segment: Mapped[CampaignRecipientSegment] = mapped_column(
        Enum(CampaignRecipientSegment),
        nullable=False,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus),
        nullable=False,
        default=CampaignStatus.draft,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    html_body: Mapped[str] = mapped_column(String, nullable=False)
    text_body: Mapped[str] = mapped_column(String, nullable=False)
    video_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    landing_page_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)


class EmailTemplate(TimestampMixin, Base):
    __tablename__ = "email_templates"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_email_templates_key_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    html_body: Mapped[str] = mapped_column(String, nullable=False)
    text_body: Mapped[str] = mapped_column(String, nullable=False)
    variables: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    audience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

