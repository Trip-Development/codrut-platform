from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.assignments import models as assignment_models  # noqa: F401
from codrut.modules.communications.campaign_tracking import (
    CampaignRecipientActionClaims,
    create_campaign_recipient_action_token,
)
from codrut.modules.communications.models import (
    CampaignContactTombstone,
    CampaignDeliveryTombstone,
    CampaignRecipient,
    CampaignRecipientEvent,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    EmailEvent,
    EmailEventType,
    EmailSend,
    EmailSendStatus,
    EmailSuppression,
)
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.schemas import CampaignRecipientEventCreateRequest
from codrut.modules.communications.service import CommunicationsService
from codrut.modules.communications.suppression import (
    email_suppression_fingerprint,
    provider_event_fingerprint,
    provider_message_fingerprint,
)
from codrut.modules.companies import models as company_models  # noqa: F401
from codrut.modules.forms import models as form_models  # noqa: F401
from codrut.modules.identity import models as identity_models  # noqa: F401

OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000111")
OTHER_OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000222")
FINGERPRINT_SECRET = "contact-archive-test-secret-at-least-32-characters"  # noqa: S105
SETTINGS = Settings(
    email_suppression_fingerprint_secret=FINGERPRINT_SECRET,
    campaign_recipient_archive_retention_days=30,
    email_suppression_review_days=365,
)
PURGE_SETTINGS = Settings(
    email_suppression_fingerprint_secret=FINGERPRINT_SECRET,
    campaign_recipient_archive_retention_days=30,
    campaign_recipient_delivery_reconciliation_days=7,
    campaign_recipient_purge_enabled=True,
    email_suppression_review_days=365,
)


def recipient(
    *,
    owner_id: uuid.UUID = OWNER_ID,
    status: CampaignRecipientStatus = CampaignRecipientStatus.active,
    status_before_archive: CampaignRecipientStatus | None = None,
    archived_at: datetime | None = None,
    purge_after: datetime | None = None,
) -> CampaignRecipient:
    return CampaignRecipient(
        id=uuid.uuid4(),
        owner_id=owner_id,
        email=" Ana@Example.Test ",
        contact_name="Ana",
        organization_name="Exemplu",
        segment=CampaignRecipientSegment.potential_customer,
        status=status,
        status_before_archive=status_before_archive,
        archived_at=archived_at,
        purge_after=purge_after,
    )


def service_with(repository: object) -> CommunicationsService:
    service = CommunicationsService()
    service.repository = cast(Any, repository)
    return service


def lifecycle_repository(
    *,
    stored_recipient: CampaignRecipient | None,
    cancelled: int = 0,
    in_flight: int = 0,
    anonymized_sends: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        get_campaign_recipient=AsyncMock(return_value=stored_recipient),
        delete_campaign_recipient_memberships=AsyncMock(return_value=2),
        cancel_unsent_campaign_recipient_sends=AsyncMock(
            return_value=(cancelled, in_flight)
        ),
        list_unresolved_campaign_recipient_sends=AsyncMock(return_value=[]),
        list_campaign_recipient_sends=AsyncMock(return_value=[]),
        list_campaign_recipient_provider_event_ids=AsyncMock(return_value=[]),
        create_campaign_contact_tombstones=AsyncMock(),
        anonymize_campaign_recipient_history=AsyncMock(
            return_value=anonymized_sends
        ),
        delete_campaign_recipient_record=AsyncMock(),
        get_email_suppression=AsyncMock(return_value=None),
        suppress_email=AsyncMock(),
        flush=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_archive_is_owner_scoped_idempotent_and_reports_delivery_state() -> None:
    stored = recipient()
    repository = lifecycle_repository(
        stored_recipient=stored,
        cancelled=3,
        in_flight=1,
    )
    service = service_with(repository)

    first = await service.archive_campaign_recipient(
        stored.id,
        owner_id=OWNER_ID,
        settings=SETTINGS,
    )
    archived_at = stored.archived_at
    purge_after = stored.purge_after
    second = await service.archive_campaign_recipient(
        stored.id,
        owner_id=OWNER_ID,
        settings=SETTINGS,
    )

    assert archived_at is not None
    assert purge_after == archived_at + timedelta(days=30)
    assert stored.archived_at == archived_at
    assert stored.purge_after == purge_after
    assert stored.status == CampaignRecipientStatus.suppressed
    assert stored.status_before_archive == CampaignRecipientStatus.active
    assert (first.memberships_removed, first.cancelled, first.in_flight) == (2, 3, 1)
    assert second.recipient is stored
    repository.get_campaign_recipient.assert_awaited_with(
        stored.id,
        owner_id=OWNER_ID,
        catalog_scope="any",
        for_update=True,
    )
    repository.delete_campaign_recipient_memberships.assert_awaited_with(
        stored.id,
        owner_id=OWNER_ID,
    )
    assert repository.cancel_unsent_campaign_recipient_sends.await_count == 2
    for call in repository.cancel_unsent_campaign_recipient_sends.await_args_list:
        assert call.args == (stored.id,)
        assert call.kwargs["owner_id"] == OWNER_ID
        assert call.kwargs["now"] >= stored.archived_at


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "protected_status",
    (CampaignRecipientStatus.suppressed, CampaignRecipientStatus.unsubscribed),
)
async def test_restore_preserves_bounce_and_unsubscribe_protection(
    protected_status: CampaignRecipientStatus,
) -> None:
    archived_at = datetime.now(UTC) - timedelta(days=2)
    stored = recipient(
        status=protected_status,
        status_before_archive=protected_status,
        archived_at=archived_at,
        purge_after=archived_at + timedelta(days=30),
    )
    repository = lifecycle_repository(stored_recipient=stored)

    restored = await service_with(repository).restore_campaign_recipient(
        stored.id,
        owner_id=OWNER_ID,
        settings=SETTINGS,
    )

    assert restored.status == protected_status
    assert restored.archived_at is None
    assert restored.purge_after is None
    assert restored.status_before_archive is None
    repository.get_campaign_recipient.assert_awaited_once_with(
        stored.id,
        owner_id=OWNER_ID,
        catalog_scope="archived",
        for_update=True,
    )


