from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from codrut.modules.communications.models import EmailSendStatus
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
async def test_contact_reads_require_and_filter_by_owner() -> None:
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

    assert "campaign_recipients.owner_id =" in list_statement
    assert "campaign_recipients.owner_id =" in get_statement
    assert "campaign_recipients.owner_id =" in email_statement

    with pytest.raises(ValueError, match="owner_id is required"):
        await repository.list_campaign_recipients(owner_id=None)


@pytest.mark.asyncio
async def test_membership_reads_filter_campaign_and_contact_owner() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=EmptyResult())
    repository = CommunicationsRepository(session)

    await repository.list_campaign_member_recipients(
        uuid4(),
        owner_id=uuid4(),
    )

    statement = str(session.execute.call_args.args[0])
    assert "campaigns.owner_id =" in statement
    assert "campaign_recipients.owner_id =" in statement


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
