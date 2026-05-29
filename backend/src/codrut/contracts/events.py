from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class QuestionnaireSubmitted:
    participant_id: UUID
    questionnaire_assignment_id: UUID
    submitted_at: datetime


@dataclass(frozen=True)
class ResultCalculated:
    participant_id: UUID
    result_id: UUID
    calculated_at: datetime
