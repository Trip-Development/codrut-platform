import uuid
from datetime import datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from codrut.contracts.emails import (
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
    EmailSendResult,
)
from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
from codrut.modules.communications.campaign_tracking import (
    CampaignRecipientActionClaims,
    create_campaign_recipient_action_token,
)
from codrut.modules.communications.models import (
    Campaign,
    CampaignAsset,
    CampaignRecipient,
    CampaignRecipientEvent,
    CampaignRecipientMembership,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
    EmailSend,
    EmailSendStatus,
    EmailTemplate,
)
from codrut.modules.communications.schemas import (
    CampaignCreateRequest,
    CampaignRecipientBulkCreateRequest,
    CampaignRecipientCreateRequest,
    CampaignRecipientMembershipUpdateRequest,
    CampaignRecipientUpdateRequest,
    CampaignSendRequest,
    CampaignUpdateRequest,
    EmailTemplateCreateRequest,
    EmailTemplateUpdateRequest,
)
from codrut.modules.communications.service import (
    AssignmentInvitationContext,
    CommunicationsService,
    TransactionalEmailService,
    _email_message_from_outbox_payload,
)
from codrut.modules.communications.templates import (
    TransactionalTemplateKey,
    get_transactional_template,
)
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.identity import models as _identity_models  # noqa: F401
from codrut.tools.local_preview import build_preview_email_templates

