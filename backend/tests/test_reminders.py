import uuid
from datetime import UTC, datetime, timedelta

from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.reminders import (
    ReminderPolicy,
    reminder_candidates,
)

NOW = datetime(2026, 6, 3, tzinfo=UTC)


def make_assignment(status: AssignmentStatus) -> QuestionnaireAssignment:
    return QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.team,
        target_team_id=uuid.uuid4(),
        status=status,
    )


def test_reminder_candidates_include_invited_and_started_assignments() -> None:
    invited = make_assignment(AssignmentStatus.invited)
    started = make_assignment(AssignmentStatus.started)
    submitted = make_assignment(AssignmentStatus.submitted)

    assert reminder_candidates([invited, started, submitted], now=NOW) == [invited, started]


def test_reminder_candidates_respect_due_time() -> None:
    assignment = make_assignment(AssignmentStatus.invited)
    assignment.reminder_due_at = NOW + timedelta(hours=1)

    assert reminder_candidates([assignment], now=NOW) == []


def test_reminder_candidates_respect_minimum_interval() -> None:
    assignment = make_assignment(AssignmentStatus.invited)
    assignment.last_reminder_sent_at = NOW - timedelta(hours=12)

    result = reminder_candidates(
        [assignment],
        now=NOW,
        policy=ReminderPolicy(minimum_interval=timedelta(days=1)),
    )

    assert result == []
