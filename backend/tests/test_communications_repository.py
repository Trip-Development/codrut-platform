from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from codrut.modules.communications.models import (
    CampaignContactTombstone,
    CampaignDeliveryTombstone,
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    EmailSendStatus,
    EmailSuppression,
)
from codrut.modules.communications.repository import CommunicationsRepository


class EmptyResult:
    def scalars(self) -> "EmptyResult":
        return self

    def all(self) -> list[object]:
        return []

    def scalar_one_or_none(self) -> None:
        return None


class RowResult:
    def __init__(self, rows: list[tuple[object, object]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[object, object]]:
        return self.rows


@pytest.mark.asyncio
async def test_suppression_reads_fall_back_to_rollback_email_rows() -> None:
    owner_id = uuid4()
    legacy = EmailSuppression(
        owner_id=owner_id,
        legacy_email="ana@example.com",
        email_fingerprint=None,
        reason="hard_bounce",
        review_after=None,
    )
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    legacy_result = MagicMock()
    legacy_result.scalar_one_or_none.return_value = legacy
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[empty, empty, legacy_result]
    )
    repository = CommunicationsRepository(session)

    suppression = await repository.get_email_suppression(
        owner_id=owner_id,
        email_fingerprint="f" * 64,
        email=" ANA@Example.com ",
    )

    assert suppression is legacy
    fallback_statement = str(session.execute.await_args_list[-1].args[0])
    assert "email_suppressions.owner_id =" in fallback_statement
    assert "lower(email_suppressions.email) =" in fallback_statement


@pytest.mark.asyncio
async def test_bulk_suppression_reads_include_rollback_email_rows() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=EmptyResult())
    repository = CommunicationsRepository(session)

    await repository.list_email_suppressions_by_fingerprints(
        owner_id=uuid4(),
        email_fingerprints={"f" * 64},
        normalized_emails={" ANA@Example.com "},
    )

    suppression_statement = str(session.execute.await_args_list[0].args[0])
    assert "email_suppressions.email_fingerprint IN" in suppression_statement
    assert "lower(email_suppressions.email) IN" in suppression_statement


@pytest.mark.asyncio
async def test_contact_catalog_and_mutations_are_owner_scoped() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=EmptyResult())
    repository = CommunicationsRepository(session)
    owner_id = uuid4()

    await repository.list_campaign_recipients(owner_id=owner_id)
    list_statement = str(session.execute.call_args.args[0])
    await repository.get_campaign_recipient(uuid4(), owner_id=owner_id)
    get_statement = str(session.execute.call_args.args[0])
    await repository.get_campaign_recipient_by_email(
        "contact@example.com",
        owner_id=owner_id,
    )
    email_statement = str(session.execute.call_args.args[0])
    await repository.list_campaign_recipients_by_ids([uuid4()], owner_id=owner_id)
    ids_statement = str(session.execute.call_args.args[0])
    await repository.list_campaign_recipient_events(owner_id=owner_id)
    events_statement = str(session.execute.call_args.args[0])

    assert "campaign_recipients.owner_id =" in list_statement
    assert "campaign_recipients.owner_id =" in get_statement
    assert "campaign_recipients.owner_id =" in email_statement
    assert "campaign_recipients.owner_id =" in ids_statement
    assert "campaign_recipient_events.owner_id =" in events_statement
    assert "campaign_recipient_events.owner_id IS NULL" in events_statement
    assert "campaign_recipients.owner_id =" in events_statement

    with pytest.raises(ValueError, match="owner_id is required"):
        await repository.list_campaign_recipients(owner_id=None)


@pytest.mark.asyncio
async def test_membership_reads_require_matching_campaign_and_contact_owners() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=EmptyResult())
    repository = CommunicationsRepository(session)

    await repository.list_campaign_member_recipients(
        uuid4(),
        owner_id=uuid4(),
    )

    recipient_statement = str(session.execute.call_args.args[0])
    await repository.list_campaign_member_recipient_ids(uuid4(), owner_id=uuid4())
    id_statement = str(session.execute.call_args.args[0])

    for statement in (recipient_statement, id_statement):
        assert "campaigns.owner_id =" in statement
        assert "campaign_recipients.owner_id =" in statement