TEST_OWNER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class FakeCommunicationsRepository:
    def __init__(self, templates: list[EmailTemplate] | None = None) -> None:
        self.templates = templates or []
        self.sends: list[EmailSend] = []
        self.sent_versions: set[tuple[str, int]] = set()
        self.campaign_recipients: list[CampaignRecipient] = []
        self.campaign_recipient_memberships: list[CampaignRecipientMembership] = []
        self.campaign_recipient_events: list[CampaignRecipientEvent] = []
        self.campaigns: list[Campaign] = []
        self.campaign_assets: list[CampaignAsset] = []
        self.list_template_calls = 0

    async def has_sent_emails(
        self,
        key: str,
        version: int,
        *,
        owner_id: uuid.UUID | None = None,
    ) -> bool:
        return (key, version) in self.sent_versions

    async def list_templates(
        self,
        *,
        active_only: bool = True,
        owner_id: uuid.UUID | None = None,
    ) -> list[EmailTemplate]:
        self.list_template_calls += 1
        templates = self.templates
        if owner_id is not None:
            templates = [t for t in templates if t.owner_id in {None, owner_id}]
        if active_only:
            templates = [t for t in templates if t.active]
        return sorted(templates, key=lambda t: (t.key, -t.version))

    async def get_template(
        self,
        key: str,
        *,
        version: int | None = None,
        owner_id: uuid.UUID | None = None,
    ) -> EmailTemplate | None:
        templates = [t for t in self.templates if t.key == key]
        if owner_id is not None:
            templates = [t for t in templates if t.owner_id in {None, owner_id}]
        if version is None:
            templates = [t for t in templates if t.active]
            templates = sorted(
                templates,
                key=lambda t: (t.owner_id is not None, t.version),
                reverse=True,
            )
            return templates[0] if templates else None
        return next(
            (t for t in templates if t.version == version),
            None,
        )

    async def get_latest_version(
        self,
        key: str,
        *,
        owner_id: uuid.UUID | None = None,
    ) -> int:
        versions = [
            t.version for t in self.templates if t.key == key and t.owner_id == owner_id
        ]
        return max(versions, default=0)

    async def add_template(
        self,
        template: EmailTemplate,
    ) -> EmailTemplate:
        template.id = uuid.uuid4()
        self.templates.append(template)
        return template

    async def deactivate_templates_for_key(
        self,
        key: str,
        *,
        except_version: int | None = None,
        owner_id: uuid.UUID | None = None,
    ) -> None:
        for t in self.templates:
            if (
                t.key == key
                and t.version != except_version
                and (owner_id is None or t.owner_id == owner_id)
            ):
                t.active = False

    async def list_campaign_recipients_by_emails(
        self,
        emails: set[str],
        *,
        owner_id: uuid.UUID | None = None,
        include_archived: bool = False,
        for_update: bool = False,
    ) -> list[CampaignRecipient]:
        del for_update
        return [
            recipient
            for recipient in self.campaign_recipients
            if recipient.email is not None
            and recipient.email.lower() in emails
            and (owner_id is None or recipient.owner_id == owner_id)
            and (include_archived or recipient.archived_at is None)
        ]

    async def add_campaign_recipients(
        self,
        recipients: list[CampaignRecipient],
        *,
        owner_id: uuid.UUID | None = None,
    ) -> None:
        if owner_id is not None:
            assert all(recipient.owner_id == owner_id for recipient in recipients)
        self.campaign_recipients.extend(recipients)

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
        if campaign.id is None:
            campaign.id = uuid.uuid4()
        self.campaigns.append(campaign)
        return campaign

    async def get_campaign_asset_by_url(
        self,
        public_url: str,
        *,
        owner_id: uuid.UUID,
        for_update: bool = False,
    ) -> CampaignAsset | None:
        del for_update
        return next(
            (
                asset
                for asset in self.campaign_assets
                if asset.public_url == public_url and asset.owner_id == owner_id
            ),
            None,
        )

    async def list_campaign_assets_for_campaign(
        self,
        campaign_id: uuid.UUID,
        *,
        owner_id: uuid.UUID,
    ) -> list[CampaignAsset]:
        return [
            asset
            for asset in self.campaign_assets
            if asset.campaign_id == campaign_id and asset.owner_id == owner_id
        ]

    async def delete_campaign(self, campaign: Campaign) -> None:
        self.campaigns = [
            saved_campaign for saved_campaign in self.campaigns if saved_campaign.id != campaign.id
        ]
        self.campaign_recipient_memberships = [
            membership
            for membership in self.campaign_recipient_memberships
            if membership.campaign_id != campaign.id
        ]

    async def list_campaign_recipients(
        self,
        *,
        owner_id: uuid.UUID | None = None,
        catalog_scope: str = "active",
    ) -> list[CampaignRecipient]:
        return [
            recipient
            for recipient in self.campaign_recipients
            if owner_id is None or recipient.owner_id == owner_id
            if (
                catalog_scope == "any"
                or (catalog_scope == "active" and recipient.archived_at is None)
                or (catalog_scope == "archived" and recipient.archived_at is not None)
            )
        ]

    async def list_campaign_recipients_by_ids(
        self,
        recipient_ids: list[uuid.UUID],
        *,
        owner_id: uuid.UUID | None = None,
    ) -> list[CampaignRecipient]:
        recipient_id_set = set(recipient_ids)
        return [
            recipient
            for recipient in self.campaign_recipients
            if recipient.id in recipient_id_set
            and (owner_id is None or recipient.owner_id == owner_id)
            and recipient.archived_at is None
        ]

    async def lock_campaign_recipients_for_send(
        self,
        recipient_ids: list[uuid.UUID],
        *,
        owner_id: uuid.UUID | None = None,
    ) -> list[CampaignRecipient]:
        return await self.list_campaign_recipients_by_ids(
            recipient_ids,
            owner_id=owner_id,
        )

    async def get_campaign_recipient(
        self,
        recipient_id: uuid.UUID,
        *,
        owner_id: uuid.UUID | None = None,
        catalog_scope: str = "active",
        for_update: bool = False,
    ) -> CampaignRecipient | None:
        del for_update
        return next(
            (
                recipient
                for recipient in self.campaign_recipients
                if recipient.id == recipient_id
                and (owner_id is None or recipient.owner_id == owner_id)
                and (
                    catalog_scope == "any"
                    or (catalog_scope == "active" and recipient.archived_at is None)
                    or (
                        catalog_scope == "archived"
                        and recipient.archived_at is not None
                    )
                )
            ),
            None,
        )

    async def get_campaign_recipient_by_email(
        self,
        email: str,
        *,
        owner_id: uuid.UUID | None = None,
    ) -> CampaignRecipient | None:
        return next(
            (
                recipient
                for recipient in self.campaign_recipients
                if recipient.email is not None
                and recipient.email.lower() == email.lower()
                and (owner_id is None or recipient.owner_id == owner_id)
                and recipient.archived_at is None
            ),
            None,
        )

    async def get_campaign_contact_tombstone(
        self,
        *,
        owner_id: uuid.UUID,
        former_recipient_id: uuid.UUID,
        for_update: bool = False,
    ) -> None:
        del owner_id, former_recipient_id, for_update
        return None

    async def get_email_suppression(
        self,
        *,
        owner_id: uuid.UUID,
        email_fingerprint: str,
        email: str | None = None,
    ) -> None:
        del owner_id, email_fingerprint, email
        return None

    async def list_email_suppressions_by_fingerprints(
        self,
        *,
        owner_id: uuid.UUID,
        email_fingerprints: set[str],
    ) -> list[object]:
        del owner_id, email_fingerprints
        return []

    async def suppress_email(
        self,
        *,
        owner_id: uuid.UUID,
        email: str,
        email_fingerprint: str,
        reason: str,
        source_email_send_id: uuid.UUID | None,
        review_after: datetime,
    ) -> object:
        return {
            "owner_id": owner_id,
            "email": email,
            "email_fingerprint": email_fingerprint,
            "reason": reason,
            "source_email_send_id": source_email_send_id,
            "review_after": review_after,
        }

    async def add_email_send(self, send: EmailSend) -> EmailSend:
        self.sends.append(send)
        return send

    async def get_email_send_by_idempotency_key(self, key: str) -> EmailSend | None:
        return next((send for send in self.sends if send.idempotency_key == key), None)

    async def add_campaign_recipient_event(
        self,
        event: CampaignRecipientEvent,
        *,
        owner_id: uuid.UUID | None = None,
    ) -> CampaignRecipientEvent:
        assert any(
            recipient.id == event.recipient_id
            and (owner_id is None or recipient.owner_id == owner_id)
            for recipient in self.campaign_recipients
        )
        self.campaign_recipient_events.append(event)
        return event

    async def list_accepted_campaign_recipient_ids(
        self,
        campaign_id: uuid.UUID,
        *,
        owner_id: uuid.UUID | None = None,
    ) -> set[uuid.UUID]:
        owned_recipient_ids = {
            recipient.id
            for recipient in self.campaign_recipients
            if owner_id is None or recipient.owner_id == owner_id
        }
        return {
            send.campaign_recipient_id
            for send in self.sends
            if send.campaign_id == campaign_id
            and send.campaign_recipient_id is not None
            and send.campaign_recipient_id in owned_recipient_ids
            and send.status in {EmailSendStatus.queued, EmailSendStatus.accepted}
        }

    async def list_campaign_delivery_status_by_recipient_ids(
        self,
        campaign_id: uuid.UUID,
        recipient_ids: list[uuid.UUID],
        *,
        owner_id: uuid.UUID | None = None,
    ) -> dict[uuid.UUID, str]:
        recipient_id_set = {
            recipient.id
            for recipient in self.campaign_recipients
            if recipient.id in recipient_ids
            and (owner_id is None or recipient.owner_id == owner_id)
        }
        statuses: dict[uuid.UUID, str] = {}
        priority = {
            "failed": 1,
            "queued": 2,
            "sent": 3,
        }
        for send in self.sends:
            if (
                send.campaign_id != campaign_id
                or send.campaign_recipient_id is None
                or send.campaign_recipient_id not in recipient_id_set
            ):
                continue
            if send.status == EmailSendStatus.accepted:
                next_status = "sent"
            elif send.status == EmailSendStatus.queued:
                next_status = "queued"
            elif send.status == EmailSendStatus.failed:
                next_status = "failed"
            else:
                next_status = "not_sent"
            if priority.get(next_status, 0) > priority.get(
                statuses.get(send.campaign_recipient_id, "not_sent"),
                0,
            ):
                statuses[send.campaign_recipient_id] = next_status
        return statuses

    async def list_campaign_member_recipient_ids(
        self,
        campaign_id: uuid.UUID,
        *,
        owner_id: uuid.UUID | None = None,
    ) -> list[uuid.UUID]:
        campaign = await self.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            return []
        return [
            membership.recipient_id
            for membership in self.campaign_recipient_memberships
            if membership.campaign_id == campaign_id
            and any(
                recipient.id == membership.recipient_id
                and (owner_id is None or recipient.owner_id == owner_id)
                for recipient in self.campaign_recipients
            )
        ]

    async def list_campaign_member_recipients(
        self,
        campaign_id: uuid.UUID,
        *,
        owner_id: uuid.UUID | None = None,
    ) -> list[CampaignRecipient]:
        member_ids = await self.list_campaign_member_recipient_ids(
            campaign_id,
            owner_id=owner_id,
        )
        member_id_set = set(member_ids)
        recipients = [
            recipient
            for recipient in self.campaign_recipients
            if recipient.id in member_id_set
            and (owner_id is None or recipient.owner_id == owner_id)
            and recipient.archived_at is None
        ]
        recipients_by_id = {recipient.id: recipient for recipient in recipients}
        return [
            recipients_by_id[recipient_id]
            for recipient_id in member_ids
            if recipient_id in recipients_by_id
        ]

    async def replace_campaign_memberships(
        self,
        campaign_id: uuid.UUID,
        recipient_ids: list[uuid.UUID],
        *,
        source: str = "manual",
        owner_id: uuid.UUID | None = None,
    ) -> None:
        campaign = await self.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            return
        next_ids = list(dict.fromkeys(recipient_ids))
        if any(
            recipient_id
            not in {
                recipient.id
                for recipient in self.campaign_recipients
                if (owner_id is None or recipient.owner_id == owner_id)
                and recipient.archived_at is None
            }
            for recipient_id in next_ids
        ):
            raise ValueError("campaign membership contains contacts from another owner")
        next_id_set = set(next_ids)
        self.campaign_recipient_memberships = [
            membership
            for membership in self.campaign_recipient_memberships
            if membership.campaign_id != campaign_id or membership.recipient_id in next_id_set
        ]
        existing_ids = {
            membership.recipient_id
            for membership in self.campaign_recipient_memberships
            if membership.campaign_id == campaign_id
        }
        for recipient_id in next_ids:
            if recipient_id not in existing_ids:
                self.campaign_recipient_memberships.append(
                    CampaignRecipientMembership(
                        id=uuid.uuid4(),
                        campaign_id=campaign_id,
                        recipient_id=recipient_id,
                        source=source,
                    )
                )

    async def count_accepted_sends_since(self, _since: object) -> int:
        return sum(1 for send in self.sends if send.status == EmailSendStatus.accepted)

    async def delete_campaign_recipient_memberships(
        self,
        recipient_id: uuid.UUID,
        *,
        owner_id: uuid.UUID,
    ) -> int:
        campaign_ids = {
            campaign.id for campaign in self.campaigns if campaign.owner_id == owner_id
        }
        before = len(self.campaign_recipient_memberships)
        self.campaign_recipient_memberships = [
            membership
            for membership in self.campaign_recipient_memberships
            if not (
                membership.recipient_id == recipient_id
                and membership.campaign_id in campaign_ids
            )
        ]
        return before - len(self.campaign_recipient_memberships)

    async def cancel_unsent_campaign_recipient_sends(
        self,
        recipient_id: uuid.UUID,
        *,
        owner_id: uuid.UUID,
        now: datetime,
    ) -> tuple[int, int]:
        cancelled = 0
        in_flight = 0
        for send in self.sends:
            if (
                send.campaign_recipient_id != recipient_id
                or send.owner_id != owner_id
                or send.status
                not in {EmailSendStatus.queued, EmailSendStatus.dispatching}
            ):
                continue
            if send.provider_request_started_at is not None:
                in_flight += 1
                continue
            send.status = EmailSendStatus.cancelled
            send.cancelled_at = now
            cancelled += 1
        in_flight += sum(
            1
            for send in self.sends
            if send.campaign_recipient_id == recipient_id
            and send.owner_id == owner_id
            and send.status == EmailSendStatus.indeterminate
        )
        return cancelled, in_flight

    async def flush(self) -> None:
        return None


class FakeEmailProvider:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> EmailSendResult:
        self.sent.append(message)
        return EmailSendResult(
            provider=EmailProviderKey.test,
            status=EmailDeliveryStatus.accepted,
            message_id=f"msg-{uuid.uuid4()}",
            recipient=message.to,
        )


def queued_messages(repository: FakeCommunicationsRepository) -> list[EmailMessage]:
    return [
        _email_message_from_outbox_payload(send.message_payload)
        for send in repository.sends
        if send.status == EmailSendStatus.queued
    ]


