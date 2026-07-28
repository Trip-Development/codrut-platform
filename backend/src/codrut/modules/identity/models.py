from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from codrut.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from codrut.modules.companies.models import CompanyMembership, ParticipantProfile

SHADOW_ACCOUNT_PASSWORD_HASH = "shadow_account_no_password"  # noqa: S105
AVATAR_PALETTE_SPACE = 55_520_640
AVATAR_PALETTE_SERVER_DEFAULT = (
    "mod(nextval('user_avatar_palette_key_seq') * 16777619 + 2166136261, 55520640)"
)


class UserRole(StrEnum):
    trainer = "trainer"
    participant = "participant"


class UserAccountType(StrEnum):
    guest = "guest"
    registered = "registered"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("avatar_palette_key"),
        CheckConstraint(
            f"avatar_palette_key >= 0 and avatar_palette_key < {AVATAR_PALETTE_SPACE}",
            name="user_avatar_palette_key_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.participant,
    )
    account_type: Mapped[UserAccountType] = mapped_column(
        Enum(UserAccountType),
        nullable=False,
        default=UserAccountType.registered,
        server_default=UserAccountType.registered.value,
    )
    avatar_palette_key: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text(AVATAR_PALETTE_SERVER_DEFAULT),
    )
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    terms_version: Mapped[str | None] = mapped_column(String(80), nullable=True)

    sessions: Mapped[list[Session]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    company_memberships: Mapped[list[CompanyMembership]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    participant_profiles: Mapped[list[ParticipantProfile]] = relationship(
        back_populates="user",
    )

    @property
    def is_registered(self) -> bool:
        # SQLAlchemy applies the registered default at flush time. Treat an
        # unflushed model without an explicit value as that same default.
        return self.account_type is not UserAccountType.guest


class Session(TimestampMixin, Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assignment_invite_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assignment_invites.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class ConsentAcceptance(TimestampMixin, Base):
    __tablename__ = "consent_acceptances"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "session_id",
            "terms_version",
            name="uq_consent_acceptances_user_session_version",
        ),
        CheckConstraint(
            "source in ('authenticated', 'secure_invite', 'local_preview')",
            name="consent_acceptance_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Audit snapshots intentionally remain after a session or invite is revoked.
    session_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    assignment_invite_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    respondent_profile_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    terms_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )


class PasswordResetToken(TimestampMixin, Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssignmentInvite(TimestampMixin, Base):
    __tablename__ = "assignment_invites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    respondent_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(2048), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
