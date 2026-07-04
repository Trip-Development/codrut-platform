import uuid
from typing import Any, cast

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
    CampaignRecipient,
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
    CampaignRecipientUpdateRequest,
    CampaignSendRequest,
    EmailTemplateCreateRequest,
    EmailTemplateUpdateRequest,
)
from codrut.modules.communications.service import (
    AssignmentInvitationContext,
    CommunicationsService,
    TransactionalEmailService,
)
from codrut.modules.communications.templates import (
    TransactionalTemplateKey,
    get_transactional_template,
)
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.identity import models as _identity_models  # noqa: F401


class FakeCommunicationsRepository:
    def __init__(self, templates: list[EmailTemplate] | None = None) -> None:
        self.templates = templates or []
        self.sends: list[EmailSend] = []
        self.sent_versions: set[tuple[str, int]] = set()
        self.campaign_recipients: list[CampaignRecipient] = []
        self.campaigns: list[Campaign] = []
        self.list_template_calls = 0

    async def has_sent_emails(self, key: str, version: int) -> bool:
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

    async def get_latest_version(self, key: str) -> int:
        versions = [t.version for t in self.templates if t.key == key]
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
    ) -> list[CampaignRecipient]:
        return [
            recipient
            for recipient in self.campaign_recipients
            if recipient.email is not None and recipient.email.lower() in emails
            and (owner_id is None or recipient.owner_id == owner_id)
        ]

    async def add_campaign_recipients(
        self,
        recipients: list[CampaignRecipient],
    ) -> None:
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
        self.campaigns.append(campaign)
        return campaign

    async def delete_campaign(self, campaign: Campaign) -> None:
        self.campaigns = [
            saved_campaign
            for saved_campaign in self.campaigns
            if saved_campaign.id != campaign.id
        ]

    async def list_campaign_recipients(
        self,
        *,
        owner_id: uuid.UUID | None = None,
    ) -> list[CampaignRecipient]:
        return [
            recipient
            for recipient in self.campaign_recipients
            if owner_id is None or recipient.owner_id == owner_id
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
        ]

    async def get_campaign_recipient(
        self,
        recipient_id: uuid.UUID,
        *,
        owner_id: uuid.UUID | None = None,
    ) -> CampaignRecipient | None:
        return next(
            (
                recipient
                for recipient in self.campaign_recipients
                if recipient.id == recipient_id
                and (owner_id is None or recipient.owner_id == owner_id)
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
                if recipient.email is not None and recipient.email.lower() == email.lower()
                and (owner_id is None or recipient.owner_id == owner_id)
            ),
            None,
        )

    async def add_email_send(self, send: EmailSend) -> EmailSend:
        self.sends.append(send)
        return send

    async def list_accepted_campaign_recipient_ids(self, campaign_id: uuid.UUID) -> set[uuid.UUID]:
        return {
            send.campaign_recipient_id
            for send in self.sends
            if send.campaign_id == campaign_id
            and send.campaign_recipient_id is not None
            and send.status == EmailSendStatus.accepted
        }

    async def count_accepted_sends_since(self, _since: object) -> int:
        return sum(1 for send in self.sends if send.status == EmailSendStatus.accepted)

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
            "<p><a href=\"${action_url}\">link</a></p>"
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
        )
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
        )
    )

    assert result.created == 1
    assert result.updated == 1
    assert len(result.recipients) == 2
    assert existing.contact_name == "Existing Again"
    assert existing.organization_name == "Existing Org Updated"
    assert existing.segment == "past_customer"


@pytest.mark.asyncio
async def test_bulk_create_campaign_recipients_dedupes_within_owner_scope() -> None:
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
    assert {recipient.owner_id for recipient in repository.campaign_recipients} == {
        first_owner_id,
        second_owner_id,
    }


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
        )
    )

    assert len(recipients) == 1
    assert recipients[0].email is None
    assert recipients[0].status == CampaignRecipientStatus.suppressed


def persisted_campaign() -> Campaign:
    return Campaign(
        id=uuid.uuid4(),
        name="Leadership video",
        segment=CampaignRecipientSegment.potential_customer,
        status=CampaignStatus.ready,
        subject="Salut ${first_name}",
        html_body="<p>Bună, {first_name}.</p>",
        text_body="Bună, {first_name}.",
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
        email=email,
        contact_name=contact_name,
        organization_name="Compania A",
        segment=segment,
        status=status,
    )


@pytest.mark.asyncio
async def test_send_campaign_sends_only_active_matching_recipients_with_unsubscribe_link() -> None:
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

    response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(recipient_ids=[active.id, suppressed.id, other_segment.id]),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    assert response.sent == 1
    assert response.skipped == 2
    assert campaign.status == CampaignStatus.completed
    assert len(provider.sent) == 1
    assert provider.sent[0].to.value == active.email
    assert provider.sent[0].subject == "Salut Ana"
    assert (
        "https://codrut.andreivacaru.ro/api/communications/campaigns/unsubscribe/"
        in provider.sent[0].html_body
    )
    assert (
        "https://codrut.andreivacaru.ro/api/communications/campaigns/track/calendly/"
        in provider.sent[0].html_body
    )
    assert (
        "https://codrut.andreivacaru.ro/api/communications/campaigns/track/calendly/"
        in provider.sent[0].text_body
    )
    assert "Ai primit acest email deoarece" in provider.sent[0].html_body
    assert "Str. Exemplu Nr. 10" in provider.sent[0].html_body
    assert len(repository.sends) == 1
    assert repository.sends[0].assignment_id is None
    assert repository.sends[0].template_key == "campaign"


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

    assert response.sent == 1
    assert 'href="https://vimeo.com/123456789"' in provider.sent[0].html_body
    assert "Vezi video: https://vimeo.com/123456789" in provider.sent[0].text_body


