import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.scoring.models import ScoringResult
from codrut.modules.scoring.router import get_assignment_scoring_result


@dataclass
class FakeQuestionnaireResponse:
    questionnaire_key: str
    questionnaire_version: int
    answers: dict[str, Any]


@dataclass
class FakeQuestionnaireDefinition:
    schema: dict[str, Any]


class FakeFormsRepository:
    response = FakeQuestionnaireResponse(
        questionnaire_key="custom_lencioni",
        questionnaire_version=7,
        answers={"custom_q01": 3},
    )
    definition = FakeQuestionnaireDefinition(
        schema={
            "scoring": {
                "method": "sum_by_group",
                "groups": [{"id": "custom_group", "question_ids": ["custom_q01"]}],
                "interpretation": [{"min": 0, "max": 9, "label": "custom"}],
            },
            "sections": [],
        }
    )

    def __init__(self, _session: object) -> None:
        return None

    async def get_response_by_assignment(
        self,
        _assignment_id: uuid.UUID,
    ) -> FakeQuestionnaireResponse:
        return self.response

    async def get_definition(
        self,
        key: str,
        *,
        version: int | None = None,
    ) -> FakeQuestionnaireDefinition | None:
        assert key == self.response.questionnaire_key
        assert version == self.response.questionnaire_version
        return self.definition


class FakeScoringService:
    last: "FakeScoringService | None" = None

    def __init__(self, _session: object) -> None:
        self.compute_kwargs: dict[str, Any] | None = None
        FakeScoringService.last = self

    async def get_result_by_assignment(self, _assignment_id: uuid.UUID) -> None:
        return None

    async def compute_and_save_score(self, **kwargs: Any) -> ScoringResult:
        self.compute_kwargs = kwargs
        return ScoringResult(
            id=uuid.uuid4(),
            assignment_id=kwargs["assignment_id"],
            scores={"custom_group": {"score": 3}},
            primary_result="custom_group",
        )


class FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_lazy_scoring_uses_response_version_and_persisted_definition_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("codrut.modules.scoring.router.FormsRepository", FakeFormsRepository)
    monkeypatch.setattr("codrut.modules.scoring.router.ScoringService", FakeScoringService)
    assignment_id = uuid.uuid4()
    session = FakeSession()

    result = await get_assignment_scoring_result(
        assignment_id,
        SessionPrincipal(
            user_id=uuid.uuid4(),
            email="trainer@example.com",
            role=UserRole.trainer,
            session_token="test-token",  # noqa: S106
        ),
        session,  # type: ignore[arg-type]
    )

    assert result.primary_result == "custom_group"
    assert session.committed is True
    assert FakeScoringService.last is not None
    assert FakeScoringService.last.compute_kwargs == {
        "assignment_id": assignment_id,
        "questionnaire_key": "custom_lencioni",
        "questionnaire_version": 7,
        "answers": {"custom_q01": 3},
        "definition_schema": FakeFormsRepository.definition.schema,
    }
