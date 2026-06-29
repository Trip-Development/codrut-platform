from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus
from codrut.modules.companies.repository import CompanyRepository
from codrut.modules.forms.definitions import get_approved_questionnaire_definition
from codrut.modules.forms.models import QuestionnaireKey
from codrut.modules.scoring.models import ScoringResult
from codrut.modules.scoring.repository import ScoringRepository
from codrut.modules.scoring.schemas import (
    CompanyReportAggregateResponse,
    ReportAverageResponse,
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
        total_assigned = len(assignment_results)
        total_completed = sum(
            1
            for assignment, _result in assignment_results
            if assignment.status in COMPLETED_STATUSES
        )
        lencioni_sums = _zero_record(LENCIONI_LABELS)
        driver_sums = _zero_record(DISTRESS_DRIVER_LABELS)
        boss_360_sums = _zero_record(ICARE_LABELS)
        lencioni_count = 0
        driver_count = 0
        boss_360_count = 0
        results: list[ScoringResultResponse] = []

        for assignment, result in assignment_results:
            if assignment.status not in COMPLETED_STATUSES or result is None:
                continue

            results.append(ScoringResultResponse.model_validate(result))
            if assignment.questionnaire_key in LENCIONI_REPORT_KEYS:
                if _add_scores(lencioni_sums, result.scores):
                    lencioni_count += 1
            elif assignment.questionnaire_key in DISTRESS_DRIVER_REPORT_KEYS:
                if _add_scores(driver_sums, result.scores):
                    driver_count += 1
            elif assignment.questionnaire_key in BOSS_360_REPORT_KEYS:
                if _add_scores(boss_360_sums, result.scores):
                    boss_360_count += 1

        return CompanyReportAggregateResponse(
            total_assigned=total_assigned,
            total_completed=total_completed,
            completion_rate=round((total_completed / total_assigned) * 100)
            if total_assigned > 0
            else 0,
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
            ),
            boss_360_averages=_averages_from_sums(
                boss_360_sums,
                ICARE_LABELS,
                boss_360_count,
            ),
            results=results,
        )

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
            scale_max = float(scoring_meta.get("scale_max", 4))
            score_min = float(scoring_meta.get("score_min", scale_min))
            score_range = max(scale_max - score_min, 1.0)

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
                percent_score = ((raw_avg - score_min) / score_range) * 100
                scores[section_id] = {
                    "score": round(percent_score, 1),
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
                    block_percent_score = ((block_raw_avg - score_min) / score_range) * 100
                    scores[question_id] = {
                        "score": round(block_percent_score, 1),
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
