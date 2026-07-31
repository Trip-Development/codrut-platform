from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleQuestionnaire,
    AssessmentCycleStatus,
    AssessmentCycleTeamMembership,
    AssignmentStatus,
    QuestionnaireAssignment,
    Team,
    TeamMembership,
    TeamMembershipRole,
    TeamType,
)
from codrut.modules.assignments.team_snapshot import (
    AssessmentCycleTeamSnapshot,
    load_assessment_cycle_team_snapshot,
)
from codrut.modules.companies.hierarchy import (
    HierarchyIssue,
    HierarchyParticipant,
    build_organization_hierarchy,
)
from codrut.modules.companies.manager_matching import (
    clean_manager_reference,
    normalize_manager_token,
)
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireKey,
    QuestionnaireResponse,
    SubmissionProcessingJob,
    SubmissionProcessingStatus,
)
from codrut.modules.scoring.models import ScoringResult
from codrut.modules.scoring.repository import ScoringRepository
from codrut.modules.scoring.scale import ScoreScale, derive_definition_score_scale
from codrut.modules.scoring.schemas import (
    CompanyReportAggregateResponse,
    CompanyReportComparisonResponse,
    CycleQuestionnaireCompatibilityResponse,
    DriverRankSummaryResponse,
    IcareAnswerReviewResponse,
    IcareAnswerReviewRowResponse,
    IcareCohortSummaryResponse,
    IcareTargetSummaryResponse,
    LeadershipMemberReportResponse,
    LeadershipMemberSummaryResponse,
    ReportAverageResponse,
    ReportDistributionResponse,
    ReportHierarchyIssueResponse,
    ReportScoreScaleResponse,
    ReportTeamLensResponse,
    ScoringResultResponse,
)

COMPLETED_STATUSES = {
    AssignmentStatus.submitted,
    AssignmentStatus.validated,
    AssignmentStatus.scored,
}

LENCIONI_REPORT_KEYS = {
    QuestionnaireKey.lencioni.value,
    QuestionnaireKey.lencioni_en.value,
}

DISTRESS_DRIVER_REPORT_KEYS = {
    QuestionnaireKey.distress_drivers.value,
    QuestionnaireKey.distress_drivers_en.value,
}

BOSS_360_REPORT_KEYS = {
    QuestionnaireKey.boss_360.value,
    QuestionnaireKey.boss_360_en.value,
    QuestionnaireKey.icare.value,
}

PCM_REPORT_KEYS = {
    QuestionnaireKey.pcm_base.value,
    QuestionnaireKey.phase.value,
    "pcm_phase",
}

PCM_PROFILES = {
    "harmonizer": ("Armonizator", "#f97316"),
    "thinker": ("Gânditor", "#2563eb"),
    "persister": ("Perseverent", "#7c3aed"),
    "imaginer": ("Imaginator", "#fb923c"),
    "rebel": ("Rebel", "#eab308"),
    "promoter": ("Promotor", "#dc2626"),
}

PCM_ALIASES = {
    "armonizator": "harmonizer",
    "harmonizer": "harmonizer",
    "ganditor": "thinker",
    "thinker": "thinker",
    "perseverent": "persister",
    "persister": "persister",
    "imaginator": "imaginer",
    "imaginer": "imaginer",
    "rebel": "rebel",
    "promotor": "promoter",
    "promoter": "promoter",
}


@dataclass(frozen=True)
class ReportParticipant:
    id: UUID
    full_name: str
    reports_to_name: str | None
    role_group: str | None
    pcm_base: str | None
    pcm_phase: str | None
    user_id: UUID | None
    position: str | None = None


@dataclass(frozen=True)
class ScoreSummary:
    lencioni_count: int
    driver_count: int
    boss_360_count: int
    lencioni_averages: list[ReportAverageResponse]
    lencioni_scale: ReportScoreScaleResponse
    driver_averages: list[ReportAverageResponse]
    driver_scale: ReportScoreScaleResponse
    boss_360_averages: list[ReportAverageResponse]


@dataclass(frozen=True)
class TeamLensBuildResult:
    team_lenses: list[ReportTeamLensResponse]
    hierarchy_ambiguous: bool
    hierarchy_ambiguity_message: str | None
    hierarchy_issues: list[ReportHierarchyIssueResponse]


@dataclass(frozen=True)
class MemberLencioniTeamResolution:
    team_id: UUID | None
    ambiguous: bool = False
    ambiguity_message: str | None = None


AssignmentResultWithDefinition = tuple[
    QuestionnaireAssignment,
    ScoringResult | None,
    QuestionnaireDefinition | None,
]


@dataclass(frozen=True)
class DriverRowSelection:
    average_rows: tuple[AssignmentResultWithDefinition, ...]
    rankable_rows: tuple[AssignmentResultWithDefinition, ...]
    insufficient_driver_score_count: int


@dataclass(frozen=True)
class ReportableScoreAvailability:
    scored: int = 0
    pending: int = 0
    failed: int = 0
    orphaned: int = 0


@dataclass
class ReportDimensionAccumulator:
    label: str
    total: float = 0
    count: int = 0
    interpretation_rules: tuple[dict[str, Any], ...] = ()