@pytest.mark.asyncio
async def test_restore_recovers_active_status_from_rollback_shadow() -> None:
    archived_at = datetime.now(UTC) - timedelta(days=2)
    stored = recipient(
        status=CampaignRecipientStatus.suppressed,
        status_before_archive=CampaignRecipientStatus.active,
        archived_at=archived_at,
        purge_after=archived_at + timedelta(days=30),
    )
    repository = lifecycle_repository(stored_recipient=stored)

    restored = await service_with(repository).restore_campaign_recipient(
        stored.id,
        owner_id=OWNER_ID,
        settings=SETTINGS,
    )

    assert restored.status == CampaignRecipientStatus.active
    assert restored.archived_at is None
    assert restored.purge_after is None
    assert restored.status_before_archive is None
    repository.get_email_suppression.assert_awaited_once_with(
        owner_id=OWNER_ID,
        email_fingerprint=email_suppression_fingerprint(
            owner_id=OWNER_ID,
            email=stored.email or "",
            secret=FINGERPRINT_SECRET,
        ),
        email=stored.email,
    )


@pytest.mark.asyncio
async def test_restore_keeps_rollback_shadow_inactive_when_suppression_exists() -> None:
    archived_at = datetime.now(UTC) - timedelta(days=2)
    stored = recipient(
        status=CampaignRecipientStatus.suppressed,
        status_before_archive=CampaignRecipientStatus.active,
        archived_at=archived_at,
        purge_after=archived_at + timedelta(days=30),
    )
    repository = lifecycle_repository(stored_recipient=stored)
    repository.get_email_suppression = AsyncMock(return_value=object())

    restored = await service_with(repository).restore_campaign_recipient(
        stored.id,
        owner_id=OWNER_ID,
        settings=SETTINGS,
    )

    assert restored.status == CampaignRecipientStatus.suppressed
    assert restored.status_before_archive is None
    repository.get_email_suppression.assert_awaited_once()


@pytest.mark.asyncio
async def test_permanent_delete_is_archive_only_and_owner_scoped() -> None:
    repository = lifecycle_repository(stored_recipient=None)

    with pytest.raises(DomainError) as exc_info:
        await service_with(repository).permanently_delete_campaign_recipient(
            uuid.uuid4(),
            owner_id=OTHER_OWNER_ID,
            settings=PURGE_SETTINGS,
        )

    assert exc_info.value.code == "campaign_recipient_archive_required"
    assert (
        repository.cancel_unsent_campaign_recipient_sends.await_count == 0
    )
    assert repository.anonymize_campaign_recipient_history.await_count == 0
    assert repository.delete_campaign_recipient_record.await_count == 0