def make_service(repository: FakeCommunicationsRepository) -> CommunicationsService:
    service = CommunicationsService()
    service.repository = cast(Any, repository)
    return service


def persisted_template(
    *,
    key: str = "account_setup",
    version: int = 1,
    active: bool = True,
) -> EmailTemplate:
    return EmailTemplate(
        id=uuid.uuid4(),
        key=key,
        version=version,
        subject="Setup account for ${company_name}",
        html_body=(
            "<p>Buna, ${participant_name}.</p>"
            "<p>Trainer: ${trainer_name}</p>"
            '<p><a href="${action_url}">link</a></p>'
        ),
        text_body="Buna, ${participant_name}. Trainer: ${trainer_name}. link: ${action_url}",
        variables=["participant_name", "trainer_name", "company_name", "action_url"],
        audience="participant",
        active=active,
    )


@pytest.mark.asyncio
async def test_bulk_create_campaign_recipients_dedupes_email_last_row_wins() -> None:
    repository = FakeCommunicationsRepository()
    existing = CampaignRecipient(
        id=uuid.uuid4(),
        owner_id=TEST_OWNER_ID,
        email="existing@example.com",
        contact_name="Existing Contact",
        organization_name="Existing Org",
        segment="potential_customer",
        source="manual",
    )
    repository.campaign_recipients.append(existing)
    service = make_service(repository)

    recipients = await service.bulk_create_campaign_recipients(
        CampaignRecipientBulkCreateRequest(
            recipients=[
                CampaignRecipientCreateRequest(
                    email="NEW@example.com",
                    contact_name="New Contact",
                    organization_name="New Org",
                    segment="potential_customer",
                    source="csv",
                ),
                CampaignRecipientCreateRequest(
                    email="new@example.com",
                    contact_name="Duplicate Contact",
                    organization_name="Duplicate Org",
                    segment="potential_customer",
                    source="csv",
                ),
                CampaignRecipientCreateRequest(
                    email="existing@example.com",
                    contact_name="Existing Again",
                    organization_name="Existing Org",
                    segment="potential_customer",
                    source="csv",
                ),
            ]
        ),
        owner_id=TEST_OWNER_ID,
    )

    assert [recipient.email for recipient in repository.campaign_recipients] == [
        "existing@example.com",
        "new@example.com",
    ]
    assert [recipient.email for recipient in recipients] == [
        "existing@example.com",
        "new@example.com",
    ]
    assert repository.campaign_recipients[1].contact_name == "Duplicate Contact"
    assert repository.campaign_recipients[1].organization_name == "Duplicate Org"


@pytest.mark.asyncio
async def test_bulk_create_campaign_recipients_reports_created_and_updated_counts() -> None:
    repository = FakeCommunicationsRepository()
    existing = CampaignRecipient(
        id=uuid.uuid4(),
        owner_id=TEST_OWNER_ID,
        email="existing@example.com",
        contact_name="Existing Contact",
        organization_name="Existing Org",
        segment="potential_customer",
        source="manual",
    )
    repository.campaign_recipients.append(existing)
    service = make_service(repository)

    result = await service.bulk_create_campaign_recipients_with_result(
        CampaignRecipientBulkCreateRequest(
            recipients=[
                CampaignRecipientCreateRequest(
                    email="new@example.com",
                    contact_name="New Contact",
                    organization_name="New Org",
                    segment="potential_customer",
                    source="csv",
                ),
                CampaignRecipientCreateRequest(
                    email="existing@example.com",
                    contact_name="Existing Again",
                    organization_name="Existing Org Updated",
                    segment="past_customer",
                    source="csv",
                ),
            ]
        ),
        owner_id=TEST_OWNER_ID,
    )

    assert result.created == 1
    assert result.updated == 1
    assert len(result.recipients) == 2
    assert result.recipients[1].segment is CampaignRecipientSegment.potential_customer
    assert existing.contact_name == "Existing Again"
    assert existing.organization_name == "Existing Org Updated"
    assert existing.segment == "past_customer"


@pytest.mark.asyncio
async def test_bulk_create_campaign_recipients_creates_owner_local_contact() -> None:
    first_owner_id = uuid.uuid4()
    second_owner_id = uuid.uuid4()
    repository = FakeCommunicationsRepository()
    existing = persisted_campaign_recipient(email="shared@example.com")
    existing.owner_id = second_owner_id
    repository.campaign_recipients.append(existing)
    service = make_service(repository)

    result = await service.bulk_create_campaign_recipients_with_result(
        CampaignRecipientBulkCreateRequest(
            recipients=[
                CampaignRecipientCreateRequest(
                    email="shared@example.com",
                    contact_name="Owner One",
                    organization_name="Compania owner one",
                    segment="potential_customer",
                    source="csv",
                ),
            ]
        ),
        owner_id=first_owner_id,
    )

    assert result.created == 1
    assert result.updated == 0
    assert len(repository.campaign_recipients) == 2
    assert existing.owner_id == second_owner_id
    assert existing.contact_name == "Ana Director"
    assert existing.organization_name == "Compania A"
    owner_local = repository.campaign_recipients[1]
    assert owner_local.owner_id == first_owner_id
    assert owner_local.email == "shared@example.com"
    assert owner_local.contact_name == "Owner One"
    assert owner_local.organization_name == "Compania owner one"


@pytest.mark.asyncio
async def test_bulk_import_locks_and_rejects_contact_archived_concurrently() -> None:
    archived_at = datetime.now()
    repository = FakeCommunicationsRepository()
    archived = persisted_campaign_recipient(email="archived@example.com")
    archived.archived_at = archived_at
    archived.purge_after = archived_at + timedelta(days=30)
    repository.campaign_recipients.append(archived)
    original_lookup = repository.list_campaign_recipients_by_emails
    repository.list_campaign_recipients_by_emails = AsyncMock(  # type: ignore[method-assign]
        wraps=original_lookup
    )
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.bulk_create_campaign_recipients_with_result(
            CampaignRecipientBulkCreateRequest(
                recipients=[
                    CampaignRecipientCreateRequest(
                        email="archived@example.com",
                        contact_name="Archived",
                        organization_name="Compania",
                        segment="potential_customer",
                        source="csv",
                    ),
                ]
            ),
            owner_id=TEST_OWNER_ID,
        )

    assert exc_info.value.code == "campaign_recipient_archived"
    repository.list_campaign_recipients_by_emails.assert_awaited_once_with(
        {"archived@example.com"},
        owner_id=TEST_OWNER_ID,
        include_archived=True,
        for_update=True,
    )


@pytest.mark.asyncio
async def test_bulk_create_campaign_recipients_allows_suppressed_contacts_without_email() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    recipients = await service.bulk_create_campaign_recipients(
        CampaignRecipientBulkCreateRequest(
            recipients=[
                CampaignRecipientCreateRequest(
                    email=None,
                    contact_name="No Email",
                    organization_name="Missing Mail Org",
                    segment="potential_customer",
                    status="suppressed",
                    source="excel_import",
                ),
            ]
        ),
        owner_id=TEST_OWNER_ID,
    )

    assert len(recipients) == 1
    assert recipients[0].email is None
    assert recipients[0].status == CampaignRecipientStatus.suppressed


def persisted_campaign() -> Campaign:
    return Campaign(
        id=uuid.uuid4(),
        owner_id=TEST_OWNER_ID,
        name="Leadership video",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignStatus.ready,
        subject="Salut ${first_name}",
        html_body="<p>Bună, {first_name}.</p>",
        text_body="Bună, {first_name}.",
        recipient_memberships_initialized=False,
    )


def persisted_protected_template(
    *,
    key: str = "preview_campaign_reactivation",
) -> EmailTemplate:
    preview = build_preview_email_templates()[key]
    return EmailTemplate(
        id=uuid.uuid4(),
        key=preview.key,
        version=preview.version,
        subject=preview.subject,
        html_body=preview.html_body,
        text_body=preview.text_body,
        variables=sorted(preview.required_context),
        audience=preview.audience,
        active=True,
        package_id="test-protected-package",
        content_checksum="a" * 64,
        system_managed=True,
        owner_id=None,
    )


