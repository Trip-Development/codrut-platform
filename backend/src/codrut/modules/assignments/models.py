import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from codrut.core.database import Base, TimestampMixin


class TeamType(StrEnum):
    leadership = "leadership"
    functional = "functional"


class TeamMembershipRole(StrEnum):
    leader = "leader"
    member = "member"


class AssignmentTargetType(StrEnum):
    self_assessment = "self"
    person = "person"
    team = "team"


class AssignmentAccessMode(StrEnum):
    account_link = "account_link"


class AssignmentStatus(StrEnum):
    assigned = "assigned"
    invited = "invited"
    started = "started"
    submitted = "submitted"
    validated = "validated"
    scored = "scored"


class ResponseVisibilityPolicy(StrEnum):
    trainer_raw_review = "trainer_raw_review"
    reviewed_anonymized = "reviewed_anonymized"


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("company_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[TeamType] = mapped_column(Enum(TeamType), nullable=False)


class TeamMembership(TimestampMixin, Base):
    __tablename__ = "team_memberships"
    __table_args__ = (
        UniqueConstraint("team_id", "participant_profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        index=True,
    )
    participant_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[TeamMembershipRole] = mapped_column(Enum(TeamMembershipRole), nullable=False)


class QuestionnaireAssignment(TimestampMixin, Base):
    __tablename__ = "questionnaire_assignments"
    __table_args__ = (
        CheckConstraint(
            """
            (
              target_type = 'self'
              and target_person_id is null
              and target_team_id is null
            )
            or (
              target_type = 'person'
              and target_person_id is not null
              and target_team_id is null
            )
            or (
              target_type = 'team'
              and target_team_id is not null
              and target_person_id is null
            )
            """,
            name="assignment_target_shape",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    respondent_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    questionnaire_key: Mapped[str] = mapped_column(String(120), nullable=False)
    target_type: Mapped[AssignmentTargetType] = mapped_column(
        Enum(AssignmentTargetType),
        nullable=False,
    )
    target_person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    target_team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    access_mode: Mapped[AssignmentAccessMode] = mapped_column(
        Enum(AssignmentAccessMode),
        nullable=False,
        default=AssignmentAccessMode.account_link,
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus),
        nullable=False,
        default=AssignmentStatus.assigned,
    )
    visibility_policy: Mapped[ResponseVisibilityPolicy] = mapped_column(
        Enum(ResponseVisibilityPolicy),
        nullable=False,
        default=ResponseVisibilityPolicy.trainer_raw_review,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
