import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from codrut.contracts.emails import (
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
    EmailSendResult,
)
from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.communications.models import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
    EmailSend,
    EmailSendStatus,
)
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.schemas import (
    CampaignCreateRequest,
    CampaignSendRequest,
    CampaignUpdateRequest,
)
from codrut.modules.communications.service import (
    CommunicationsService,
    _render_campaign_message,
    validate_campaign_placeholders,
    validate_template_placeholders,
)

OWNER_ID = uuid.UUID("00000000-0000-0000-0000-000000000111")
SETTINGS = Settings(public_app_url="https://cody.andreivacaru.ro")


class MemoryCommunicationsRepository:
    def __init__(self) -> None:
        self.campaigns: list[Campaign] = []
        self.recipients: list[CampaignRecipient] = []
        self.sends: list[EmailSend] = []

    async def get_campaign(
        self,
        campaign_id: uuid.UUID,
        *,
        owner_id: uuid.UUID | None = None,
    ) -> Campaign | None:
        return next(
            (
                campaign
                for campaign in self.campaigns
                if campaign.id == campaign_id
                and (owner_id is None or campaign.owner_id == owner_id)
            ),
            None,
        )

    async def add_campaign(self, campaign: Campaign) -> Campaign:
        self.campaigns.append(campaign)
        return campaign

    async def list_campaign_recipients_by_ids(
        self,
        recipient_ids: list[uuid.UUID],
        *,
        owner_id: uuid.UUID | None = None,
    ) -> list[CampaignRecipient]:
        return [
            recipient
            for recipient in self.recipients
            if recipient.id in recipient_ids
            and (owner_id is None or recipient.owner_id == owner_id)
        ]

    async def count_accepted_sends_since(self, _since: datetime) -> int:
        return sum(
            send.status != EmailSendStatus.cancelled
            for send in self.sends
        )

    async def get_email_suppression(
        self,
        *,
        owner_id: uuid.UUID,
        email_fingerprint: str,
        email: str | None = None,
    ) -> None:
        del owner_id, email_fingerprint, email
        return None

    async def add_email_send(self, send: EmailSend) -> EmailSend:
        self.sends.append(send)
        return send

    async def get_email_send_by_idempotency_key(self, key: str) -> EmailSend | None:
        return next((send for send in self.sends if send.idempotency_key == key), None)

    async def reclaim_stale_email_send(
        self,
        key: str,
        payload_fingerprint: str,
        *,
        now: datetime,
        lease_duration: timedelta,
    ) -> EmailSend | None:
        send = await self.get_email_send_by_idempotency_key(key)
        if (
            send is None
            or send.payload_fingerprint != payload_fingerprint
            or send.status != EmailSendStatus.queued
            or send.lease_expires_at is None
            or send.lease_expires_at > now
        ):
            return None
        send.lease_expires_at = now + lease_duration
        send.last_event_at = now
        return send

    async def flush(self) -> None:
        return None


class RecordingProvider:
    key = EmailProviderKey.test

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> EmailSendResult:
        self.sent.append(message)
        return EmailSendResult(
            provider=self.key,
            status=EmailDeliveryStatus.accepted,
            message_id=f"message-{len(self.sent)}",
            recipient=message.to,
        )


def make_campaign() -> Campaign:
    return Campaign(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        name="Hardening campaign",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignStatus.ready,
        subject="Salut ${first_name}",
        html_body='<div style="font-family:Inter,Arial,sans-serif"><p>Mesaj personalizat</p></div>',
        text_body="Mesaj personalizat",
        recipient_memberships_initialized=True,
    )


def make_recipient() -> CampaignRecipient:
    return CampaignRecipient(
        id=uuid.uuid4(),
        owner_id=OWNER_ID,
        email="ana@example.com",
        contact_name="Ana Popescu",
        organization_name="Exemplu SRL",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignRecipientStatus.active,
    )


def make_service(repository: MemoryCommunicationsRepository) -> CommunicationsService:
    service = CommunicationsService()
    service.repository = cast(Any, repository)
    return service


@pytest.mark.asyncio
async def test_campaign_send_replays_same_idempotent_delivery() -> None:
    repository = MemoryCommunicationsRepository()
    campaign = make_campaign()
    recipient = make_recipient()
    repository.campaigns.append(campaign)
    repository.recipients.append(recipient)
    provider = RecordingProvider()
    service = make_service(repository)

    first = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(mode="selected", recipient_ids=[recipient.id]),
        provider=provider,
        settings=SETTINGS,
        owner_id=OWNER_ID,
        idempotency_key="stable-request-key",
    )
    replay = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(mode="selected", recipient_ids=[recipient.id]),
        provider=provider,
        settings=SETTINGS,
        owner_id=OWNER_ID,
        idempotency_key="stable-request-key",
    )

    assert first.queued == replay.queued == 1
    assert first.sent == replay.sent == 0
    assert len(provider.sent) == 0
    assert len(repository.sends) == 1
    assert repository.sends[0].payload_fingerprint is not None


