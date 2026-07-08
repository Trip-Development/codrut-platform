from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
from codrut.modules.companies.manager_matching import (
    clean_manager_reference,
    is_external_matrix_manager_label,
    manager_reference_key,
    normalize_manager_token,
)
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.forms.definitions import get_approved_questionnaire_definition
from codrut.modules.forms.models import QuestionnaireKey
from codrut.modules.scoring.models import ScoringResult
from codrut.modules.scoring.repository import ScoringRepository
from codrut.modules.scoring.schemas import (
    CompanyReportAggregateResponse,
    ReportAverageResponse,
    ReportDistributionResponse,
    ReportHierarchyIssueResponse,
    ReportTeamLensResponse,
    ScoringResultResponse,
)

LENCIONI_LABELS = {
    "absence_of_trust": "Absența încrederii (Trust)",
    "fear_of_conflict": "Teama de conflict (Conflict)",
    "lack_of_commitment": "Lipsa angajamentului (Commitment)",
    "avoidance_of_accountability": "Evitarea responsabilității (Accountability)",
    "inattention_to_results": "Neatenția la rezultate (Results)",
}

DISTRESS_DRIVER_LABELS = {
    "be_strong": "Fii Puternic (Be Strong)",
    "be_perfect": "Fii Perfect (Be Perfect)",
    "try_hard": "Străduiește-te (Try Hard)",
    "hurry_up": "Grăbește-te (Hurry Up)",
    "please_people": "Mulțumește-i pe alții (Please People)",
}

ICARE_LABELS = {
    "icare_01_dezvolta_oamenii": "Dezvoltă oamenii",
    "icare_02_conduce_prin_puterea_exemplului": "Conduce prin puterea exemplului",
    "icare_03_creeaza_un_mediu_care_stimuleaza_implicarea": (
        "Creează un mediu care stimulează implicarea"
    ),
    "icare_04_promotor_al_colaborarii": "Promotor al colaborării",
    "icare_05_ancorat_in_realitate": "Ancorat în realitate",
    "icare_06_aduce_claritate": "Aduce claritate",
    "icare_07_modestie": "Modestie",
    "icare_08_inteligenta_emotionala_si_situationala": (
        "Inteligență emoțională și situațională"
    ),
    "icare_09_deschis_catre_lume": "Deschis către lume",
    "icare_10_ambitios_pentru_companie": "Ambițios pentru companie",
    "icare_11_grija_egala_pentru_angajati_si_clienti": (
        "Grijă egală pentru angajați și clienți"
    ),
    "icare_12_agilitate_antreprenoriala": "Agilitate antreprenorială",
    "icare_13_decizii_cat_mai_aproape_de_teren": "Decizii cât mai aproape de teren",
    "icare_14_cultiva_inteligenta_colectiva": "Cultivă inteligența colectivă",
    "icare_15_ajuta_echipa": "Ajută echipa",
}

