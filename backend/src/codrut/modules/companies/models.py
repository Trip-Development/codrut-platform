from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from codrut.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from codrut.modules.identity.models import User


class CompanyMembershipRole(StrEnum):
    owner = "owner"
    trainer = "trainer"
    participant = "participant"


class CompanyProjectStatus(StrEnum):
    draft = "draft"
    active = "active"
    completed = "completed"
    archived = "archived"


class ProjectLifecycleAction(StrEnum):
    archived = "archived"
    restored = "restored"
    permanently_deleted = "permanently_deleted"


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    memberships: Mapped[list[CompanyMembership]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    participants: Mapped[list[ParticipantProfile]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    reporting_relationships: Mapped[list[ParticipantReportingRelationship]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    access_codes: Mapped[list[CompanyAccessCode]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list[CompanyProject]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    project_memberships: Mapped[list[ProjectMembership]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        overlaps="participant,project_memberships",
    )


class CompanyProject(TimestampMixin, Base):
    __tablename__ = "company_projects"
    __table_args__ = (UniqueConstraint("company_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[CompanyProjectStatus] = mapped_column(
        Enum(CompanyProjectStatus),
        nullable=False,
        default=CompanyProjectStatus.draft,
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    form_opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    form_closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    archived_from_status: Mapped[CompanyProjectStatus | None] = mapped_column(
        Enum(CompanyProjectStatus),
        nullable=True,
    )
    leadership_invitation_template_key: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    member_invitation_template_key: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    leadership_reminder_template_key: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    member_reminder_template_key: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    company: Mapped[Company] = relationship(back_populates="projects")
    memberships: Mapped[list[ProjectMembership]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectLifecycleEvent(Base):
    __tablename__ = "project_lifecycle_events"
    __table_args__ = (
        CheckConstraint(
            "action in ('archived', 'restored', 'permanently_deleted')",
            name="project_lifecycle_event_action",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # This is intentionally not a foreign key so the audit survives a permanent deletion.
    project_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    next_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CompanyMembership(TimestampMixin, Base):
    __tablename__ = "company_memberships"
    __table_args__ = (UniqueConstraint("company_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[CompanyMembershipRole] = mapped_column(
        Enum(CompanyMembershipRole),
        nullable=False,
        default=CompanyMembershipRole.participant,
    )

    company: Mapped[Company] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="company_memberships")


class ParticipantProfile(TimestampMixin, Base):
    __tablename__ = "participant_profiles"
    __table_args__ = (
        UniqueConstraint("company_id", "email"),
        UniqueConstraint(
            "anonymous_name",
            name="uq_participant_profiles_anonymous_name",
        ),
        UniqueConstraint(
            "company_id",
            "id",
            name="uq_participant_profiles_company_id_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reports_to_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pcm_profile: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pcm_base: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pcm_phase: Mapped[str | None] = mapped_column(String(80), nullable=True)
    anonymous_name: Mapped[str | None] = mapped_column(String(80), nullable=True)

    company: Mapped[Company] = relationship(back_populates="participants")
    user: Mapped[User | None] = relationship(
        back_populates="participant_profiles",
        lazy="selectin",
    )
    direct_reports: Mapped[list[ParticipantReportingRelationship]] = relationship(
        back_populates="manager",
        cascade="all, delete-orphan",
        foreign_keys="ParticipantReportingRelationship.manager_profile_id",
    )
    manager_relationship: Mapped[ParticipantReportingRelationship | None] = relationship(
        back_populates="participant",
        cascade="all, delete-orphan",
        foreign_keys="ParticipantReportingRelationship.participant_profile_id",
        uselist=False,
    )
    project_memberships: Mapped[list[ProjectMembership]] = relationship(
        back_populates="participant",
        cascade="all, delete-orphan",
        overlaps="company,project_memberships",
    )

    @property
    def is_shadow_account(self) -> bool:
        return bool(self.user is not None and not self.user.is_registered)

    @property
    def account_type(self) -> str | None:
        if self.user is None:
            return None
        return "registered" if self.user.is_registered else "guest"

    @property
    def avatar_palette_key(self) -> int | None:
        if self.user is None:
            return None
        return self.user.avatar_palette_key


class ParticipantAccountLinkAudit(Base):
    __tablename__ = "participant_account_link_audits"
    __table_args__ = (
        CheckConstraint(
            "action in ('link_matching_email', 'unlink', 'invite_claim', 'registration_claim')",
            name="participant_account_link_audit_action",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    previous_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    previous_user_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    new_user_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    new_user_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ProjectMembership(TimestampMixin, Base):
    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("project_id", "participant_profile_id"),
        ForeignKeyConstraint(
            ["company_id", "participant_profile_id"],
            ["participant_profiles.company_id", "participant_profiles.id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("company_projects.id", ondelete="CASCADE"),
        index=True,
    )
    participant_profile_id: Mapped[uuid.UUID] = mapped_column(index=True)
    reports_to_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped[Company] = relationship(
        back_populates="project_memberships",
        overlaps="participant,project_memberships",
    )
    project: Mapped[CompanyProject] = relationship(back_populates="memberships")
    participant: Mapped[ParticipantProfile] = relationship(
        back_populates="project_memberships",
        overlaps="company,project_memberships",
    )


class ParticipantReportingRelationship(TimestampMixin, Base):
    __tablename__ = "participant_reporting_relationships"
    __table_args__ = (
        UniqueConstraint("participant_profile_id"),
        ForeignKeyConstraint(
            ["company_id", "participant_profile_id"],
            ["participant_profiles.company_id", "participant_profiles.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["company_id", "manager_profile_id"],
            ["participant_profiles.company_id", "participant_profiles.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "participant_profile_id <> manager_profile_id",
            name="participant_reporting_not_self",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    participant_profile_id: Mapped[uuid.UUID] = mapped_column(
        index=True,
    )
    manager_profile_id: Mapped[uuid.UUID] = mapped_column(
        index=True,
    )

    company: Mapped[Company] = relationship(back_populates="reporting_relationships")
    participant: Mapped[ParticipantProfile] = relationship(
        back_populates="manager_relationship",
        foreign_keys=[participant_profile_id],
    )
    manager: Mapped[ParticipantProfile] = relationship(
        back_populates="direct_reports",
        foreign_keys=[manager_profile_id],
    )


class CompanyAccessCode(TimestampMixin, Base):
    __tablename__ = "company_access_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    company: Mapped[Company] = relationship(back_populates="access_codes")


class ParticipantViewAudit(Base):
    __tablename__ = "participant_view_audits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trainer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trainer_email: Mapped[str] = mapped_column(String(320), nullable=False)
    participant_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    screen: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