@pytest.mark.asyncio
async def test_manual_permanent_delete_is_disabled_during_expand_release() -> None:
    repository = lifecycle_repository(stored_recipient=recipient())

    with pytest.raises(DomainError) as exc_info:
        await service_with(repository).permanently_delete_campaign_recipient(
            uuid.uuid4(),
            owner_id=OWNER_ID,
            settings=SETTINGS,
        )

    assert exc_info.value.code == "campaign_recipient_purge_disabled"
    repository.get_campaign_recipient.assert_not_awaited()
    repository.delete_campaign_recipient_record.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_delete_defers_accepted_delivery_before_reconciliation_grace() -> None:
    archived_at = datetime.now(UTC) - timedelta(days=31)
    stored = recipient(
        archived_at=archived_at,
        purge_after=archived_at + timedelta(days=30),
    )
    repository = lifecycle_repository(
        stored_recipient=stored,
        cancelled=2,
    )
    recent_accepted = EmailSend(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        campaign_recipient_id=stored.id,
        recipient_email="ana@example.test",
        template_key="campaign",
        template_version=1,
        provider="brevo",
        status=EmailSendStatus.accepted,
        created_at=datetime.now(UTC) - timedelta(days=1),
        updated_at=datetime.now(UTC) - timedelta(days=1),
    )
    repository.list_unresolved_campaign_recipient_sends = AsyncMock(
        return_value=[recent_accepted]
    )

    with pytest.raises(DomainError) as exc_info:
        await service_with(repository).permanently_delete_campaign_recipient(
            stored.id,
            owner_id=OWNER_ID,
            settings=PURGE_SETTINGS,
        )

    assert exc_info.value.code == "campaign_recipient_delivery_in_flight"
    assert repository.anonymize_campaign_recipient_history.await_count == 0
    assert repository.delete_campaign_recipient_record.await_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stale_status",
    (EmailSendStatus.accepted, EmailSendStatus.indeterminate),
)
async def test_manual_delete_closes_provider_delivery_only_after_grace(
    stale_status: EmailSendStatus,
) -> None:
    now = datetime.now(UTC)
    archived_at = now - timedelta(days=31)
    stored = recipient(
        archived_at=archived_at,
        purge_after=archived_at + timedelta(days=30),
    )
    stale_send = EmailSend(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        campaign_recipient_id=stored.id,
        recipient_email="ana@example.test",
        template_key="campaign",
        template_version=1,
        provider="brevo",
        provider_message_id=f"provider-stale-{stale_status.value}",
        status=stale_status,
        created_at=now - timedelta(days=8),
        updated_at=now - timedelta(days=8),
        last_event_at=now - timedelta(days=8),
    )
    repository = lifecycle_repository(
        stored_recipient=stored,
        cancelled=1,
        anonymized_sends=1,
    )
    repository.list_unresolved_campaign_recipient_sends = AsyncMock(
        return_value=[stale_send]
    )
    repository.list_campaign_recipient_sends = AsyncMock(
        return_value=[stale_send]
    )

    result = await service_with(repository).permanently_delete_campaign_recipient(
        stored.id,
        owner_id=OWNER_ID,
        settings=PURGE_SETTINGS,
    )

    assert result.cancelled == 1
    tombstone_call = repository.create_campaign_contact_tombstones.await_args.kwargs
    assert tombstone_call["do_not_contact_reason"] is None
    assert tombstone_call["suppressed_at"] is None
    assert (
        tombstone_call["review_after"]
        >= tombstone_call["delivery_expires_at"]
    )
    repository.anonymize_campaign_recipient_history.assert_awaited_once_with(
        stored.id,
        owner_id=OWNER_ID,
        allow_provider_unresolved=True,
    )
    repository.delete_campaign_recipient_record.assert_awaited_once_with(stored)


@pytest.mark.asyncio
async def test_permanent_delete_retains_unsubscribe_tombstone_and_aggregate_history() -> None:
    archived_at = datetime.now(UTC) - timedelta(days=31)
    stored = recipient(
        status=CampaignRecipientStatus.unsubscribed,
        archived_at=archived_at,
        purge_after=archived_at + timedelta(days=30),
    )
    repository = lifecycle_repository(
        stored_recipient=stored,
        cancelled=1,
        anonymized_sends=4,
    )

    result = await service_with(repository).permanently_delete_campaign_recipient(
        stored.id,
        owner_id=OWNER_ID,
        settings=PURGE_SETTINGS,
    )

    expected_fingerprint = email_suppression_fingerprint(
        owner_id=OWNER_ID,
        email=stored.email or "",
        secret=FINGERPRINT_SECRET,
    )
    tombstone_call = repository.create_campaign_contact_tombstones.await_args.kwargs
    assert tombstone_call["owner_id"] == OWNER_ID
    assert tombstone_call["former_recipient_id"] == stored.id
    assert tombstone_call["email_fingerprint"] == expected_fingerprint
    assert tombstone_call["do_not_contact_reason"] == "unsubscribed"
    assert tombstone_call["suppressed_at"] is not None
    assert tombstone_call["review_after"] > datetime.now(UTC) + timedelta(days=364)
    assert tombstone_call["delivery_fingerprints"] == []
    assert tombstone_call["delivery_expires_at"] > datetime.now(UTC) + timedelta(
        days=364
    )
    assert tombstone_call["provider_event_fingerprints"] == []
    assert result.recipient_id == stored.id
    assert result.cancelled == 1
    assert result.anonymized_sends == 4
    repository.delete_campaign_recipient_record.assert_awaited_once_with(stored)


