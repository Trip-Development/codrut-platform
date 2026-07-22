from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
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
)
from codrut.modules.scoring.models import ScoringResult
from codrut.modules.scoring.repository import ScoringRepository
from codrut.modules.scoring.schemas import (
    CompanyReportAggregateResponse,
    IcareAnswerReviewResponse,
    IcareAnswerReviewRowResponse,
    ReportAverageResponse,
    ReportDistributionResponse,
    ReportHierarchyIssueResponse,
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


@dataclass(frozen=True)
class ScoreSummary:
    lencioni_count: int
    driver_count: int
    boss_360_count: int
    lencioni_averages: list[ReportAverageResponse]
    driver_averages: list[ReportAverageResponse]
    boss_360_averages: list[ReportAverageResponse]


@dataclass(frozen=True)
class TeamLensBuildResult:
    team_lenses: list[ReportTeamLensResponse]
    hierarchy_ambiguous: bool
    hierarchy_ambiguity_message: str | None
    hierarchy_issues: list[ReportHierarchyIssueResponse]


AssignmentResultWithDefinition = tuple[
    QuestionnaireAssignment,
    ScoringResult | None,
    QuestionnaireDefinition | None,
]


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
    ) -> CompanyReportAggregateResponse:
        company = await self.company_repository.get_company(company_id)
        if company is None:
            raise DomainError("Company not found.", code="company_not_found")
        if project_id is not None:
            project = await self.company_repository.get_project(company_id, project_id)
            if project is None:
                raise DomainError("Project not found in this company.", code="project_not_found")

        assignment_results = await self.repository.list_company_assignment_results_with_definitions(
            company_id,
            project_id,
        )
        participants = await self._list_report_participants(company_id, project_id)
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
        score_summary = _build_score_summary(assignment_results)
        pcm_base_distribution = _distribution_from_completed_pcm_assignments(
            participants,
            assignments,
            "pcm_base",
        )
        pcm_phase_distribution = _distribution_from_completed_pcm_assignments(
            participants,
            assignments,
            "pcm_phase",
        )
        team_lens_result = _build_team_lenses(participants, assignment_results)

        return CompanyReportAggregateResponse(
            total_assigned=total_assigned,
            total_completed=total_completed,
            completion_rate=round((total_completed / total_assigned) * 100)
            if total_assigned > 0
            else 0,
            lencioni_count=score_summary.lencioni_count,
            driver_count=score_summary.driver_count,
            boss_360_count=score_summary.boss_360_count,
            pcm_base_count=_distribution_count(pcm_base_distribution),
            pcm_phase_count=_distribution_count(pcm_phase_distribution),
            lencioni_averages=score_summary.lencioni_averages,
            driver_averages=score_summary.driver_averages,
            boss_360_averages=score_summary.boss_360_averages,
            pcm_base_distribution=pcm_base_distribution,
            pcm_phase_distribution=pcm_phase_distribution,
            team_lenses=team_lens_result.team_lenses,
            hierarchy_ambiguous=team_lens_result.hierarchy_ambiguous,
            hierarchy_ambiguity_message=team_lens_result.hierarchy_ambiguity_message,
            hierarchy_issues=team_lens_result.hierarchy_issues,
            results=results,
        )

    async def get_icare_answer_review(
        self,
        company_id: UUID,
        project_id: UUID | None = None,
    ) -> IcareAnswerReviewResponse:
        company = await self.company_repository.get_company(company_id)
        if company is None:
            raise DomainError("Company not found.", code="company_not_found")
        if project_id is not None:
            project = await self.company_repository.get_project(company_id, project_id)
            if project is None:
                raise DomainError("Project not found in this company.", code="project_not_found")

        rows: list[IcareAnswerReviewRowResponse] = []
        answer_responses = await self.repository.list_company_icare_answer_responses(
            company_id,
            project_id,
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

    async def _list_report_participants(
        self,
        company_id: UUID,
        project_id: UUID | None,
    ) -> list[ReportParticipant]:
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
        role_group=membership.role_group,
        pcm_base=participant.pcm_base,
        pcm_phase=participant.pcm_phase,
        user_id=participant.user_id,
    )


def _build_score_summary(
    assignment_results: Iterable[AssignmentResultWithDefinition],
) -> ScoreSummary:
    lencioni_dimensions: dict[str, ReportDimensionAccumulator] = {}
    driver_dimensions: dict[str, ReportDimensionAccumulator] = {}
    boss_360_dimensions: dict[str, ReportDimensionAccumulator] = {}
    lencioni_count = 0
    driver_count = 0
    boss_360_count = 0

    for assignment, result, definition in assignment_results:
        if assignment.status not in COMPLETED_STATUSES or result is None:
            continue
        if assignment.questionnaire_key in LENCIONI_REPORT_KEYS:
            if _accumulate_scores(lencioni_dimensions, result, definition):
                lencioni_count += 1
        elif assignment.questionnaire_key in DISTRESS_DRIVER_REPORT_KEYS:
            if _accumulate_scores(driver_dimensions, result, definition):
                driver_count += 1
        elif assignment.questionnaire_key in BOSS_360_REPORT_KEYS:
            if _accumulate_scores(boss_360_dimensions, result, definition):
                boss_360_count += 1

    return ScoreSummary(
        lencioni_count=lencioni_count,
        driver_count=driver_count,
        boss_360_count=boss_360_count,
        lencioni_averages=_averages_from_accumulators(lencioni_dimensions),
        driver_averages=_averages_from_accumulators(driver_dimensions),
        boss_360_averages=_averages_from_accumulators(boss_360_dimensions),
    )


def _distribution_from_completed_pcm_assignments(
    participants: list[ReportParticipant],
    assignments: list[QuestionnaireAssignment],
    field: str,
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


def _distribution_count(distribution: list[ReportDistributionResponse]) -> int:
    return sum(item.value for item in distribution)


def _build_team_lenses(
    participants: list[ReportParticipant],
    assignment_results: list[AssignmentResultWithDefinition],
) -> TeamLensBuildResult:
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
        direct_report_ids = {
            direct_report.id
            for direct_report in direct_reports
            if direct_report.id not in leadership_ids
        }
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
        _build_team_lens(team_id, name, member_ids, participants, assignment_results)
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
) -> ReportTeamLensResponse:
    team_assignment_results = [
        (assignment, result, definition)
        for assignment, result, definition in assignment_results
        if assignment.respondent_profile_id in member_ids
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
    )
    pcm_phase_distribution = _distribution_from_completed_pcm_assignments(
        team_participants,
        team_assignments,
        "pcm_phase",
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
