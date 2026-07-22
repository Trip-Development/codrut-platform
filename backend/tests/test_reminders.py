import uuid
from datetime import UTC, datetime, timedelta

from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
from codrut.modules.communications.reminders import reminder_candidates


def _assignment(
    *,
    status: AssignmentStatus = AssignmentStatus.invited,
    reminder_count: int | None = 0,
    reminder_due_at: datetime | None = None,
    last_reminder_sent_at: datetime | None = None,
) -> QuestionnaireAssignment:
    assignment = QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        respondent_profile_id=uuid.uuid4(),
        questionnaire_key="lencioni",
        target_type="team",
        status=status,
        reminder_due_at=reminder_due_at,
        last_reminder_sent_at=last_reminder_sent_at,
    )
    assignment.reminder_count = reminder_count
    return assignment


def test_reminder_candidates_allow_only_due_invited_or_started_assignments() -> None:
    now = datetime.now(UTC)
    due_invited = _assignment(reminder_due_at=now - timedelta(seconds=1))
    due_started = _assignment(
        status=AssignmentStatus.started,
        reminder_count=1,
        last_reminder_sent_at=now - timedelta(days=3),
    )
    not_due = _assignment(reminder_due_at=now + timedelta(days=1))
    uninvited = _assignment(status=AssignmentStatus.assigned)

    assert reminder_candidates(
        [due_invited, due_started, not_due, uninvited],
        now=now,
    ) == [due_invited, due_started]


def test_reminder_candidates_stop_after_two_rounds() -> None:
    exhausted = _assignment(reminder_count=2)

    assert reminder_candidates([exhausted], now=datetime.now(UTC)) == []


def test_reminder_candidates_treat_unflushed_default_as_zero() -> None:
    assignment = _assignment(reminder_count=None)

    assert reminder_candidates([assignment], now=datetime.now(UTC)) == [assignment]