@pytest.mark.parametrize(
    ("target", "attribute", "replacement"),
    [
        ("campaign", "name", "Changed campaign"),
        ("campaign", "subject", "Changed message"),
        ("recipient", "email", "changed@example.com"),
    ],
)
@pytest.mark.asyncio
async def test_campaign_send_rejects_idempotency_key_reuse_for_changed_payload(
    target: str,
    attribute: str,
    replacement: str,
) -> None:
    repository = MemoryCommunicationsRepository()
    campaign = make_campaign()
    recipient = make_recipient()
    repository.campaigns.append(campaign)
    repository.recipients.append(recipient)
    provider = RecordingProvider()
    service = make_service(repository)
    request = CampaignSendRequest(mode="selected", recipient_ids=[recipient.id])

    await service.send_campaign(
        campaign.id,
        request,
        provider=provider,
        settings=SETTINGS,
        owner_id=OWNER_ID,
        idempotency_key="reused-request-key",
    )
    setattr(campaign if target == "campaign" else recipient, attribute, replacement)

    with pytest.raises(DomainError) as exc_info:
        await service.send_campaign(
            campaign.id,
            request,
            provider=provider,
            settings=SETTINGS,
            owner_id=OWNER_ID,
            idempotency_key="reused-request-key",
        )

    assert exc_info.value.code == "email_send_idempotency_payload_conflict"
    assert len(provider.sent) == 0


@pytest.mark.asyncio
async def test_repository_claim_uses_skip_locked_for_due_and_stale_rows() -> None:
    now = datetime(2026, 7, 16, 12, tzinfo=UTC)
    send = EmailSend(
        id=uuid.uuid4(),
        recipient_email="ana@example.com",
        template_key="campaign",
        template_version=1,
        provider="test",
        idempotency_key="a" * 64,
        payload_fingerprint="b" * 64,
        message_payload={"version": 1},
        attempt_count=1,
        max_attempts=5,
        next_attempt_at=now - timedelta(seconds=1),
        lease_expires_at=now - timedelta(seconds=1),
        status=EmailSendStatus.dispatching,
    )
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [send]
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    repository = CommunicationsRepository(session)

    claims = await repository.claim_due_email_sends(
        now=now,
        lease_duration=timedelta(minutes=5),
        limit=10,
    )

    assert claims == [send]
    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert sql.startswith("SELECT email_sends.id")
    assert "email_sends.next_attempt_at <=" in sql
    assert "email_sends.lease_expires_at <=" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert send.status == EmailSendStatus.dispatching
    assert send.attempt_count == 2
    assert send.lease_token is not None


@pytest.mark.parametrize("malformed", ["Cost $", "Hello ${broken-name}"])
def test_template_validation_rejects_malformed_string_template_syntax(malformed: str) -> None:
    with pytest.raises(DomainError) as exc_info:
        validate_template_placeholders("Subject", malformed, "Text", [], "custom")

    assert exc_info.value.code == "email_template_malformed_placeholder"


@pytest.mark.parametrize(
    ("variables", "expected_code"),
    [
        (["invalid-name"], "email_template_invalid_variables"),
        (["name", "name"], "email_template_duplicate_variables"),
    ],
)
def test_template_validation_rejects_invalid_variable_declarations(
    variables: list[str],
    expected_code: str,
) -> None:
    with pytest.raises(DomainError) as exc_info:
        validate_template_placeholders("Subject", "Hello", "Text", variables, "custom")

    assert exc_info.value.code == expected_code


def test_template_validation_rejects_undeclared_and_missing_required_placeholders() -> None:
    with pytest.raises(DomainError) as undeclared:
        validate_template_placeholders("Hello $name", "Body", "Text", [], "custom")
    assert undeclared.value.code == "email_template_undeclared_variables"

    required = ["participant_name", "trainer_name", "company_name", "action_url"]
    with pytest.raises(DomainError) as missing:
        validate_template_placeholders("Price $$5", "Body", "Text", required, "account_setup")
    assert missing.value.code == "email_template_missing_required_placeholders"


@pytest.mark.asyncio
async def test_campaign_create_and_update_reject_unsupported_placeholders_without_mutation() -> (
    None
):
    repository = MemoryCommunicationsRepository()
    service = make_service(repository)

    with pytest.raises(DomainError) as create_error:
        await service.create_campaign(
            CampaignCreateRequest(
                name="Invalid campaign",
                subject="Hello ${unsupported}",
                html_body="<p>Body $$ literal</p>",
                text_body="Body",
            ),
            owner_id=OWNER_ID,
        )
    assert create_error.value.code == "campaign_template_unsupported_variables"
    assert repository.campaigns == []

    campaign = make_campaign()
    repository.campaigns.append(campaign)
    original_html = campaign.html_body
    with pytest.raises(DomainError) as update_error:
        await service.update_campaign(
            campaign.id,
            CampaignUpdateRequest(html_body="<p>${not_in_campaign_context}</p>"),
            owner_id=OWNER_ID,
        )
    assert update_error.value.code == "campaign_template_unsupported_variables"
    assert campaign.html_body == original_html


def test_custom_branded_campaign_html_gets_sanitized_untracked_unsubscribe_link() -> None:
    message = _render_campaign_message(
        make_campaign(),
        make_recipient(),
        "https://example.com/u/1",
        SETTINGS,
    )

    unsubscribe_anchor = next(
        anchor
        for anchor in message.html_body.split("</a>")
        if 'data-codrut-cta="unsubscribe"' in anchor
    )
    assert 'href="https://example.com/u/1"' in unsubscribe_anchor
    assert "/track/" not in unsubscribe_anchor
    assert "Dezabonare" in message.html_body
    assert "Ai primit acest email deoarece" not in message.html_body


def test_campaign_placeholder_validation_allows_literal_dollar_escapes() -> None:
    validate_campaign_placeholders("Preț $$5", "<p>Cost $$</p>", "Cost $$")
