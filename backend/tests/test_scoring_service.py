import uuid

import pytest

from codrut.core.errors import DomainError
from codrut.modules.forms.models import QuestionnaireKey
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
        "Disfunctia probabil nu este o problema."
    )

    assert result.scores["fear_of_conflict"]["score"] == 5
    assert result.scores["fear_of_conflict"]["interpretation"] == (
        "Disfunctia trebuie probabil abordata."
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

    with pytest.raises(DomainError, match="No scoring definition for key"):
        await service.compute_and_save_score(
            assignment_id=uuid.uuid4(),
            questionnaire_key=QuestionnaireKey.boss_360,
            answers={},
        )
