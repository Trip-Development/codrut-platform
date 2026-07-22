from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from codrut.modules.communications.models import (
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    EmailSendStatus,
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
async def test_contact_catalog_is_shared_but_contact_mutations_remain_owner_scoped() -> None:
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

    assert "campaign_recipients.owner_id =" not in list_statement
    assert "campaign_recipients.owner_id =" in get_statement
    assert "campaign_recipients.owner_id =" in email_statement
    assert "campaign_recipients.owner_id =" not in ids_statement
    assert "campaign_recipients.owner_id =" in events_statement

    with pytest.raises(ValueError, match="owner_id is required"):
        await repository.list_campaign_recipients(owner_id=None)


@pytest.mark.asyncio
async def test_membership_reads_keep_campaign_owner_scope_for_shared_contacts() -> None:
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
        assert "campaign_recipients.owner_id =" not in statement


@pytest.mark.asyncio
async def test_campaign_membership_accepts_legacy_and_cross_trainer_contacts() -> None:
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
    repository.list_campaign_recipients_by_ids = AsyncMock(return_value=recipients)
    repository.list_campaign_member_recipient_ids = AsyncMock(return_value=[])

    await repository.replace_campaign_memberships(
        campaign_id,
        [recipient.id for recipient in recipients],
        owner_id=owner_id,
    )

    repository.get_campaign.assert_awaited_once_with(campaign_id, owner_id=owner_id)
    session.add_all.assert_called_once()
    assert {membership.recipient_id for membership in session.add_all.call_args.args[0]} == {
        recipient.id for recipient in recipients
    }
    session.flush.assert_awaited_once()


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
