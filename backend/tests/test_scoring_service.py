import uuid

import pytest

from codrut.core.database import SessionLocal, engine
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.companies.models import Company, CompanyProject, ParticipantProfile
from codrut.modules.forms.models import QuestionnaireKey
from codrut.modules.identity import models as identity_models  # noqa: F401
from codrut.modules.scoring.models import ScoringResult
from codrut.modules.scoring.service import ScoringService


class FakeScoringRepository:
    def __init__(self) -> None:
        self.results: dict[uuid.UUID, ScoringResult] = {}

    async def get_by_assignment(self, assignment_id: uuid.UUID) -> ScoringResult | None:
        return self.results.get(assignment_id)

    async def add_scoring_result(self, result: ScoringResult) -> ScoringResult:
        self.results[result.assignment_id] = result
        return result

    async def delete_by_assignment(self, assignment_id: uuid.UUID) -> None:
        if assignment_id in self.results:
            del self.results[assignment_id]


@pytest.mark.asyncio
async def test_compute_and_save_score_lencioni() -> None:
    repo = FakeScoringRepository()
    service = ScoringService(session=None)  # type: ignore
    service.repository = repo

    assignment_id = uuid.uuid4()

    answers = {
        # Group absence_of_trust (q04, q06, q12) -> 3 + 3 + 2 = 8
        "lencioni_q04": 3,
        "lencioni_q06": 3,
        "lencioni_q12": 2,
        # Group fear_of_conflict (q01, q07, q10) -> 2 + 1 + 2 = 5
        "lencioni_q01": 2,
        "lencioni_q07": 1,
        "lencioni_q10": 2,
        # Group avoidance_of_accountability (q02, q11, q14) -> 3 + 3 + 3 = 9
        "lencioni_q02": 3,
        "lencioni_q11": 3,
        "lencioni_q14": 3,
        # Group lack_of_commitment (q03, q08, q13) -> 1 + 1 + 1 = 3
        "lencioni_q03": 1,
        "lencioni_q08": 1,
        "lencioni_q13": 1,
        # Group inattention_to_results (q05, q09, q15) -> 2 + 2 + 2 = 6
        "lencioni_q05": 2,
        "lencioni_q09": 2,
        "lencioni_q15": 2,
    }

    result = await service.compute_and_save_score(
        assignment_id=assignment_id,
        questionnaire_key=QuestionnaireKey.lencioni,
        answers=answers,
    )

    assert result.assignment_id == assignment_id
    assert result.scores["absence_of_trust"]["score"] == 8
    assert result.scores["absence_of_trust"]["interpretation"] == (
        "Disfuncția probabil nu este o problemă."
    )

    assert result.scores["fear_of_conflict"]["score"] == 5
    assert result.scores["fear_of_conflict"]["interpretation"] == (
        "Disfuncția trebuie probabil abordată."
    )

    assert result.scores["lack_of_commitment"]["score"] == 3
    assert result.scores["inattention_to_results"]["score"] == 6
    assert result.scores["avoidance_of_accountability"]["score"] == 9

    assert result.primary_result == "lack_of_commitment"


@pytest.mark.asyncio
async def test_compute_and_save_score_distress_drivers() -> None:
    repo = FakeScoringRepository()
    service = ScoringService(session=None)  # type: ignore
    service.repository = repo

    assignment_id = uuid.uuid4()

    # Generate a sample answer set where Be Strong gets 10 for all of its questions, others 1
    # Catalog mapping for distress drivers:
    # We can programmatically check which driver is in which question statement.
    from codrut.modules.forms.definitions.catalog import DISTRESS_DRIVERS_DEFINITION

    answers = {}
    for section in DISTRESS_DRIVERS_DEFINITION.schema.get("sections", []):
        for question in section.get("questions", []):
            q_id = question["id"]
            for statement in question.get("statements", []):
                s_id = statement["id"]
                driver = statement["scoring"]["driver"]
                answers[f"{q_id}:{s_id}"] = 10 if driver == "be_strong" else 1

    result = await service.compute_and_save_score(
        assignment_id=assignment_id,
        questionnaire_key=QuestionnaireKey.distress_drivers,
        answers=answers,
    )

    assert result.assignment_id == assignment_id
    assert result.scores["be_strong"] == 100
    assert result.scores["be_perfect"] == 10
    assert result.primary_result == "be_strong"


