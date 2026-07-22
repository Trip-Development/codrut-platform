import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.campaign_tracking import (
    CampaignTrackingClaims,
    create_campaign_tracking_token,
)
from codrut.modules.communications.models import (
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    EmailSendStatus,
)
from codrut.modules.communications.schemas import CampaignRecipientEventCreateRequest
from codrut.modules.communications.service import CommunicationsService
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.identity import models as identity_models  # noqa: F401


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


class FakeScalarOneResult:
    def __init__(self, value: Any) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Any:
        return self.value


@pytest.mark.asyncio
async def test_get_email_ops_summary_success() -> None:
    owner_id = uuid.uuid4()
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

    profiles_result = FakeTupleResult(
        [
            (profile_1, "Compania A"),
            (profile_2, "Compania A"),
        ]
    )

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

    sends_result = FakeTupleResult([("ana@example.com", EmailSendStatus.accepted)])

    # Setup session
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.side_effect = [
        profiles_result,
        assignments_result,
        sends_result,
        FakeScalarsResult([]),
        FakeTupleResult([]),
        FakeTupleResult([]),
    ]

    service = CommunicationsService(session)
    summary = await service.get_email_ops_summary(owner_id=owner_id)

    latest_send_statement = session.execute.await_args_list[2].args[0]
    latest_send_sql = str(latest_send_statement)
    assert "email_sends.owner_id =" in latest_send_sql
    assert "PARTITION BY email_sends.owner_id" in latest_send_sql

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


@pytest.mark.asyncio
async def test_get_email_ops_summary_includes_campaign_reply_and_calendly_metrics() -> None:
    owner_id = uuid.uuid4()
    recipient_id = uuid.uuid4()
    recipient = CampaignRecipient(
        id=recipient_id,
        owner_id=owner_id,
        email="ceo@example.com",
        contact_name="Ana Director",
        organization_name="Compania B",
        segment=CampaignRecipientSegment.potential_customer,
        source="excel_import",
        status=CampaignRecipientStatus.active,
    )
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.side_effect = [
        FakeTupleResult([]),
        FakeScalarsResult([]),
        FakeTupleResult([]),
        FakeScalarsResult([recipient]),
        FakeTupleResult(
            [
                (recipient_id, "opened", 1),
                (recipient_id, "clicked", 1),
                (recipient_id, "video_viewed", 1),
                (recipient_id, "calendly_clicked", 1),
                (recipient_id, "replied", 1),
            ]
        ),
        FakeTupleResult([(recipient_id, "variant_a")]),
    ]

    summary = await CommunicationsService(session).get_email_ops_summary(owner_id=owner_id)

    [row] = summary["campaign"]["recipients"]
    assert row["company"] == "Compania B"
    assert row["firstName"] == "Ana"
    assert row["lastName"] == "Director"
    assert row["clientType"] == "tip_2"
    assert row["status"] == "ready"
    assert row["openCount"] == 1
    assert row["clickCount"] == 1
    assert row["viewCount"] == 1
    assert row["replyCount"] == 1
    assert row["calendlyClickCount"] == 1
    assert row["source"] == "excel_import"
    assert row["emailVariant"] == "variant_a"
    assert "reply-uri" in summary["campaign"]["weeklyReport"]["metrics"]
    assert "clickuri Calendly" in summary["campaign"]["weeklyReport"]["metrics"]


@pytest.mark.asyncio
async def test_get_email_ops_summary_keeps_unsubscribed_campaign_status() -> None:
    owner_id = uuid.uuid4()
    recipient = CampaignRecipient(
        id=uuid.uuid4(),
        owner_id=owner_id,
        email="stop@example.com",
        contact_name="Stop Contact",
        organization_name="Compania C",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.unsubscribed,
    )

    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.side_effect = [
        FakeTupleResult([]),
        FakeScalarsResult([]),
        FakeTupleResult([]),
        FakeScalarsResult([recipient]),
        FakeTupleResult([]),
        FakeTupleResult([]),
    ]

    summary = await CommunicationsService(session).get_email_ops_summary(owner_id=owner_id)

    [row] = summary["campaign"]["recipients"]
    assert row["status"] == "unsubscribed"


@pytest.mark.asyncio
async def test_record_campaign_recipient_event_persists_allowed_event() -> None:
    owner_id = uuid.uuid4()
    recipient_id = uuid.uuid4()
    occurred_at = datetime.now(UTC)
    recipient = CampaignRecipient(
        id=recipient_id,
        owner_id=owner_id,
        email="ceo@example.com",
        contact_name="Ana Director",
        organization_name="Compania B",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.active,
    )
    session = MagicMock()
    session.execute = AsyncMock(return_value=FakeScalarOneResult(recipient))
    session.flush = AsyncMock()

    event = await CommunicationsService(session).record_campaign_recipient_event(
        recipient_id,
        CampaignRecipientEventCreateRequest(
            event_type="calendly_clicked",
            variant_key="variant_b",
            occurred_at=occurred_at,
        ),
        owner_id=owner_id,
    )

    session.add.assert_called_once()
    saved_event = session.add.call_args.args[0]
    assert saved_event.recipient_id == recipient_id
    assert saved_event.event_type == "calendly_clicked"
    assert saved_event.variant_key == "variant_b"
    assert saved_event.occurred_at == occurred_at
    assert event.recipient_id == recipient_id
    assert event.event_type == "calendly_clicked"


@pytest.mark.asyncio
async def test_record_calendly_tracking_click_persists_event_and_returns_target() -> None:
    recipient_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    recipient = CampaignRecipient(
        id=recipient_id,
        owner_id=owner_id,
        email="ceo@example.com",
        contact_name="Ana Director",
        organization_name="Compania B",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.active,
    )
    settings = Settings()
    target_url = "https://calendly.com/codrut/demo"
    token = create_campaign_tracking_token(
        CampaignTrackingClaims(
            recipient_id=recipient_id,
            owner_id=owner_id,
            target_url=target_url,
            event_type="calendly_clicked",
            variant_key="variant_b",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        ),
        settings,
    )
    session = MagicMock()
    session.execute = AsyncMock(return_value=FakeScalarOneResult(recipient))
    session.flush = AsyncMock()

    returned_url = await CommunicationsService(session).record_calendly_tracking_click(
        token,
        settings,
    )

    session.add.assert_called_once()
    saved_event = session.add.call_args.args[0]
    assert returned_url == target_url
    assert saved_event.recipient_id == recipient_id
    assert saved_event.event_type == "calendly_clicked"
    assert saved_event.variant_key == "variant_b"


@pytest.mark.asyncio
async def test_record_calendly_tracking_click_rejects_non_calendly_target() -> None:
    recipient_id = uuid.uuid4()
    settings = Settings()
    with pytest.raises(DomainError, match="Calendly URL"):
        create_campaign_tracking_token(
            CampaignTrackingClaims(
                recipient_id=recipient_id,
                owner_id=uuid.uuid4(),
                target_url="https://example.com/book",
                event_type="calendly_clicked",
                variant_key="variant_b",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            ),
            settings,
        )