def persisted_campaign_recipient(
    *,
    email: str = "ana@example.com",
    contact_name: str = "Ana Director",
    segment: CampaignRecipientSegment = CampaignRecipientSegment.potential_customer,
    status: CampaignRecipientStatus = CampaignRecipientStatus.active,
) -> CampaignRecipient:
    return CampaignRecipient(
        id=uuid.uuid4(),
        owner_id=TEST_OWNER_ID,
        email=email,
        contact_name=contact_name,
        organization_name="Compania A",
        segment=segment,
        status=status,
    )


@pytest.mark.asyncio
async def test_send_campaign_sends_active_members_across_segments_with_unsubscribe_link() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    active = persisted_campaign_recipient()
    suppressed = persisted_campaign_recipient(
        email="stop@example.com",
        status=CampaignRecipientStatus.unsubscribed,
    )
    other_segment = persisted_campaign_recipient(
        email="old@example.com",
        segment=CampaignRecipientSegment.past_customer,
    )
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([active, suppressed, other_segment])
    provider = FakeEmailProvider()
    service = make_service(repository)

    settings = Settings(
        public_app_url="https://codrut.andreivacaru.ro",
        email_legal_address="Cody legal footer",
    )
    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(recipient_ids=[active.id, suppressed.id, other_segment.id]),
        provider=provider,
        settings=settings,
    )

    assert response.queued == 2
    assert response.sent == 0
    assert response.skipped == 1
    assert campaign.status == CampaignStatus.ready
    assert provider.sent == []
    message = queued_messages(repository)[0]
    assert message.to.value == active.email
    assert message.subject == "Salut Ana"
    assert (
        "https://codrut.andreivacaru.ro/api/communications/campaigns/unsubscribe/"
        in message.html_body
    )
    assert (
        "https://codrut.andreivacaru.ro/api/communications/campaigns/track/calendly/"
        in message.html_body
    )
    assert "Alege un slot" in message.html_body
    assert (
        "https://codrut.andreivacaru.ro/api/communications/campaigns/track/calendly/"
        in message.text_body
    )
    assert "Ai primit acest email deoarece" in message.html_body
    assert settings.email_legal_address in message.html_body
    assert {send.recipient_email for send in repository.sends} == {
        active.email,
        other_segment.email,
    }
    assert all(send.assignment_id is None for send in repository.sends)
    assert all(send.template_key == "campaign" for send in repository.sends)


@pytest.mark.asyncio
async def test_send_campaign_does_not_append_duplicate_calendly_cta() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.html_body = (
        "<p>Bună, ${first_name}.</p>"
        '<p><a href="https://calendly.com/andrei-vacaru/discutie">'
        "Alege un slot"
        "</a></p>"
    )
    campaign.text_body = (
        "Bună, ${first_name}.\nAlege un slot: https://calendly.com/andrei-vacaru/discutie"
    )
    active = persisted_campaign_recipient()
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(active)
    provider = FakeEmailProvider()
    service = make_service(repository)

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(recipient_ids=[active.id]),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    assert response.queued == 1
    message = queued_messages(repository)[0]
    assert message.html_body.count("Alege un slot") == 1
    assert message.text_body.count("Alege un slot") == 1
    assert (
        "https://codrut.andreivacaru.ro/api/communications/campaigns/track/calendly/"
        in message.html_body
    )


@pytest.mark.asyncio
async def test_send_campaign_adds_open_click_and_video_tracking() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.video_url = "https://vimeo.com/123456789"
    campaign.thumbnail_url = "https://codrut.andreivacaru.ro/api/campaign-assets/demo.jpg"
    campaign.landing_page_url = "https://codrut.andreivacaru.ro/campanii/demo"
    campaign.html_body = (
        '<p><a href="${landing_page_url}"><img src="${thumbnail_url}" alt="Video" /></a></p>'
        '<p><a href="https://example.com/articol">Citește articolul</a></p>'
        '<p><a href="${calendly_url}" data-codrut-cta="calendly">Alege un slot</a></p>'
    )
    active = persisted_campaign_recipient()
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(active)
    provider = FakeEmailProvider()
    service = make_service(repository)
    settings = Settings(public_app_url="https://codrut.andreivacaru.ro")

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(recipient_ids=[active.id]),
        provider=provider,
        settings=settings,
    )

    html_body = queued_messages(repository)[0].html_body
    assert response.queued == 1
    assert "/api/communications/campaigns/track/opened/" in html_body
    assert "/api/communications/campaigns/track/video_viewed/" in html_body
    assert "/api/communications/campaigns/track/clicked/" in html_body
    assert html_body.count("/api/communications/campaigns/track/calendly/") == 1

    clicked_token = html_body.split("/api/communications/campaigns/track/clicked/", 1)[1].split(
        '"', 1
    )[0]
    target_url = await service.record_campaign_tracking_link(
        clicked_token,
        settings,
        expected_event_type="clicked",
    )
    assert target_url == "https://example.com/articol"
    assert repository.campaign_recipient_events[-1].event_type == "clicked"


@pytest.mark.asyncio
async def test_send_campaign_repairs_plain_video_and_calendly_content() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.video_url = "https://vimeo.com/123456789"
    campaign.thumbnail_url = "https://codrut.andreivacaru.ro/api/campaign-assets/demo.jpg"
    campaign.landing_page_url = "https://codrut.andreivacaru.ro/campanii/demo"
    campaign.html_body = (
        "<p>Material video: ${landing_page_url}</p>"
        "<p>Alege un slot: ${calendly_url}</p>"
    )
    campaign.text_body = (
        "Material video: ${landing_page_url}\n"
        "Alege un slot: ${calendly_url}"
    )
    active = persisted_campaign_recipient()
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(active)
    provider = FakeEmailProvider()
    service = make_service(repository)

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(recipient_ids=[active.id]),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    message = queued_messages(repository)[0]
    assert response.queued == 1
    assert campaign.thumbnail_url in message.html_body
    assert "/api/communications/campaigns/track/video_viewed/" in message.html_body
    assert 'data-codrut-cta="calendly"' in message.html_body
    assert message.html_body.count("Alege un slot în Calendly") == 1
    assert "Material video:" not in message.html_body
    assert "Alege un slot:" not in message.html_body
    assert "Material video:" in message.text_body
    assert message.text_body.count("Alege un slot:") == 1


@pytest.mark.asyncio
async def test_send_campaign_removes_styled_fallback_links_from_html() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.video_url = "https://vimeo.com/123456789"
    campaign.thumbnail_url = "https://codrut.andreivacaru.ro/api/campaign-assets/demo.jpg"
    campaign.landing_page_url = "https://codrut.andreivacaru.ro/campanii/demo"
    campaign.html_body = (
        '<p><a href="${landing_page_url}">'
        '<img src="${thumbnail_url}" alt="Video" />'
        "</a></p>"
        '<p>Link platformă: <a href="${landing_page_url}">${landing_page_url}</a></p>'
        '<p><a href="${calendly_url}" data-codrut-cta="calendly">'
        "Alege un slot"
        "</a></p>"
        '<p>Link platformă: <a href="${calendly_url}">${calendly_url}</a></p>'
    )
    campaign.text_body = (
        "Material video: ${landing_page_url}\n"
        "Alege un slot: ${calendly_url}"
    )
    active = persisted_campaign_recipient()
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(active)
    service = make_service(repository)

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(recipient_ids=[active.id]),
        provider=FakeEmailProvider(),
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    message = queued_messages(repository)[0]
    assert response.queued == 1
    assert "Link platformă:" not in message.html_body
    assert "/api/communications/campaigns/track/video_viewed/" in message.html_body
    assert 'data-codrut-cta="calendly"' in message.html_body
    assert "Material video:" in message.text_body
    assert "Alege un slot:" in message.text_body


@pytest.mark.asyncio
async def test_send_campaign_rejects_calendly_substring_as_existing_text_link() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.html_body = "<p>Link extern: https://calendly.com.evil.example/demo</p>"
    campaign.text_body = "Link extern: https://calendly.com.evil.example/demo"
    active = persisted_campaign_recipient()
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(active)
    service = make_service(repository)

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(recipient_ids=[active.id]),
        provider=FakeEmailProvider(),
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    message = queued_messages(repository)[0]
    assert response.queued == 1
    assert 'data-codrut-cta="calendly"' in message.html_body
    assert "Alege un slot în Calendly:" in message.text_body