@pytest.mark.asyncio
async def test_permanent_delete_does_not_treat_archive_shadow_as_suppression() -> None:
    archived_at = datetime.now(UTC) - timedelta(days=31)
    stored = recipient(
        status=CampaignRecipientStatus.suppressed,
        status_before_archive=CampaignRecipientStatus.active,
        archived_at=archived_at,
        purge_after=archived_at + timedelta(days=30),
    )
    repository = lifecycle_repository(stored_recipient=stored)

    retention_settings = PURGE_SETTINGS.model_copy(
        update={
            "email_suppression_review_days": 30,
            "campaign_delivery_tombstone_retention_days": 365,
        }
    )

    await service_with(repository).permanently_delete_campaign_recipient(
        stored.id,
        owner_id=OWNER_ID,
        settings=retention_settings,
    )

    tombstone_call = repository.create_campaign_contact_tombstones.await_args.kwargs
    assert tombstone_call["do_not_contact_reason"] is None
    assert tombstone_call["suppressed_at"] is None
    assert tombstone_call["review_after"] == tombstone_call["delivery_expires_at"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("protected_status", "expected_reason"),
    [
        (CampaignRecipientStatus.suppressed, "suppressed"),
        (CampaignRecipientStatus.unsubscribed, "unsubscribed"),
    ],
)
async def test_permanent_delete_retains_restriction_received_while_archived(
    protected_status: CampaignRecipientStatus,
    expected_reason: str,
) -> None:
    archived_at = datetime.now(UTC) - timedelta(days=31)
    stored = recipient(
        status=protected_status,
        status_before_archive=protected_status,
        archived_at=archived_at,
        purge_after=archived_at + timedelta(days=30),
    )
    repository = lifecycle_repository(stored_recipient=stored)

    await service_with(repository).permanently_delete_campaign_recipient(
        stored.id,
        owner_id=OWNER_ID,
        settings=PURGE_SETTINGS,
    )

    tombstone_call = repository.create_campaign_contact_tombstones.await_args.kwargs
    assert tombstone_call["do_not_contact_reason"] == expected_reason
    assert tombstone_call["suppressed_at"] is not None


@pytest.mark.asyncio
async def test_due_purge_deletes_terminal_contact_and_defers_in_flight_contact() -> None:
    now = datetime.now(UTC)
    terminal = recipient(
        archived_at=now - timedelta(days=31),
        purge_after=now - timedelta(days=1),
    )
    in_flight = recipient(
        owner_id=OTHER_OWNER_ID,
        archived_at=now - timedelta(days=31),
        purge_after=now - timedelta(hours=1),
    )
    repository = lifecycle_repository(stored_recipient=None)
    repository.list_due_archived_campaign_recipients = AsyncMock(
        return_value=[terminal, in_flight]
    )
    repository.cancel_unsent_campaign_recipient_sends = AsyncMock(
        side_effect=[(1, 0), (0, 1)]
    )
    recent_accepted = EmailSend(
        id=uuid.uuid4(),
        owner_id=OTHER_OWNER_ID,
        campaign_recipient_id=in_flight.id,
        recipient_email="ana@example.test",
        template_key="campaign",
        template_version=1,
        provider="brevo",
        status=EmailSendStatus.accepted,
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(days=1),
    )
    repository.list_unresolved_campaign_recipient_sends = AsyncMock(
        side_effect=[[], [recent_accepted]]
    )
    service = service_with(repository)
    service._preserve_do_not_contact_restriction = AsyncMock()  # type: ignore[method-assign]

    result = await service.purge_due_campaign_recipients(
        settings=PURGE_SETTINGS,
        now=now,
        limit=20,
    )

    assert (result.examined, result.purged, result.deferred) == (2, 1, 1)
    assert in_flight.purge_after == now + timedelta(days=1)
    assert repository.cancel_unsent_campaign_recipient_sends.await_args_list[
        0
    ].kwargs["owner_id"] == OWNER_ID
    assert repository.cancel_unsent_campaign_recipient_sends.await_args_list[
        1
    ].kwargs["owner_id"] == OTHER_OWNER_ID
    repository.anonymize_campaign_recipient_history.assert_awaited_once_with(
        terminal.id,
        owner_id=OWNER_ID,
        allow_provider_unresolved=False,
    )
    repository.delete_campaign_recipient_record.assert_awaited_once_with(terminal)


