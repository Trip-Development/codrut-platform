from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    feedback: str | None = None


class ReportScoreScaleResponse(BaseModel):
    score_unit: str | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    score_scale_compatible: bool = True
    unavailable_reason: Literal["incompatible_score_scales"] | None = None


class ReportDistributionResponse(BaseModel):
    id: str
    label: str
    value: int = Field(ge=0)
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
    lencioni_scale: ReportScoreScaleResponse
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
    response_kind: str
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


class IcareTargetSummaryResponse(BaseModel):
    target_profile_id: UUID
    target_name: str
    external_response_count: int
    self_response_count: int
    external_averages: list[ReportAverageResponse]
    self_averages: list[ReportAverageResponse]
    cohorts: list["IcareCohortSummaryResponse"] = Field(default_factory=list)


class IcareCohortSummaryResponse(BaseModel):
    cohort: Literal["direct_team", "leadership_peers", "self"]
    response_count: int
    averages: list[ReportAverageResponse]
    score_unit: str | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    score_scale_compatible: bool = True
    unavailable_reason: Literal["incompatible_score_scales"] | None = None


class DriverRankSummaryResponse(BaseModel):
    total_people: int = Field(
        ge=0,
        description="Participants with at least two numeric driver scores.",
    )
    first_rank: list[ReportDistributionResponse]
    second_rank: list[ReportDistributionResponse]
    first_rank_tie_breaks: int = Field(ge=0)
    second_rank_tie_breaks: int = Field(ge=0)
    insufficient_driver_score_count: int = Field(
        ge=0,
        description=(
            "Selected completed participants omitted from both rankings because "
            "fewer than two driver scores were numeric."
        ),
    )

    @model_validator(mode="after")
    def validate_rank_totals(self) -> "DriverRankSummaryResponse":
        if sum(item.value for item in self.first_rank) != self.total_people:
            raise ValueError("First-rank driver counts must sum to total_people.")
        if sum(item.value for item in self.second_rank) != self.total_people:
            raise ValueError("Second-rank driver counts must sum to total_people.")
        if (
            self.first_rank_tie_breaks > self.total_people
            or self.second_rank_tie_breaks > self.total_people
        ):
            raise ValueError("Driver tie-break counts cannot exceed total_people.")
        return self


class LeadershipMemberSummaryResponse(BaseModel):
    participant_profile_id: UUID
    full_name: str
    position: str | None = None
    role_group: str | None = None


class LeadershipMemberReportResponse(BaseModel):
    project_id: UUID
    assessment_cycle_id: UUID | None = None
    member: LeadershipMemberSummaryResponse
    pcm_base: str | None = None
    pcm_phase: str | None = None
    lencioni_count: int
    lencioni_averages: list[ReportAverageResponse]
    lencioni_scale: ReportScoreScaleResponse
    icare_cohorts: list[IcareCohortSummaryResponse]
    driver_count: int
    driver_averages: list[ReportAverageResponse]
    driver_scale: ReportScoreScaleResponse


class CompanyReportAggregateResponse(BaseModel):
    project_id: UUID | None = None
    assessment_cycle_id: UUID | None = None
    total_assigned: int
    total_completed: int
    reportable_scored_count: int
    reportable_pending_score_count: int
    reportable_failed_score_count: int
    reportable_orphaned_score_count: int
    completion_rate: int
    lencioni_count: int
    driver_count: int
    boss_360_count: int
    pcm_base_count: int
    pcm_phase_count: int
    lencioni_averages: list[ReportAverageResponse]
    lencioni_scale: ReportScoreScaleResponse
    driver_averages: list[ReportAverageResponse]
    driver_scale: ReportScoreScaleResponse
    boss_360_averages: list[ReportAverageResponse]
    icare_target_summaries: list[IcareTargetSummaryResponse]
    icare_cohorts: list[IcareCohortSummaryResponse] = Field(default_factory=list)
    driver_rank_summary: DriverRankSummaryResponse
    leadership_members: list[LeadershipMemberSummaryResponse] = Field(default_factory=list)
    pcm_base_distribution: list[ReportDistributionResponse]
    pcm_phase_distribution: list[ReportDistributionResponse]
    team_lenses: list[ReportTeamLensResponse]
    hierarchy_ambiguous: bool = False
    hierarchy_ambiguity_message: str | None = None
    hierarchy_issues: list[ReportHierarchyIssueResponse]
    results: list[ScoringResultResponse]


class CycleQuestionnaireCompatibilityResponse(BaseModel):
    questionnaire_key: str
    baseline_definition_id: UUID | None
    comparison_definition_id: UUID | None
    compatible: bool


class CompanyReportComparisonResponse(BaseModel):
    baseline_cycle_id: UUID
    comparison_cycle_id: UUID
    definition_compatibility: list[CycleQuestionnaireCompatibilityResponse]
    baseline: CompanyReportAggregateResponse
    comparison: CompanyReportAggregateResponse
