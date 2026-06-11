import uuid

import pytest

from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
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
async def test_scoring_unsupported_key() -> None:
    repo = FakeScoringRepository()
    service = ScoringService(session=None)  # type: ignore
    service.repository = repo

    with pytest.raises(DomainError, match="has no scoring metadata"):
        await service.compute_and_save_score(
            assignment_id=uuid.uuid4(),
            questionnaire_key=QuestionnaireKey.boss_360,
            answers={},
        )


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
                            "hurry_up": 40,
                            "please_people": 50,
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

            assert aggregate.total_assigned == 4
            assert aggregate.total_completed == 4
            assert aggregate.completion_rate == 100
            assert aggregate.lencioni_count == 2
            assert aggregate.driver_count == 1
            assert {result.assignment_id for result in aggregate.results} == {
                lencioni_assignment.id,
                driver_assignment.id,
                other_project_assignment.id,
            }
            assert aggregate.lencioni_averages[0].avg == 10.5
            assert aggregate.driver_averages[1].avg == 20

            project_aggregate = await ScoringService(session).get_company_report_aggregate(
                company.id,
                project.id,
            )

            assert project_aggregate.total_assigned == 3
            assert {result.assignment_id for result in project_aggregate.results} == {
                lencioni_assignment.id,
                driver_assignment.id,
            }

            await session.rollback()
    finally:
        await engine.dispose()
