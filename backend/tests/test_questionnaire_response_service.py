import uuid
from typing import Any, cast

import pytest

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.companies import models as company_models  # noqa: F401
from codrut.modules.forms.models import QuestionnaireResponse, QuestionnaireResponseStatus
from codrut.modules.forms.schemas import QuestionnaireResponseSaveRequest
from codrut.modules.forms.service import FormsService
from codrut.modules.identity import models as identity_models  # noqa: F401


class FakeFormsRepository:
    def __init__(self, assignment: QuestionnaireAssignment | None) -> None:
        self.assignment = assignment
        self.response: QuestionnaireResponse | None = None

    async def get_assignment_for_user(
        self,
        assignment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> QuestionnaireAssignment | None:
        if self.assignment and self.assignment.id == assignment_id:
            return self.assignment
        return None

    async def get_response_by_assignment(
        self,
        assignment_id: uuid.UUID,
    ) -> QuestionnaireResponse | None:
        if self.response and self.response.assignment_id == assignment_id:
            return self.response
        return None

    async def add_response(self, response: QuestionnaireResponse) -> QuestionnaireResponse:
        response.id = uuid.uuid4()
        self.response = response
        return response


def make_service(repository: FakeFormsRepository) -> FormsService:
    service = FormsService()
    service.repository = cast(Any, repository)
    return service


def make_assignment() -> QuestionnaireAssignment:
    return QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.team,
        target_team_id=uuid.uuid4(),
        status=AssignmentStatus.assigned,
    )


def complete_lencioni_answers() -> dict[str, int]:
    return {f"lencioni_q{number:02d}": 3 for number in range(1, 16)}


async def test_save_assignment_response_creates_draft_and_starts_assignment() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))
    payload = QuestionnaireResponseSaveRequest(answers={"lencioni_q01": 3})

    response = await service.save_assignment_response(uuid.uuid4(), assignment.id, payload)

    assert response.status == QuestionnaireResponseStatus.draft
    assert response.questionnaire_key == "lencioni"
    assert response.questionnaire_version == 1
    assert response.answers == {"lencioni_q01": 3}
    assert assignment.status == AssignmentStatus.started
    assert assignment.started_at is not None


async def test_submit_assignment_response_marks_response_and_assignment_submitted() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))

    response = await service.save_assignment_response(
        uuid.uuid4(),
        assignment.id,
        QuestionnaireResponseSaveRequest(answers=complete_lencioni_answers()),
        submit=True,
    )

    assert response.status == QuestionnaireResponseStatus.submitted
    assert assignment.status == AssignmentStatus.submitted
    assert assignment.submitted_at is not None


async def test_save_assignment_response_rejects_missing_assignment() -> None:
    service = make_service(FakeFormsRepository(None))

    with pytest.raises(DomainError, match="Assignment not found"):
        await service.save_assignment_response(
            uuid.uuid4(),
            uuid.uuid4(),
            QuestionnaireResponseSaveRequest(answers={}),
        )


async def test_get_assignment_response_does_not_create_draft() -> None:
    assignment = make_assignment()
    repository = FakeFormsRepository(assignment)
    service = make_service(repository)

    res = await service.get_assignment_response(uuid.uuid4(), assignment.id)
    assert res.answers == {}
    assert res.questionnaire_key == assignment.questionnaire_key
    assert repository.response is None


async def test_submit_rejects_incomplete_required_answers() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))

    with pytest.raises(DomainError, match="missing required answers"):
        await service.save_assignment_response(
            uuid.uuid4(),
            assignment.id,
            QuestionnaireResponseSaveRequest(answers={"lencioni_q01": 3}),
            submit=True,
        )


async def test_submit_rejects_answers_outside_question_scale() -> None:
    assignment = make_assignment()
    service = make_service(FakeFormsRepository(assignment))
    answers = complete_lencioni_answers()
    answers["lencioni_q01"] = 999

    with pytest.raises(DomainError, match="outside the allowed scale"):
        await service.save_assignment_response(
            uuid.uuid4(),
            assignment.id,
            QuestionnaireResponseSaveRequest(answers=answers),
            submit=True,
        )