@pytest.mark.asyncio
async def test_scheduled_purge_terminalizes_stale_provider_delivery_after_grace() -> None:
    now = datetime.now(UTC)
    stored = recipient(
        archived_at=now - timedelta(days=40),
        purge_after=now - timedelta(days=10),
    )
    stale_accepted = EmailSend(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        campaign_recipient_id=stored.id,
        recipient_email="ana@example.test",
        template_key="campaign",
        template_version=1,
        provider="brevo",
        provider_message_id="provider-stale-accepted",
        status=EmailSendStatus.accepted,
        created_at=now - timedelta(days=8),
        updated_at=now - timedelta(days=8),
        last_event_at=now - timedelta(days=8),
    )
    repository = lifecycle_repository(stored_recipient=None)
    repository.list_due_archived_campaign_recipients = AsyncMock(
        return_value=[stored]
    )
    repository.list_unresolved_campaign_recipient_sends = AsyncMock(
        return_value=[stale_accepted]
    )
    repository.list_campaign_recipient_sends = AsyncMock(
        return_value=[stale_accepted]
    )
    repository.list_campaign_recipient_provider_event_ids = AsyncMock(
        return_value=[
            (
                "provider-stale-accepted",
                "brevo:existing-provider-event",
            )
        ]
    )

    result = await service_with(repository).purge_due_campaign_recipients(
        settings=PURGE_SETTINGS,
        now=now,
    )

    assert (result.examined, result.purged, result.deferred) == (1, 1, 0)
    tombstone_call = repository.create_campaign_contact_tombstones.await_args.kwargs
    assert tombstone_call["do_not_contact_reason"] is None
    assert tombstone_call["suppressed_at"] is None
    assert (
        tombstone_call["review_after"]
        >= tombstone_call["delivery_expires_at"]
    )
    assert len(tombstone_call["delivery_fingerprints"]) == 1
    assert tombstone_call["provider_event_fingerprints"] == [
        (
            provider_message_fingerprint(
                message_id="provider-stale-accepted",
                secret=FINGERPRINT_SECRET,
            ),
            provider_event_fingerprint(
                provider_event_id="brevo:existing-provider-event",
                secret=FINGERPRINT_SECRET,
            ),
        )
    ]
    repository.anonymize_campaign_recipient_history.assert_awaited_once_with(
        stored.id,
        owner_id=OWNER_ID,
        allow_provider_unresolved=True,
    )
    repository.delete_campaign_recipient_record.assert_awaited_once_with(stored)


@pytest.mark.asyncio
async def test_scheduled_purge_is_disabled_during_expand_release_by_default() -> None:
    repository = lifecycle_repository(stored_recipient=None)
    repository.list_due_archived_campaign_recipients = AsyncMock()

    result = await service_with(repository).purge_due_campaign_recipients(
        settings=SETTINGS,
    )

    assert (result.examined, result.purged, result.deferred) == (0, 0, 0)
    repository.list_due_archived_campaign_recipients.assert_not_awaited()