@pytest.mark.asyncio
async def test_send_campaign_without_video_removes_empty_video_blocks() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.html_body = (
        "<p>Intro.</p>"
        '<p><a href="${landing_page_url}"><img src="${thumbnail_url}" alt="Video" /></a></p>'
    )
    campaign.text_body = "Intro.\nVideo: ${landing_page_url}\nFinal."
    active = persisted_campaign_recipient()
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(active)
    provider = FakeEmailProvider()
    service = make_service(repository)

    await service.send_campaign(
        campaign.id,
        CampaignSendRequest(recipient_ids=[active.id]),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    message = queued_messages(repository)[0]
    assert '<img src=""' not in message.html_body
    assert 'href=""' not in message.html_body
    assert "Video:" not in message.text_body


@pytest.mark.asyncio
async def test_trainer_edit_clones_protected_template_without_mutating_source() -> None:
    source = persisted_protected_template()
    repository = FakeCommunicationsRepository([source])
    service = make_service(repository)

    result = await service.update_template(
        source.key,
        EmailTemplateUpdateRequest(subject="Variantă locală pentru ${first_name}"),
        owner_id=TEST_OWNER_ID,
    )

    assert result.version == source.version + 1
    assert result.owner_id == TEST_OWNER_ID
    assert result.subject == "Variantă locală pentru ${first_name}"
    assert source.subject == build_preview_email_templates()[source.key].subject
    assert source.owner_id is None
    assert source.system_managed is True
    assert source.package_id == "test-protected-package"


@pytest.mark.asyncio
async def test_trainer_cannot_retire_protected_template() -> None:
    source = persisted_protected_template(key="preview_evaluation_invite")
    repository = FakeCommunicationsRepository([source])
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.retire_template(source.key, owner_id=TEST_OWNER_ID)

    assert exc_info.value.code == "email_template_system_retire_forbidden"
    assert source.active is True


@pytest.mark.asyncio
async def test_send_campaign_uses_video_url_when_landing_page_is_missing() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.video_url = "https://vimeo.com/123456789"
    campaign.thumbnail_url = "https://codrut.andreivacaru.ro/api/campaign-assets/demo.jpg"
    campaign.landing_page_url = None
    campaign.html_body = '<a href="${landing_page_url}">Vezi video</a>'
    campaign.text_body = "Vezi video: ${landing_page_url}"
    recipient = persisted_campaign_recipient()
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(recipient)
    provider = FakeEmailProvider()
    service = make_service(repository)

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(recipient_ids=[recipient.id]),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    assert response.queued == 1
    message = queued_messages(repository)[0]
    assert "/api/communications/campaigns/track/video_viewed/" in message.html_body
    assert "Vezi video: https://vimeo.com/123456789" in message.text_body


@pytest.mark.asyncio
async def test_send_campaign_default_mode_skips_already_accepted_recipients() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    first = persisted_campaign_recipient(email="first@example.com", contact_name="First")
    second = persisted_campaign_recipient(email="second@example.com", contact_name="Second")
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([first, second])
    repository.campaign_recipient_memberships.extend(
        [
            CampaignRecipientMembership(
                id=uuid.uuid4(),
                campaign_id=campaign.id,
                recipient_id=first.id,
                source="manual",
            ),
            CampaignRecipientMembership(
                id=uuid.uuid4(),
                campaign_id=campaign.id,
                recipient_id=second.id,
                source="manual",
            ),
        ]
    )
    repository.sends.append(
        EmailSend(
            id=uuid.uuid4(),
            campaign_id=campaign.id,
            campaign_recipient_id=first.id,
            recipient_email=first.email or "",
            template_key="campaign",
            template_version=1,
            provider="test",
            status=EmailSendStatus.accepted,
        )
    )
    provider = FakeEmailProvider()
    service = make_service(repository)

    second_response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    assert second_response.queued == 1
    assert queued_messages(repository)[0].to.value == second.email
    assert provider.sent == []


@pytest.mark.asyncio
async def test_send_campaign_reuses_result_for_same_idempotency_key() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    recipient = persisted_campaign_recipient(email="safe@example.com", contact_name="Safe")
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(recipient)
    repository.campaign_recipient_memberships.append(
        CampaignRecipientMembership(
            id=uuid.uuid4(),
            campaign_id=campaign.id,
            recipient_id=recipient.id,
            source="manual",
        )
    )
    provider = FakeEmailProvider()
    service = make_service(repository)
    settings = Settings(public_app_url="https://codrut.andreivacaru.ro")

    first = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(mode="all"),
        provider=provider,
        settings=settings,
        idempotency_key="same-request-key",
    )
    second = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(mode="all"),
        provider=provider,
        settings=settings,
        idempotency_key="same-request-key",
    )

    assert first.queued == second.queued == 1
    assert first.sent == second.sent == 0
    assert provider.sent == []
    assert len(repository.sends) == 1


@pytest.mark.asyncio
async def test_campaign_membership_marks_sent_and_failed_delivery() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    sent_recipient = persisted_campaign_recipient(email="sent@example.com", contact_name="Sent")
    failed_recipient = persisted_campaign_recipient(
        email="failed@example.com",
        contact_name="Failed",
    )
    unsent_recipient = persisted_campaign_recipient(
        email="unsent@example.com",
        contact_name="Unsent",
    )
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([sent_recipient, failed_recipient, unsent_recipient])
    repository.campaign_recipient_memberships.extend(
        [
            CampaignRecipientMembership(
                id=uuid.uuid4(),
                campaign_id=campaign.id,
                recipient_id=sent_recipient.id,
                source="manual",
            ),
            CampaignRecipientMembership(
                id=uuid.uuid4(),
                campaign_id=campaign.id,
                recipient_id=failed_recipient.id,
                source="manual",
            ),
            CampaignRecipientMembership(
                id=uuid.uuid4(),
                campaign_id=campaign.id,
                recipient_id=unsent_recipient.id,
                source="manual",
            ),
        ]
    )
    repository.sends.extend(
        [
            EmailSend(
                id=uuid.uuid4(),
                campaign_id=campaign.id,
                campaign_recipient_id=sent_recipient.id,
                recipient_email=sent_recipient.email or "",
                template_key="campaign",
                template_version=1,
                provider="test",
                status=EmailSendStatus.accepted,
            ),
            EmailSend(
                id=uuid.uuid4(),
                campaign_id=campaign.id,
                campaign_recipient_id=failed_recipient.id,
                recipient_email=failed_recipient.email or "",
                template_key="campaign",
                template_version=1,
                provider="test",
                status=EmailSendStatus.failed,
            ),
        ]
    )
    service = make_service(repository)

    members = await service.list_campaign_recipient_memberships(campaign.id)

    delivery_by_email = {member.email: member.campaignDelivery for member in members}
    assert delivery_by_email == {
        "sent@example.com": "sent",
        "failed@example.com": "failed",
        "unsent@example.com": "not_sent",
    }


@pytest.mark.asyncio
async def test_campaign_membership_isolated_between_campaigns_with_same_segment() -> None:
    repository = FakeCommunicationsRepository()
    first_campaign = persisted_campaign()
    second_campaign = persisted_campaign()
    second_campaign.id = uuid.uuid4()
    second_campaign.name = "Altă campanie"
    first = persisted_campaign_recipient(email="first@example.com", contact_name="First")
    second = persisted_campaign_recipient(email="second@example.com", contact_name="Second")
    repository.campaigns.extend([first_campaign, second_campaign])
    repository.campaign_recipients.extend([first, second])
    service = make_service(repository)

    first_members = await service.replace_campaign_recipient_memberships(
        first_campaign.id,
        CampaignRecipientMembershipUpdateRequest(recipient_ids=[first.id]),
    )
    second_members = await service.replace_campaign_recipient_memberships(
        second_campaign.id,
        CampaignRecipientMembershipUpdateRequest(recipient_ids=[second.id]),
    )

    assert [member.email for member in first_members] == ["first@example.com"]
    assert [member.email for member in second_members] == ["second@example.com"]
    assert [
        membership.recipient_id
        for membership in repository.campaign_recipient_memberships
        if membership.campaign_id == first_campaign.id
    ] == [first.id]
    assert [
        membership.recipient_id
        for membership in repository.campaign_recipient_memberships
        if membership.campaign_id == second_campaign.id
    ] == [second.id]