LENCIONI_INTERPRETATION_RANGES = (
    (8.0, 9.0, "8-9", "Disfuncția probabil nu este o problemă."),
    (6.0, 7.99, "6-7", "Disfuncția poate fi o problemă."),
    (3.0, 5.99, "3-5", "Disfuncția trebuie probabil abordată."),
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

        assignment_results = await self.repository.list_company_assignment_results(
            company_id,
            project_id,
        )
        participants = await self._list_report_participants(company_id, project_id)
        assignments = [assignment for assignment, _result in assignment_results]
        total_assigned = len(assignment_results)
        total_completed = sum(
            1
            for assignment, _result in assignment_results
            if assignment.status in COMPLETED_STATUSES
        )
        results: list[ScoringResultResponse] = []

        for assignment, result in assignment_results:
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
            try:
                definition = get_approved_questionnaire_definition(questionnaire_key)
            except KeyError as e:
                raise DomainError(
                    f"No scoring definition for key: {key_value}",
                    code="scoring_not_supported",
                ) from e
            definition_schema = definition.schema

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
            for driver in drivers:
                scores[driver["id"]] = 0

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

            if scores:
                highest_driver = max(scores.keys(), key=lambda k: scores[k])
                primary_result = highest_driver

        elif method == "average_statement_scores_by_section":
            scale_min = float(scoring_meta.get("scale_min", 1))
            scale_max = float(scoring_meta.get("scale_max", 5))
            score_unit = scoring_meta.get("score_unit", "percent")
            score_min = float(scoring_meta.get("score_min", scale_min))
            score_range = max(scale_max - score_min, 1.0)

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
                if key in ICARE_LABELS
                and isinstance(value, dict)
                and value.get("answered", 0) > 0
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


def _zero_record(labels: dict[str, str]) -> dict[str, float]:
    return dict.fromkeys(labels, 0.0)


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


def _add_scores(sums: dict[str, float], scores: dict[str, Any]) -> bool:
    found_score = False
    for key in sums:
        score = _coerce_score(scores.get(key))
        if score is None:
            continue
        sums[key] += score
        found_score = True
    return found_score


def _averages_from_sums(
    sums: dict[str, float],
    labels: dict[str, str],
    count: int,
    *,
    minimum_avg: float | None = None,
    interpretation_fn: Callable[[float], tuple[str, str]] | None = None,
) -> list[ReportAverageResponse]:
    averages: list[ReportAverageResponse] = []
    for key, total in sums.items():
        avg = round((total / count) if count > 0 else 0, 1)
        if minimum_avg is not None and avg < minimum_avg:
            continue
        interpretation = interpretation_fn(avg) if interpretation_fn is not None else None
        averages.append(
            ReportAverageResponse(
                id=key,
                label=labels.get(key, key),
                avg=avg,
                interpretation=interpretation[0] if interpretation is not None else None,
                range_label=interpretation[1] if interpretation is not None else None,
            )
        )
    return averages


def _lencioni_interpretation(score: float) -> tuple[str, str]:
    for minimum, maximum, range_label, label in LENCIONI_INTERPRETATION_RANGES:
        if minimum <= score <= maximum:
            return label, range_label
    if score < 3:
        return "Scor sub intervalul de referință Lencioni.", "<3"
    return "Scor peste intervalul de referință Lencioni.", ">9"


def _distress_driver_interpretation(score: float) -> tuple[str, str] | None:
    if score <= 50:
        return None
    return "Driver prezent peste pragul de atenție; merită explorat în debrief.", ">50"


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
    assignment_results: Iterable[tuple[QuestionnaireAssignment, ScoringResult | None]],
) -> ScoreSummary:
    lencioni_sums = _zero_record(LENCIONI_LABELS)
    driver_sums = _zero_record(DISTRESS_DRIVER_LABELS)
    boss_360_sums = _zero_record(ICARE_LABELS)
    lencioni_count = 0
    driver_count = 0
    boss_360_count = 0

    for assignment, result in assignment_results:
        if assignment.status not in COMPLETED_STATUSES or result is None:
            continue
        if assignment.questionnaire_key in LENCIONI_REPORT_KEYS:
            if _add_scores(lencioni_sums, result.scores):
                lencioni_count += 1
        elif assignment.questionnaire_key in DISTRESS_DRIVER_REPORT_KEYS:
            if _add_scores(driver_sums, result.scores):
                driver_count += 1
        elif assignment.questionnaire_key in BOSS_360_REPORT_KEYS:
            if _add_scores(boss_360_sums, result.scores):
                boss_360_count += 1

    return ScoreSummary(
        lencioni_count=lencioni_count,
        driver_count=driver_count,
        boss_360_count=boss_360_count,
        lencioni_averages=_averages_from_sums(
            lencioni_sums,
            LENCIONI_LABELS,
            lencioni_count,
            interpretation_fn=_lencioni_interpretation,
        ),
        driver_averages=_averages_from_sums(
            driver_sums,
            DISTRESS_DRIVER_LABELS,
            driver_count,
            interpretation_fn=_distress_driver_interpretation,
        ),
        boss_360_averages=_averages_from_sums(
            boss_360_sums,
            ICARE_LABELS,
            boss_360_count,
        ),
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
    assignment_results: list[tuple[QuestionnaireAssignment, ScoringResult | None]],
) -> TeamLensBuildResult:
    ambiguous_name = _find_ambiguous_referenced_name(participants)
    if ambiguous_name is not None:
        message = (
            f'Numele "{ambiguous_name}" apare de mai multe ori în roster și este folosit '
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
    participant_by_name = {
        manager_reference_key(participant.full_name): participant
        for participant in participants
        if manager_reference_key(participant.full_name)
        and not is_external_matrix_manager_label(participant.full_name)
    }
    teams_by_id: dict[str, tuple[str, set[UUID]]] = {}
    direct_reports_by_manager_id: dict[UUID, list[ReportParticipant]] = {}
    root_ids: set[UUID] = set()
    manager_ids: set[UUID] = set()
    hierarchy_issues: list[ReportHierarchyIssueResponse] = []

    for participant in participants:
        manager_name = clean_manager_reference(participant.reports_to_name)
        manager = (
            participant_by_name.get(manager_reference_key(manager_name))
            if manager_name is not None
            else None
        )
        if manager_name is None:
            root_ids.add(participant.id)
            continue
        if manager is None:
            root_ids.add(participant.id)
            hierarchy_issues.append(
                ReportHierarchyIssueResponse(
                    code="manager_unresolved",
                    participant_id=participant.id,
                    participant_name=participant.full_name,
                    reports_to_name=manager_name,
                    message=(
                        f'Managerul "{manager_name}" nu a fost găsit în roster pentru '
                        f"{participant.full_name}."
                    ),
                )
            )
            continue
        if manager.id == participant.id:
            root_ids.add(participant.id)
            hierarchy_issues.append(
                ReportHierarchyIssueResponse(
                    code="manager_self_reference",
                    participant_id=participant.id,
                    participant_name=participant.full_name,
                    reports_to_name=manager_name,
                    message=f"{participant.full_name} este setat ca propriul manager.",
                )
            )
            continue

        manager_ids.add(manager.id)
        direct_reports = direct_reports_by_manager_id.get(manager.id, [])
        direct_reports.append(participant)
        direct_reports_by_manager_id[manager.id] = direct_reports

    for manager_id in manager_ids:
        manager = participant_by_id.get(manager_id)
        if manager is None:
            continue
        direct_reports = direct_reports_by_manager_id.get(manager.id, [])
        root_leadership_manager = bool(root_ids) and manager.id in root_ids and any(
            item.id in manager_ids for item in direct_reports
        )
        if root_leadership_manager and all(item.id in manager_ids for item in direct_reports):
            continue

        team_id = f"manager:{manager.id}"
        teams_by_id[team_id] = (
            f"Echipa {manager.full_name}",
            {manager.id, *[direct_report.id for direct_report in direct_reports]},
        )

    leadership_ids = set(root_ids)
    for root_id in root_ids:
        for direct_report in direct_reports_by_manager_id.get(root_id, []):
            if _is_manager_like_participant(direct_report, manager_ids):
                leadership_ids.add(direct_report.id)

    if len(leadership_ids) > 1 or len(root_ids) > 1:
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
    assignment_results: list[tuple[QuestionnaireAssignment, ScoringResult | None]],
) -> ReportTeamLensResponse:
    team_assignment_results = [
        (assignment, result)
        for assignment, result in assignment_results
        if assignment.respondent_profile_id in member_ids
    ]
    team_assignments = [assignment for assignment, _result in team_assignment_results]
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


def _is_manager_like_participant(
    participant: ReportParticipant,
    manager_ids: set[UUID],
) -> bool:
    role = participant.role_group.strip().casefold() if participant.role_group else ""
    return (
        participant.id in manager_ids
        or role in {"manager", "leadership"}
        or participant.user_id is not None
    )


def _find_ambiguous_referenced_name(participants: list[ReportParticipant]) -> str | None:
    names: dict[str, tuple[str, int]] = {}
    for participant in participants:
        label = participant.full_name.strip()
        if is_external_matrix_manager_label(label):
            continue
        key = manager_reference_key(label)
        if not key:
            continue
        existing = names.get(key)
        names[key] = (existing[0] if existing else label, (existing[1] if existing else 0) + 1)

    referenced_manager_keys = {
        manager_reference_key(manager_name)
        for manager_name in (
            clean_manager_reference(participant.reports_to_name) for participant in participants
        )
        if manager_name
    }
    for key, (label, count) in names.items():
        if count > 1 and key in referenced_manager_keys:
            return label
    return None


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
