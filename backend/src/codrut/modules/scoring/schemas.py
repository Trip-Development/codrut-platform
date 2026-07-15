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
    interpretation: str | None = None
    range_label: str | None = None


class ReportDistributionResponse(BaseModel):
    id: str
    label: str
    value: int
    color: str | None = None


class ReportTeamLensResponse(BaseModel):
    id: str
    name: str
    member_count: int
    assigned_count: int
    completed_count: int
    completion_rate: int
    lencioni_count: int
    driver_count: int
    boss_360_count: int
    pcm_base_count: int
    pcm_phase_count: int
    lencioni_averages: list[ReportAverageResponse]
    driver_averages: list[ReportAverageResponse]
    boss_360_averages: list[ReportAverageResponse]
    pcm_base_distribution: list[ReportDistributionResponse]
    pcm_phase_distribution: list[ReportDistributionResponse]


class ReportHierarchyIssueResponse(BaseModel):
    code: str
    participant_id: UUID | None = None
    participant_name: str | None = None
    reports_to_name: str | None = None
    message: str


class IcareAnswerReviewRowResponse(BaseModel):
    assignment_id: UUID
    response_id: UUID
    submitted_at: str | None = None
    respondent_profile_id: UUID
    respondent_name: str
    respondent_email: str | None = None
    target_profile_id: UUID | None = None
    target_name: str | None = None
    target_type: str
    section_id: str
    section_label: str
    measurement_id: str
    measurement_label: str
    statement_id: str
    statement_label: str
    answer_value: int | str
    answer_label: str
    answer_description: str | None = None


class IcareAnswerReviewResponse(BaseModel):
    rows: list[IcareAnswerReviewRowResponse]
    row_count: int


class CompanyReportAggregateResponse(BaseModel):
    total_assigned: int
    total_completed: int
    completion_rate: int
    lencioni_count: int
    driver_count: int
    boss_360_count: int
    pcm_base_count: int
    pcm_phase_count: int
    lencioni_averages: list[ReportAverageResponse]
    driver_averages: list[ReportAverageResponse]
    boss_360_averages: list[ReportAverageResponse]
    pcm_base_distribution: list[ReportDistributionResponse]
    pcm_phase_distribution: list[ReportDistributionResponse]
    team_lenses: list[ReportTeamLensResponse]
    hierarchy_ambiguous: bool = False
    hierarchy_ambiguity_message: str | None = None
    hierarchy_issues: list[ReportHierarchyIssueResponse]
    results: list[ScoringResultResponse]