@pytest.mark.asyncio
async def test_repository_cancels_only_not_started_work_and_counts_uncertain_work() -> None:
    now = datetime.now(UTC)
    queued = EmailSend(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        campaign_recipient_id=uuid.uuid4(),
        recipient_email="ana@example.test",
        template_key="campaign",
        template_version=1,
        provider="brevo",
        idempotency_key="queued-key",
        status=EmailSendStatus.queued,
        message_payload={"to": "ana@example.test"},
        next_attempt_at=now,
    )
    started = EmailSend(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        campaign_recipient_id=queued.campaign_recipient_id,
        recipient_email="ana@example.test",
        template_key="campaign",
        template_version=1,
        provider="brevo",
        idempotency_key="started-key",
        status=EmailSendStatus.dispatching,
        message_payload={"to": "ana@example.test"},
        provider_request_started_at=now - timedelta(seconds=1),
    )
    sends_result = MagicMock()
    sends_result.scalars.return_value.all.return_value = [queued, started]
    indeterminate_result = MagicMock()
    indeterminate_result.scalar_one.return_value = 2
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[sends_result, indeterminate_result])
    session.add = MagicMock()
    session.flush = AsyncMock()
    repository = CommunicationsRepository(cast(Any, session))

    cancelled, in_flight = await repository.cancel_unsent_campaign_recipient_sends(
        queued.campaign_recipient_id,
        owner_id=OWNER_ID,
        now=now,
    )

    assert (cancelled, in_flight) == (1, 3)
    assert queued.status == EmailSendStatus.cancelled
    assert queued.cancelled_at == now
    assert started.status == EmailSendStatus.dispatching
    assert started.provider_request_started_at is not None
    unresolved_statement = str(
        session.execute.await_args_list[1].args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "accepted" in unresolved_statement
    assert "indeterminate" in unresolved_statement


@pytest.mark.asyncio
async def test_purge_materializes_aggregates_then_deletes_row_level_history() -> None:
    recipient_id = uuid.uuid4()
    campaign_id = uuid.uuid4()
    sent = EmailSend(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        campaign_id=campaign_id,
        campaign_recipient_id=recipient_id,
        recipient_email="ana@example.test",
        template_key="campaign",
        template_version=3,
        provider="brevo",
        provider_message_id="provider-message",
        provider_idempotency_key="provider-idempotency",
        idempotency_key="application-idempotency",
        payload_fingerprint="a" * 64,
        message_payload={"to": "ana@example.test", "subject": "Salut"},
        error_details="provider metadata",
        status=EmailSendStatus.delivered,
    )
    event = CampaignRecipientEvent(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        campaign_id=campaign_id,
        recipient_id=recipient_id,
        event_type="opened",
        variant_key=None,
        occurred_at=datetime.now(UTC),
    )
    provider_event = EmailEvent(
        id=uuid.uuid4(),
        email_send_id=sent.id,
        event_type=EmailEventType.clicked,
        occurred_at=datetime.now(UTC),
    )
    send_result = MagicMock()
    send_result.scalars.return_value.all.return_value = [sent]
    provider_event_result = MagicMock()
    provider_event_result.all.return_value = [(provider_event, campaign_id)]
    event_result = MagicMock()
    event_result.scalars.return_value.all.return_value = [event]
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            send_result,
            provider_event_result,
            event_result,
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]
    )
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    repository = CommunicationsRepository(cast(Any, session))

    purged_send_count = await repository.anonymize_campaign_recipient_history(
        recipient_id,
        owner_id=OWNER_ID,
    )

    assert purged_send_count == 1
    assert sent.campaign_id == campaign_id
    assert sent.status == EmailSendStatus.delivered
    assert session.execute.await_count == 6
    aggregate_statements = [
        call.args[0] for call in session.execute.await_args_list[3:]
    ]
    assert all(
        "campaign_contact_aggregates" in str(statement)
        for statement in aggregate_statements
    )
    assert {
        statement.compile(dialect=postgresql.dialect()).params["metric"]
        for statement in aggregate_statements
    } == {
        "send:delivered",
        "provider_event:clicked",
        "event:opened",
    }
    assert session.delete.await_args_list[0].args == (event,)
    assert session.delete.await_args_list[1].args == (sent,)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_accepted_send_blocks_row_level_history_purge() -> None:
    accepted = EmailSend(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        campaign_recipient_id=uuid.uuid4(),
        recipient_email="ana@example.test",
        template_key="campaign",
        template_version=1,
        provider="brevo",
        status=EmailSendStatus.accepted,
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [accepted]
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.delete = AsyncMock()
    repository = CommunicationsRepository(cast(Any, session))

    with pytest.raises(ValueError, match="unresolved email deliveries"):
        await repository.anonymize_campaign_recipient_history(
            accepted.campaign_recipient_id,
            owner_id=OWNER_ID,
        )

    assert session.execute.await_count == 1
    session.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_suppression_reason_never_downgrades_unsubscribe() -> None:
    review_after = datetime.now(UTC) + timedelta(days=365)
    existing = EmailSuppression(
        owner_id=OWNER_ID,
        legacy_email="ana@example.test",
        email_fingerprint="a" * 64,
        reason="unsubscribed",
        source_email_send_id=None,
        review_after=review_after,
    )
    session = MagicMock()
    session.flush = AsyncMock()
    repository = CommunicationsRepository(cast(Any, session))
    repository.get_email_suppression = AsyncMock(return_value=existing)

    retained = await repository.suppress_email(
        owner_id=OWNER_ID,
        email="ana@example.test",
        email_fingerprint="b" * 64,
        reason="hard_bounce",
        source_email_send_id=uuid.uuid4(),
        review_after=review_after + timedelta(days=1),
    )

    assert retained.reason == "unsubscribed"
    assert retained.source_email_send_id is None
    assert retained.email_fingerprint == "b" * 64
    assert retained.review_after == review_after + timedelta(days=1)


@pytest.mark.asyncio
async def test_due_suppression_review_audits_retention_and_manual_review() -> None:
    now = datetime.now(UTC)
    retained = EmailSuppression(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        legacy_email="retained@example.test",
        email_fingerprint="a" * 64,
        reason="hard_bounce",
        source_email_send_id=None,
        review_after=now - timedelta(days=1),
    )
    needs_review = EmailSuppression(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        legacy_email="needs-review@example.test",
        email_fingerprint="b" * 64,
        reason="soft_bounce",
        source_email_send_id=None,
        review_after=now - timedelta(days=1),
    )
    repository = SimpleNamespace(
        list_due_email_suppressions=AsyncMock(
            return_value=[retained, needs_review]
        ),
        add_email_suppression_review=AsyncMock(),
        delete_email_suppression=AsyncMock(),
    )

    result = await service_with(repository).review_due_email_suppressions(
        settings=SETTINGS,
        now=now,
        limit=100,
    )

    assert (
        result.examined,
        result.retained,
        result.needs_review,
        result.deleted,
    ) == (2, 1, 1, 0)
    assert retained.last_reviewed_at == now
    assert retained.review_after == now + timedelta(days=365)
    reviews = [
        call.args[0]
        for call in repository.add_email_suppression_review.await_args_list
    ]
    assert [(review.reason, review.decision) for review in reviews] == [
        ("hard_bounce", "retained"),
        ("soft_bounce", "needs_review"),
    ]
    assert all(review.reviewer == "system-policy" for review in reviews)
    assert reviews[0].next_review_at == now + timedelta(days=365)
    assert reviews[1].next_review_at == now + timedelta(days=30)
    repository.delete_email_suppression.assert_not_awaited()


@pytest.mark.asyncio
async def test_due_suppression_review_quarantines_unknown_reason_for_manual_review() -> None:
    now = datetime.now(UTC)
    unknown = EmailSuppression(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        legacy_email="legacy@example.test",
        email_fingerprint="c" * 64,
        reason="legacy_provider_reject",
        source_email_send_id=None,
        review_after=now - timedelta(days=1),
    )
    repository = SimpleNamespace(
        list_due_email_suppressions=AsyncMock(return_value=[unknown]),
        add_email_suppression_review=AsyncMock(),
        delete_email_suppression=AsyncMock(),
    )

    result = await service_with(repository).review_due_email_suppressions(
        settings=SETTINGS,
        now=now,
        limit=100,
    )

    assert (
        result.examined,
        result.retained,
        result.needs_review,
        result.deleted,
    ) == (1, 0, 1, 0)
    assert unknown.last_reviewed_at == now
    assert unknown.review_after == now + timedelta(days=30)
    [review_call] = repository.add_email_suppression_review.await_args_list
    review = review_call.args[0]
    assert (review.reason, review.decision) == (
        "legacy_provider_reject",
        "needs_review",
    )
    assert review.next_review_at == now + timedelta(days=30)
    repository.delete_email_suppression.assert_not_awaited()


@pytest.mark.asyncio
async def test_suppression_worker_cleanup_deletes_expired_delivery_mapping() -> None:
    now = datetime.now(UTC)
    expired = CampaignDeliveryTombstone(
        id=uuid.uuid4(),
        contact_tombstone_id=uuid.uuid4(),
        campaign_id=None,
        provider_message_fingerprint="f" * 64,
        expires_at=now - timedelta(seconds=1),
    )
    repository = SimpleNamespace(
        list_due_email_suppressions=AsyncMock(return_value=[]),
        list_due_campaign_delivery_tombstones=AsyncMock(
            return_value=[expired]
        ),
        delete_campaign_delivery_tombstone=AsyncMock(),
    )

    result = await service_with(repository).review_due_email_suppressions(
        settings=SETTINGS,
        now=now,
        limit=100,
    )

    assert (
        result.examined,
        result.retained,
        result.needs_review,
        result.deleted,
    ) == (1, 0, 0, 1)
    repository.list_due_campaign_delivery_tombstones.assert_awaited_once_with(
        now=now,
        limit=100,
    )
    repository.delete_campaign_delivery_tombstone.assert_awaited_once_with(
        expired
    )


@pytest.mark.asyncio
async def test_suppression_worker_deletes_neutral_parent_after_mappings_expire() -> None:
    now = datetime.now(UTC)
    neutral = CampaignContactTombstone(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        former_recipient_id=uuid.uuid4(),
        email_fingerprint="e" * 64,
        do_not_contact_reason=None,
        suppressed_at=None,
        review_after=now - timedelta(seconds=1),
    )
    repository = SimpleNamespace(
        list_due_email_suppressions=AsyncMock(return_value=[]),
        list_due_campaign_delivery_tombstones=AsyncMock(return_value=[]),
        list_due_campaign_contact_tombstones=AsyncMock(
            return_value=[neutral]
        ),
        add_email_suppression_review=AsyncMock(),
        delete_campaign_contact_tombstone=AsyncMock(),
    )

    result = await service_with(repository).review_due_email_suppressions(
        settings=SETTINGS,
        now=now,
        limit=100,
    )

    assert (
        result.examined,
        result.retained,
        result.needs_review,
        result.deleted,
    ) == (1, 0, 0, 1)
    review = repository.add_email_suppression_review.await_args.args[0]
    assert (review.reason, review.decision, review.next_review_at) == (
        "token_provider_mapping",
        "mapping_expired",
        None,
    )
    repository.delete_campaign_contact_tombstone.assert_awaited_once_with(
        neutral
    )


@pytest.mark.asyncio
async def test_old_unsubscribe_token_updates_contact_tombstone_after_pii_purge() -> None:
    former_recipient_id = uuid.uuid4()
    tombstone = CampaignContactTombstone(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        former_recipient_id=former_recipient_id,
        email_fingerprint="d" * 64,
        do_not_contact_reason=None,
        suppressed_at=None,
        review_after=datetime.now(UTC) + timedelta(days=30),
    )
    repository = SimpleNamespace(
        get_campaign_recipient=AsyncMock(return_value=None),
        get_campaign_contact_tombstone=AsyncMock(return_value=tombstone),
        suppress_email=AsyncMock(),
        flush=AsyncMock(),
    )
    token = create_campaign_recipient_action_token(
        CampaignRecipientActionClaims(
            recipient_id=former_recipient_id,
            owner_id=OWNER_ID,
            action="unsubscribe",
        ),
        SETTINGS,
    )

    target = await service_with(repository).unsubscribe_campaign_recipient(
        token,
        SETTINGS,
    )

    assert target.tombstone is tombstone
    assert target.recipient is None
    assert tombstone.do_not_contact_reason == "unsubscribed"
    assert tombstone.suppressed_at is not None
    assert tombstone.review_after > datetime.now(UTC) + timedelta(days=364)
    repository.get_campaign_contact_tombstone.assert_awaited_once_with(
        owner_id=OWNER_ID,
        former_recipient_id=former_recipient_id,
        for_update=True,
    )
    repository.suppress_email.assert_not_awaited()
    repository.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_unsubscribe_locks_live_recipient_before_mutating_status() -> None:
    stored = recipient()
    repository = SimpleNamespace(
        get_campaign_recipient=AsyncMock(return_value=stored),
        get_campaign_contact_tombstone=AsyncMock(),
        suppress_email=AsyncMock(),
        flush=AsyncMock(),
    )
    token = create_campaign_recipient_action_token(
        CampaignRecipientActionClaims(
            recipient_id=stored.id,
            owner_id=OWNER_ID,
            action="unsubscribe",
        ),
        SETTINGS,
    )

    target = await service_with(repository).unsubscribe_campaign_recipient(
        token,
        SETTINGS,
    )

    assert target.recipient is stored
    assert stored.status == CampaignRecipientStatus.unsubscribed
    repository.get_campaign_recipient.assert_awaited_once_with(
        stored.id,
        owner_id=OWNER_ID,
        catalog_scope="any",
        for_update=True,
    )
    repository.get_campaign_contact_tombstone.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_event_rejects_campaign_from_another_owner() -> None:
    stored = recipient()
    foreign_campaign_id = uuid.uuid4()
    repository = SimpleNamespace(
        get_campaign_recipient=AsyncMock(return_value=stored),
        get_campaign=AsyncMock(return_value=None),
        add_campaign_recipient_event=AsyncMock(),
    )

    with pytest.raises(DomainError) as exc_info:
        await service_with(repository).record_campaign_recipient_event(
            stored.id,
            CampaignRecipientEventCreateRequest(
                event_type="opened",
                variant_key=str(foreign_campaign_id),
            ),
            owner_id=OWNER_ID,
        )

    assert exc_info.value.code == "campaign_not_found"
    repository.get_campaign_recipient.assert_awaited_once_with(
        stored.id,
        owner_id=OWNER_ID,
        catalog_scope="any",
        for_update=True,
    )
    repository.get_campaign.assert_awaited_once_with(
        foreign_campaign_id,
        owner_id=OWNER_ID,
    )
    repository.add_campaign_recipient_event.assert_not_awaited()


def test_suppression_fingerprint_is_normalized_owner_scoped_and_non_reversible() -> None:
    first = email_suppression_fingerprint(
        owner_id=OWNER_ID,
        email="  ANA@Example.Test ",
        secret=FINGERPRINT_SECRET,
    )
    normalized = email_suppression_fingerprint(
        owner_id=OWNER_ID,
        email="ana@example.test",
        secret=FINGERPRINT_SECRET,
    )
    other_owner = email_suppression_fingerprint(
        owner_id=OTHER_OWNER_ID,
        email="ana@example.test",
        secret=FINGERPRINT_SECRET,
    )

    assert first == normalized
    assert first != other_owner
    assert len(first) == 64
    assert "ana" not in first
