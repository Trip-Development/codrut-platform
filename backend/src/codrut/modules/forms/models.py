import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from codrut.core.database import Base, TimestampMixin


class QuestionnaireKey(StrEnum):
    pcm_base = "pcm_base"
    phase = "phase"
    lencioni = "lencioni"
    distress_drivers = "distress_drivers"
    boss_360 = "boss_360"


class QuestionnaireResponseStatus(StrEnum):
    draft = "draft"
    submitted = "submitted"


class QuestionnaireDefinition(TimestampMixin, Base):
    __tablename__ = "questionnaire_definitions"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_questionnaire_definitions_key_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[QuestionnaireKey] = mapped_column(Enum(QuestionnaireKey), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    schema: Mapped[dict] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class QuestionnaireResponse(TimestampMixin, Base):
    __tablename__ = "questionnaire_responses"
    __table_args__ = (
        UniqueConstraint("assignment_id", name="uq_questionnaire_responses_assignment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("questionnaire_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    questionnaire_key: Mapped[QuestionnaireKey] = mapped_column(
        Enum(QuestionnaireKey),
        nullable=False,
    )
    questionnaire_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[QuestionnaireResponseStatus] = mapped_column(
        Enum(QuestionnaireResponseStatus),
        nullable=False,
        default=QuestionnaireResponseStatus.draft,
    )
    answers: Mapped[dict] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