@pytest.mark.asyncio
async def test_empty_manual_campaign_membership_does_not_auto_backfill() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    first = persisted_campaign_recipient(email="first@example.com", contact_name="First")
    second = persisted_campaign_recipient(email="second@example.com", contact_name="Second")
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([first, second])
    service = make_service(repository)

    members = await service.replace_campaign_recipient_memberships(
        campaign.id,
        CampaignRecipientMembershipUpdateRequest(recipient_ids=[]),
    )
    listed_members = await service.list_campaign_recipient_memberships(campaign.id)

    assert members == []
    assert listed_members == []
    assert campaign.recipient_memberships_initialized is True
    assert [
        membership.recipient_id
        for membership in repository.campaign_recipient_memberships
        if membership.campaign_id == campaign.id
    ] == []


@pytest.mark.asyncio
async def test_no_group_campaign_does_not_auto_backfill_recipients() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.segment = None
    first = persisted_campaign_recipient(email="first@example.com", contact_name="First")
    second = persisted_campaign_recipient(
        email="second@example.com",
        contact_name="Second",
        segment=CampaignRecipientSegment.past_customer,
    )
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([first, second])
    service = make_service(repository)

    listed_members = await service.list_campaign_recipient_memberships(campaign.id)

    assert listed_members == []
    assert campaign.recipient_memberships_initialized is False
    assert repository.campaign_recipient_memberships == []


@pytest.mark.asyncio
async def test_no_group_campaign_accepts_recipients_from_both_segments() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.segment = None
    potential = persisted_campaign_recipient(
        email="potential@example.com",
        contact_name="Potential",
    )
    existing = persisted_campaign_recipient(
        email="existing@example.com",
        contact_name="Existing",
        segment=CampaignRecipientSegment.past_customer,
    )
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([potential, existing])
    service = make_service(repository)

    members = await service.replace_campaign_recipient_memberships(
        campaign.id,
        CampaignRecipientMembershipUpdateRequest(recipient_ids=[potential.id, existing.id]),
    )

    assert [member.email for member in members] == [
        "potential@example.com",
        "existing@example.com",
    ]
    assert campaign.recipient_memberships_initialized is True


@pytest.mark.asyncio
async def test_segment_campaign_accepts_manual_cross_segment_membership() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    existing = persisted_campaign_recipient(
        email="existing@example.com",
        contact_name="Existing",
        segment=CampaignRecipientSegment.past_customer,
    )
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(existing)
    service = make_service(repository)

    members = await service.replace_campaign_recipient_memberships(
        campaign.id,
        CampaignRecipientMembershipUpdateRequest(recipient_ids=[existing.id]),
    )

    assert [member.email for member in members] == ["existing@example.com"]
    assert campaign.recipient_memberships_initialized is True
    assert [
        membership.recipient_id
        for membership in repository.campaign_recipient_memberships
        if membership.campaign_id == campaign.id
    ] == [existing.id]


@pytest.mark.asyncio
async def test_send_campaign_uses_persisted_membership_not_all_segment_contacts() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    selected = persisted_campaign_recipient(email="selected@example.com", contact_name="Selected")
    unselected = persisted_campaign_recipient(
        email="unselected@example.com",
        contact_name="Unselected",
    )
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([selected, unselected])
    repository.campaign_recipient_memberships.append(
        CampaignRecipientMembership(
            id=uuid.uuid4(),
            campaign_id=campaign.id,
            recipient_id=selected.id,
            source="manual",
        )
    )
    provider = FakeEmailProvider()
    service = make_service(repository)

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    assert response.queued == 1
    assert queued_messages(repository)[0].to.value == "selected@example.com"
    assert all(
        message.to.value != "unselected@example.com" for message in queued_messages(repository)
    )


@pytest.mark.asyncio
async def test_send_campaign_all_resends_only_campaign_members() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    selected = persisted_campaign_recipient(email="selected@example.com", contact_name="Selected")
    unselected = persisted_campaign_recipient(
        email="unselected@example.com",
        contact_name="Unselected",
    )
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([selected, unselected])
    repository.campaign_recipient_memberships.append(
        CampaignRecipientMembership(
            id=uuid.uuid4(),
            campaign_id=campaign.id,
            recipient_id=selected.id,
            source="manual",
        )
    )
    provider = FakeEmailProvider()
    service = make_service(repository)

    await service.send_campaign(
        campaign.id,
        CampaignSendRequest(),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )
    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(mode="all"),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    assert response.queued == 1
    assert [message.to.value for message in queued_messages(repository)] == ["selected@example.com"]
    assert provider.sent == []


@pytest.mark.asyncio
async def test_send_campaign_only_uses_contacts_owned_by_campaign_owner() -> None:
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.owner_id = owner_id
    matching = persisted_campaign_recipient(email="owner@example.com", contact_name="Owner")
    matching.owner_id = owner_id
    other_owner = persisted_campaign_recipient(email="other@example.com", contact_name="Other")
    other_owner.owner_id = other_owner_id
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([matching, other_owner])
    provider = FakeEmailProvider()
    service = make_service(repository)

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(mode="all"),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
        owner_id=owner_id,
    )

    assert response.queued == 1
    assert {message.to.value for message in queued_messages(repository)} == {"owner@example.com"}


@pytest.mark.asyncio
async def test_campaign_membership_rejects_contact_from_another_owner() -> None:
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.owner_id = owner_id
    other_owner_contact = persisted_campaign_recipient(email="other@example.com")
    other_owner_contact.owner_id = other_owner_id
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(other_owner_contact)
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.replace_campaign_recipient_memberships(
            campaign.id,
            CampaignRecipientMembershipUpdateRequest(recipient_ids=[other_owner_contact.id]),
            owner_id=owner_id,
        )

    assert exc_info.value.code == "campaign_membership_recipient_not_found"
    assert repository.campaign_recipient_memberships == []


@pytest.mark.asyncio
async def test_send_campaign_respects_daily_email_cap() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    first = persisted_campaign_recipient(email="first@example.com", contact_name="First")
    second = persisted_campaign_recipient(email="second@example.com", contact_name="Second")
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([first, second])
    provider = FakeEmailProvider()
    service = make_service(repository)

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(mode="all"),
        provider=provider,
        settings=Settings(
            public_app_url="https://codrut.andreivacaru.ro",
            email_daily_send_cap=1,
        ),
    )

    assert response.queued == 1
    assert response.sent == 0
    assert response.skipped == 1
    assert response.results[1].error == "Daily email send cap reached."
    assert provider.sent == []


@pytest.mark.asyncio
async def test_send_campaign_dry_run_does_not_send_or_log() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    recipient = persisted_campaign_recipient()
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(recipient)
    provider = FakeEmailProvider()
    service = make_service(repository)

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(dry_run=True),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    assert response.dry_run is True
    assert response.sent == 0
    assert response.skipped == 1
    assert provider.sent == []
    assert repository.sends == []
    assert campaign.status == CampaignStatus.ready


@pytest.mark.asyncio
async def test_create_campaign_marks_valid_campaign_ready() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    campaign = await service.create_campaign(
        CampaignCreateRequest(
            name="Campanie pilot",
            segment="potential_customer",
            subject="Salut ${first_name}",
            html_body="<p>Bună.</p>",
            text_body="Bună.",
        )
    )

    assert campaign.status == CampaignStatus.ready


@pytest.mark.asyncio
async def test_create_campaign_keeps_incomplete_video_as_draft() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    campaign = await service.create_campaign(
        CampaignCreateRequest(
            name="Video în lucru",
            segment="potential_customer",
            subject="Salut ${first_name}",
            html_body="<p>Bună.</p>",
            text_body="Bună.",
            video_url="https://vimeo.com/123456789",
        )
    )

    assert campaign.status == CampaignStatus.draft


@pytest.mark.asyncio
async def test_create_campaign_allows_no_preselected_group() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    campaign = await service.create_campaign(
        CampaignCreateRequest(
            name="Campanie fără grup",
            segment=None,
            subject="Salut ${first_name}",
            html_body="<p>Bună.</p>",
            text_body="Bună.",
        )
    )

    assert campaign.segment is None
    assert campaign.status == CampaignStatus.ready