class ScoringService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ScoringRepository(session)
        self.company_repository = CompanyRepository(session)

    async def get_result_by_assignment(self, assignment_id: UUID) -> ScoringResult | None:
        return await self.repository.get_by_assignment(assignment_id)

    async def get_company_report_aggregate(
        self,
        company_id: UUID,
        project_id: UUID | None = None,
        assessment_cycle_id: UUID | None = None,
    ) -> CompanyReportAggregateResponse:
        company = await self.company_repository.get_company(company_id)
        if company is None:
            raise DomainError("Company not found.", code="company_not_found")
        if project_id is not None:
            project = await self.company_repository.get_project(company_id, project_id)
            if project is None:
                raise DomainError("Project not found in this company.", code="project_not_found")
        project_id, assessment_cycle_id = await self._resolve_report_scope(
            company_id,
            project_id,
            assessment_cycle_id,
        )

        assignment_results = await self.repository.list_company_assignment_results_with_definitions(
            company_id,
            project_id,
            assessment_cycle_id,
        )
        participants = await self._list_report_participants(
            company_id,
            project_id,
            assessment_cycle_id,
            assignment_results,
        )
        pcm_values = (
            _pcm_values_from_responses(
                await self.repository.list_company_pcm_responses(
                    company_id,
                    project_id,
                    assessment_cycle_id,
                )
            )
            if assessment_cycle_id is not None
            else None
        )
        assignments = [assignment for assignment, _result, _definition in assignment_results]
        total_assigned = len(assignment_results)
        total_completed = sum(
            1
            for assignment, _result, _definition in assignment_results
            if assignment.status in COMPLETED_STATUSES
        )
        results: list[ScoringResultResponse] = []

        for assignment, result, _definition in assignment_results:
            if assignment.status not in COMPLETED_STATUSES or result is None:
                continue

            results.append(ScoringResultResponse.model_validate(result))
        missing_reportable_assignment_ids = {
            assignment.id
            for assignment, result, _definition in assignment_results
            if assignment.questionnaire_key
            in (LENCIONI_REPORT_KEYS | DISTRESS_DRIVER_REPORT_KEYS | BOSS_360_REPORT_KEYS)
            and assignment.status in COMPLETED_STATUSES
            and result is None
        }
        processing_jobs = (
            list(
                (
                    await self.session.execute(
                        select(SubmissionProcessingJob).where(
                            SubmissionProcessingJob.assignment_id.in_(
                                missing_reportable_assignment_ids
                            )
                        )
                    )
                ).scalars()
            )
            if missing_reportable_assignment_ids
            else []
        )
        score_availability = _reportable_score_availability(
            assignment_results,
            processing_jobs,
        )
        driver_selection = _select_latest_completed_driver_rows(assignment_results)
        score_summary = _build_score_summary(
            assignment_results,
            driver_rows=driver_selection.average_rows,
        )
        team_snapshot = (
            await load_assessment_cycle_team_snapshot(self.session, assessment_cycle_id)
            if assessment_cycle_id is not None
            else None
        )
        if team_snapshot is not None:
            team_snapshot = _with_persisted_icare_cohorts(
                team_snapshot,
                assignment_results,
            )
        icare_cohorts = _build_icare_cohort_summaries(
            assignment_results,
            participants,
            team_snapshot=team_snapshot,
        )
        icare_unclassified_response_count = _icare_unclassified_response_count(
            assignment_results,
            participants,
        )
        icare_target_summaries = _build_icare_target_summaries(
            assignment_results,
            participants,
            team_snapshot=team_snapshot,
        )
        driver_rank_summary = _build_driver_rank_summary(
            driver_selection.rankable_rows,
            insufficient_driver_score_count=(driver_selection.insufficient_driver_score_count),
        )
        pcm_base_distribution = _distribution_from_completed_pcm_assignments(
            participants,
            assignments,
            "pcm_base",
            pcm_values,
        )
        pcm_phase_distribution = _distribution_from_completed_pcm_assignments(
            participants,
            assignments,
            "pcm_phase",
            pcm_values,
        )
        team_lens_result = _build_team_lenses(
            participants,
            assignment_results,
            pcm_values,
            team_snapshot=team_snapshot,
        )

        return CompanyReportAggregateResponse(
            project_id=project_id,
            assessment_cycle_id=assessment_cycle_id,
            total_assigned=total_assigned,
            total_completed=total_completed,
            reportable_scored_count=score_availability.scored,
            reportable_pending_score_count=score_availability.pending,
            reportable_failed_score_count=score_availability.failed,
            reportable_orphaned_score_count=score_availability.orphaned,
            completion_rate=round((total_completed / total_assigned) * 100)
            if total_assigned > 0
            else 0,
            lencioni_count=score_summary.lencioni_count,
            driver_count=score_summary.driver_count,
            boss_360_count=score_summary.boss_360_count,
            pcm_base_count=_distribution_count(pcm_base_distribution),
            pcm_phase_count=_distribution_count(pcm_phase_distribution),
            lencioni_averages=score_summary.lencioni_averages,
            lencioni_scale=score_summary.lencioni_scale,
            driver_averages=score_summary.driver_averages,
            driver_scale=score_summary.driver_scale,
            boss_360_averages=score_summary.boss_360_averages,
            icare_target_summaries=icare_target_summaries,
            icare_cohorts=icare_cohorts,
            icare_unclassified_response_count=icare_unclassified_response_count,
            icare_unclassified_reason=(
                "historical_cohort_unavailable"
                if icare_unclassified_response_count
                else None
            ),
            driver_rank_summary=driver_rank_summary,
            leadership_members=_build_leadership_members(
                participants,
                leadership_ids=(
                    set(team_snapshot.leadership_ids) if team_snapshot is not None else None
                ),
            ),
            pcm_base_distribution=pcm_base_distribution,
            pcm_phase_distribution=pcm_phase_distribution,
            team_lenses=team_lens_result.team_lenses,
            hierarchy_ambiguous=team_lens_result.hierarchy_ambiguous,
            hierarchy_ambiguity_message=team_lens_result.hierarchy_ambiguity_message,
            hierarchy_issues=team_lens_result.hierarchy_issues,
            results=results,
        )

    async def get_leadership_member_report(
        self,
        company_id: UUID,
        project_id: UUID,
        participant_profile_id: UUID,
        assessment_cycle_id: UUID | None = None,
    ) -> LeadershipMemberReportResponse:
        company = await self.company_repository.get_company(company_id)
        if company is None:
            raise DomainError("Company not found.", code="company_not_found")
        project = await self.company_repository.get_project(company_id, project_id)
        if project is None:
            raise DomainError("Project not found in this company.", code="project_not_found")
        project_id, assessment_cycle_id = await self._resolve_report_scope(
            company_id,
            project_id,
            assessment_cycle_id,
        )
        assert project_id is not None
        assignment_results = await self.repository.list_company_assignment_results_with_definitions(
            company_id,
            project_id,
            assessment_cycle_id,
        )
        participants = await self._list_report_participants(
            company_id,
            project_id,
            assessment_cycle_id,
            assignment_results,
        )
        participant_by_id = {participant.id: participant for participant in participants}
        hierarchy = build_organization_hierarchy(
            [_hierarchy_participant_from_report(participant) for participant in participants]
        )
        team_snapshot = (
            await load_assessment_cycle_team_snapshot(self.session, assessment_cycle_id)
            if assessment_cycle_id is not None
            else None
        )
        if team_snapshot is not None:
            team_snapshot = _with_persisted_icare_cohorts(
                team_snapshot,
                assignment_results,
            )
        member = participant_by_id.get(participant_profile_id)
        leadership_ids = (
            set(team_snapshot.leadership_ids)
            if team_snapshot is not None
            else _leadership_ids_for_report(hierarchy, participants)
        )
        if member is None or participant_profile_id not in leadership_ids:
            raise DomainError(
                "Leadership member not found in this project.",
                code="leadership_member_not_found",
            )

        pcm_values = (
            _pcm_values_from_responses(
                await self.repository.list_company_pcm_responses(
                    company_id,
                    project_id,
                    assessment_cycle_id,
                )
            )
            if assessment_cycle_id is not None
            else {}
        )
        member_results = [
            row
            for row in assignment_results
            if row[0].respondent_profile_id == participant_profile_id
        ]
        lencioni_team = await self._resolve_member_lencioni_team(
            participant_profile_id,
            assessment_cycle_id,
            assignment_results,
            prefer_leadership=(
                assessment_cycle_id is None
                and participant_profile_id in hierarchy.top_level_ids
            ),
        )
        lencioni_summary = _leadership_member_lencioni_summary(
            assignment_results,
            target_team_id=lencioni_team.team_id,
        )
        target_summary = next(
            (
                summary
                for summary in _build_icare_target_summaries(
                    assignment_results,
                    participants,
                    team_snapshot=team_snapshot,
                )
                if summary.target_profile_id == participant_profile_id
            ),
            None,
        )
        driver_summary = _build_score_summary(member_results)
        driver_feedback = _driver_feedback_by_dimension(member_results)
        cycle_pcm = pcm_values.get(participant_profile_id, {})

        return LeadershipMemberReportResponse(
            project_id=project_id,
            assessment_cycle_id=assessment_cycle_id,
            member=LeadershipMemberSummaryResponse(
                participant_profile_id=member.id,
                full_name=member.full_name,
                position=member.position,
                role_group=member.role_group,
            ),
            pcm_base=cycle_pcm.get("pcm_base", member.pcm_base),
            pcm_phase=cycle_pcm.get("pcm_phase", member.pcm_phase),
            lencioni_count=lencioni_summary.lencioni_count,
            lencioni_averages=lencioni_summary.lencioni_averages,
            lencioni_scale=lencioni_summary.lencioni_scale,
            lencioni_team_ambiguous=lencioni_team.ambiguous,
            lencioni_team_ambiguity_message=lencioni_team.ambiguity_message,
            icare_cohorts=target_summary.cohorts if target_summary is not None else [],
            icare_unclassified_response_count=(
                target_summary.unclassified_response_count if target_summary is not None else 0
            ),
            icare_unclassified_reason=(
                target_summary.unclassified_reason if target_summary is not None else None
            ),
            driver_count=driver_summary.driver_count,
            driver_averages=[
                average.model_copy(update={"feedback": driver_feedback.get(average.id)})
                for average in driver_summary.driver_averages
            ],
            driver_scale=driver_summary.driver_scale,
        )

    async def _resolve_member_lencioni_team_id(
        self,
        member_id: UUID,
        assessment_cycle_id: UUID | None,
        assignment_results: Iterable[AssignmentResultWithDefinition],
        *,
        prefer_leadership: bool,
    ) -> UUID | None:
        return (
            await self._resolve_member_lencioni_team(
                member_id,
                assessment_cycle_id,
                assignment_results,
                prefer_leadership=prefer_leadership,
            )
        ).team_id

    async def _resolve_member_lencioni_team(
        self,
        member_id: UUID,
        assessment_cycle_id: UUID | None,
        assignment_results: Iterable[AssignmentResultWithDefinition],
        *,
        prefer_leadership: bool,
    ) -> MemberLencioniTeamResolution:
        assignment_result_rows = list(assignment_results)
        if assessment_cycle_id is not None:
            rows = (
                await self.session.execute(
                    select(
                        AssessmentCycleTeamMembership.team_id,
                        Team.type,
                        AssessmentCycleTeamMembership.role,
                    )
                    .join(Team, Team.id == AssessmentCycleTeamMembership.team_id)
                    .where(
                        AssessmentCycleTeamMembership.assessment_cycle_id == assessment_cycle_id,
                        AssessmentCycleTeamMembership.participant_profile_id == member_id,
                    )
                )
            ).all()
        else:
            rows = (
                await self.session.execute(
                    select(TeamMembership.team_id, Team.type, TeamMembership.role)
                    .join(Team, Team.id == TeamMembership.team_id)
                    .where(TeamMembership.participant_profile_id == member_id)
                )
            ).all()

        leadership_ids = sorted(
            team_id for team_id, team_type, _role in rows if team_type == TeamType.leadership
        )
        leadership_leader_ids = sorted(
            team_id
            for team_id, team_type, role in rows
            if team_type == TeamType.leadership and role == TeamMembershipRole.leader
        )
        functional_leader_ids = sorted(
            team_id
            for team_id, team_type, role in rows
            if team_type == TeamType.functional and role == TeamMembershipRole.leader
        )
        if assessment_cycle_id is not None and len(leadership_leader_ids) == 1:
            return MemberLencioniTeamResolution(leadership_leader_ids[0])
        if assessment_cycle_id is not None and len(leadership_leader_ids) > 1:
            return MemberLencioniTeamResolution(
                team_id=None,
                ambiguous=True,
                ambiguity_message=(
                    "Ciclul istoric conține mai mulți lideri pentru echipa de leadership."
                ),
            )
        if assessment_cycle_id is None and prefer_leadership and leadership_ids:
            return MemberLencioniTeamResolution(leadership_ids[0])
        if assessment_cycle_id is not None and leadership_ids and functional_leader_ids:
            leadership_snapshot_leaders = (
                await self.session.execute(
                    select(
                        AssessmentCycleTeamMembership.team_id,
                        AssessmentCycleTeamMembership.participant_profile_id,
                    )
                    .join(Team, Team.id == AssessmentCycleTeamMembership.team_id)
                    .where(
                        AssessmentCycleTeamMembership.assessment_cycle_id
                        == assessment_cycle_id,
                        AssessmentCycleTeamMembership.team_id.in_(leadership_ids),
                        Team.type == TeamType.leadership,
                        AssessmentCycleTeamMembership.role == TeamMembershipRole.leader,
                    )
                )
            ).all()
            if leadership_snapshot_leaders:
                if len(leadership_snapshot_leaders) == 1 and len(functional_leader_ids) == 1:
                    return MemberLencioniTeamResolution(functional_leader_ids[0])
                return MemberLencioniTeamResolution(
                    team_id=None,
                    ambiguous=True,
                    ambiguity_message=(
                        "Ciclul conține mai multe roluri de lider și nu putem stabili "
                        "sigur echipa Lencioni."
                    ),
                )

            # Older cycle snapshots did not record the top leader. Current hierarchy
            # is intentionally not consulted: only scored targets already scoped to
            # this cycle can resolve a single unambiguous historical team.
            candidate_ids = set(leadership_ids) | set(functional_leader_ids)
            result_target_ids = {
                assignment.target_team_id
                for assignment, result, _definition in assignment_result_rows
                if assignment.questionnaire_key in LENCIONI_REPORT_KEYS
                and assignment.status in COMPLETED_STATUSES
                and result is not None
                and assignment.target_team_id in candidate_ids
            }
            if len(result_target_ids) == 1:
                return MemberLencioniTeamResolution(next(iter(result_target_ids)))
            return MemberLencioniTeamResolution(
                team_id=None,
                ambiguous=True,
                ambiguity_message=(
                    "Nu putem stabili sigur dacă rezultatul istoric Lencioni aparține "
                    "echipei de leadership sau echipei funcționale."
                ),
            )
        if functional_leader_ids:
            return MemberLencioniTeamResolution(functional_leader_ids[0])
        if leadership_ids:
            return MemberLencioniTeamResolution(leadership_ids[0])

        # Legacy projects may predate team snapshots. This fallback is intentionally
        # restricted to a team the member personally evaluated in the already scoped
        # assignment set, so it cannot pull rows from another project or cycle.
        fallback_team_id = min(
            (
                assignment.target_team_id
                for assignment, result, _definition in assignment_result_rows
                if assignment.questionnaire_key in LENCIONI_REPORT_KEYS
                and assignment.respondent_profile_id == member_id
                and result is not None
                and assignment.target_team_id is not None
            ),
            default=None,
        )
        return MemberLencioniTeamResolution(fallback_team_id)

    async def get_icare_answer_review(
        self,
        company_id: UUID,
        project_id: UUID | None = None,
        assessment_cycle_id: UUID | None = None,
    ) -> IcareAnswerReviewResponse:
        company = await self.company_repository.get_company(company_id)
        if company is None:
            raise DomainError("Company not found.", code="company_not_found")
        if project_id is not None:
            project = await self.company_repository.get_project(company_id, project_id)
            if project is None:
                raise DomainError("Project not found in this company.", code="project_not_found")
        project_id, assessment_cycle_id = await self._resolve_report_scope(
            company_id,
            project_id,
            assessment_cycle_id,
        )

        rows: list[IcareAnswerReviewRowResponse] = []
        answer_responses = await self.repository.list_company_icare_answer_responses(
            company_id,
            project_id,
            assessment_cycle_id,
        )

        for assignment, response, respondent, target, definition in answer_responses:
            schema = definition.schema
            if definition.private_config:
                schema = definition.private_config.get("schema", schema)

            rows.extend(
                _icare_answer_review_rows(
                    assignment=assignment,
                    response=response,
                    respondent=respondent,
                    target=target,
                    schema=schema,
                )
            )

        return IcareAnswerReviewResponse(rows=rows, row_count=len(rows))

    async def get_company_report_comparison(
        self,
        company_id: UUID,
        project_id: UUID,
        baseline_cycle_id: UUID,
        comparison_cycle_id: UUID,
    ) -> CompanyReportComparisonResponse:
        if baseline_cycle_id == comparison_cycle_id:
            raise DomainError(
                "Select two different assessment cycles.",
                code="comparison_cycles_must_differ",
            )
        compatibility = await self._get_cycle_definition_compatibility(
            baseline_cycle_id,
            comparison_cycle_id,
        )
        incompatible_questionnaire_keys = {
            item.questionnaire_key for item in compatibility if not item.compatible
        }
        baseline = await self.get_company_report_aggregate(
            company_id,
            project_id,
            baseline_cycle_id,
        )
        comparison = await self.get_company_report_aggregate(
            company_id,
            project_id,
            comparison_cycle_id,
        )
        return CompanyReportComparisonResponse(
            baseline_cycle_id=baseline_cycle_id,
            comparison_cycle_id=comparison_cycle_id,
            definition_compatibility=compatibility,
            baseline=_without_incompatible_overlay_dimensions(
                baseline,
                incompatible_questionnaire_keys,
            ),
            comparison=comparison,
        )

    async def _resolve_report_scope(
        self,
        company_id: UUID,
        project_id: UUID | None,
        assessment_cycle_id: UUID | None,
    ) -> tuple[UUID | None, UUID | None]:
        if assessment_cycle_id is None:
            if project_id is None:
                return None, None
            cycle = (
                await self.session.execute(
                    select(AssessmentCycle)
                    .where(
                        AssessmentCycle.company_id == company_id,
                        AssessmentCycle.project_id == project_id,
                        AssessmentCycle.status != AssessmentCycleStatus.draft,
                    )
                    .order_by(AssessmentCycle.sequence.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if cycle is None:
                cycle = (
                    await self.session.execute(
                        select(AssessmentCycle)
                        .where(
                            AssessmentCycle.company_id == company_id,
                            AssessmentCycle.project_id == project_id,
                        )
                        .order_by(AssessmentCycle.sequence.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
            return project_id, cycle.id if cycle is not None else None
        cycle = (
            await self.session.execute(
                select(AssessmentCycle).where(
                    AssessmentCycle.id == assessment_cycle_id,
                    AssessmentCycle.company_id == company_id,
                )
            )
        ).scalar_one_or_none()
        if cycle is None or (project_id is not None and cycle.project_id != project_id):
            raise DomainError(
                "Assessment cycle not found in this project.",
                code="assessment_cycle_not_found",
            )
        return cycle.project_id, cycle.id

    async def _get_cycle_definition_compatibility(
        self,
        baseline_cycle_id: UUID,
        comparison_cycle_id: UUID,
    ) -> list[CycleQuestionnaireCompatibilityResponse]:
        result = await self.session.execute(
            select(
                AssessmentCycleQuestionnaire.assessment_cycle_id,
                AssessmentCycleQuestionnaire.questionnaire_key,
                AssessmentCycleQuestionnaire.questionnaire_definition_id,
            ).where(
                AssessmentCycleQuestionnaire.assessment_cycle_id.in_(
                    (baseline_cycle_id, comparison_cycle_id)
                )
            )
        )
        definitions_by_cycle: dict[UUID, dict[str, UUID]] = {
            baseline_cycle_id: {},
            comparison_cycle_id: {},
        }
        for cycle_id, questionnaire_key, definition_id in result.all():
            definitions_by_cycle[cycle_id][questionnaire_key] = definition_id

        baseline_definitions = definitions_by_cycle[baseline_cycle_id]
        comparison_definitions = definitions_by_cycle[comparison_cycle_id]
        return [
            CycleQuestionnaireCompatibilityResponse(
                questionnaire_key=questionnaire_key,
                baseline_definition_id=baseline_definitions.get(questionnaire_key),
                comparison_definition_id=comparison_definitions.get(questionnaire_key),
                compatible=(
                    baseline_definitions.get(questionnaire_key)
                    == comparison_definitions.get(questionnaire_key)
                    and questionnaire_key in baseline_definitions
                    and questionnaire_key in comparison_definitions
                ),
            )
            for questionnaire_key in sorted(
                baseline_definitions.keys() | comparison_definitions.keys()
            )
        ]

    async def _list_report_participants(
        self,
        company_id: UUID,
        project_id: UUID | None,
        assessment_cycle_id: UUID | None = None,
        assignment_results: Iterable[AssignmentResultWithDefinition] = (),
    ) -> list[ReportParticipant]:
        if project_id is not None and assessment_cycle_id is not None:
            assignment_result_rows = list(assignment_results)
            rows = (
                await self.session.execute(
                    select(ParticipantProfile, ProjectMembership)
                    .join(
                        AssessmentCycleTeamMembership,
                        AssessmentCycleTeamMembership.participant_profile_id
                        == ParticipantProfile.id,
                    )
                    .outerjoin(
                        ProjectMembership,
                        and_(
                            ProjectMembership.company_id == company_id,
                            ProjectMembership.project_id == project_id,
                            ProjectMembership.participant_profile_id
                            == ParticipantProfile.id,
                        ),
                    )
                    .where(
                        AssessmentCycleTeamMembership.assessment_cycle_id
                        == assessment_cycle_id,
                        ParticipantProfile.company_id == company_id,
                    )
                    .order_by(ParticipantProfile.full_name)
                )
            ).all()
            participants_by_id: dict[UUID, ReportParticipant] = {}
            for participant, membership in rows:
                participants_by_id.setdefault(
                    participant.id,
                    (
                        _report_participant_from_membership(membership, participant)
                        if membership is not None
                        else _report_participant_from_profile(participant)
                    ),
                )
            persisted_participant_ids = {
                participant_id
                for assignment, _result, _definition in assignment_result_rows
                for participant_id in (
                    assignment.respondent_profile_id,
                    _icare_target_id(assignment),
                )
                if participant_id is not None
            }
            missing_participant_ids = (
                persisted_participant_ids - participants_by_id.keys()
            )
            if missing_participant_ids:
                missing_rows = (
                    await self.session.execute(
                        select(ParticipantProfile, ProjectMembership)
                        .outerjoin(
                            ProjectMembership,
                            and_(
                                ProjectMembership.company_id == company_id,
                                ProjectMembership.project_id == project_id,
                                ProjectMembership.participant_profile_id
                                == ParticipantProfile.id,
                            ),
                        )
                        .where(
                            ParticipantProfile.company_id == company_id,
                            ParticipantProfile.id.in_(missing_participant_ids),
                        )
                        .order_by(ParticipantProfile.full_name)
                    )
                ).all()
                for participant, membership in missing_rows:
                    participants_by_id[participant.id] = (
                        _report_participant_from_membership(membership, participant)
                        if membership is not None
                        else _report_participant_from_profile(participant)
                    )
            return list(participants_by_id.values())
        if project_id is not None:
            memberships = await self.company_repository.list_project_memberships(
                company_id,
                project_id,
            )
            return [
                _report_participant_from_membership(membership, participant)
                for membership, participant in memberships
            ]

        participants = await self.company_repository.list_participants(company_id)
        return [_report_participant_from_profile(participant) for participant in participants]

    async def compute_and_save_score(
        self,
        assignment_id: UUID,
        questionnaire_key: QuestionnaireKey | str,
        answers: dict[str, Any],
        *,
        questionnaire_version: int | None = None,
        definition_schema: dict[str, Any] | None = None,
    ) -> ScoringResult:
        if definition_schema is None:
            key_value = (
                questionnaire_key.value
                if isinstance(questionnaire_key, QuestionnaireKey)
                else questionnaire_key
            )
            raise DomainError(
                f"No persisted scoring definition for key: {key_value}",
                code="scoring_not_supported",
            )

        scoring_meta = definition_schema.get("scoring")
        if not scoring_meta:
            key_value = (
                questionnaire_key.value
                if isinstance(questionnaire_key, QuestionnaireKey)
                else questionnaire_key
            )
            raise DomainError(
                f"Questionnaire {key_value} has no scoring metadata.",
                code="scoring_metadata_missing",
            )

        method = scoring_meta.get("method")
        scores: dict[str, Any] = {}
        primary_result: str | None = None

        if method == "sum_by_group":
            groups = scoring_meta.get("groups", [])
            interpretations = scoring_meta.get("interpretation", [])
            for group in groups:
                group_id = group["id"]
                q_ids = group.get("question_ids", [])
                group_score = sum(int(answers.get(q_id, 0)) for q_id in q_ids)

                interpretation_label = ""
                for rule in interpretations:
                    r_min = rule.get("min")
                    r_max = rule.get("max")
                    if r_min is not None and r_max is not None and r_min <= group_score <= r_max:
                        interpretation_label = rule.get("label", "")
                        break

                scores[group_id] = {
                    "score": group_score,
                    "interpretation": interpretation_label,
                }

            if scores:
                lowest_group = min(scores.keys(), key=lambda k: scores[k]["score"])
                primary_result = lowest_group

        elif method == "sum_statement_scores_by_driver":
            drivers = scoring_meta.get("drivers", [])
            raw_max_by_driver: dict[str, float] = {}
            for driver in drivers:
                scores[driver["id"]] = 0
                raw_max_by_driver[driver["id"]] = 0

            for section in definition_schema.get("sections", []):
                for question in section.get("questions", []):
                    if question.get("type") == "statement_score_set":
                        q_id = question["id"]
                        for statement in question.get("statements", []):
                            s_id = statement["id"]
                            driver_id = statement.get("scoring", {}).get("driver")
                            if driver_id:
                                answer_key = f"{q_id}:{s_id}"
                                score_val = int(answers.get(answer_key, 0))
                                scores[driver_id] = scores.get(driver_id, 0) + score_val
                                scale = statement.get("scale") or question.get("scale", [])
                                scale_values = [
                                    value
                                    for option in scale
                                    if isinstance(option, dict)
                                    and (value := _coerce_score(option.get("value"))) is not None
                                ]
                                raw_max_by_driver[driver_id] = raw_max_by_driver.get(
                                    driver_id, 0
                                ) + max(scale_values, default=0)

            normalize_to = _coerce_score(scoring_meta.get("normalize_to"))
            if normalize_to is not None and normalize_to > 0:
                for driver_id, raw_score in scores.items():
                    raw_max = raw_max_by_driver.get(driver_id, 0)
                    scores[driver_id] = (
                        round((float(raw_score) / raw_max) * normalize_to, 1) if raw_max > 0 else 0
                    )

            if scores:
                highest_driver = max(scores.keys(), key=lambda k: scores[k])
                primary_result = highest_driver

        elif method == "average_statement_scores_by_section":
            scale_min = float(scoring_meta.get("scale_min", 1))
            scale_max = float(scoring_meta.get("scale_max", 5))
            score_unit = scoring_meta.get("score_unit", "percent")
            score_min = float(scoring_meta.get("score_min", scale_min))
            score_range = max(scale_max - score_min, 1.0)
            dimension_ids: set[str] = set()

            def output_score(raw_avg: float) -> float:
                if score_unit == "grade_1_to_5":
                    return round(raw_avg, 1)
                percent_score = ((raw_avg - score_min) / score_range) * 100
                return round(percent_score, 1)

            for section in definition_schema.get("sections", []):
                section_id = section["id"]
                values: list[float] = []
                for question in section.get("questions", []):
                    if question.get("type") != "statement_score_set":
                        continue
                    question_id = question["id"]
                    dimension_ids.add(question_id)
                    for statement in question.get("statements", []):
                        answer_key = f"{question_id}:{statement['id']}"
                        value = _coerce_score(answers.get(answer_key))
                        if value is not None:
                            values.append(min(max(value, scale_min), scale_max))

                if not values:
                    scores[section_id] = {
                        "score": 0,
                        "raw_avg": 0,
                        "answered": 0,
                    }
                    continue

                raw_avg = sum(values) / len(values)
                scores[section_id] = {
                    "score": output_score(raw_avg),
                    "raw_avg": round(raw_avg, 2),
                    "answered": len(values),
                }

                for question in section.get("questions", []):
                    if question.get("type") != "statement_score_set":
                        continue
                    question_id = question["id"]
                    block_values: list[float] = []
                    for statement in question.get("statements", []):
                        answer_key = f"{question_id}:{statement['id']}"
                        value = _coerce_score(answers.get(answer_key))
                        if value is not None:
                            block_values.append(min(max(value, scale_min), scale_max))

                    if not block_values:
                        scores[question_id] = {
                            "score": 0,
                            "raw_avg": 0,
                            "answered": 0,
                        }
                        continue

                    block_raw_avg = sum(block_values) / len(block_values)
                    scores[question_id] = {
                        "score": output_score(block_raw_avg),
                        "raw_avg": round(block_raw_avg, 2),
                        "answered": len(block_values),
                    }

            scored_dimensions = {
                key: value
                for key, value in scores.items()
                if key in dimension_ids and isinstance(value, dict) and value.get("answered", 0) > 0
            }
            if scored_dimensions:
                primary_result = min(
                    scored_dimensions.keys(),
                    key=lambda key: scored_dimensions[key]["score"],
                )

        else:
            raise DomainError(
                f"Unsupported scoring method: {method}",
                code="unsupported_scoring_method",
            )

        existing = await self.repository.get_by_assignment(assignment_id)
        if existing:
            existing.scores = scores
            existing.primary_result = primary_result
            result = existing
        else:
            result = ScoringResult(
                assignment_id=assignment_id,
                scores=scores,
                primary_result=primary_result,
            )
            await self.repository.add_scoring_result(result)

        return result


def _icare_answer_review_rows(
    *,
    assignment: QuestionnaireAssignment,
    response: QuestionnaireResponse,
    respondent: ParticipantProfile,
    target: ParticipantProfile | None,
    schema: dict[str, Any],
) -> list[IcareAnswerReviewRowResponse]:
    rows: list[IcareAnswerReviewRowResponse] = []
    target_type = _enum_value(assignment.target_type)
    target_profile_id = target.id if target is not None else None
    target_name = target.full_name if target is not None else None
    if target_type == "self" and target is None:
        target_profile_id = respondent.id
        target_name = respondent.full_name

    for section in schema.get("sections", []):
        section_id = str(section.get("id") or "")
        section_label = str(section.get("title") or section_id or "Secțiune")
        for question in section.get("questions", []):
            if question.get("type") != "statement_score_set":
                continue
            question_id = str(question.get("id") or "")
            if not question_id:
                continue
            measurement_label = str(question.get("label") or question_id)
            question_scale = question.get("scale") or []
            for statement in question.get("statements", []):
                statement_id = str(statement.get("id") or "")
                if not statement_id:
                    continue
                answer_key = f"{question_id}:{statement_id}"
                if answer_key not in response.answers:
                    continue
                answer_value = response.answers[answer_key]
                if isinstance(answer_value, bool) or answer_value is None:
                    continue
                option = _matching_scale_option(
                    statement.get("scale") or question_scale,
                    answer_value,
                )
                rows.append(
                    IcareAnswerReviewRowResponse(
                        assignment_id=assignment.id,
                        response_id=response.id,
                        submitted_at=response.submitted_at.isoformat()
                        if response.submitted_at is not None
                        else None,
                        respondent_profile_id=respondent.id,
                        respondent_name=respondent.full_name,
                        respondent_email=respondent.email,
                        target_profile_id=target_profile_id,
                        target_name=target_name,
                        target_type=target_type,
                        response_kind=(
                            "self_assessment"
                            if _is_self_boss_assignment(assignment)
                            else "external_feedback"
                        ),
                        section_id=section_id,
                        section_label=section_label,
                        measurement_id=question_id,
                        measurement_label=measurement_label,
                        statement_id=statement_id,
                        statement_label=str(statement.get("label") or statement_id),
                        answer_value=answer_value
                        if isinstance(answer_value, int | str)
                        else str(answer_value),
                        answer_label=_scale_option_label(option, answer_value),
                        answer_description=(
                            str(option["description"])
                            if option is not None and option.get("description") is not None
                            else None
                        ),
                    )
                )
    return rows


def _matching_scale_option(
    scale: list[dict[str, Any]],
    answer_value: Any,
) -> dict[str, Any] | None:
    for option in scale:
        if str(option.get("value")) == str(answer_value):
            return option
    return None


def _scale_option_label(option: dict[str, Any] | None, answer_value: Any) -> str:
    if option is None:
        return str(answer_value)
    label = option.get("label")
    return str(label if label is not None else answer_value)


def _enum_value(value: Any) -> str:
    enum_value = getattr(value, "value", value)
    return str(enum_value)


def _coerce_score(value: Any) -> float | None:
    raw_score = value.get("score") if isinstance(value, dict) else value
    if isinstance(raw_score, bool) or raw_score is None:
        return None
    if isinstance(raw_score, int | float):
        return float(raw_score)
    if isinstance(raw_score, str):
        try:
            return float(raw_score)
        except ValueError:
            return None
    return None


def _private_definition_schema(
    definition: QuestionnaireDefinition | None,
) -> dict[str, Any]:
    if definition is None or not definition.private_config:
        return {}
    schema = definition.private_config.get("schema")
    return schema if isinstance(schema, dict) else {}


def _driver_feedback_by_dimension(
    assignment_results: Iterable[AssignmentResultWithDefinition],
) -> dict[str, str]:
    feedback: dict[str, str] = {}
    for assignment, result, definition in assignment_results:
        if (
            assignment.questionnaire_key not in DISTRESS_DRIVER_REPORT_KEYS
            or assignment.status not in COMPLETED_STATUSES
            or result is None
        ):
            continue
        if definition is None:
            continue
        for schema in (
            getattr(definition, "schema", None),
            _private_definition_schema(definition),
        ):
            if not isinstance(schema, dict):
                continue
            scoring = schema.get("scoring")
            if not isinstance(scoring, dict):
                continue
            for driver in scoring.get("drivers", []):
                if not isinstance(driver, dict):
                    continue
                dimension_id = _non_empty_string(driver.get("id"))
                if dimension_id is None:
                    continue
                for key in (
                    "feedback_above_50",
                    "participant_feedback",
                    "feedback",
                    "guidance",
                ):
                    value = _non_empty_string(driver.get(key))
                    if value is not None:
                        feedback.setdefault(dimension_id, value)
                        break
    return feedback


def _report_dimensions(
    definition: QuestionnaireDefinition | None,
    scores: dict[str, Any],
) -> dict[str, tuple[str, tuple[dict[str, Any], ...]]]:
    schema = _private_definition_schema(definition)
    scoring = schema.get("scoring") if isinstance(schema.get("scoring"), dict) else {}
    method = scoring.get("method")
    dimensions: dict[str, tuple[str, tuple[dict[str, Any], ...]]] = {}

    if method == "sum_by_group":
        global_rules = _valid_interpretation_rules(scoring.get("interpretation"))
        for group in scoring.get("groups", []):
            if not isinstance(group, dict):
                continue
            dimension_id = _non_empty_string(group.get("id"))
            if dimension_id is None:
                continue
            label = _non_empty_string(group.get("label")) or _prettify_score_key(dimension_id)
            rules = _valid_interpretation_rules(group.get("interpretation")) or global_rules
            dimensions[dimension_id] = (label, rules)
    elif method == "sum_statement_scores_by_driver":
        global_rules = _valid_interpretation_rules(scoring.get("interpretation"))
        for driver in scoring.get("drivers", []):
            if not isinstance(driver, dict):
                continue
            dimension_id = _non_empty_string(driver.get("id"))
            if dimension_id is None:
                continue
            label = _non_empty_string(driver.get("label")) or _prettify_score_key(dimension_id)
            rules = _valid_interpretation_rules(driver.get("interpretation")) or global_rules
            dimensions[dimension_id] = (label, rules)
    elif method == "average_statement_scores_by_section":
        for section in schema.get("sections", []):
            if not isinstance(section, dict):
                continue
            for question in section.get("questions", []):
                if not isinstance(question, dict) or question.get("type") != "statement_score_set":
                    continue
                dimension_id = _non_empty_string(question.get("id"))
                if dimension_id is None:
                    continue
                label = _non_empty_string(question.get("label")) or _prettify_score_key(
                    dimension_id
                )
                dimensions[dimension_id] = (
                    label,
                    _valid_interpretation_rules(question.get("interpretation")),
                )

    if dimensions:
        return dimensions

    return {
        key: (_prettify_score_key(key), ())
        for key, value in scores.items()
        if _coerce_score(value) is not None
    }


def _valid_interpretation_rules(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(rule for rule in value if isinstance(rule, dict))


def _non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _prettify_score_key(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", " ").split()) or value


def _accumulate_scores(
    accumulators: dict[str, ReportDimensionAccumulator],
    result: ScoringResult,
    definition: QuestionnaireDefinition | None,
) -> bool:
    found = False
    for dimension_id, (label, rules) in _report_dimensions(definition, result.scores).items():
        score = _coerce_score(result.scores.get(dimension_id))
        if score is None:
            continue
        accumulator = accumulators.setdefault(
            dimension_id,
            ReportDimensionAccumulator(
                label=label,
                interpretation_rules=rules,
            ),
        )
        accumulator.total += score
        accumulator.count += 1
        found = True
    return found


def _interpretation_from_rules(
    score: float,
    rules: tuple[dict[str, Any], ...],
) -> tuple[str, str | None] | None:
    for rule in rules:
        minimum = _coerce_score(rule.get("min"))
        maximum = _coerce_score(rule.get("max"))
        label = _non_empty_string(rule.get("label"))
        if minimum is None or maximum is None or label is None:
            continue
        if minimum <= score <= maximum:
            explicit_range = _non_empty_string(rule.get("range_label"))
            range_label = explicit_range or f"{minimum:g}-{maximum:g}"
            return label, range_label
    return None


def _averages_from_accumulators(
    accumulators: dict[str, ReportDimensionAccumulator],
) -> list[ReportAverageResponse]:
    averages: list[ReportAverageResponse] = []
    for dimension_id, accumulator in sorted(accumulators.items()):
        if accumulator.count <= 0:
            continue
        average = round(accumulator.total / accumulator.count, 1)
        interpretation = _interpretation_from_rules(
            average,
            accumulator.interpretation_rules,
        )
        averages.append(
            ReportAverageResponse(
                id=dimension_id,
                label=accumulator.label,
                avg=average,
                interpretation=interpretation[0] if interpretation is not None else None,
                range_label=interpretation[1] if interpretation is not None else None,
            )
        )
    return averages


def _report_participant_from_profile(participant: ParticipantProfile) -> ReportParticipant:
    return ReportParticipant(
        id=participant.id,
        full_name=participant.full_name,
        reports_to_name=clean_manager_reference(participant.reports_to_name),
        position=participant.position,
        role_group=participant.role_group,
        pcm_base=participant.pcm_base,
        pcm_phase=participant.pcm_phase,
        user_id=participant.user_id,
    )


def _report_participant_from_membership(
    membership: ProjectMembership,
    participant: ParticipantProfile,
) -> ReportParticipant:
    return ReportParticipant(
        id=participant.id,
        full_name=participant.full_name,
        reports_to_name=clean_manager_reference(membership.reports_to_name),
        position=membership.position or participant.position,
        role_group=membership.role_group,
        pcm_base=participant.pcm_base,
        pcm_phase=participant.pcm_phase,
        user_id=participant.user_id,
    )


def _score_scale_response(
    scales: set[ScoreScale],
    *,
    has_unknown_scale: bool,
) -> ReportScoreScaleResponse:
    compatible = len(scales) <= 1 and not has_unknown_scale
    scale = next(iter(scales), None) if compatible else None
    return ReportScoreScaleResponse(
        score_unit=scale.score_unit if scale is not None else None,
        scale_min=scale.scale_min if scale is not None else None,
        scale_max=scale.scale_max if scale is not None else None,
        score_scale_compatible=compatible,
        unavailable_reason=None if compatible else "incompatible_score_scales",
    )


def _summarize_report_rows(
    rows: Iterable[AssignmentResultWithDefinition],
) -> tuple[int, list[ReportAverageResponse], ReportScoreScaleResponse]:
    dimensions: dict[str, ReportDimensionAccumulator] = {}
    scales: set[ScoreScale] = set()
    has_unknown_scale = False
    count = 0
    for _assignment, result, definition in rows:
        assert result is not None
        if not _accumulate_scores(dimensions, result, definition):
            continue
        count += 1
        dimension_ids = {
            dimension_id
            for dimension_id in _report_dimensions(definition, result.scores)
            if _coerce_score(result.scores.get(dimension_id)) is not None
        }
        derived_scale = derive_definition_score_scale(
            definition,
            dimension_ids=dimension_ids,
        )
        if not derived_scale.compatible or derived_scale.scale is None:
            has_unknown_scale = True
        else:
            scales.add(derived_scale.scale)
    scale_response = _score_scale_response(scales, has_unknown_scale=has_unknown_scale)
    averages = (
        _averages_from_accumulators(dimensions) if scale_response.score_scale_compatible else []
    )
    return count, averages, scale_response


def _build_score_summary(
    assignment_results: Iterable[AssignmentResultWithDefinition],
    *,
    driver_rows: Iterable[AssignmentResultWithDefinition] | None = None,
) -> ScoreSummary:
    assignment_result_rows = list(assignment_results)
    selected_driver_rows = (
        list(driver_rows)
        if driver_rows is not None
        else list(_select_latest_completed_driver_rows(assignment_result_rows).average_rows)
    )
    boss_360_dimensions: dict[str, ReportDimensionAccumulator] = {}
    boss_360_count = 0
    lencioni_rows: list[AssignmentResultWithDefinition] = []

    for assignment, result, definition in assignment_result_rows:
        if assignment.status not in COMPLETED_STATUSES or result is None:
            continue
        if assignment.questionnaire_key in LENCIONI_REPORT_KEYS:
            lencioni_rows.append((assignment, result, definition))
        elif assignment.questionnaire_key in BOSS_360_REPORT_KEYS:
            if _is_self_boss_assignment(assignment):
                continue
            if _accumulate_scores(boss_360_dimensions, result, definition):
                boss_360_count += 1
    lencioni_count, lencioni_averages, lencioni_scale = _summarize_report_rows(lencioni_rows)
    driver_count, driver_averages, driver_scale = _summarize_report_rows(selected_driver_rows)

    return ScoreSummary(
        lencioni_count=lencioni_count,
        driver_count=driver_count,
        boss_360_count=boss_360_count,
        lencioni_averages=lencioni_averages,
        lencioni_scale=lencioni_scale,
        driver_averages=driver_averages,
        driver_scale=driver_scale,
        boss_360_averages=_averages_from_accumulators(boss_360_dimensions),
    )


def _leadership_member_lencioni_summary(
    assignment_results: Iterable[AssignmentResultWithDefinition],
    *,
    target_team_id: UUID | None,
) -> ScoreSummary:
    if target_team_id is None:
        return _build_score_summary([])
    rows = [
        row
        for row in assignment_results
        if row[0].questionnaire_key in LENCIONI_REPORT_KEYS
        and row[0].status in COMPLETED_STATUSES
        and row[1] is not None
        and _enum_value(row[0].target_type) == "team"
        and row[0].target_team_id == target_team_id
    ]
    return _build_score_summary(rows)


def _reportable_score_availability(
    assignment_results: Iterable[AssignmentResultWithDefinition],
    processing_jobs: Iterable[SubmissionProcessingJob],
) -> ReportableScoreAvailability:
    jobs_by_assignment_id = {job.assignment_id: job for job in processing_jobs}
    scored = pending = failed = orphaned = 0
    for assignment, result, _definition in assignment_results:
        if (
            assignment.questionnaire_key
            not in (LENCIONI_REPORT_KEYS | DISTRESS_DRIVER_REPORT_KEYS | BOSS_360_REPORT_KEYS)
            or assignment.status not in COMPLETED_STATUSES
        ):
            continue
        if result is not None:
            scored += 1
            continue
        job = jobs_by_assignment_id.get(assignment.id)
        if job is None or job.status == SubmissionProcessingStatus.completed:
            orphaned += 1
        elif job.status == SubmissionProcessingStatus.failed:
            failed += 1
        else:
            pending += 1
    return ReportableScoreAvailability(
        scored=scored,
        pending=pending,
        failed=failed,
        orphaned=orphaned,
    )


def _is_self_boss_assignment(assignment: QuestionnaireAssignment) -> bool:
    if assignment.questionnaire_key not in BOSS_360_REPORT_KEYS:
        return False
    target_type = _enum_value(assignment.target_type)
    if target_type == "self":
        return True
    return (
        target_type == "person"
        and assignment.target_person_id is not None
        and assignment.target_person_id == assignment.respondent_profile_id
    )


def _icare_target_id(assignment: QuestionnaireAssignment) -> UUID | None:
    target_type = _enum_value(assignment.target_type)
    if target_type == "self":
        return assignment.respondent_profile_id
    if target_type == "person":
        return assignment.target_person_id
    return None


ICARE_COHORT_ORDER = ("direct_team", "leadership_peers", "self")


def _with_persisted_icare_cohorts(
    team_snapshot: AssessmentCycleTeamSnapshot,
    assignment_results: Iterable[AssignmentResultWithDefinition],
) -> AssessmentCycleTeamSnapshot:
    icare_assignments = [
        assignment
        for assignment, _result, _definition in assignment_results
        if assignment.questionnaire_key in BOSS_360_REPORT_KEYS
    ]
    derived_leadership_ids = {
        target_id
        for assignment in icare_assignments
        if (target_id := _icare_target_id(assignment)) is not None
        and assignment.respondent_profile_id != target_id
    }
    leadership_ids = team_snapshot.leadership_ids | derived_leadership_ids
    direct_report_ids_by_leader_id = {
        leader_id: set(direct_report_ids)
        for leader_id, direct_report_ids in team_snapshot.direct_report_ids_by_leader_id.items()
    }
    for assignment in icare_assignments:
        target_id = _icare_target_id(assignment)
        respondent_id = assignment.respondent_profile_id
        if (
            target_id in leadership_ids
            and respondent_id != target_id
            and respondent_id not in leadership_ids
        ):
            direct_report_ids_by_leader_id.setdefault(target_id, set()).add(
                respondent_id
            )
    return AssessmentCycleTeamSnapshot(
        leadership_ids=leadership_ids,
        direct_report_ids_by_leader_id={
            leader_id: frozenset(direct_report_ids)
            for leader_id, direct_report_ids in direct_report_ids_by_leader_id.items()
        },
        teams=team_snapshot.teams,
    )


def _icare_score_scale(
    definition: QuestionnaireDefinition | None,
) -> ScoreScale | None:
    if definition is None:
        return None
    for schema in (
        _private_definition_schema(definition),
        getattr(definition, "schema", None),
    ):
        if not isinstance(schema, dict):
            continue
        scoring = schema.get("scoring")
        if not isinstance(scoring, dict):
            continue
        unit = _non_empty_string(scoring.get("score_unit")) or "percent"
        if unit == "grade_1_to_5":
            minimum = _coerce_score(scoring.get("scale_min"))
            maximum = _coerce_score(scoring.get("scale_max"))
            if minimum is not None and maximum is not None and maximum > minimum:
                return ScoreScale(unit, minimum, maximum)
        else:
            return ScoreScale(unit, 0.0, 100.0)
    return None


def _icare_assignment_cohort(
    assignment: QuestionnaireAssignment,
    *,
    hierarchy: Any,
    team_snapshot: AssessmentCycleTeamSnapshot | None = None,
) -> str | None:
    if getattr(assignment, "assessment_cycle_id", None) is not None:
        persisted_cohort = _enum_value(getattr(assignment, "icare_cohort", None))
        return persisted_cohort if persisted_cohort in ICARE_COHORT_ORDER else None
    target_id = _icare_target_id(assignment)
    leadership_ids = (
        team_snapshot.leadership_ids
        if team_snapshot is not None
        else hierarchy.leadership_ids
    )
    if target_id is None or target_id not in leadership_ids:
        return None
    if _is_self_boss_assignment(assignment):
        return "self"
    respondent_id = assignment.respondent_profile_id
    if respondent_id in leadership_ids and respondent_id != target_id:
        return "leadership_peers"
    direct_report_ids = (
        team_snapshot.direct_report_ids_by_leader_id.get(target_id, frozenset())
        if team_snapshot is not None
        else {
            participant.id
            for participant in hierarchy.direct_reports_by_manager_id.get(target_id, [])
        }
    )
    if respondent_id in direct_report_ids and respondent_id not in leadership_ids:
        return "direct_team"
    return None


def _build_icare_cohort_summaries(
    assignment_results: Iterable[AssignmentResultWithDefinition],
    participants: list[ReportParticipant],
    *,
    target_profile_id: UUID | None = None,
    team_snapshot: AssessmentCycleTeamSnapshot | None = None,
) -> list[IcareCohortSummaryResponse]:
    hierarchy = build_organization_hierarchy(
        [_hierarchy_participant_from_report(participant) for participant in participants]
    )
    eligible_rows = [
        row
        for row in assignment_results
        if row[0].questionnaire_key in BOSS_360_REPORT_KEYS
        and row[0].status in COMPLETED_STATUSES
        and row[1] is not None
        and (target_profile_id is None or _icare_target_id(row[0]) == target_profile_id)
    ]
    explicit_leadership_ids = {
        participant.id
        for participant in participants
        if (participant.role_group or "").strip().casefold() in {"leadership", "manager"}
    }

    def cohort_for_row(assignment: QuestionnaireAssignment) -> str | None:
        if getattr(assignment, "assessment_cycle_id", None) is not None:
            return _icare_assignment_cohort(assignment, hierarchy=hierarchy)
        if hierarchy.ambiguous_name is None:
            return _icare_assignment_cohort(assignment, hierarchy=hierarchy)
        target_id = _icare_target_id(assignment)
        if _is_self_boss_assignment(assignment) and target_id in explicit_leadership_ids:
            return "self"
        return None

    classified_rows = [
        (assignment, result, definition, cohort)
        for assignment, result, definition in eligible_rows
        if (cohort := cohort_for_row(assignment)) is not None
    ]
    summaries: list[IcareCohortSummaryResponse] = []
    for cohort in ICARE_COHORT_ORDER:
        cohort_rows = [row for row in classified_rows if row[3] == cohort]
        scales = {
            scale
            for _assignment, _result, definition, _cohort in cohort_rows
            if (scale := _icare_score_scale(definition)) is not None
        }
        definition_ids = {
            definition_id
            for _assignment, _result, definition, _cohort in cohort_rows
            if definition is not None
            and (definition_id := getattr(definition, "id", None)) is not None
        }
        if len(scales) > 1 or len(definition_ids) > 1:
            summaries.append(
                IcareCohortSummaryResponse(
                    cohort=cohort,  # type: ignore[arg-type]
                    response_count=len(cohort_rows),
                    averages=[],
                    score_scale_compatible=False,
                    unavailable_reason="incompatible_score_scales",
                )
            )
            continue
        dimensions: dict[str, ReportDimensionAccumulator] = {}
        for _assignment, result, definition, _cohort in cohort_rows:
            assert result is not None
            _accumulate_scores(dimensions, result, definition)
        score_scale = next(iter(scales), None)
        summaries.append(
            IcareCohortSummaryResponse(
                cohort=cohort,  # type: ignore[arg-type]
                response_count=len(cohort_rows),
                averages=_averages_from_accumulators(dimensions),
                score_unit=score_scale.score_unit if score_scale is not None else None,
                scale_min=score_scale.scale_min if score_scale is not None else None,
                scale_max=score_scale.scale_max if score_scale is not None else None,
            )
        )
    return summaries


def _icare_unclassified_response_count(
    assignment_results: Iterable[AssignmentResultWithDefinition],
    participants: list[ReportParticipant],
    *,
    target_profile_id: UUID | None = None,
) -> int:
    hierarchy = build_organization_hierarchy(
        [_hierarchy_participant_from_report(participant) for participant in participants]
    )
    explicit_leadership_ids = _explicit_leadership_ids(participants)
    count = 0
    for assignment, result, definition in assignment_results:
        if (
            assignment.questionnaire_key not in BOSS_360_REPORT_KEYS
            or assignment.status not in COMPLETED_STATUSES
            or result is None
            or definition is None
            or (target_profile_id is not None and _icare_target_id(assignment) != target_profile_id)
        ):
            continue
        if hierarchy.ambiguous_name is None:
            cohort = _icare_assignment_cohort(assignment, hierarchy=hierarchy)
        elif (
            getattr(assignment, "assessment_cycle_id", None) is not None
            and _enum_value(getattr(assignment, "icare_cohort", None))
            in ICARE_COHORT_ORDER
        ):
            cohort = _enum_value(getattr(assignment, "icare_cohort", None))
        elif _is_self_boss_assignment(assignment) and (
            _icare_target_id(assignment) in explicit_leadership_ids
        ):
            cohort = "self"
        else:
            cohort = None
        if cohort is None:
            count += 1
    return count


def _build_icare_target_summaries(
    assignment_results: Iterable[AssignmentResultWithDefinition],
    participants: list[ReportParticipant],
    *,
    team_snapshot: AssessmentCycleTeamSnapshot | None = None,
) -> list[IcareTargetSummaryResponse]:
    assignment_result_rows = list(assignment_results)
    participant_names = {participant.id: participant.full_name for participant in participants}
    hierarchy = build_organization_hierarchy(
        [_hierarchy_participant_from_report(participant) for participant in participants]
    )
    leadership_ids = (
        team_snapshot.leadership_ids
        if team_snapshot is not None
        else (
            hierarchy.leadership_ids
            if hierarchy.ambiguous_name is None
            else {
                participant.id
                for participant in participants
                if (participant.role_group or "").strip().casefold()
                in {"leadership", "manager"}
            }
        )
    )
    grouped: dict[
        UUID,
        tuple[
            dict[str, ReportDimensionAccumulator],
            dict[str, ReportDimensionAccumulator],
            int,
            int,
        ],
    ] = {}

    for assignment, result, definition in assignment_result_rows:
        if (
            assignment.questionnaire_key not in BOSS_360_REPORT_KEYS
            or assignment.status not in COMPLETED_STATUSES
            or result is None
        ):
            continue
        target_id = _icare_target_id(assignment)
        if target_id is None or target_id not in leadership_ids:
            continue
        external_dimensions, self_dimensions, external_count, self_count = grouped.setdefault(
            target_id,
            ({}, {}, 0, 0),
        )
        cohort = _icare_assignment_cohort(assignment, hierarchy=hierarchy)
        if cohort is None:
            continue
        if cohort == "self":
            if _accumulate_scores(self_dimensions, result, definition):
                self_count += 1
        elif _accumulate_scores(external_dimensions, result, definition):
            external_count += 1
        grouped[target_id] = (
            external_dimensions,
            self_dimensions,
            external_count,
            self_count,
        )

    unclassified_counts = {
        target_id: _icare_unclassified_response_count(
            assignment_result_rows,
            participants,
            target_profile_id=target_id,
        )
        for target_id in grouped
    }
    return [
        IcareTargetSummaryResponse(
            target_profile_id=target_id,
            target_name=participant_names.get(target_id, "Participant"),
            external_response_count=external_count,
            self_response_count=self_count,
            external_averages=_averages_from_accumulators(external_dimensions),
            self_averages=_averages_from_accumulators(self_dimensions),
            cohorts=_build_icare_cohort_summaries(
                assignment_result_rows,
                participants,
                target_profile_id=target_id,
                team_snapshot=team_snapshot,
            ),
            unclassified_response_count=unclassified_counts[target_id],
            unclassified_reason=(
                "historical_cohort_unavailable"
                if unclassified_counts[target_id]
                else None
            ),
        )
        for target_id, (
            external_dimensions,
            self_dimensions,
            external_count,
            self_count,
        ) in sorted(
            grouped.items(),
            key=lambda item: participant_names.get(item[0], "").casefold(),
        )
    ]


def _driver_assignment_order_key(
    row: AssignmentResultWithDefinition,
) -> tuple[datetime, str]:
    assignment = row[0]
    created_at = getattr(assignment, "created_at", None)
    if not isinstance(created_at, datetime):
        created_at = datetime.min.replace(tzinfo=UTC)
    elif created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    else:
        created_at = created_at.astimezone(UTC)
    return created_at, str(getattr(assignment, "id", UUID(int=0)))


def _select_latest_completed_driver_rows(
    assignment_results: Iterable[AssignmentResultWithDefinition],
) -> DriverRowSelection:
    participants_with_results: set[UUID] = set()
    average_rows: list[AssignmentResultWithDefinition] = []
    latest_valid_by_participant: dict[UUID, AssignmentResultWithDefinition] = {}
    for row in assignment_results:
        assignment, result, definition = row
        if (
            assignment.questionnaire_key not in DISTRESS_DRIVER_REPORT_KEYS
            or assignment.status not in COMPLETED_STATUSES
            or result is None
        ):
            continue
        participant_id = assignment.respondent_profile_id
        participants_with_results.add(participant_id)
        ranked_scores = _ranked_driver_scores(result, definition)
        if ranked_scores:
            average_rows.append(row)
        if len(ranked_scores) < 2:
            continue
        current = latest_valid_by_participant.get(participant_id)
        if current is None or _driver_assignment_order_key(row) > _driver_assignment_order_key(
            current
        ):
            latest_valid_by_participant[participant_id] = row
    rankable_rows = [
        latest_valid_by_participant[participant_id]
        for participant_id in sorted(latest_valid_by_participant, key=str)
    ]
    return DriverRowSelection(
        average_rows=tuple(average_rows),
        rankable_rows=tuple(rankable_rows),
        insufficient_driver_score_count=(
            len(participants_with_results) - len(latest_valid_by_participant)
        ),
    )


def _ranked_driver_scores(
    result: ScoringResult,
    definition: QuestionnaireDefinition | None,
) -> list[tuple[str, str, float]]:
    definition_dimensions = _report_dimensions(definition, result.scores)
    order_index = {dimension_id: index for index, dimension_id in enumerate(definition_dimensions)}
    ranked = [
        (dimension_id, label, score)
        for dimension_id, (label, _rules) in definition_dimensions.items()
        if (score := _coerce_score(result.scores.get(dimension_id))) is not None
    ]
    ranked.sort(
        key=lambda item: (
            -item[2],
            order_index.get(item[0], len(order_index)),
            item[0],
        )
    )
    return ranked


def _build_driver_rank_summary(
    rankable_driver_rows: Iterable[AssignmentResultWithDefinition],
    *,
    insufficient_driver_score_count: int,
) -> DriverRankSummaryResponse:
    first_counts: dict[str, int] = {}
    second_counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    colors: dict[str, str | None] = {}
    first_tie_breaks = 0
    second_tie_breaks = 0
    total_people = 0

    for _assignment, result, definition in rankable_driver_rows:
        assert result is not None
        ranked = _ranked_driver_scores(result, definition)
        if len(ranked) < 2:
            raise ValueError("Rankable driver rows must contain at least two scores.")
        for dimension_id, label, _score in ranked:
            labels[dimension_id] = label
            colors.setdefault(dimension_id, None)
        first, second = ranked[0], ranked[1]
        first_counts[first[0]] = first_counts.get(first[0], 0) + 1
        second_counts[second[0]] = second_counts.get(second[0], 0) + 1
        total_people += 1
        if sum(score == first[2] for _dimension_id, _label, score in ranked) > 1:
            first_tie_breaks += 1
        if sum(score == second[2] for _dimension_id, _label, score in ranked[1:]) > 1:
            second_tie_breaks += 1

    def distribution(counts: dict[str, int]) -> list[ReportDistributionResponse]:
        return [
            ReportDistributionResponse(
                id=dimension_id,
                label=labels.get(dimension_id, _prettify_score_key(dimension_id)),
                value=count,
                color=colors.get(dimension_id),
            )
            for dimension_id, count in sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

    return DriverRankSummaryResponse(
        total_people=total_people,
        first_rank=distribution(first_counts),
        second_rank=distribution(second_counts),
        first_rank_tie_breaks=first_tie_breaks,
        second_rank_tie_breaks=second_tie_breaks,
        insufficient_driver_score_count=insufficient_driver_score_count,
    )


def _build_leadership_members(
    participants: list[ReportParticipant],
    *,
    leadership_ids: set[UUID] | None = None,
) -> list[LeadershipMemberSummaryResponse]:
    hierarchy = build_organization_hierarchy(
        [_hierarchy_participant_from_report(participant) for participant in participants]
    )
    leadership_ids = (
        leadership_ids
        if leadership_ids is not None
        else _leadership_ids_for_report(hierarchy, participants)
    )
    participant_by_id = {participant.id: participant for participant in participants}
    return [
        LeadershipMemberSummaryResponse(
            participant_profile_id=participant.id,
            full_name=participant.full_name,
            position=participant.position,
            role_group=participant.role_group,
        )
        for participant_id in sorted(
            leadership_ids,
            key=lambda value: (
                participant_by_id.get(value).full_name.casefold()
                if participant_by_id.get(value) is not None
                else ""
            ),
        )
        if (participant := participant_by_id.get(participant_id)) is not None
    ]


def _explicit_leadership_ids(participants: Iterable[ReportParticipant]) -> set[UUID]:
    return {
        participant.id
        for participant in participants
        if (participant.role_group or "").strip().casefold() in {"leadership", "manager"}
    }


def _leadership_ids_for_report(
    hierarchy: Any,
    participants: Iterable[ReportParticipant],
) -> set[UUID]:
    if hierarchy.ambiguous_name is None:
        return set(hierarchy.leadership_ids)
    return _explicit_leadership_ids(participants)


def _without_incompatible_overlay_dimensions(
    report: CompanyReportAggregateResponse,
    incompatible_questionnaire_keys: set[str],
) -> CompanyReportAggregateResponse:
    updates: dict[str, object] = {}
    if incompatible_questionnaire_keys & LENCIONI_REPORT_KEYS:
        updates["lencioni_averages"] = []
    if incompatible_questionnaire_keys & DISTRESS_DRIVER_REPORT_KEYS:
        updates["driver_averages"] = []
        updates["driver_rank_summary"] = DriverRankSummaryResponse(
            total_people=0,
            first_rank=[],
            second_rank=[],
            first_rank_tie_breaks=0,
            second_rank_tie_breaks=0,
            insufficient_driver_score_count=0,
        )
    if incompatible_questionnaire_keys & BOSS_360_REPORT_KEYS:
        updates["boss_360_averages"] = []
        updates["icare_target_summaries"] = []
        updates["icare_cohorts"] = []
    if QuestionnaireKey.pcm_base.value in incompatible_questionnaire_keys:
        updates["pcm_base_distribution"] = []
    if {QuestionnaireKey.phase.value, "pcm_phase"} & incompatible_questionnaire_keys:
        updates["pcm_phase_distribution"] = []
    return report.model_copy(update=updates) if updates else report


def _distribution_from_completed_pcm_assignments(
    participants: list[ReportParticipant],
    assignments: list[QuestionnaireAssignment],
    field: str,
    cycle_values: dict[UUID, dict[str, str]] | None = None,
) -> list[ReportDistributionResponse]:
    counts: dict[str, int] = {}
    participants_by_id = {participant.id: participant for participant in participants}
    participant_ids_with_completed_pcm = {
        assignment.respondent_profile_id
        for assignment in assignments
        if assignment.status in COMPLETED_STATUSES
        and assignment.questionnaire_key in PCM_REPORT_KEYS
    }

    for participant_id in participant_ids_with_completed_pcm:
        participant = participants_by_id.get(participant_id)
        if participant is None:
            continue
        value = (cycle_values or {}).get(participant_id, {}).get(field)
        if value is None and cycle_values is None:
            value = getattr(participant, field)
        if not isinstance(value, str) or not value.strip():
            continue
        cleaned = value.strip()
        counts[cleaned] = counts.get(cleaned, 0) + 1

    return sorted(
        [
            ReportDistributionResponse(
                id=profile,
                label=_format_pcm_label(profile),
                value=count,
                color=_get_pcm_color(profile),
            )
            for profile, count in counts.items()
        ],
        key=lambda item: (-item.value, item.label),
    )


def _pcm_values_from_responses(
    responses: list[tuple[QuestionnaireAssignment, QuestionnaireResponse]],
) -> dict[UUID, dict[str, str]]:
    values: dict[UUID, dict[str, str]] = {}
    for assignment, response in responses:
        profile_values = values.setdefault(assignment.respondent_profile_id, {})
        for field in ("pcm_base", "pcm_phase"):
            value = response.answers.get(field)
            if isinstance(value, str) and value.strip():
                profile_values[field] = value.strip()
    return values


def _distribution_count(distribution: list[ReportDistributionResponse]) -> int:
    return sum(item.value for item in distribution)


def _build_team_lenses(
    participants: list[ReportParticipant],
    assignment_results: list[AssignmentResultWithDefinition],
    pcm_values: dict[UUID, dict[str, str]] | None = None,
    *,
    team_snapshot: AssessmentCycleTeamSnapshot | None = None,
) -> TeamLensBuildResult:
    if team_snapshot is not None:
        return TeamLensBuildResult(
            team_lenses=[
                _build_team_lens(
                    str(team.id),
                    team.name,
                    set(team.member_ids),
                    participants,
                    assignment_results,
                    pcm_values,
                    lencioni_target_team_id=team.id,
                )
                for team in team_snapshot.teams
            ],
            hierarchy_ambiguous=False,
            hierarchy_ambiguity_message=None,
            hierarchy_issues=[],
        )
    hierarchy = build_organization_hierarchy(
        [_hierarchy_participant_from_report(participant) for participant in participants]
    )
    if hierarchy.ambiguous_name is not None:
        message = (
            f'Numele "{hierarchy.ambiguous_name}" apare de mai multe ori în roster și este folosit '
            "ca manager."
        )
        return TeamLensBuildResult(
            team_lenses=[],
            hierarchy_ambiguous=True,
            hierarchy_ambiguity_message=message,
            hierarchy_issues=[
                ReportHierarchyIssueResponse(
                    code="manager_ambiguous",
                    message=message,
                )
            ],
        )

    participant_by_id = {participant.id: participant for participant in participants}
    teams_by_id: dict[str, tuple[str, set[UUID]]] = {}
    direct_reports_by_manager_id = {
        manager_id: [
            participant_by_id[direct_report.id]
            for direct_report in direct_reports
            if direct_report.id in participant_by_id
        ]
        for manager_id, direct_reports in hierarchy.direct_reports_by_manager_id.items()
    }
    leadership_ids = set(hierarchy.leadership_ids)
    hierarchy_issues = [_report_hierarchy_issue(issue) for issue in hierarchy.issues]

    for manager_id in leadership_ids:
        manager = participant_by_id.get(manager_id)
        if manager is None:
            continue
        direct_reports = direct_reports_by_manager_id.get(manager.id, [])
        direct_report_ids = {direct_report.id for direct_report in direct_reports}
        if not direct_report_ids:
            continue

        team_id = f"manager:{manager.id}"
        teams_by_id[team_id] = (
            f"Echipa {manager.full_name}",
            {manager.id, *direct_report_ids},
        )

    if len(leadership_ids) > 1 or len(hierarchy.top_level_ids) > 1:
        teams_by_id["leadership"] = ("Leadership", leadership_ids)

    team_lenses = [
        _build_team_lens(
            team_id,
            name,
            member_ids,
            participants,
            assignment_results,
            pcm_values,
        )
        for team_id, (name, member_ids) in teams_by_id.items()
    ]
    team_lenses.sort(
        key=lambda team: (
            0 if team.id == "leadership" else 1,
            -team.member_count,
            team.name,
        )
    )

    return TeamLensBuildResult(
        team_lenses=team_lenses,
        hierarchy_ambiguous=False,
        hierarchy_ambiguity_message=None,
        hierarchy_issues=hierarchy_issues,
    )


def _build_team_lens(
    team_id: str,
    name: str,
    member_ids: set[UUID],
    participants: list[ReportParticipant],
    assignment_results: list[AssignmentResultWithDefinition],
    pcm_values: dict[UUID, dict[str, str]] | None = None,
    *,
    lencioni_target_team_id: UUID | None = None,
) -> ReportTeamLensResponse:
    team_assignment_results = [
        (assignment, result, definition)
        for assignment, result, definition in assignment_results
        if (
            assignment.questionnaire_key in LENCIONI_REPORT_KEYS
            and lencioni_target_team_id is not None
            and assignment.target_team_id == lencioni_target_team_id
        )
        or (
            assignment.respondent_profile_id in member_ids
            and (
                lencioni_target_team_id is None
                or assignment.questionnaire_key not in LENCIONI_REPORT_KEYS
            )
        )
    ]
    team_assignments = [assignment for assignment, _result, _definition in team_assignment_results]
    assigned_count = len(team_assignments)
    completed_count = sum(
        1 for assignment in team_assignments if assignment.status in COMPLETED_STATUSES
    )
    score_summary = _build_score_summary(team_assignment_results)
    team_participants = [
        participant for participant in participants if participant.id in member_ids
    ]
    pcm_base_distribution = _distribution_from_completed_pcm_assignments(
        team_participants,
        team_assignments,
        "pcm_base",
        pcm_values,
    )
    pcm_phase_distribution = _distribution_from_completed_pcm_assignments(
        team_participants,
        team_assignments,
        "pcm_phase",
        pcm_values,
    )

    return ReportTeamLensResponse(
        id=team_id,
        name=name,
        member_count=len(member_ids),
        assigned_count=assigned_count,
        completed_count=completed_count,
        completion_rate=round((completed_count / assigned_count) * 100)
        if assigned_count > 0
        else 0,
        lencioni_count=score_summary.lencioni_count,
        driver_count=score_summary.driver_count,
        boss_360_count=score_summary.boss_360_count,
        pcm_base_count=_distribution_count(pcm_base_distribution),
        pcm_phase_count=_distribution_count(pcm_phase_distribution),
        lencioni_averages=score_summary.lencioni_averages,
        lencioni_scale=score_summary.lencioni_scale,
        driver_averages=score_summary.driver_averages,
        boss_360_averages=score_summary.boss_360_averages,
        pcm_base_distribution=pcm_base_distribution,
        pcm_phase_distribution=pcm_phase_distribution,
    )


def _hierarchy_participant_from_report(participant: ReportParticipant) -> HierarchyParticipant:
    return HierarchyParticipant(
        id=participant.id,
        full_name=participant.full_name,
        reports_to_name=participant.reports_to_name,
        role_group=participant.role_group,
        user_id=participant.user_id,
    )


def _report_hierarchy_issue(issue: HierarchyIssue) -> ReportHierarchyIssueResponse:
    if issue.code == "manager_unresolved" and issue.participant_name and issue.reports_to_name:
        message = (
            f'Managerul "{issue.reports_to_name}" nu a fost găsit în roster pentru '
            f"{issue.participant_name}."
        )
    elif issue.code == "manager_self_reference" and issue.participant_name:
        message = f"{issue.participant_name} este setat ca propriul manager."
    else:
        message = issue.message

    return ReportHierarchyIssueResponse(
        code=issue.code,
        participant_id=issue.participant_id,
        participant_name=issue.participant_name,
        reports_to_name=issue.reports_to_name,
        message=message,
    )


def _pcm_profile_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = normalize_manager_token(value).replace("_", " ")
    compact = normalized.replace(" ", "")
    return PCM_ALIASES.get(normalized) or PCM_ALIASES.get(compact)


def _format_pcm_label(value: str | None) -> str:
    key = _pcm_profile_key(value)
    if key is not None:
        return PCM_PROFILES[key][0]
    if not value:
        return "Necompletată"
    return " ".join(part.capitalize() for part in value.replace("_", " ").split())


def _get_pcm_color(value: str | None) -> str | None:
    key = _pcm_profile_key(value)
    return PCM_PROFILES[key][1] if key is not None else None
