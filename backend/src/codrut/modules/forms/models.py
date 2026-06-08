import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from codrut.core.database import Base, TimestampMixin


class QuestionnaireKeyMeta(type):
    def __iter__(cls):
        for attr in ["pcm_base", "phase", "lencioni", "distress_drivers", "boss_360", "icare"]:
            yield cls(attr)

    def __getattribute__(cls, name):
        val = super().__getattribute__(name)
        if isinstance(val, str) and not name.startswith("_"):
            return cls(val)
        return val


class QuestionnaireKey(str, metaclass=QuestionnaireKeyMeta):
    pcm_base = "pcm_base"
    phase = "phase"
    lencioni = "lencioni"
    distress_drivers = "distress_drivers"
    boss_360 = "boss_360"
    icare = "icare"

    @property
    def value(self) -> str:
        return self

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.str_schema()


class QuestionnaireResponseStatus(StrEnum):
    draft = "draft"
    submitted = "submitted"


class QuestionnaireDefinition(TimestampMixin, Base):
    __tablename__ = "questionnaire_definitions"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_questionnaire_definitions_key_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[QuestionnaireKey] = mapped_column(String(50), nullable=False)
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
        String(50),
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