@pytest.mark.asyncio
async def test_campaign_asset_is_owner_validated_and_returns_to_staged_on_replacement() -> None:
    repository = FakeCommunicationsRepository()
    asset = CampaignAsset(
        id=uuid.uuid4(),
        owner_id=TEST_OWNER_ID,
        file_name="owned-thumbnail.png",
        public_url="https://codrut.local/api/campaign-assets/owned-thumbnail.png",
        content_type="image/png",
        size_bytes=128,
        status="staged",
    )
    repository.campaign_assets.append(asset)
    service = make_service(repository)
    settings = Settings(campaign_asset_public_path="/api/campaign-assets")

    campaign = await service.create_campaign(
        CampaignCreateRequest(
            name="Campanie cu imagine",
            subject="Salut ${first_name}",
            html_body="<p>Bună.</p>",
            text_body="Bună.",
            thumbnail_url=asset.public_url,
        ),
        owner_id=TEST_OWNER_ID,
        settings=settings,
    )

    assert asset.status == "attached"
    assert asset.campaign_id == campaign.id

    await service.update_campaign(
        campaign.id,
        CampaignUpdateRequest(thumbnail_url=None),
        owner_id=TEST_OWNER_ID,
        settings=settings,
    )

    assert asset.status == "staged"
    assert asset.campaign_id is None


@pytest.mark.asyncio
async def test_campaign_rejects_managed_asset_owned_by_another_trainer() -> None:
    repository = FakeCommunicationsRepository()
    other_asset = CampaignAsset(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        file_name="other-thumbnail.png",
        public_url="https://codrut.local/api/campaign-assets/other-thumbnail.png",
        content_type="image/png",
        size_bytes=128,
        status="staged",
    )
    repository.campaign_assets.append(other_asset)
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.create_campaign(
            CampaignCreateRequest(
                name="Campanie invalidă",
                subject="Salut ${first_name}",
                html_body="<p>Bună.</p>",
                text_body="Bună.",
                thumbnail_url=other_asset.public_url,
            ),
            owner_id=TEST_OWNER_ID,
            settings=Settings(campaign_asset_public_path="/api/campaign-assets"),
        )

    assert exc_info.value.code == "campaign_asset_not_owned"


@pytest.mark.asyncio
async def test_delete_campaign_removes_saved_campaign() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    repository.campaigns.append(campaign)
    service = make_service(repository)

    await service.delete_campaign(campaign.id)

    assert repository.campaigns == []


@pytest.mark.asyncio
async def test_delete_campaign_rejects_unknown_campaign() -> None:
    service = make_service(FakeCommunicationsRepository())

    with pytest.raises(DomainError) as exc_info:
        await service.delete_campaign(uuid.uuid4())

    assert exc_info.value.code == "campaign_not_found"


@pytest.mark.asyncio
async def test_delete_campaign_rejects_other_owner_campaign() -> None:
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.owner_id = other_owner_id
    repository.campaigns.append(campaign)
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.delete_campaign(campaign.id, owner_id=owner_id)

    assert exc_info.value.code == "campaign_not_found"
    assert repository.campaigns == [campaign]


@pytest.mark.asyncio
async def test_update_campaign_recipient_persists_operational_fields() -> None:
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient()
    repository.campaign_recipients.append(recipient)
    service = make_service(repository)

    result = await service.update_campaign_recipient(
        recipient.id,
        CampaignRecipientUpdateRequest(
            email="NEW@example.com",
            contact_name="  Ioana Popescu  ",
            organization_name="  Compania B  ",
            segment="past_customer",
        ),
    )

    assert result.id == recipient.id
    assert recipient.email == "new@example.com"
    assert recipient.contact_name == "Ioana Popescu"
    assert recipient.organization_name == "Compania B"
    assert recipient.segment == CampaignRecipientSegment.past_customer


@pytest.mark.asyncio
async def test_update_campaign_recipient_rejects_duplicate_email() -> None:
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient(email="first@example.com")
    existing = persisted_campaign_recipient(email="existing@example.com")
    repository.campaign_recipients.extend([recipient, existing])
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.update_campaign_recipient(
            recipient.id,
            CampaignRecipientUpdateRequest(email="Existing@example.com"),
        )

    assert exc_info.value.code == "campaign_recipient_email_exists"
    assert recipient.email == "first@example.com"


@pytest.mark.asyncio
async def test_update_campaign_recipient_rejects_other_owner_contact() -> None:
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient(email="private@example.com")
    recipient.owner_id = other_owner_id
    repository.campaign_recipients.append(recipient)
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.update_campaign_recipient(
            recipient.id,
            CampaignRecipientUpdateRequest(contact_name="Leaked update"),
            owner_id=owner_id,
        )

    assert exc_info.value.code == "campaign_recipient_not_found"
    assert recipient.contact_name == "Ana Director"


@pytest.mark.asyncio
async def test_update_campaign_recipient_preserves_unsubscribe_status() -> None:
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient(status=CampaignRecipientStatus.unsubscribed)
    repository.campaign_recipients.append(recipient)
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.update_campaign_recipient(
            recipient.id,
            CampaignRecipientUpdateRequest(status="active"),
        )

    assert exc_info.value.code == "campaign_recipient_unsubscribe_preserved"
    assert recipient.status == CampaignRecipientStatus.unsubscribed


@pytest.mark.asyncio
async def test_delete_campaign_recipient_archives_contact_without_erasing_history() -> None:
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient()
    repository.campaign_recipients.append(recipient)
    service = make_service(repository)

    await service.delete_campaign_recipient(
        recipient.id,
        owner_id=TEST_OWNER_ID,
        settings=Settings(campaign_recipient_archive_retention_days=30),
    )

    assert repository.campaign_recipients == [recipient]
    assert recipient.status == CampaignRecipientStatus.suppressed
    assert recipient.status_before_archive == CampaignRecipientStatus.active
    assert recipient.archived_at is not None
    assert recipient.purge_after == recipient.archived_at + timedelta(days=30)

    with pytest.raises(DomainError) as reimport_error:
        await service.bulk_create_campaign_recipients(
            CampaignRecipientBulkCreateRequest(
                recipients=[
                    CampaignRecipientCreateRequest(
                        email=recipient.email,
                        contact_name="Reimportat",
                        organization_name="Compania nouă",
                        segment="potential_customer",
                    )
                ]
            ),
            owner_id=TEST_OWNER_ID,
        )

    assert reimport_error.value.code == "campaign_recipient_archived"
    assert repository.campaign_recipients == [recipient]
    assert recipient.status == CampaignRecipientStatus.suppressed
    assert recipient.status_before_archive == CampaignRecipientStatus.active


@pytest.mark.asyncio
async def test_delete_campaign_recipient_preserves_unsubscribe_state() -> None:
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient(status=CampaignRecipientStatus.unsubscribed)
    repository.campaign_recipients.append(recipient)
    service = make_service(repository)

    await service.delete_campaign_recipient(
        recipient.id,
        owner_id=TEST_OWNER_ID,
        settings=Settings(campaign_recipient_archive_retention_days=30),
    )

    assert repository.campaign_recipients == [recipient]
    assert recipient.status == CampaignRecipientStatus.unsubscribed
    assert recipient.archived_at is not None


@pytest.mark.asyncio
async def test_delete_campaign_recipient_rejects_other_owner_contact() -> None:
    owner_id = uuid.uuid4()
    other_owner_id = uuid.uuid4()
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient()
    recipient.owner_id = other_owner_id
    repository.campaign_recipients.append(recipient)
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.delete_campaign_recipient(recipient.id, owner_id=owner_id)

    assert exc_info.value.code == "campaign_recipient_not_found"
    assert recipient.status == CampaignRecipientStatus.active
    assert recipient.archived_at is None


@pytest.mark.asyncio
async def test_send_campaign_rejects_campaigns_that_are_not_ready() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    campaign.status = CampaignStatus.paused
    repository.campaigns.append(campaign)
    repository.campaign_recipients.append(persisted_campaign_recipient())
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.send_campaign(
            campaign.id,
            CampaignSendRequest(),
            provider=FakeEmailProvider(),
            settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
        )

    assert exc_info.value.code == "campaign_not_ready"


@pytest.mark.asyncio
async def test_unsubscribe_campaign_recipient_marks_recipient_unsubscribed() -> None:
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient()
    repository.campaign_recipients.append(recipient)
    settings = Settings(public_app_url="https://codrut.andreivacaru.ro")
    token = create_campaign_recipient_action_token(
        CampaignRecipientActionClaims(
            recipient_id=recipient.id,
            owner_id=recipient.owner_id,
            action="unsubscribe",
        ),
        settings,
    )
    service = make_service(repository)

    result = await service.unsubscribe_campaign_recipient(token, settings)

    assert result.id == recipient.id
    assert recipient.status == CampaignRecipientStatus.unsubscribed