@pytest.mark.asyncio
async def test_campaign_membership_rejects_legacy_and_cross_trainer_contacts() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    repository = CommunicationsRepository(session)
    campaign_id = uuid4()
    owner_id = uuid4()
    recipients = [
        CampaignRecipient(
            id=uuid4(),
            owner_id=None,
            email="legacy@example.com",
            segment=CampaignRecipientSegment.potential_customer,
            status=CampaignRecipientStatus.active,
        ),
        CampaignRecipient(
            id=uuid4(),
            owner_id=uuid4(),
            email="shared@example.com",
            segment=CampaignRecipientSegment.past_customer,
            status=CampaignRecipientStatus.active,
        ),
    ]
    repository.get_campaign = AsyncMock(return_value=object())
    repository.lock_campaign_recipients_for_send = AsyncMock(
        return_value=recipients
    )
    repository.list_campaign_member_recipient_ids = AsyncMock(return_value=[])

    with pytest.raises(
        ValueError,
        match="contacts owned by another trainer",
    ):
        await repository.replace_campaign_memberships(
            campaign_id,
            [recipient.id for recipient in recipients],
            owner_id=owner_id,
        )

    repository.get_campaign.assert_awaited_once_with(campaign_id, owner_id=owner_id)
    session.add_all.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_membership_replacement_rejects_contact_archived_before_lock() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    repository = CommunicationsRepository(session)
    campaign_id = uuid4()
    owner_id = uuid4()
    recipient_id = uuid4()
    repository.get_campaign = AsyncMock(return_value=object())
    repository.lock_campaign_recipients_for_send = AsyncMock(return_value=[])
    repository.list_campaign_member_recipient_ids = AsyncMock(return_value=[])

    with pytest.raises(
        ValueError,
        match="contacts owned by another trainer",
    ):
        await repository.replace_campaign_memberships(
            campaign_id,
            [recipient_id],
            owner_id=owner_id,
        )

    repository.lock_campaign_recipients_for_send.assert_awaited_once_with(
        [recipient_id],
        owner_id=owner_id,
    )
    repository.list_campaign_member_recipient_ids.assert_not_awaited()
    session.add_all.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_membership_recipient_lock_excludes_archived_rows() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=EmptyResult())
    repository = CommunicationsRepository(session)

    await repository.lock_campaign_recipients_for_send(
        [uuid4()],
        owner_id=uuid4(),
    )

    statement = session.execute.await_args.args[0]
    compiled = str(statement)
    assert "campaign_recipients.owner_id =" in compiled
    assert "campaign_recipients.archived_at IS NULL" in compiled
    assert "ORDER BY campaign_recipients.id ASC" in compiled
    assert statement._for_update_arg is not None


@pytest.mark.asyncio
async def test_new_contacts_keep_creator_owner() -> None:
    session = MagicMock()
    session.flush = AsyncMock()
    repository = CommunicationsRepository(session)
    owner_id = uuid4()
    recipient = CampaignRecipient(
        id=uuid4(),
        owner_id=owner_id,
        email="new@example.com",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.active,
    )

    await repository.add_campaign_recipients([recipient], owner_id=owner_id)

    session.add_all.assert_called_once_with([recipient])
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_archive_mutations_and_due_worker_serialize_contact_rows() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=EmptyResult())
    repository = CommunicationsRepository(session)
    owner_id = uuid4()

    await repository.get_campaign_recipient(
        uuid4(),
        owner_id=owner_id,
        catalog_scope="any",
        for_update=True,
    )
    mutation_statement = str(session.execute.await_args.args[0])
    await repository.list_due_archived_campaign_recipients(
        now=datetime.now(UTC),
        limit=100,
    )
    worker_statement = str(session.execute.await_args.args[0])

    assert "FOR UPDATE" in mutation_statement
    assert "FOR UPDATE" in worker_statement
    mutation_select = session.execute.await_args_list[0].args[0]
    worker_select = session.execute.await_args.args[0]
    assert mutation_select._for_update_arg.skip_locked is False
    assert worker_select._for_update_arg.skip_locked is True


