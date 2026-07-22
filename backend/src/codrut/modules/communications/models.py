import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from codrut.core.database import Base, TimestampMixin


class EmailSendStatus(StrEnum):
    queued = "queued"
    dispatching = "dispatching"
    accepted = "accepted"
    failed = "failed"
    delivered = "delivered"
    bounced = "bounced"
    cancelled = "cancelled"
    indeterminate = "indeterminate"


class EmailEventType(StrEnum):
    queued = "queued"
    claimed = "claimed"
    retry_scheduled = "retry_scheduled"
    cancelled = "cancelled"
    accepted = "accepted"
    failed = "failed"
    delivered = "delivered"
    bounced = "bounced"
    opened = "opened"
    clicked = "clicked"
    unsubscribed = "unsubscribed"
    complained = "complained"
    indeterminate = "indeterminate"


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
    __table_args__ = (
        Index("ix_email_sends_idempotency_key", "idempotency_key", unique=True),
        Index(
            "ix_email_sends_provider_idempotency_key",
            "provider_idempotency_key",
            unique=True,
        ),
        Index(
            "ix_email_sends_outbox_due",
            "status",
            "next_attempt_at",
            "lease_expires_at",
        ),
        CheckConstraint(
            "status not in ('queued', 'dispatching') or message_payload is not null",
            name="outbox_payload_present",
        ),
        CheckConstraint(
            "attempt_count >= 0 and max_attempts > 0 and attempt_count <= max_attempts",
            name="outbox_attempt_bounds",
        ),
        CheckConstraint(
            "status <> 'queued' or next_attempt_at is not null",
            name="outbox_next_attempt_present",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("questionnaire_assignments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    campaign_recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaign_recipients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    template_key: Mapped[str] = mapped_column(String(120), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    provider_idempotency_key: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    provider_request_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    payload_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message_payload: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[EmailSendStatus] = mapped_column(
        Enum(EmailSendStatus),
        nullable=False,
        default=EmailSendStatus.queued,
    )
    error_details: Mapped[str | None] = mapped_column(String, nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailEvent(TimestampMixin, Base):
    __tablename__ = "email_events"
    __table_args__ = (
        Index(
            "uq_email_events_provider_event_id",
            "provider_event_id",
            unique=True,
            postgresql_where=sa_text("provider_event_id is not null"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email_send_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_sends.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[EmailEventType] = mapped_column(Enum(EmailEventType), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EmailSuppression(TimestampMixin, Base):
    __tablename__ = "email_suppressions"
    __table_args__ = (
        Index(
            "uq_email_suppressions_owner_normalized_email",
            "owner_id",
            sa_text("lower(email)"),
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    source_email_send_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("email_sends.id", ondelete="SET NULL"),
        nullable=True,
    )


class CampaignRecipient(TimestampMixin, Base):
    __tablename__ = "campaign_recipients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
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
    __table_args__ = (
        Index(
            "uq_campaign_recipients_owner_normalized_email",
            owner_id,
            func.lower(email),
            unique=True,
            postgresql_where=email.is_not(None),
        ),
    )


class CampaignRecipientMembership(TimestampMixin, Base):
    __tablename__ = "campaign_recipient_memberships"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "recipient_id",
            name="uq_campaign_recipient_memberships_campaign_recipient",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign_recipients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)


class CampaignRecipientEvent(TimestampMixin, Base):
    __tablename__ = "campaign_recipient_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign_recipients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    variant_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    segment: Mapped[CampaignRecipientSegment | None] = mapped_column(
        Enum(CampaignRecipientSegment),
        nullable=True,
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
    recipient_memberships_initialized: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )


class CampaignAsset(TimestampMixin, Base):
    __tablename__ = "campaign_assets"
    __table_args__ = (
        CheckConstraint(
            "status in ('staged', 'attached')",
            name="campaign_asset_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    public_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="staged")


class EmailTemplate(TimestampMixin, Base):
    __tablename__ = "email_templates"
    __table_args__ = (
        Index(
            "uq_email_templates_owner_key_version",
            "owner_id",
            "key",
            "version",
            unique=True,
            postgresql_where=sa_text("owner_id is not null"),
        ),
        Index(
            "uq_email_templates_system_key_version",
            "key",
            "version",
            unique=True,
            postgresql_where=sa_text("owner_id is null"),
        ),
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
    package_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    content_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    system_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
