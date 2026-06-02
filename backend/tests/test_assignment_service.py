import uuid

import pytest

from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.assignments.schemas import AssignmentCreateRequest
from codrut.modules.assignments.service import _stamp_status_time, _validate_target_shape


def test_assignment_target_shape_accepts_self_assignment() -> None:
    _validate_target_shape(
        AssignmentCreateRequest(
            respondent_profile_id=uuid.uuid4(),
            questionnaire_key="pcm_base",
            target_type=AssignmentTargetType.self_assessment,
        )
    )


def test_assignment_target_shape_accepts_person_assignment() -> None:
    _validate_target_shape(
        AssignmentCreateRequest(
            respondent_profile_id=uuid.uuid4(),
            questionnaire_key="boss_360",
            target_type=AssignmentTargetType.person,
            target_person_id=uuid.uuid4(),
        )
    )


def test_assignment_target_shape_rejects_mismatched_target() -> None:
    with pytest.raises(DomainError, match="target does not match"):
        _validate_target_shape(
            AssignmentCreateRequest(
                respondent_profile_id=uuid.uuid4(),
                questionnaire_key="lencioni",
                target_type=AssignmentTargetType.team,
                target_person_id=uuid.uuid4(),
            )
        )


def test_stamp_status_time_sets_first_matching_timestamp_once() -> None:
    assignment = QuestionnaireAssignment(
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="pcm_base",
        target_type=AssignmentTargetType.self_assessment,
    )
    assignment.status = AssignmentStatus.started

    _stamp_status_time(assignment)
    first_started_at = assignment.started_at
    _stamp_status_time(assignment)

    assert first_started_at is not None
    assert assignment.started_at == first_started_at
