import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, text

from codrut.contracts.emails import (
    EmailAddress,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
    EmailSendResult,
)
from codrut.core.config import Settings
from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.communications.models import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
    EmailEvent,
    EmailEventType,
    EmailSend,
    EmailSendStatus,
    EmailSuppression,
)
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.service import (
    EmailOutboxProcessor,
    _email_outbox_payload,
    _email_outbox_payload_fingerprint,
    _email_outbox_retry_delay,
    _require_matching_email_send_payload,
)
from codrut.modules.communications.suppression import email_suppression_fingerprint
from codrut.modules.companies.models import Company, ParticipantProfile
from codrut.modules.forms import models as form_models  # noqa: F401
from codrut.modules.identity import models as identity_models  # noqa: F401
from codrut.modules.identity.models import User, UserRole

EARLY_DUE_AT = datetime(2000, 1, 1, tzinfo=UTC)


class AcceptingProvider:
    key = EmailProviderKey.test

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> EmailSendResult:
        self.messages.append(message)
        return EmailSendResult(
            provider=self.key,
            status=EmailDeliveryStatus.accepted,
            message_id=f"provider:{len(self.messages)}",
            recipient=message.to,
        )


class FailingProvider:
    key = EmailProviderKey.test

    async def send(self, message: EmailMessage) -> EmailSendResult:
        return EmailSendResult(
            provider=self.key,
            status=EmailDeliveryStatus.failed,
            message_id="provider:failed",
            recipient=message.to,
            error_details="Temporary provider failure.",
        )


def outbox_payload(*, subject: str = "Salut") -> dict[str, object]:
    return _email_outbox_payload(
        EmailMessage(
            to=EmailAddress("ana@example.com"),
            subject=subject,
            html_body="<p>Mesaj</p>",
            text_body="Mesaj",
        )
    )


def outbox_send(
    *,
    key: str | None = None,
    payload: dict[str, object] | None = None,
    campaign_id: uuid.UUID | None = None,
    campaign_recipient_id: uuid.UUID | None = None,
    status: EmailSendStatus = EmailSendStatus.queued,
    attempt_count: int = 0,
    lease_expires_at: datetime | None = None,
    owner_id: uuid.UUID | None = None,
    sandbox_required: bool = False,
) -> EmailSend:
    message_payload = payload or outbox_payload()
    return EmailSend(
        id=uuid.uuid4(),
        owner_id=owner_id,
        campaign_id=campaign_id,
        campaign_recipient_id=campaign_recipient_id,
        recipient_email="ana@example.com",
        template_key="campaign",
        template_version=1,
        provider="test",
        idempotency_key=key or uuid.uuid4().hex,
        payload_fingerprint=_email_outbox_payload_fingerprint(message_payload),
        message_payload=message_payload,
        sandbox_required=sandbox_required,
        attempt_count=attempt_count,
        max_attempts=5,
        next_attempt_at=EARLY_DUE_AT if status == EmailSendStatus.queued else None,
        lease_token=str(uuid.uuid4()) if status == EmailSendStatus.dispatching else None,
        lease_expires_at=lease_expires_at,
        status=status,
        last_event_at=EARLY_DUE_AT,
    )


async def cleanup_send(send_id: uuid.UUID) -> None:
    async with SessionLocal() as session:
        await session.execute(delete(EmailSend).where(EmailSend.id == send_id))
        await session.commit()
    await engine.dispose()


async def test_duplicate_enqueue_returns_existing_outbox_row() -> None:
    key = uuid.uuid4().hex
    first = outbox_send(key=key)
    replay = outbox_send(key=key, payload=first.message_payload)
    try:
        async with SessionLocal() as session:
            repository = CommunicationsRepository(session)
            stored, created = await repository.enqueue_email_send(first)
            await session.commit()
            replayed, replay_created = await repository.enqueue_email_send(replay)

            assert created is True
            assert replay_created is False
            assert replayed.id == stored.id
    finally:
        await cleanup_send(first.id)


async def test_payload_conflict_is_rejected_for_existing_idempotency_key() -> None:
    original = outbox_send()

    with pytest.raises(DomainError) as exc_info:
        _require_matching_email_send_payload(
            original,
            _email_outbox_payload_fingerprint(outbox_payload(subject="Alt subiect")),
        )

    assert exc_info.value.code == "email_send_idempotency_payload_conflict"


