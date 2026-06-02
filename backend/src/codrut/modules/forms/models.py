import uuid
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Enum, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from codrut.core.database import Base, TimestampMixin


class QuestionnaireKey(StrEnum):
    pcm_base = "pcm_base"
    phase = "phase"
    lencioni = "lencioni"
    distress_drivers = "distress_drivers"
    boss_360 = "boss_360"


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