@pytest.mark.asyncio
async def test_expired_delivery_mapping_cleanup_uses_bounded_skip_locked_batch() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=EmptyResult())
    repository = CommunicationsRepository(session)
    now = datetime.now(UTC)

    await repository.list_due_campaign_delivery_tombstones(
        now=now,
        limit=100,
    )

    statement = session.execute.await_args.args[0]
    compiled = str(statement)
    assert "campaign_delivery_tombstones.expires_at <=" in compiled
    assert statement._limit_clause.value == 100
    assert statement._for_update_arg.skip_locked is True


@pytest.mark.asyncio
async def test_neutral_contact_tombstone_waits_for_active_delivery_mapping() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=EmptyResult())
    repository = CommunicationsRepository(session)
    now = datetime.now(UTC)

    await repository.list_due_campaign_contact_tombstones(
        now=now,
        limit=100,
    )

    statement = session.execute.await_args.args[0]
    compiled = str(statement)
    assert "campaign_contact_tombstones.do_not_contact_reason IS NOT NULL" in compiled
    assert "campaign_delivery_tombstones.contact_tombstone_id" in compiled
    assert "campaign_delivery_tombstones.expires_at >" in compiled
    assert "NOT (EXISTS" in compiled
    assert statement._for_update_arg.skip_locked is True


@pytest.mark.asyncio
async def test_expired_delivery_mapping_is_ignored_before_cleanup_runs() -> None:
    result = MagicMock()
    result.one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    repository = CommunicationsRepository(session)
    active_at = datetime.now(UTC)

    match = (
        await repository.get_campaign_delivery_tombstone_by_provider_message_fingerprints(
            {"a" * 64},
            active_at=active_at,
            for_update=True,
        )
    )

    assert match is None
    statement = session.execute.await_args.args[0]
    compiled = str(statement)
    assert "campaign_delivery_tombstones.expires_at >" in compiled
    assert statement._for_update_arg is not None


@pytest.mark.asyncio
async def test_delivery_fingerprint_cannot_attach_to_another_contact_tombstone() -> None:
    tombstone = CampaignContactTombstone(
        id=uuid4(),
        owner_id=uuid4(),
        former_recipient_id=uuid4(),
        email_fingerprint="a" * 64,
        do_not_contact_reason=None,
        review_after=datetime.now(UTC) + timedelta(days=365),
    )
    foreign_delivery = CampaignDeliveryTombstone(
        id=uuid4(),
        contact_tombstone_id=uuid4(),
        campaign_id=None,
        provider_message_fingerprint="b" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    tombstone_result = MagicMock()
    tombstone_result.scalar_one_or_none.return_value = tombstone
    delivery_result = MagicMock()
    delivery_result.scalars.return_value.all.return_value = [foreign_delivery]
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[tombstone_result, MagicMock(), delivery_result]
    )
    session.flush = AsyncMock()
    repository = CommunicationsRepository(session)

    with pytest.raises(
        ValueError,
        match="fingerprint belongs to another contact",
    ):
        await repository.create_campaign_contact_tombstones(
            owner_id=tombstone.owner_id,
            former_recipient_id=tombstone.former_recipient_id,
            email_fingerprint=tombstone.email_fingerprint,
            do_not_contact_reason=None,
            suppressed_at=None,
            review_after=tombstone.review_after,
            delivery_fingerprints=[
                (foreign_delivery.provider_message_fingerprint, None)
            ],
            delivery_expires_at=foreign_delivery.expires_at,
            provider_event_fingerprints=[],
        )

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_campaign_delivery_status_maps_provider_terminal_states() -> None:
    delivered_id = uuid4()
    bounced_id = uuid4()
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=RowResult(
            [
                (delivered_id, EmailSendStatus.delivered),
                (bounced_id, EmailSendStatus.bounced),
            ]
        )
    )
    repository = CommunicationsRepository(session)

    statuses = await repository.list_campaign_delivery_status_by_recipient_ids(
        uuid4(),
        [delivered_id, bounced_id],
        owner_id=uuid4(),
    )

    assert statuses == {delivered_id: "sent", bounced_id: "failed"}
