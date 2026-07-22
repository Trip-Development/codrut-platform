import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from codrut.core.database import Base, TimestampMixin


class QuestionnaireKey(StrEnum):
    pcm_base = "pcm_base"
    phase = "phase"
    lencioni = "lencioni"
    lencioni_en = "lencioni_en"
    distress_drivers = "distress_drivers"
    distress_drivers_en = "distress_drivers_en"
    boss_360 = "boss_360"
    boss_360_en = "boss_360_en"
    icare = "icare"


class QuestionnaireResponseStatus(StrEnum):
    draft = "draft"
    submitted = "submitted"


class QuestionnaireDefinition(TimestampMixin, Base):
    __tablename__ = "questionnaire_definitions"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_questionnaire_definitions_key_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    private_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    feedback_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    trainer_visibility_policy: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    package_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    content_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    system_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProtectedContentImport(TimestampMixin, Base):
    __tablename__ = "protected_content_imports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    package_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    questionnaire_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    template_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


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
    questionnaire_key: Mapped[str] = mapped_column(String(120), nullable=False)
    questionnaire_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[QuestionnaireResponseStatus] = mapped_column(
        Enum(QuestionnaireResponseStatus),
        nullable=False,
        default=QuestionnaireResponseStatus.draft,
    )
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