@pytest.mark.asyncio
async def test_send_campaign_default_mode_skips_already_accepted_recipients() -> None:
    repository = FakeCommunicationsRepository()
    campaign = persisted_campaign()
    first = persisted_campaign_recipient(email="first@example.com", contact_name="First")
    second = persisted_campaign_recipient(email="second@example.com", contact_name="Second")
    repository.campaigns.append(campaign)
    repository.campaign_recipients.extend([first, second])
    provider = FakeEmailProvider()
    service = make_service(repository)

    first_response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(recipient_ids=[first.id]),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )
    second_response = await service.send_campaign(
        campaign.id,
        CampaignSendRequest(),
        provider=provider,
        settings=Settings(public_app_url="https://codrut.andreivacaru.ro"),
    )

    assert first_response.sent == 1
    assert second_response.sent == 1
    assert provider.sent[0].to.value == first.email
    assert provider.sent[1].to.value == second.email
    assert len(provider.sent) == 2


@pytest.mark.asyncio
async def test_send_campaign_does_not_use_other_owner_recipients() -> None:
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

    assert response.sent == 1
    assert provider.sent[0].to.value == "owner@example.com"


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

    assert response.sent == 1
    assert response.skipped == 1
    assert response.results[1].error == "Daily email send cap reached."
    assert len(provider.sent) == 1


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
async def test_delete_campaign_recipient_suppresses_contact_without_erasing_history() -> None:
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient()
    repository.campaign_recipients.append(recipient)
    service = make_service(repository)

    await service.delete_campaign_recipient(recipient.id)

    assert repository.campaign_recipients == [recipient]
    assert recipient.status == CampaignRecipientStatus.suppressed

    imported = await service.bulk_create_campaign_recipients(
        CampaignRecipientBulkCreateRequest(
            recipients=[
                CampaignRecipientCreateRequest(
                    email=recipient.email,
                    contact_name="Reimportat",
                    organization_name="Compania nouă",
                    segment="potential_customer",
                )
            ]
        )
    )

    assert imported == [recipient]
    assert repository.campaign_recipients == [recipient]
    assert recipient.status == CampaignRecipientStatus.suppressed


@pytest.mark.asyncio
async def test_delete_campaign_recipient_preserves_unsubscribe_state() -> None:
    repository = FakeCommunicationsRepository()
    recipient = persisted_campaign_recipient(status=CampaignRecipientStatus.unsubscribed)
    repository.campaign_recipients.append(recipient)
    service = make_service(repository)

    await service.delete_campaign_recipient(recipient.id)

    assert repository.campaign_recipients == [recipient]
    assert recipient.status == CampaignRecipientStatus.unsubscribed


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
        CampaignRecipientActionClaims(recipient_id=recipient.id, action="unsubscribe"),
        settings,
    )
    service = make_service(repository)

    result = await service.unsubscribe_campaign_recipient(token, settings)

    assert result.id == recipient.id
    assert recipient.status == CampaignRecipientStatus.unsubscribed


@pytest.mark.asyncio
async def test_create_template_persists_versioned_structure() -> None:
    repository = FakeCommunicationsRepository()
    service = make_service(repository)

    result = await service.create_template(
        EmailTemplateCreateRequest(
            key="account_setup",
            subject="Welcome, ${participant_name}",
            html_body=(
                "<p>Buna, ${participant_name}. "
                "${trainer_name} ${company_name} ${action_url}</p>"
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
async def test_update_template_versions_used_template() -> None:
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

    assert result.version == 2
    assert result.active is True
    assert template.active is False
    assert template.subject == "Setup account for ${company_name}"
    assert repository.templates[1].subject == "New Setup for ${company_name}"


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
async def test_list_templates_does_not_reactivate_retired_catalog_template() -> None:
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
    trans_service = TransactionalEmailService(provider)

    # Inject fake session/service
    class FakeSession:
        def add(self, obj: Any) -> None:
            pass
        async def flush(self) -> None:
            pass
    session = cast(Any, FakeSession())
    trans_service.session = session
    
    async def fake_get_template(key: str, *, version: int | None = None):
        # Return modified subject to verify it was read from database!
        t = persisted_template()
        t.subject = "Custom DB Subject for ${company_name}"
        return t

    class MockCommunicationsRepository:
        def __init__(self, s: Any) -> None:
            pass

        async def get_template(self, key: str, *, version: int | None = None):
            return await fake_get_template(key, version=version)

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

        assert result.status == EmailDeliveryStatus.accepted
        assert len(provider.sent) == 1
        assert provider.sent[0].subject == "Custom DB Subject for Demo Corp"
    finally:
        comm_svc_mod.CommunicationsRepository = original_repository
