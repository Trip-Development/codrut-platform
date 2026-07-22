import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from codrut.core.database import Base, TimestampMixin


class ScoringResult(TimestampMixin, Base):
    __tablename__ = "scoring_results"
    __table_args__ = (UniqueConstraint("assignment_id", name="uq_scoring_results_assignment_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questionnaire_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scores: Mapped[dict] = mapped_column(JSONB, nullable=False)
    primary_result: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ResultPublicationKind(StrEnum):
    individual = "individual"
    aggregate_360 = "aggregate_360"


class ResultPublication(TimestampMixin, Base):
    __tablename__ = "result_publications"
    __table_args__ = (
        UniqueConstraint("publication_key", name="uq_result_publications_publication_key"),
        CheckConstraint("source_count > 0", name="source_count_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    publication_key: Mapped[str] = mapped_column(String(255), nullable=False)
    participant_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participant_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignment_round_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    assessment_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessment_cycles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    questionnaire_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("questionnaire_definitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    questionnaire_key: Mapped[str] = mapped_column(String(120), nullable=False)
    source_assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("questionnaire_assignments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[ResultPublicationKind] = mapped_column(
        Enum(ResultPublicationKind),
        nullable=False,
    )
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
