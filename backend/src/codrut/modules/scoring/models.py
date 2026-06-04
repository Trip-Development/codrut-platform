import uuid

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
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
    scores: Mapped[dict] = mapped_column(JSON, nullable=False)
    primary_result: Mapped[str | None] = mapped_column(String(255), nullable=True)
