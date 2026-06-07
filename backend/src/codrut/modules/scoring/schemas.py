from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScoringResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    scores: dict
    primary_result: str | None