def test_retry_backoff_is_exponential_and_bounded() -> None:
    assert _email_outbox_retry_delay(1) == timedelta(seconds=30)
    assert _email_outbox_retry_delay(2) == timedelta(seconds=60)
    assert _email_outbox_retry_delay(20) == timedelta(minutes=15)


async def test_claim_exclusivity_skips_rows_locked_by_another_worker() -> None:
    send = outbox_send()
    try:
        async with SessionLocal() as setup_session:
            await CommunicationsRepository(setup_session).enqueue_email_send(send)
            await setup_session.commit()

        first_session = SessionLocal()
        second_session = SessionLocal()
        try:
            first_claim = await CommunicationsRepository(first_session).claim_due_email_sends(
                now=datetime.now(UTC),
                lease_duration=timedelta(minutes=5),
                limit=1,
            )
            second_claim = await CommunicationsRepository(second_session).claim_due_email_sends(
                now=datetime.now(UTC),
                lease_duration=timedelta(minutes=5),
                limit=1,
            )

            assert [row.id for row in first_claim] == [send.id]
            assert second_claim == []
        finally:
            await first_session.rollback()
            await second_session.rollback()
            await first_session.close()
            await second_session.close()
    finally:
        await cleanup_send(send.id)


async def test_stale_dispatch_lease_is_recovered() -> None:
    send = outbox_send(
        status=EmailSendStatus.dispatching,
        attempt_count=1,
        lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    try:
        async with SessionLocal() as session:
            session.add(send)
            await session.commit()
            claimed = await CommunicationsRepository(session).claim_due_email_sends(
                now=datetime.now(UTC),
                lease_duration=timedelta(minutes=5),
                limit=1,
            )
            await session.commit()

            assert [row.id for row in claimed] == [send.id]
            assert claimed[0].attempt_count == 2
            assert claimed[0].lease_expires_at > datetime.now(UTC)
    finally:
        await cleanup_send(send.id)


async def test_exhausted_stale_lease_fails_and_reconciles_campaign() -> None:
    campaign = Campaign(
        id=uuid.uuid4(),
        name=f"Exhausted lease {uuid.uuid4()}",
        status=CampaignStatus.ready,
        subject="Salut",
        html_body="<p>Mesaj</p>",
        text_body="Mesaj",
    )
    accepted_send = outbox_send(
        campaign_id=campaign.id,
        status=EmailSendStatus.accepted,
    )
    exhausted_send = outbox_send(
        campaign_id=campaign.id,
        status=EmailSendStatus.dispatching,
        attempt_count=5,
        lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    provider = AcceptingProvider()
    try:
        async with SessionLocal() as session:
            session.add_all([campaign, accepted_send, exhausted_send])
            await session.commit()

            result = await EmailOutboxProcessor(session, provider).process_due(limit=1)
            stored_send = await session.get(EmailSend, exhausted_send.id)
            stored_campaign = await session.get(Campaign, campaign.id)

            assert result.failed == 1
            assert result.claimed == 0
            assert stored_send is not None
            assert stored_send.status == EmailSendStatus.failed
            assert stored_send.next_attempt_at is None
            assert stored_campaign is not None
            assert stored_campaign.status == CampaignStatus.completed
            assert provider.messages == []
    finally:
        async with SessionLocal() as session:
            await session.execute(
                delete(EmailSend).where(EmailSend.id.in_((accepted_send.id, exhausted_send.id)))
            )
            await session.execute(delete(Campaign).where(Campaign.id == campaign.id))
            await session.commit()
        await engine.dispose()


async def test_provider_failure_schedules_bounded_retry() -> None:
    send = outbox_send()
    try:
        async with SessionLocal() as session:
            await CommunicationsRepository(session).enqueue_email_send(send)
            await session.commit()

            result = await EmailOutboxProcessor(session, FailingProvider()).process_due(limit=1)
            stored = await session.get(EmailSend, send.id)
            events = await session.execute(
                select(EmailEvent.event_type).where(EmailEvent.email_send_id == send.id)
            )

            assert result.retried == 1
            assert stored is not None
            assert stored.status == EmailSendStatus.queued
            assert stored.attempt_count == 1
            assert stored.next_attempt_at is not None
            assert stored.next_attempt_at <= datetime.now(UTC) + timedelta(seconds=31)
            assert EmailEventType.retry_scheduled in set(events.scalars().all())
    finally:
        await cleanup_send(send.id)


async def test_provider_acceptance_completes_same_outbox_row() -> None:
    send = outbox_send(sandbox_required=True)
    provider = AcceptingProvider()
    try:
        async with SessionLocal() as session:
            await CommunicationsRepository(session).enqueue_email_send(send)
            await session.commit()

            result = await EmailOutboxProcessor(session, provider).process_due(limit=1)
            stored = await session.get(EmailSend, send.id)

            assert result.accepted == 1
            assert stored is not None
            assert stored.status == EmailSendStatus.accepted
            assert stored.provider_message_id == "provider:1"
            assert stored.lease_token is None
            assert [message.subject for message in provider.messages] == ["Salut"]
            assert provider.messages[0].provider_sandbox is True
    finally:
        await cleanup_send(send.id)


async def test_forged_cross_owner_campaign_send_never_reaches_provider() -> None:
    owner_a = User(
        id=uuid.uuid4(),
        email=f"trainer-a-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",  # noqa: S106
        role=UserRole.trainer,
    )
    owner_b = User(
        id=uuid.uuid4(),
        email=f"trainer-b-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",  # noqa: S106
        role=UserRole.trainer,
    )
    campaign = Campaign(
        id=uuid.uuid4(),
        owner_id=owner_b.id,
        name=f"Cross-owner campaign {uuid.uuid4()}",
        status=CampaignStatus.ready,
        subject="Salut",
        html_body="<p>Mesaj</p>",
        text_body="Mesaj",
    )
    recipient_id = uuid.uuid4()
    send = outbox_send(
        owner_id=owner_a.id,
        campaign_id=campaign.id,
        campaign_recipient_id=recipient_id,
    )
    provider = AcceptingProvider()
    try:
        async with SessionLocal() as session:
            session.add_all([owner_a, owner_b])
            await session.flush()
            session.add(campaign)
            await session.flush()
            await session.execute(
                text(
                    "insert into campaign_recipients "
                    "(id, owner_id, email, contact_name, segment, status, "
                    "created_at, updated_at) "
                    "values (:id, :owner_id, :email, :contact_name, "
                    "cast(:segment as campaignrecipientsegment), "
                    "cast(:status as campaignrecipientstatus), :now, :now)"
                ),
                {
                    "id": recipient_id,
                    "owner_id": owner_a.id,
                    "email": "ana@example.com",
                    "contact_name": "Ana",
                    "segment": CampaignRecipientSegment.potential_customer.value,
                    "status": CampaignRecipientStatus.active.value,
                    "now": datetime.now(UTC),
                },
            )
            await CommunicationsRepository(session).enqueue_email_send(send)
            await session.commit()

            result = await EmailOutboxProcessor(session, provider).process_due(limit=1)
            stored = await session.get(EmailSend, send.id)

            assert result.claimed == 1
            assert result.cancelled == 1
            assert stored is not None
            assert stored.status == EmailSendStatus.cancelled
            assert stored.error_details == (
                "Campaign, contact, and queued delivery ownership do not match."
            )
            assert stored.provider_request_started_at is None
            assert stored.provider_idempotency_key is None
            assert provider.messages == []
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(EmailSend).where(EmailSend.id == send.id))
            await session.execute(delete(Campaign).where(Campaign.id == campaign.id))
            await session.execute(
                delete(CampaignRecipient).where(CampaignRecipient.id == recipient_id)
            )
            await session.execute(
                delete(User).where(User.id.in_((owner_a.id, owner_b.id)))
            )
            await session.commit()
        await engine.dispose()


async def test_concurrent_final_sends_complete_campaign_after_both_commit() -> None:
    await engine.dispose()
    owner = User(
        id=uuid.uuid4(),
        email=f"trainer-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",  # noqa: S106
        role=UserRole.trainer,
    )
    campaign = Campaign(
        id=uuid.uuid4(),
        owner_id=owner.id,
        name=f"Concurrent completion {uuid.uuid4()}",
        status=CampaignStatus.ready,
        subject="Salut",
        html_body="<p>Mesaj</p>",
        text_body="Mesaj",
    )
    sends = [
        outbox_send(
            owner_id=owner.id,
            campaign_id=campaign.id,
            status=EmailSendStatus.dispatching,
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        for _index in range(2)
    ]
    first_session = SessionLocal()
    second_session = SessionLocal()
    completion_task: asyncio.Task[None] | None = None
    try:
        async with SessionLocal() as setup_session:
            setup_session.add(owner)
            await setup_session.flush()
            setup_session.add(campaign)
            await setup_session.flush()
            setup_session.add_all(sends)
            await setup_session.commit()

        first_send = (
            await first_session.execute(
                select(EmailSend)
                .where(EmailSend.id == sends[0].id)
                .with_for_update()
            )
        ).scalar_one()
        second_send = (
            await second_session.execute(
                select(EmailSend)
                .where(EmailSend.id == sends[1].id)
                .with_for_update()
            )
        ).scalar_one()
        first_send.status = EmailSendStatus.accepted
        second_send.status = EmailSendStatus.accepted
        await first_session.flush()
        await second_session.flush()
        second_pid = int(
            (await second_session.execute(text("select pg_backend_pid()"))).scalar_one()
        )

        await EmailOutboxProcessor(
            first_session,
            AcceptingProvider(),
        )._complete_campaign_if_idle(campaign.id)
        completion_task = asyncio.create_task(
            EmailOutboxProcessor(
                second_session,
                AcceptingProvider(),
            )._complete_campaign_if_idle(campaign.id)
        )

        observed_wait = False
        async with SessionLocal() as observer:
            for _attempt in range(500):
                wait_event_type = (
                    await observer.execute(
                        text(
                            "select wait_event_type from pg_stat_activity "
                            "where pid = :backend_pid"
                        ),
                        {"backend_pid": second_pid},
                    )
                ).scalar_one_or_none()
                if wait_event_type == "Lock":
                    observed_wait = True
                    break
                if completion_task.done():
                    await completion_task
                    raise AssertionError(
                        "the completion check finished before waiting for the campaign row"
                    )
                await asyncio.sleep(0.01)
        assert observed_wait, "the second completion check must wait for the campaign row"

        await first_session.commit()
        await asyncio.wait_for(completion_task, timeout=10)
        await second_session.commit()

        async with SessionLocal() as verification_session:
            stored_campaign = await verification_session.get(Campaign, campaign.id)
            assert stored_campaign is not None
            assert stored_campaign.status == CampaignStatus.completed
    finally:
        if completion_task is not None and not completion_task.done():
            completion_task.cancel()
            await asyncio.gather(completion_task, return_exceptions=True)
        await first_session.rollback()
        await second_session.rollback()
        await first_session.close()
        await second_session.close()
        async with SessionLocal() as cleanup_session:
            await cleanup_session.execute(
                delete(EmailSend).where(
                    EmailSend.id.in_((sends[0].id, sends[1].id))
                )
            )
            await cleanup_session.execute(
                delete(Campaign).where(Campaign.id == campaign.id)
            )
            await cleanup_session.execute(delete(User).where(User.id == owner.id))
            await cleanup_session.commit()
        await engine.dispose()


async def test_stale_started_provider_request_becomes_indeterminate_without_replay() -> None:
    send = outbox_send(
        status=EmailSendStatus.dispatching,
        attempt_count=1,
        lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    send.provider_request_started_at = datetime.now(UTC) - timedelta(minutes=6)
    send.provider_idempotency_key = str(uuid.uuid4())
    provider = AcceptingProvider()
    try:
        async with SessionLocal() as session:
            session.add(send)
            await session.commit()

            result = await EmailOutboxProcessor(session, provider).process_due(limit=1)
            stored = await session.get(EmailSend, send.id)

            assert result.indeterminate == 1
            assert result.claimed == 0
            assert stored is not None
            assert stored.status == EmailSendStatus.indeterminate
            assert stored.next_attempt_at is None
            assert provider.messages == []
    finally:
        await cleanup_send(send.id)


async def test_provider_acceptance_db_failure_is_not_replayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send = outbox_send()
    send_id = send.id
    provider = AcceptingProvider()
    try:
        async with SessionLocal() as session:
            await CommunicationsRepository(session).enqueue_email_send(send)
            await session.commit()
            real_commit = session.commit
            commit_count = 0

            async def fail_acceptance_commit_once() -> None:
                nonlocal commit_count
                commit_count += 1
                if commit_count == 3:
                    raise RuntimeError("simulated accepted-send persistence failure")
                await real_commit()

            monkeypatch.setattr(session, "commit", fail_acceptance_commit_once)

            first = await EmailOutboxProcessor(session, provider).process_due(limit=1)
            second = await EmailOutboxProcessor(session, provider).process_due(limit=1)
            stored = await session.get(EmailSend, send_id)

            assert first.indeterminate == 1
            assert second.claimed == 0
            assert len(provider.messages) == 1
            assert provider.messages[0].provider_idempotency_key is not None
            assert stored is not None
            assert stored.status == EmailSendStatus.indeterminate
            assert stored.provider_message_id == "provider:1"
            assert stored.provider_idempotency_key == (
                provider.messages[0].provider_idempotency_key
            )
    finally:
        await cleanup_send(send_id)


async def test_provider_retry_after_delays_next_attempt() -> None:
    class RateLimitedProvider:
        key = EmailProviderKey.test

        async def send(self, message: EmailMessage) -> EmailSendResult:
            return EmailSendResult(
                provider=self.key,
                status=EmailDeliveryStatus.failed,
                message_id="provider:rate-limited",
                recipient=message.to,
                error_details="Rate limited",
                retryable=True,
                retry_after_seconds=180,
            )

    send = outbox_send()
    started_at = datetime.now(UTC)
    try:
        async with SessionLocal() as session:
            await CommunicationsRepository(session).enqueue_email_send(send)
            await session.commit()

            result = await EmailOutboxProcessor(session, RateLimitedProvider()).process_due(
                limit=1
            )
            stored = await session.get(EmailSend, send.id)

            assert result.retried == 1
            assert stored is not None
            assert stored.status == EmailSendStatus.queued
            assert stored.next_attempt_at is not None
            assert stored.next_attempt_at >= started_at + timedelta(seconds=180)
    finally:
        await cleanup_send(send.id)


async def test_owner_suppression_blocks_only_that_owners_delivery() -> None:
    owner_a = User(
        id=uuid.uuid4(),
        email=f"trainer-a-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",  # noqa: S106
        role=UserRole.trainer,
    )
    owner_b = User(
        id=uuid.uuid4(),
        email=f"trainer-b-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",  # noqa: S106
        role=UserRole.trainer,
    )
    suppressed_send = outbox_send(owner_id=owner_a.id)
    permitted_send = outbox_send(owner_id=owner_b.id)
    provider = AcceptingProvider()
    try:
        async with SessionLocal() as session:
            session.add_all([owner_a, owner_b])
            await session.flush()
            session.add(
                EmailSuppression(
                    owner_id=owner_a.id,
                    email_fingerprint=email_suppression_fingerprint(
                        owner_id=owner_a.id,
                        email="ANA@example.com",
                        secret=Settings().effective_email_suppression_fingerprint_secret,
                    ),
                    reason="hard_bounce",
                    review_after=datetime.now(UTC) + timedelta(days=365),
                )
            )
            await CommunicationsRepository(session).enqueue_email_send(suppressed_send)
            await CommunicationsRepository(session).enqueue_email_send(permitted_send)
            await session.commit()

            result = await EmailOutboxProcessor(session, provider).process_due(limit=10)
            stored_suppressed = await session.get(EmailSend, suppressed_send.id)
            stored_permitted = await session.get(EmailSend, permitted_send.id)

            assert result.cancelled == 1
            assert result.accepted == 1
            assert stored_suppressed is not None
            assert stored_suppressed.status == EmailSendStatus.cancelled
            assert stored_permitted is not None
            assert stored_permitted.status == EmailSendStatus.accepted
            assert len(provider.messages) == 1
    finally:
        async with SessionLocal() as session:
            await session.execute(
                delete(EmailSuppression).where(
                    EmailSuppression.owner_id.in_((owner_a.id, owner_b.id))
                )
            )
            await session.execute(
                delete(EmailSend).where(
                    EmailSend.id.in_((suppressed_send.id, permitted_send.id))
                )
            )
            await session.execute(delete(User).where(User.id.in_((owner_a.id, owner_b.id))))
            await session.commit()
        await engine.dispose()


async def test_campaign_cancellation_prevents_provider_dispatch() -> None:
    campaign = Campaign(
        id=uuid.uuid4(),
        name=f"Cancellation {uuid.uuid4()}",
        status=CampaignStatus.ready,
        subject="Salut",
        html_body="<p>Mesaj</p>",
        text_body="Mesaj",
    )
    send = outbox_send(campaign_id=campaign.id)
    provider = AcceptingProvider()
    try:
        async with SessionLocal() as session:
            session.add(campaign)
            await session.flush()
            await CommunicationsRepository(session).enqueue_email_send(send)
            await session.commit()

            cancelled = await CommunicationsRepository(session).cancel_queued_campaign_sends(
                campaign.id,
                now=datetime.now(UTC),
            )
            await session.commit()
            result = await EmailOutboxProcessor(session, provider).process_due(limit=1)
            stored = await session.get(EmailSend, send.id)

            assert cancelled == 1
            assert result.claimed == 0
            assert stored is not None
            assert stored.status == EmailSendStatus.cancelled
            assert provider.messages == []
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(EmailSend).where(EmailSend.id == send.id))
            await session.execute(delete(Campaign).where(Campaign.id == campaign.id))
            await session.commit()
        await engine.dispose()


async def test_provider_acceptance_advances_reminder_round_once(
    questionnaire_definition_factory,
) -> None:
    company = Company(id=uuid.uuid4(), name=f"Reminder company {uuid.uuid4()}")
    participant = ParticipantProfile(
        id=uuid.uuid4(),
        company_id=company.id,
        email=f"reminder-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Ana Reminder",
    )
    definition = questionnaire_definition_factory("lencioni")
    assignment = QuestionnaireAssignment(
        id=uuid.uuid4(),
        company_id=company.id,
        respondent_profile_id=participant.id,
        questionnaire_key="lencioni",
        questionnaire_definition_id=definition.id,
        target_type=AssignmentTargetType.self_assessment,
        status=AssignmentStatus.invited,
        reminder_count=0,
    )
    payload = _email_outbox_payload(
        EmailMessage(
            to=EmailAddress(participant.email or "ana@example.com"),
            subject="Reminder",
            html_body="<p>Continuă</p>",
            text_body="Continuă",
        ),
        assignment_ids=[assignment.id],
        reminder_assignment_ids=[assignment.id],
        delivery_kind="reminder",
    )
    send = outbox_send(payload=payload)
    send.assignment_id = assignment.id
    provider = AcceptingProvider()
    try:
        async with SessionLocal() as session:
            session.add_all([company, definition])
            await session.flush()
            session.add(participant)
            await session.flush()
            session.add(assignment)
            await session.flush()
            await CommunicationsRepository(session).enqueue_email_send(send)
            await session.commit()

            first = await EmailOutboxProcessor(session, provider).process_due(limit=1)
            second = await EmailOutboxProcessor(session, provider).process_due(limit=1)
            stored = await session.get(QuestionnaireAssignment, assignment.id)

            assert first.accepted == 1
            assert second.claimed == 0
            assert stored is not None
            assert stored.reminder_count == 1
            assert stored.last_reminder_sent_at is not None
            assert stored.reminder_due_at is not None
            assert stored.reminder_due_at >= stored.last_reminder_sent_at + timedelta(days=2)
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(EmailSend).where(EmailSend.id == send.id))
            await session.execute(delete(Company).where(Company.id == company.id))
            await session.execute(
                delete(form_models.QuestionnaireDefinition).where(
                    form_models.QuestionnaireDefinition.id == definition.id
                )
            )
            await session.commit()
        await engine.dispose()
