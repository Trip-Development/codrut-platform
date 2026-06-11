from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScoringResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    scores: dict
    primary_result: str | None


class ReportAverageResponse(BaseModel):
    id: str
    label: str
    avg: float


class CompanyReportAggregateResponse(BaseModel):
    total_assigned: int
    total_completed: int
    completion_rate: int
    lencioni_count: int
    driver_count: int
    boss_360_count: int
    lencioni_averages: list[ReportAverageResponse]
    driver_averages: list[ReportAverageResponse]
    boss_360_averages: list[ReportAverageResponse]
    results: list[ScoringResultResponse]
