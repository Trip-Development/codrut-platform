from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from codrut.modules.assignments.models import (
    AssignmentStatus,
    QuestionnaireAssignment,
)

REMINDABLE_STATUSES = {AssignmentStatus.invited, AssignmentStatus.started}


@dataclass(frozen=True)
class ReminderPolicy:
    minimum_interval: timedelta = timedelta(days=2)


DEFAULT_REMINDER_POLICY = ReminderPolicy()


def reminder_candidates(
    assignments: list[QuestionnaireAssignment],
    *,
    now: datetime | None = None,
    policy: ReminderPolicy = DEFAULT_REMINDER_POLICY,
) -> list[QuestionnaireAssignment]:
    current_time = now or datetime.now(UTC)
    return [
        assignment
        for assignment in assignments
        if _is_reminder_candidate(assignment, current_time, policy)
    ]


def _is_reminder_candidate(
    assignment: QuestionnaireAssignment,
    now: datetime,
    policy: ReminderPolicy,
) -> bool:
    if assignment.status not in REMINDABLE_STATUSES:
        return False
    if assignment.reminder_due_at is not None and assignment.reminder_due_at > now:
        return False
    if assignment.last_reminder_sent_at is None:
        return True
    return assignment.last_reminder_sent_at + policy.minimum_interval <= now
