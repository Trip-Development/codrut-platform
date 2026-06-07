import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.models import EmailSend, EmailSendStatus
from codrut.modules.communications.service import CommunicationsService
from codrut.modules.companies.models import ParticipantProfile


class FakeScalarsResult:
    def __init__(self, val: Any = None) -> None:
        self.val = val

    def scalars(self) -> Any:
        return self

    def all(self) -> list[Any]:
        if isinstance(self.val, list):
            return self.val
        return [self.val] if self.val is not None else []


class FakeTupleResult:
    def __init__(self, rows: list[tuple]) -> None:
        self.rows = rows

    def all(self) -> list[tuple]:
        return self.rows


@pytest.mark.asyncio
async def test_get_email_ops_summary_success() -> None:
    company_id = uuid.uuid4()
    respondent_1_id = uuid.uuid4()
    respondent_2_id = uuid.uuid4()

    # 1. Profiles & Companies
    profile_1 = ParticipantProfile(
        id=respondent_1_id,
        company_id=company_id,
        user_id=uuid.uuid4(),
        full_name="Ana Pop",
        email="ana@example.com",
    )
    profile_2 = ParticipantProfile(
        id=respondent_2_id,
        company_id=company_id,
        user_id=None,
        full_name="Mihai Matei",
        email="mihai@example.com",
    )

    profiles_result = FakeTupleResult([
        (profile_1, "Compania A"),
        (profile_2, "Compania A"),
    ])

    # 2. Assignments
    assignment_1 = QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=respondent_1_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.submitted,
    )
    assignment_2 = QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=company_id,
        respondent_profile_id=respondent_2_id,
        questionnaire_key="lencioni",
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
        last_reminder_sent_at=datetime.now(UTC) - timedelta(days=3),
    )

    assignments_result = FakeScalarsResult([assignment_1, assignment_2])

    # 3. EmailSends
    send_1 = EmailSend(
        assignment_id=assignment_1.id,
        recipient_email="ana@example.com",
        template_key="account_setup",
        template_version=1,
        provider="test",
        provider_message_id="test:1",
        status=EmailSendStatus.accepted,
        created_at=datetime.now(UTC) - timedelta(days=4),
    )

    sends_result = FakeScalarsResult([send_1])

    # Setup session
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.side_effect = [
        profiles_result,
        assignments_result,
        sends_result,
    ]

    service = CommunicationsService(session)
    summary = await service.get_email_ops_summary()

    # Assert metrics
    # Invitatii trimise: 1 (send_1 exists)
    # Au intrat in app: 1 (profile_1 has user_id, profile_2 doesn't and assignments are not started)
    # Completate: 1 (profile_1 has completed 1/1 tasks)
    # Reminder azi: 1 (profile_2 has invited assignment where last reminder was 3 days ago)
    assert any(m["label"] == "Invitatii trimise" and m["value"] == "1" for m in summary["metrics"])
    assert any(m["label"] == "Au intrat in app" and m["value"] == "1" for m in summary["metrics"])
    assert any(m["label"] == "Completate" and m["value"] == "1" for m in summary["metrics"])
    assert any(m["label"] == "Reminder azi" and m["value"] == "1" for m in summary["metrics"])

    # Assert rows
    assert len(summary["assessmentRows"]) == 2
    row_1 = next(r for r in summary["assessmentRows"] if r["email"] == "ana@example.com")
    assert row_1["participant"] == "Ana Pop"
    assert row_1["audience"] == "leadership_account"
    assert row_1["tasks"] == "1/1"
    assert row_1["completion"] == "completed"
    assert row_1["delivery"] == "sent"  # EmailSendStatus.accepted mapped to "sent"
    assert row_1["reminder"] == "none"
    assert row_1["nextAction"] == "Completat"

    row_2 = next(r for r in summary["assessmentRows"] if r["email"] == "mihai@example.com")
    assert row_2["participant"] == "Mihai Matei"
    assert row_2["audience"] == "secure_link"
    assert row_2["tasks"] == "0/1"
    assert row_2["completion"] == "not_started"
    assert row_2["delivery"] == "draft"  # No EmailSend exists
    assert row_2["reminder"] == "today"
    assert row_2["nextAction"] == "Trimite reminder"