@pytest.mark.asyncio
async def test_unsubscribe_campaign_recipient_rejects_other_owner_token() -> None:
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient()
    repository.campaign_recipients.append(recipient)
    settings = Settings(public_app_url="https://codrut.andreivacaru.ro")
    token = create_campaign_recipient_action_token(
        CampaignRecipientActionClaims(
            recipient_id=recipient.id,
            owner_id=uuid.uuid4(),
            action="unsubscribe",
        ),
        settings,
    )
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.unsubscribe_campaign_recipient(token, settings)

    assert exc_info.value.code == "campaign_recipient_not_found"
    assert recipient.status == CampaignRecipientStatus.active


@pytest.mark.asyncio
async def test_create_template_persists_versioned_structure() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    result = await service.create_template(
        EmailTemplateCreateRequest(
            key="account_setup",
            subject="Welcome, ${participant_name}",
            html_body=(
                "<p>Buna, ${participant_name}. ${trainer_name} ${company_name} ${action_url}</p>"
            ),
            text_body="Buna, ${participant_name}. ${trainer_name} ${company_name} ${action_url}",
            variables=["participant_name", "trainer_name", "company_name", "action_url"],
        )
    )

    assert result.key == "account_setup"
    assert result.version == 1
    assert result.active is True
    assert "Welcome" in result.subject


@pytest.mark.asyncio
async def test_update_template_mutates_unused_version() -> None:
    template = persisted_template()
    repository = FakeCommunicationsRepository([template])
    service = make_service(repository)

    result = await service.update_template(
        "account_setup",
        EmailTemplateUpdateRequest(
            subject="New Setup for ${company_name}",
        ),
    )

    assert result.version == 1
    assert result.subject == "New Setup for ${company_name}"
    assert repository.templates[0].subject == "New Setup for ${company_name}"


@pytest.mark.asyncio
async def test_update_template_keeps_used_trainer_version_stable() -> None:
    template = persisted_template()
    repository = FakeCommunicationsRepository([template])
    repository.sent_versions.add(("account_setup", 1))

    service = make_service(repository)

    result = await service.update_template(
        "account_setup",
        EmailTemplateUpdateRequest(
            subject="New Setup for ${company_name}",
        ),
    )

    assert result.version == 1
    assert result.active is True
    assert template.active is True
    assert template.subject == "New Setup for ${company_name}"
    assert len(repository.templates) == 1


@pytest.mark.asyncio
async def test_activate_template_deactivates_sibling_versions() -> None:
    t1 = persisted_template(version=1, active=False)
    t2 = persisted_template(version=2, active=True)
    repository = FakeCommunicationsRepository([t1, t2])
    service = make_service(repository)

    result = await service.activate_template("account_setup", 1)

    assert result.version == 1
    assert t1.active is True
    assert t2.active is False


@pytest.mark.asyncio
async def test_retire_template_marks_active_false() -> None:
    template = persisted_template()
    repository = FakeCommunicationsRepository([template])
    service = make_service(repository)

    result = await service.retire_template("account_setup")

    assert result.active is False
    assert repository.templates == [template]


@pytest.mark.asyncio
async def test_retire_template_without_version_marks_all_versions_inactive() -> None:
    v1 = persisted_template(key="custom_template", version=1, active=False)
    v2 = persisted_template(key="custom_template", version=2, active=True)
    repository = FakeCommunicationsRepository([v1, v2])
    service = make_service(repository)

    result = await service.retire_template("custom_template")

    assert result.version == 2
    assert v1.active is False
    assert v2.active is False


@pytest.mark.asyncio
async def test_list_templates_does_not_reactivate_retired_transactional_template() -> None:
    catalog = get_transactional_template(TransactionalTemplateKey.account_setup)
    template = persisted_template(
        key=TransactionalTemplateKey.account_setup.value,
        version=catalog.version,
        active=False,
    )
    repository = FakeCommunicationsRepository([template])
    service = make_service(repository)

    result = await service.list_templates(active_only=True)

    assert all(item.key != TransactionalTemplateKey.account_setup.value for item in result)
    assert template.active is False


@pytest.mark.asyncio
async def test_list_templates_does_not_seed_transactional_templates() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    result = await service.list_templates(active_only=True)

    transactional_keys = {
        TransactionalTemplateKey.account_setup.value,
        TransactionalTemplateKey.assignment_bundle.value,
    }
    assert transactional_keys.isdisjoint({item.key for item in result})
    assert transactional_keys.isdisjoint({template.key for template in repository.templates})


@pytest.mark.asyncio
async def test_get_template_does_not_seed_when_template_exists() -> None:
    repository = FakeCommunicationsRepository(
        [
            persisted_template(
                key=TransactionalTemplateKey.account_setup.value,
                version=1,
                active=True,
            )
        ]
    )
    service = make_service(repository)

    first = await service.get_template(TransactionalTemplateKey.account_setup.value)
    second = await service.get_template(TransactionalTemplateKey.account_setup.value)

    assert first.key == TransactionalTemplateKey.account_setup.value
    assert second.key == TransactionalTemplateKey.account_setup.value
    assert repository.list_template_calls == 0


@pytest.mark.asyncio
async def test_template_validation_missing_required() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    # Missing participant_name which is required for account_setup
    with pytest.raises(DomainError) as exc_info:
        await service.create_template(
            EmailTemplateCreateRequest(
                key="account_setup",
                subject="Test",
                html_body="No vars",
                text_body="No vars",
                variables=[],
            )
        )
    assert exc_info.value.code == "email_template_missing_required_variables"


@pytest.mark.asyncio
async def test_template_validation_undeclared_variables() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    with pytest.raises(DomainError) as exc_info:
        await service.create_template(
            EmailTemplateCreateRequest(
                key="custom_template",
                subject="Welcome ${missing_var}",
                html_body="Hello",
                text_body="Hello",
                variables=[],
            )
        )
    assert exc_info.value.code == "email_template_undeclared_variables"


@pytest.mark.asyncio
async def test_transactional_email_service_uses_db_template() -> None:
    # Set up provider and transactional service
    provider = FakeEmailProvider()
    trans_service = TransactionalEmailService(provider, owner_id=TEST_OWNER_ID)

    # Inject fake session/service
    class FakeSession:
        def add(self, obj: Any) -> None:
            pass

        async def flush(self) -> None:
            pass

    session = cast(Any, FakeSession())
    trans_service.session = session

    async def fake_get_template(
        key: str,
        *,
        version: int | None = None,
        owner_id: uuid.UUID | None = None,
    ):
        # Return modified subject to verify it was read from database!
        t = persisted_template()
        t.subject = "Custom DB Subject for ${company_name}"
        return t

    queued_sends: list[EmailSend] = []

    class MockCommunicationsRepository:
        def __init__(self, s: Any) -> None:
            pass

        async def get_template(
            self,
            key: str,
            *,
            version: int | None = None,
            owner_id: uuid.UUID | None = None,
        ):
            return await fake_get_template(key, version=version, owner_id=owner_id)

        async def get_email_send_by_idempotency_key(self, key: str):
            return next(
                (send for send in queued_sends if send.idempotency_key == key),
                None,
            )

        async def add_email_send(self, send: EmailSend):
            queued_sends.append(send)
            return send

    import codrut.modules.communications.service as comm_svc_mod

    original_repository = comm_svc_mod.CommunicationsRepository
    comm_svc_mod.CommunicationsRepository = MockCommunicationsRepository

    try:
        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            respondent_profile_id=uuid.uuid4(),
            questionnaire_key="icare",
            target_type="self",
            status=AssignmentStatus.assigned,
        )
        respondent = ParticipantProfile(
            id=uuid.uuid4(),
            full_name="Ana",
            email="ana@example.com",
            user_id=None,  # triggers account_setup
        )
        context = AssignmentInvitationContext(
            company_name="Demo Corp",
            trainer_name="Andrei",
            action_url="http://action",
            task_count=1,
        )

        result = await trans_service.send_assignment_invitation(
            assignment,
            respondent,
            context,
        )

        assert result.status == EmailDeliveryStatus.queued
        assert provider.sent == []
        assert len(queued_sends) == 1
        message = _email_message_from_outbox_payload(queued_sends[0].message_payload)
        assert message.subject == "Custom DB Subject for Demo Corp"
    finally:
        comm_svc_mod.CommunicationsRepository = original_repository
