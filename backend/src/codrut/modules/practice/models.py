from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from codrut.core.database import Base, TimestampMixin, utcnow


class KnowledgePackState(StrEnum):
    draft = "draft"
    approved = "approved"
    frozen = "frozen"


class ScenarioState(StrEnum):
    draft = "draft"
    piloted = "piloted"
    validated = "validated"


class ProgramMode(StrEnum):
    training = "training"
    course = "course"


class SessionKind(StrEnum):
    roleplay = "roleplay"
    coaching = "coaching"
    knowledge = "knowledge"
    research = "research"


class SessionState(StrEnum):
    open = "open"
    closed = "closed"


class TurnRole(StrEnum):
    participant = "participant"
    actor = "actor"
    system = "system"


class OutcomeKind(StrEnum):
    good = "good"
    bad = "bad"
    turn_limit = "turn_limit"
    safety_stop = "safety_stop"


class CreatorNoteState(StrEnum):
    new = "new"
    accepted = "accepted"
    rejected = "rejected"
    applied = "applied"


class BudgetReservationState(StrEnum):
    reserved = "reserved"
    settled = "settled"
    released = "released"


class PracticeTheme(TimestampMixin, Base):
    __tablename__ = "practice_themes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PracticeCompetency(TimestampMixin, Base):
    __tablename__ = "practice_competencies"
    __table_args__ = (
        UniqueConstraint("theme_id", "slug", name="uq_practice_competencies_theme_id_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    theme_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_themes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    level_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    level_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    level_3: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PracticeKnowledgePack(TimestampMixin, Base):
    __tablename__ = "practice_knowledge_packs"
    __table_args__ = (
        UniqueConstraint(
            "theme_id",
            "version",
            name="uq_practice_knowledge_packs_theme_id_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    theme_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_themes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[KnowledgePackState] = mapped_column(
        Enum(KnowledgePackState),
        nullable=False,
        default=KnowledgePackState.draft,
    )
    checksum: Mapped[str] = mapped_column(String(255), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    content_uri: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class PracticeScenario(TimestampMixin, Base):
    __tablename__ = "practice_scenarios"
    __table_args__ = (
        UniqueConstraint(
            "theme_id",
            "slug",
            "version",
            name="uq_practice_scenarios_theme_slug_version",
        ),
        CheckConstraint(
            "difficulty >= 1 AND difficulty <= 5",
            name="ck_practice_scenarios_difficulty",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    theme_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_themes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[ScenarioState] = mapped_column(
        Enum(ScenarioState),
        nullable=False,
        default=ScenarioState.draft,
    )
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    shared_brief: Mapped[str] = mapped_column(Text, nullable=False)
    roles: Mapped[dict] = mapped_column(JSONB, nullable=False)
    exits: Mapped[dict] = mapped_column(JSONB, nullable=False)
    criteria: Mapped[dict] = mapped_column(JSONB, nullable=False)
    debrief_questions: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=20)


class PracticeProgramSettings(TimestampMixin, Base):
    __tablename__ = "practice_program_settings"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_practice_program_settings_project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("company_projects.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    mode: Mapped[ProgramMode] = mapped_column(
        Enum(ProgramMode),
        nullable=False,
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_themes.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    active_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_knowledge_packs.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_turns_per_session: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_sessions_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_chars_per_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=1200)
    turn_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    usd_cap_per_participant: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("3.00"),
    )


class PracticeSession(TimestampMixin, Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (
        Index(
            "ix_practice_sessions_participant_started",
            "participant_profile_id",
            text("started_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    program_settings_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_program_settings.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    participant_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pack_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_knowledge_packs.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_scenarios.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    kind: Mapped[SessionKind] = mapped_column(
        Enum(SessionKind),
        nullable=False,
    )
    state: Mapped[SessionState] = mapped_column(
        Enum(SessionState),
        nullable=False,
        default=SessionState.open,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)


class PracticeTurn(TimestampMixin, Base):
    __tablename__ = "practice_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "ordinal", name="uq_practice_turns_session_id_ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[TurnRole] = mapped_column(
        Enum(TurnRole),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thought_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )


class PracticeOutcome(TimestampMixin, Base):
    __tablename__ = "practice_outcomes"
    __table_args__ = (UniqueConstraint("session_id", name="uq_practice_outcomes_session_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    kind: Mapped[OutcomeKind] = mapped_column(
        Enum(OutcomeKind),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PracticeFeedback(TimestampMixin, Base):
    __tablename__ = "practice_feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    competency_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_competencies.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    criterion: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    quote_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )


class PracticeSessionSample(TimestampMixin, Base):
    __tablename__ = "practice_session_samples"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    real_weak: Mapped[str | None] = mapped_column(Text, nullable=True)
    real_improved: Mapped[str | None] = mapped_column(Text, nullable=True)
    invented_weak: Mapped[str | None] = mapped_column(Text, nullable=True)
    invented_improved: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )


class PracticeCreatorNote(TimestampMixin, Base):
    __tablename__ = "practice_creator_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[CreatorNoteState] = mapped_column(
        Enum(CreatorNoteState),
        nullable=False,
        default=CreatorNoteState.new,
    )
    applied_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_knowledge_packs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )


class PracticeBudgetReservation(TimestampMixin, Base):
    __tablename__ = "practice_budget_reservations"
    __table_args__ = (
        Index(
            "ix_practice_budget_reservations_program_state",
            "program_settings_id",
            "state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    program_settings_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_program_settings.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    actual_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    state: Mapped[BudgetReservationState] = mapped_column(
        Enum(BudgetReservationState),
        nullable=False,
        default=BudgetReservationState.reserved,
    )


class CompetencyScore(TimestampMixin, Base):
    __tablename__ = "competency_scores"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_competency_scores_score"),
        CheckConstraint("level >= 1 AND level <= 3", name="ck_competency_scores_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_projects.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    competency_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_competencies.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    competency_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="session")


class InsightMoment(TimestampMixin, Base):
    __tablename__ = "insight_moments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    competency_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_competencies.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    competency_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)


class SessionSample(TimestampMixin, Base):
    __tablename__ = "session_samples"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    competency_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_competencies.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    real_weak: Mapped[str | None] = mapped_column(Text, nullable=True)
    real_improved: Mapped[str | None] = mapped_column(Text, nullable=True)
    invented_weak: Mapped[str | None] = mapped_column(Text, nullable=True)
    invented_improved: Mapped[str | None] = mapped_column(Text, nullable=True)


class ParticipantMemory(TimestampMixin, Base):
    __tablename__ = "participant_memory"
    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 100",
            name="ck_participant_memory_relevance_score",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_projects.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_quotes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evolution_signals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    personal_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    relevant_competencies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)


class EvolutionLog(TimestampMixin, Base):
    __tablename__ = "evolution_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    qualitative_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProjectCompetency(TimestampMixin, Base):
    __tablename__ = "project_competencies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("company_projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CompetencyTemplate(TimestampMixin, Base):
    __tablename__ = "competencies_template"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    theme_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_themes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TrainerNote(TimestampMixin, Base):
    __tablename__ = "trainer_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trainer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_projects.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)