@pytest.mark.asyncio
async def test_compute_and_save_score_boss_360_averages_icare_sections() -> None:
    repo = FakeScoringRepository()
    service = ScoringService(session=None)  # type: ignore
    service.repository = repo

    assignment_id = uuid.uuid4()

    from codrut.modules.forms.definitions.catalog import BOSS_360_DEFINITION

    answers = {}
    for section in BOSS_360_DEFINITION.schema.get("sections", []):
        for question in section.get("questions", []):
            for statement in question.get("statements", []):
                score = 1 if section["id"] == "awareness" else 4
                answers[f"{question['id']}:{statement['id']}"] = score

    result = await service.compute_and_save_score(
        assignment_id=assignment_id,
        questionnaire_key=QuestionnaireKey.boss_360,
        answers=answers,
    )

    assert result.assignment_id == assignment_id
    assert result.scores["inspiring"] == {"score": 100.0, "raw_avg": 4.0, "answered": 9}
    assert result.scores["create_trust"] == {"score": 100.0, "raw_avg": 4.0, "answered": 9}
    assert result.scores["awareness"] == {"score": 25.0, "raw_avg": 1.0, "answered": 9}
    assert result.scores["icare_01_dezvolta_oamenii"] == {
        "score": 100.0,
        "raw_avg": 4.0,
        "answered": 3,
    }
    assert result.scores["icare_07_modestie"] == {
        "score": 25.0,
        "raw_avg": 1.0,
        "answered": 3,
    }
    assert result.primary_result == "icare_07_modestie"


