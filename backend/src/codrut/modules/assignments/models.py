import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
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
    cancelled = "cancelled"


class AssessmentCycleStatus(StrEnum):
    draft = "draft"
    active = "active"
    closed = "closed"


class ResponseVisibilityPolicy(StrEnum):
    trainer_raw_review = "trainer_raw_review"
    reviewed_anonymized = "reviewed_anonymized"


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("company_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[TeamType] = mapped_column(Enum(TeamType), nullable=False)


class TeamMembership(TimestampMixin, Base):
    __tablename__ = "team_memberships"
    __table_args__ = (UniqueConstraint("team_id", "participant_profile_id"),)

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


class AssessmentCycle(TimestampMixin, Base):
    __tablename__ = "assessment_cycles"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence", name="uq_assessment_cycles_project_sequence"),
        Index(
            "uq_assessment_cycles_open_project",
            "project_id",
            unique=True,
            postgresql_where=text("status in ('draft', 'active')"),
        ),
        CheckConstraint("sequence > 0", name="ck_assessment_cycles_sequence_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("company_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[AssessmentCycleStatus] = mapped_column(
        Enum(AssessmentCycleStatus), nullable=False, default=AssessmentCycleStatus.draft
    )
    source_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessment_cycles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )


class AssessmentCycleQuestionnaire(TimestampMixin, Base):
    __tablename__ = "assessment_cycle_questionnaires"
    __table_args__ = (
        UniqueConstraint(
            "assessment_cycle_id",
            "questionnaire_key",
            name="uq_assessment_cycle_questionnaires_cycle_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_cycles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    questionnaire_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questionnaire_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    questionnaire_key: Mapped[str] = mapped_column(String(120), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AssessmentCycleTeamMembership(TimestampMixin, Base):
    __tablename__ = "assessment_cycle_team_memberships"
    __table_args__ = (
        UniqueConstraint(
            "assessment_cycle_id",
            "team_id",
            "participant_profile_id",
            name="uq_assessment_cycle_team_memberships_member",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_cycles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    participant_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
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
        CheckConstraint(
            "reminder_count >= 0 and reminder_count <= 2",
            name="reminder_count_bounds",
        ),
        Index(
            "uq_questionnaire_assignments_cycle_shape",
            "cycle_shape_guard",
            "respondent_profile_id",
            "questionnaire_key",
            "target_type",
            text("coalesce(target_person_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            text("coalesce(target_team_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            unique=True,
            postgresql_where=text("cycle_shape_guard is not null"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignment_round_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        index=True,
    )
    assessment_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessment_cycles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cycle_shape_guard: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessment_cycles.id", ondelete="SET NULL"), nullable=True
    )
    respondent_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    questionnaire_key: Mapped[str] = mapped_column(String(120), nullable=False)
    questionnaire_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questionnaire_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[AssignmentTargetType] = mapped_column(
        Enum(
            AssignmentTargetType,
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
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
    reminder_count: Mapped[int] = mapped_column(nullable=False, default=0)