async def test_company_report_aggregate_is_scoped_and_uses_only_scored_results() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            company = Company(id=uuid.uuid4(), name=f"Aggregate {uuid.uuid4().hex[:8]}")
            other_company = Company(id=uuid.uuid4(), name=f"Other Aggregate {uuid.uuid4().hex[:8]}")
            session.add_all([company, other_company])
            await session.flush()

            participant = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Ana Aggregate",
                email=f"ana-{uuid.uuid4().hex[:8]}@example.com",
            )
            other_participant = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=other_company.id,
                full_name="Other Aggregate",
                email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            )
            session.add_all([participant, other_participant])
            await session.flush()

            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership Septembrie",
            )
            other_project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Vânzări Octombrie",
            )
            session.add_all([project, other_project])
            await session.flush()

            lencioni_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=participant.id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.scored,
            )
            driver_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=participant.id,
                questionnaire_key="distress_drivers",
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.scored,
            )
            submitted_without_score = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=participant.id,
                questionnaire_key="boss_360",
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.submitted,
            )
            boss_360_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=participant.id,
                questionnaire_key="boss_360",
                target_type=AssignmentTargetType.person,
                target_person_id=participant.id,
                status=AssignmentStatus.scored,
            )
            other_company_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=other_company.id,
                respondent_profile_id=other_participant.id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.scored,
            )
            other_project_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=other_project.id,
                respondent_profile_id=participant.id,
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.scored,
            )
            session.add_all(
                [
                    lencioni_assignment,
                    driver_assignment,
                    submitted_without_score,
                    boss_360_assignment,
                    other_company_assignment,
                    other_project_assignment,
                ]
            )
            await session.flush()

            session.add_all(
                [
                    ScoringResult(
                        assignment_id=lencioni_assignment.id,
                        primary_result="absence_of_trust",
                        scores={
                            "absence_of_trust": {"score": 6},
                            "fear_of_conflict": {"score": 9},
                            "lack_of_commitment": {"score": 8},
                            "avoidance_of_accountability": {"score": 7},
                            "inattention_to_results": {"score": 5},
                        },
                    ),
                    ScoringResult(
                        assignment_id=driver_assignment.id,
                        primary_result="hurry_up",
                        scores={
                            "be_strong": 10,
                            "be_perfect": "20",
                            "try_hard": 30,
                            "hurry_up": 60,
                            "please_people": 50,
                        },
                    ),
                    ScoringResult(
                        assignment_id=boss_360_assignment.id,
                        primary_result="awareness",
                        scores={
                            "inspiring": {"score": 80},
                            "create_trust": {"score": 75},
                            "awareness": {"score": 60},
                            "results": {"score": 90},
                            "empowerment": {"score": 85},
                            "icare_01_dezvolta_oamenii": {"score": 80},
                            "icare_02_conduce_prin_puterea_exemplului": {"score": 75},
                            "icare_03_creeaza_un_mediu_care_stimuleaza_implicarea": {
                                "score": 70
                            },
                            "icare_04_promotor_al_colaborarii": {"score": 65},
                            "icare_05_ancorat_in_realitate": {"score": 60},
                            "icare_06_aduce_claritate": {"score": 55},
                            "icare_07_modestie": {"score": 50},
                            "icare_08_inteligenta_emotionala_si_situationala": {"score": 45},
                            "icare_09_deschis_catre_lume": {"score": 40},
                            "icare_10_ambitios_pentru_companie": {"score": 35},
                            "icare_11_grija_egala_pentru_angajati_si_clienti": {
                                "score": 30
                            },
                            "icare_12_agilitate_antreprenoriala": {"score": 25},
                            "icare_13_decizii_cat_mai_aproape_de_teren": {"score": 20},
                            "icare_14_cultiva_inteligenta_colectiva": {"score": 15},
                            "icare_15_ajuta_echipa": {"score": 10},
                        },
                    ),
                    ScoringResult(
                        assignment_id=other_company_assignment.id,
                        primary_result="fear_of_conflict",
                        scores={
                            "absence_of_trust": {"score": 1},
                            "fear_of_conflict": {"score": 1},
                            "lack_of_commitment": {"score": 1},
                            "avoidance_of_accountability": {"score": 1},
                            "inattention_to_results": {"score": 1},
                        },
                    ),
                    ScoringResult(
                        assignment_id=other_project_assignment.id,
                        primary_result="absence_of_trust",
                        scores={
                            "absence_of_trust": {"score": 15},
                            "fear_of_conflict": {"score": 15},
                            "lack_of_commitment": {"score": 15},
                            "avoidance_of_accountability": {"score": 15},
                            "inattention_to_results": {"score": 15},
                        },
                    ),
                ]
            )
            await session.flush()

            aggregate = await ScoringService(session).get_company_report_aggregate(company.id)

            assert aggregate.total_assigned == 5
            assert aggregate.total_completed == 5
            assert aggregate.completion_rate == 100
            assert aggregate.lencioni_count == 2
            assert aggregate.driver_count == 1
            assert aggregate.boss_360_count == 1
            assert {result.assignment_id for result in aggregate.results} == {
                lencioni_assignment.id,
                driver_assignment.id,
                boss_360_assignment.id,
                other_project_assignment.id,
            }
            assert aggregate.lencioni_averages[0].avg == 10.5
            assert [item.id for item in aggregate.driver_averages] == [
                "be_strong",
                "be_perfect",
                "try_hard",
                "hurry_up",
                "please_people",
            ]
            assert [item.avg for item in aggregate.driver_averages] == [10, 20, 30, 60, 50]
            assert aggregate.boss_360_averages[0].avg == 80
            assert aggregate.boss_360_averages[-1].id == "icare_15_ajuta_echipa"

            project_aggregate = await ScoringService(session).get_company_report_aggregate(
                company.id,
                project.id,
            )

            assert project_aggregate.total_assigned == 4
            assert {result.assignment_id for result in project_aggregate.results} == {
                lencioni_assignment.id,
                driver_assignment.id,
                boss_360_assignment.id,
            }

            await session.rollback()
    finally:
        await engine.dispose()
