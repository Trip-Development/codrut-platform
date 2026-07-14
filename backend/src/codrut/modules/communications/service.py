import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape as html_escape
from html import unescape as html_unescape
from string import Template
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.contracts.emails import EmailAddress, EmailDeliveryStatus, EmailMessage, EmailSendResult
from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
from codrut.modules.communications.campaign_policy import require_campaign_send_allowed
from codrut.modules.communications.campaign_tracking import (
    CampaignRecipientActionClaims,
    CampaignTrackingClaims,
    build_campaign_tracking_url,
    build_campaign_unsubscribe_url,
    create_campaign_recipient_action_token,
    create_campaign_tracking_token,
    parse_campaign_recipient_action_token,
    parse_campaign_tracking_token,
)
from codrut.modules.communications.email_provider import EmailProvider
from codrut.modules.communications.models import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientEvent,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
    EmailSend,
    EmailSendStatus,
    EmailTemplate,
)
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.schemas import (
    CampaignCreateRequest,
    CampaignRecipientBulkCreateRequest,
    CampaignRecipientEventCreateRequest,
    CampaignRecipientEventResponse,
    CampaignRecipientMembershipRowResponse,
    CampaignRecipientMembershipUpdateRequest,
    CampaignRecipientUpdateRequest,
    CampaignSendRecipientResult,
    CampaignSendRequest,
    CampaignSendResponse,
    CampaignUpdateRequest,
    EmailTemplateCreateRequest,
    EmailTemplateResponse,
    EmailTemplateUpdateRequest,
)
from codrut.modules.communications.templates import (
    EMAIL_SHELL_OPEN,
    EVALUATION_TEMPLATES,
    PROMOTIONAL_SHELL_CLOSE,
    PROMOTIONAL_TEMPLATES,
    TransactionalTemplateKey,
    get_transactional_template,
)
from codrut.modules.companies.models import ParticipantProfile

# Regex to find placeholders in python string.Template format, e.g. ${variable}
PLACEHOLDER_PATTERN = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

SYSTEM_TEMPLATE_REQUIRED_VARS = {
    "account_setup": {"participant_name", "trainer_name", "company_name", "action_url"},
    "assignment_bundle": {"participant_name", "company_name", "task_count", "action_url"},
}
CAMPAIGN_CALENDLY_URL = "https://calendly.com/andreivacaru/intalnire-de-apropiere"


@dataclass(frozen=True)
class CampaignRecipientBulkCreateResult:
    recipients: list[CampaignRecipient]
    created: int
    updated: int


def extract_placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER_PATTERN.findall(text))


def validate_template_placeholders(
    subject: str,
    html_body: str,
    text_body: str,
    declared_variables: list[str],
    key: str,
) -> None:
    # 1. Check required variables for system templates
    required = SYSTEM_TEMPLATE_REQUIRED_VARS.get(key, set())
    declared_set = set(declared_variables)
    missing_declared = required - declared_set
    if missing_declared:
        msg = (
            "Missing required variables for system template: "
            f"{', '.join(sorted(missing_declared))}"
        )
        raise DomainError(
            msg,
            code="email_template_missing_required_variables",
        )

    # 2. Check that all declared variables are actually used in the templates
    all_placeholders = (
        extract_placeholders(subject)
        | extract_placeholders(html_body)
        | extract_placeholders(text_body)
    )

    undeclared = all_placeholders - declared_set
    if undeclared:
        raise DomainError(
            f"Template contains undeclared variables: {', '.join(sorted(undeclared))}",
            code="email_template_undeclared_variables",
        )


def render_template_content(
    subject: str,
    html_body: str,
    text_body: str,
    required_variables: list[str],
    to: EmailAddress,
    context: dict[str, str],
) -> EmailMessage:
    missing = sorted(set(required_variables) - context.keys())
    if missing:
        raise DomainError(
            "Email template context is missing required values.",
            code="email_template_context_incomplete",
        )
    from string import Template
    return EmailMessage(
        to=to,
        subject=Template(subject).substitute(context),
        html_body=Template(html_body).substitute(context),
        text_body=Template(text_body).substitute(context),
    )


class CommunicationsService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.repository = CommunicationsRepository(session) if session is not None else None

    async def list_templates(
        self,
        *,
        active_only: bool = True,
        owner_id: UUID | None = None,
    ) -> list[EmailTemplateResponse]:
        repository = self._require_repository()
        await self._seed_catalog_templates(repository)
        templates = await repository.list_templates(active_only=active_only, owner_id=owner_id)
        return [EmailTemplateResponse.model_validate(t) for t in templates]

    async def get_template(
        self,
        key: str,
        *,
        version: int | None = None,
        owner_id: UUID | None = None,
    ) -> EmailTemplateResponse:
        repository = self._require_repository()
        template = await repository.get_template(key, version=version, owner_id=owner_id)
        if template is None:
            await self._seed_catalog_templates(repository)
            template = await repository.get_template(key, version=version, owner_id=owner_id)
        if template is None:
            raise DomainError("Email template not found.", code="email_template_not_found")
        return EmailTemplateResponse.model_validate(template)

    async def create_template(
        self,
        payload: EmailTemplateCreateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> EmailTemplateResponse:
        repository = self._require_repository()
        validate_template_placeholders(
            payload.subject,
            payload.html_body,
            payload.text_body,
            payload.variables,
            payload.key,
        )
        version = await repository.get_latest_version(payload.key) + 1
        if payload.active:
            await repository.deactivate_templates_for_key(payload.key, owner_id=owner_id)
        template = await repository.add_template(
            EmailTemplate(
                key=payload.key,
                version=version,
                subject=payload.subject,
                html_body=payload.html_body,
                text_body=payload.text_body,
                variables=payload.variables,
                audience=payload.audience,
                active=payload.active,
                owner_id=owner_id,
            )
        )
        return EmailTemplateResponse.model_validate(template)

    async def update_template(
        self,
        key: str,
        payload: EmailTemplateUpdateRequest,
        *,
        version: int | None = None,
        owner_id: UUID | None = None,
    ) -> EmailTemplateResponse:
        repository = self._require_repository()
        template = await repository.get_template(key, version=version, owner_id=owner_id)
        if template is None:
            raise DomainError("Email template not found.", code="email_template_not_found")

        updated_subject = payload.subject if payload.subject is not None else template.subject
        updated_html = payload.html_body if payload.html_body is not None else template.html_body
        updated_text = payload.text_body if payload.text_body is not None else template.text_body
        updated_variables = (
            payload.variables if payload.variables is not None else template.variables
        )

        validate_template_placeholders(
            updated_subject,
            updated_html,
            updated_text,
            updated_variables,
            key,
        )

        has_sends = await repository.has_sent_emails(key, template.version)
        if has_sends or (owner_id is not None and template.owner_id is None):
            next_version = await repository.get_latest_version(key) + 1
            await repository.deactivate_templates_for_key(key, owner_id=owner_id)
            template = await repository.add_template(
                EmailTemplate(
                    key=key,
                    version=next_version,
                    subject=updated_subject,
                    html_body=updated_html,
                    text_body=updated_text,
                    variables=updated_variables,
                    audience=(
                        payload.audience
                        if payload.audience is not None
                        else template.audience
                    ),
                    active=payload.active if payload.active is not None else True,
                    owner_id=owner_id if owner_id is not None else template.owner_id,
                )
            )
        else:
            template.subject = updated_subject
            template.html_body = updated_html
            template.text_body = updated_text
            template.variables = updated_variables
            if payload.audience is not None:
                template.audience = payload.audience
            if payload.active is not None:
                template.active = payload.active

        if template.active:
            await repository.deactivate_templates_for_key(
                key,
                except_version=template.version,
                owner_id=owner_id,
            )

        return EmailTemplateResponse.model_validate(template)

    async def activate_template(
        self,
        key: str,
        version: int,
        *,
        owner_id: UUID | None = None,
    ) -> EmailTemplateResponse:
        repository = self._require_repository()
        template = await repository.get_template(key, version=version, owner_id=owner_id)
        if template is None:
            raise DomainError("Email template not found.", code="email_template_not_found")
        if owner_id is not None and template.owner_id is None:
            template = await repository.add_template(
                EmailTemplate(
                    key=key,
                    version=await repository.get_latest_version(key) + 1,
                    subject=template.subject,
                    html_body=template.html_body,
                    text_body=template.text_body,
                    variables=template.variables,
                    audience=template.audience,
                    active=True,
                    owner_id=owner_id,
                )
            )
        else:
            template.active = True
        await repository.deactivate_templates_for_key(
            key,
            except_version=template.version,
            owner_id=owner_id,
        )
        return EmailTemplateResponse.model_validate(template)

    async def retire_template(
        self,
        key: str,
        *,
        version: int | None = None,
        owner_id: UUID | None = None,
    ) -> EmailTemplateResponse:
        repository = self._require_repository()
        template = await repository.get_template(key, version=version, owner_id=owner_id)
        if template is None:
            raise DomainError("Email template not found.", code="email_template_not_found")
        if owner_id is not None and template.owner_id is None:
            raise DomainError(
                "System email templates cannot be retired from a trainer workspace.",
                code="email_template_system_retire_forbidden",
            )
        if version is None:
            await repository.deactivate_templates_for_key(key, owner_id=owner_id)
        else:
            template.active = False
        return EmailTemplateResponse.model_validate(template)

    def _require_repository(self) -> CommunicationsRepository:
        if self.repository is None:
            raise RuntimeError("CommunicationsService requires a database session")
        return self.repository

    async def _seed_catalog_templates(self, repository: CommunicationsRepository) -> None:
        existing_templates = {
            (template.key, template.version): template
            for template in await repository.list_templates(active_only=False)
        }
        for catalog_template in (*PROMOTIONAL_TEMPLATES, *EVALUATION_TEMPLATES):
            existing = existing_templates.get((catalog_template.key, catalog_template.version))
            if existing is None:
                existing = await repository.add_template(
                    EmailTemplate(
                        key=catalog_template.key,
                        version=catalog_template.version,
                        subject=catalog_template.subject,
                        html_body=catalog_template.html_body,
                        text_body=catalog_template.text_body,
                        variables=list(catalog_template.required_context),
                        audience=catalog_template.audience,
                        active=True,
                    )
                )
                existing_templates[(catalog_template.key, catalog_template.version)] = existing
                await repository.deactivate_templates_for_key(
                    catalog_template.key,
                    except_version=catalog_template.version,
                )

    async def bulk_create_campaign_recipients(
        self,
        payload: CampaignRecipientBulkCreateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> list[CampaignRecipient]:
        result = await self.bulk_create_campaign_recipients_with_result(
            payload,
            owner_id=owner_id,
        )
        return result.recipients

    async def bulk_create_campaign_recipients_with_result(
        self,
        payload: CampaignRecipientBulkCreateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> CampaignRecipientBulkCreateResult:
        repository = self._require_repository()

        recipients_by_email: dict[str, CampaignRecipient] = {}
        recipients_without_email: list[CampaignRecipient] = []
        status_provided_by_email: dict[str, bool] = {}
        for req in payload.recipients:
            normalized_email = str(req.email).lower() if req.email is not None else None
            try:
                recipient_status = (
                    CampaignRecipientStatus(req.status)
                    if req.status is not None
                    else CampaignRecipientStatus.active
                )
            except ValueError as exc:
                raise DomainError(
                    "Invalid campaign recipient status.",
                    code="campaign_recipient_status_invalid",
                ) from exc
            if normalized_email is None:
                if recipient_status == CampaignRecipientStatus.active:
                    raise DomainError(
                        "Active campaign recipients require an email.",
                        code="campaign_recipient_email_required",
                    )
                recipients_without_email.append(
                    CampaignRecipient(
                        owner_id=owner_id,
                        email=None,
                        contact_name=req.contact_name,
                        organization_name=req.organization_name,
                        segment=req.segment,
                        source=req.source,
                        status=recipient_status,
                    )
                )
                continue
            status_provided_by_email[normalized_email] = req.status is not None
            recipients_by_email[normalized_email] = CampaignRecipient(
                owner_id=owner_id,
                email=normalized_email,
                contact_name=req.contact_name,
                organization_name=req.organization_name,
                segment=req.segment,
                source=req.source,
                status=recipient_status,
            )

        existing = await repository.list_campaign_recipients_by_emails(
            set(recipients_by_email),
            owner_id=owner_id,
        )
        existing_by_email = {
            recipient.email.lower(): recipient
            for recipient in existing
            if recipient.email is not None
        }
        recipients_to_create = [
            recipient
            for email, recipient in recipients_by_email.items()
            if email not in existing_by_email
        ]
        for email, recipient in recipients_by_email.items():
            existing_recipient = existing_by_email.get(email)
            if existing_recipient is None:
                continue
            existing_recipient.contact_name = recipient.contact_name
            existing_recipient.organization_name = recipient.organization_name
            existing_recipient.segment = recipient.segment
            existing_recipient.source = recipient.source
            if (
                status_provided_by_email.get(email, False)
                and existing_recipient.status != CampaignRecipientStatus.unsubscribed
            ):
                existing_recipient.status = recipient.status
        recipients_to_create.extend(recipients_without_email)
        if recipients_to_create:
            await repository.add_campaign_recipients(recipients_to_create)
        return CampaignRecipientBulkCreateResult(
            recipients=[*existing, *recipients_to_create],
            created=len(recipients_to_create),
            updated=len(existing),
        )

    async def update_campaign_recipient(
        self,
        recipient_id: UUID,
        payload: CampaignRecipientUpdateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> CampaignRecipient:
        repository = self._require_repository()
        recipient = await repository.get_campaign_recipient(recipient_id, owner_id=owner_id)
        if recipient is None:
            raise DomainError("Campaign recipient not found.", code="campaign_recipient_not_found")

        if payload.email is not None:
            normalized_email = str(payload.email).lower()
            existing_email_recipient = await repository.get_campaign_recipient_by_email(
                normalized_email,
                owner_id=owner_id,
            )
            if (
                existing_email_recipient is not None
                and existing_email_recipient.id != recipient.id
            ):
                raise DomainError(
                    "Campaign recipient email already exists.",
                    code="campaign_recipient_email_exists",
                )
            recipient.email = normalized_email
        if payload.contact_name is not None:
            recipient.contact_name = payload.contact_name.strip() or None
        if payload.organization_name is not None:
            recipient.organization_name = payload.organization_name.strip() or None
        if payload.segment is not None:
            try:
                recipient.segment = CampaignRecipientSegment(payload.segment)
            except ValueError as exc:
                raise DomainError(
                    "Invalid campaign recipient segment.",
                    code="campaign_recipient_segment_invalid",
                ) from exc
        if payload.status is not None:
            try:
                next_status = CampaignRecipientStatus(payload.status)
            except ValueError as exc:
                raise DomainError(
                    "Invalid campaign recipient status.",
                    code="campaign_recipient_status_invalid",
                ) from exc
            if (
                recipient.status == CampaignRecipientStatus.unsubscribed
                and next_status != CampaignRecipientStatus.unsubscribed
            ):
                raise DomainError(
                    "Unsubscribed campaign recipients cannot be reactivated from contact editing.",
                    code="campaign_recipient_unsubscribe_preserved",
                )
            recipient.status = next_status
        if recipient.status == CampaignRecipientStatus.active and not recipient.email:
            raise DomainError(
                "Active campaign recipients require an email.",
                code="campaign_recipient_email_required",
            )
        if payload.source is not None:
            recipient.source = payload.source.strip() or None

        await repository.flush()
        return recipient

    async def delete_campaign_recipient(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> None:
        repository = self._require_repository()
        recipient = await repository.get_campaign_recipient(recipient_id, owner_id=owner_id)
        if recipient is None:
            raise DomainError("Campaign recipient not found.", code="campaign_recipient_not_found")
        if recipient.status == CampaignRecipientStatus.active:
            recipient.status = CampaignRecipientStatus.suppressed
        await repository.flush()

    async def create_campaign(
        self,
        payload: CampaignCreateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> Campaign:
        repository = self._require_repository()

        campaign = Campaign(
            owner_id=owner_id,
            name=payload.name,
            segment=(
                CampaignRecipientSegment(payload.segment)
                if payload.segment is not None
                else None
            ),
            status=CampaignStatus.ready,
            subject=payload.subject,
            html_body=payload.html_body,
            text_body=payload.text_body,
            video_url=payload.video_url,
            thumbnail_url=payload.thumbnail_url,
            landing_page_url=payload.landing_page_url,
        )
        return await repository.add_campaign(campaign)

    async def update_campaign(
        self,
        campaign_id: UUID,
        payload: CampaignUpdateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> Campaign:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")

        provided_fields = payload.model_fields_set
        if "name" in provided_fields and payload.name is not None:
            campaign.name = payload.name.strip()
        if "segment" in provided_fields:
            campaign.segment = (
                CampaignRecipientSegment(payload.segment)
                if payload.segment is not None
                else None
            )
        if "status" in provided_fields and payload.status is not None:
            try:
                campaign.status = CampaignStatus(payload.status)
            except ValueError as exc:
                raise DomainError(
                    "Invalid campaign status.",
                    code="campaign_status_invalid",
                ) from exc
        if "subject" in provided_fields and payload.subject is not None:
            campaign.subject = payload.subject
        if "html_body" in provided_fields and payload.html_body is not None:
            campaign.html_body = payload.html_body
        if "text_body" in provided_fields and payload.text_body is not None:
            campaign.text_body = payload.text_body
        if "video_url" in provided_fields:
            campaign.video_url = payload.video_url
        if "thumbnail_url" in provided_fields:
            campaign.thumbnail_url = payload.thumbnail_url
        if "landing_page_url" in provided_fields:
            campaign.landing_page_url = payload.landing_page_url

        if bool(campaign.video_url) != bool(campaign.thumbnail_url):
            raise DomainError(
                "Video campaigns require video_url and thumbnail_url.",
                code="campaign_video_assets_incomplete",
            )

        await repository.flush()
        return campaign

    async def list_campaigns(self, *, owner_id: UUID | None = None) -> list[Campaign]:
        repository = self._require_repository()
        return await repository.list_campaigns(owner_id=owner_id)

    async def delete_campaign(
        self,
        campaign_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> None:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")
        await repository.delete_campaign(campaign)

    async def list_campaign_recipient_memberships(
        self,
        campaign_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> list[CampaignRecipientMembershipRowResponse]:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")

        await self._ensure_default_campaign_memberships(campaign, owner_id=owner_id)
        recipients = await repository.list_campaign_member_recipients(
            campaign.id,
            owner_id=owner_id,
        )
        return [_campaign_recipient_membership_row(recipient) for recipient in recipients]

    async def replace_campaign_recipient_memberships(
        self,
        campaign_id: UUID,
        payload: CampaignRecipientMembershipUpdateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> list[CampaignRecipientMembershipRowResponse]:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")

        recipient_ids = list(dict.fromkeys(payload.recipient_ids))
        recipients = await repository.list_campaign_recipients_by_ids(
            recipient_ids,
            owner_id=owner_id,
        )
        recipients_by_id = {recipient.id: recipient for recipient in recipients}
        missing_ids = [
            recipient_id
            for recipient_id in recipient_ids
            if recipient_id not in recipients_by_id
        ]
        if missing_ids:
            raise DomainError(
                "Campaign recipient membership includes unknown contacts.",
                code="campaign_membership_recipient_not_found",
            )
        wrong_segment = []
        if campaign.segment is not None:
            wrong_segment = [
                recipient.email or str(recipient.id)
                for recipient in recipients
                if recipient.segment != campaign.segment
            ]
        if wrong_segment:
            raise DomainError(
                "Campaign recipient membership must match the campaign segment.",
                code="campaign_membership_segment_mismatch",
            )

        await repository.replace_campaign_memberships(
            campaign.id,
            recipient_ids,
            source="manual",
            owner_id=owner_id,
        )
        campaign.recipient_memberships_initialized = True
        ordered_recipients = [recipients_by_id[recipient_id] for recipient_id in recipient_ids]
        return [_campaign_recipient_membership_row(recipient) for recipient in ordered_recipients]

    async def send_campaign(
        self,
        campaign_id: UUID,
        payload: CampaignSendRequest,
        *,
        provider: EmailProvider,
        settings: Settings,
        owner_id: UUID | None = None,
    ) -> CampaignSendResponse:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")
        if campaign.status not in {CampaignStatus.ready, CampaignStatus.completed}:
            raise DomainError(
                "Campaign must be ready before sending.",
                code="campaign_not_ready",
            )

        recipients = await self._campaign_send_recipients(campaign, payload, owner_id=owner_id)
        if not recipients:
            raise DomainError("Campaign has no matching recipients.", code="campaign_no_recipients")

        results: list[CampaignSendRecipientResult] = []
        remaining_sends = await _remaining_email_sends_today(repository, settings)
        for recipient in recipients:
            if campaign.segment is not None and recipient.segment != campaign.segment:
                results.append(
                    CampaignSendRecipientResult(
                        recipient_id=recipient.id,
                        email=recipient.email or "",
                        status="skipped",
                        error="Recipient segment does not match campaign segment.",
                    )
                )
                continue
            if recipient.status != CampaignRecipientStatus.active or not recipient.email:
                results.append(
                    CampaignSendRecipientResult(
                        recipient_id=recipient.id,
                        email=recipient.email or "",
                        status="skipped",
                        error="Recipient is suppressed or unsubscribed.",
                    )
                )
                continue

            if not payload.dry_run and remaining_sends <= 0:
                results.append(
                    CampaignSendRecipientResult(
                        recipient_id=recipient.id,
                        email=recipient.email or "",
                        status="skipped",
                        error="Daily email send cap reached.",
                    )
                )
                continue

            unsubscribe_url = _campaign_unsubscribe_url(recipient, settings)
            require_campaign_send_allowed(
                recipient,
                unsubscribe_url=unsubscribe_url,
                allow_insecure_localhost=not settings.is_production,
            )
            message = _render_campaign_message(campaign, recipient, unsubscribe_url, settings)

            if payload.dry_run:
                results.append(
                    CampaignSendRecipientResult(
                        recipient_id=recipient.id,
                        email=recipient.email,
                        status="dry_run",
                    )
                )
                continue

            email_send = await repository.add_email_send(
                EmailSend(
                    assignment_id=None,
                    campaign_id=campaign.id,
                    campaign_recipient_id=recipient.id,
                    recipient_email=recipient.email,
                    template_key="campaign",
                    template_version=1,
                    provider=str(getattr(provider, "key", "unknown")),
                    provider_message_id=None,
                    status=EmailSendStatus.queued,
                    last_event_at=datetime.now(UTC),
                )
            )
            result = await provider.send(message)
            send_status = (
                EmailSendStatus.accepted
                if result.status == EmailDeliveryStatus.accepted
                else EmailSendStatus.failed
            )
            email_send.provider = result.provider.value
            email_send.provider_message_id = result.message_id
            email_send.status = send_status
            email_send.error_details = result.error_details
            email_send.last_event_at = datetime.now(UTC)
            results.append(
                CampaignSendRecipientResult(
                    recipient_id=recipient.id,
                    email=recipient.email,
                    status=result.status.value,
                    message_id=result.message_id,
                    error=result.error_details,
                )
            )
            if result.status == EmailDeliveryStatus.accepted:
                remaining_sends -= 1

        if not payload.dry_run and any(result.status == "accepted" for result in results):
            campaign.status = CampaignStatus.completed

        return CampaignSendResponse(
            campaign_id=campaign.id,
            total=len(results),
            sent=sum(1 for result in results if result.status == "accepted"),
            failed=sum(1 for result in results if result.status == "failed"),
            skipped=sum(1 for result in results if result.status in {"skipped", "dry_run"}),
            dry_run=payload.dry_run,
            results=results,
        )

    async def _ensure_default_campaign_memberships(
        self,
        campaign: Campaign,
        *,
        owner_id: UUID | None = None,
    ) -> list[UUID]:
        repository = self._require_repository()
        member_ids = await repository.list_campaign_member_recipient_ids(
            campaign.id,
            owner_id=owner_id,
        )
        if (
            member_ids
            or campaign.recipient_memberships_initialized
            or campaign.segment is None
            or campaign.status not in {CampaignStatus.draft, CampaignStatus.ready}
        ):
            return member_ids

        recipients = await repository.list_campaign_recipients(owner_id=owner_id)
        default_ids = [
            recipient.id
            for recipient in recipients
            if recipient.segment == campaign.segment
            and recipient.status == CampaignRecipientStatus.active
            and recipient.email
        ]
        if default_ids:
            await repository.replace_campaign_memberships(
                campaign.id,
                default_ids,
                source="segment_backfill",
                owner_id=owner_id,
            )
            campaign.recipient_memberships_initialized = True
        return default_ids

    async def unsubscribe_campaign_recipient(
        self,
        token: str,
        settings: Settings,
    ) -> CampaignRecipient:
        recipient = await self.get_campaign_unsubscribe_recipient(token, settings)
        recipient.status = CampaignRecipientStatus.unsubscribed
        await self._require_repository().flush()
        return recipient

    async def get_campaign_unsubscribe_recipient(
        self,
        token: str,
        settings: Settings,
    ) -> CampaignRecipient:
        repository = self._require_repository()
        claims = parse_campaign_recipient_action_token(token, settings)
        if claims.action != "unsubscribe":
            raise DomainError(
                "Invalid campaign recipient action link.",
                code="campaign_recipient_action_invalid",
            )
        recipient = await repository.get_campaign_recipient(claims.recipient_id)
        if recipient is None:
            raise DomainError("Campaign recipient not found.", code="campaign_recipient_not_found")
        return recipient

    async def _campaign_send_recipients(
        self,
        campaign: Campaign,
        payload: CampaignSendRequest,
        *,
        owner_id: UUID | None = None,
    ) -> list[CampaignRecipient]:
        repository = self._require_repository()
        if payload.recipient_ids and "mode" not in payload.model_fields_set:
            payload.mode = "selected"
        if payload.mode == "selected":
            if not payload.recipient_ids:
                raise DomainError(
                    "Selected campaign send requires recipient_ids.",
                    code="campaign_selected_recipients_required",
                )
            return await repository.list_campaign_recipients_by_ids(
                payload.recipient_ids,
                owner_id=owner_id,
            )
        await self._ensure_default_campaign_memberships(campaign, owner_id=owner_id)
        matching = await repository.list_campaign_member_recipients(
            campaign.id,
            owner_id=owner_id,
        )
        if payload.mode == "all":
            return matching
        if not hasattr(repository, "list_accepted_campaign_recipient_ids"):
            return matching
        sent_recipient_ids = await repository.list_accepted_campaign_recipient_ids(campaign.id)
        return [recipient for recipient in matching if recipient.id not in sent_recipient_ids]

    async def record_campaign_recipient_event(
        self,
        recipient_id: UUID,
        payload: CampaignRecipientEventCreateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> CampaignRecipientEventResponse:
        repository = self._require_repository()
        recipient = await repository.get_campaign_recipient(recipient_id, owner_id=owner_id)
        if recipient is None:
            raise DomainError("Campaign recipient not found.", code="campaign_recipient_not_found")

        event = await repository.add_campaign_recipient_event(
            CampaignRecipientEvent(
                id=uuid.uuid4(),
                recipient_id=recipient.id,
                event_type=payload.event_type,
                variant_key=payload.variant_key,
                occurred_at=payload.occurred_at or datetime.now(UTC),
            )
        )
        return CampaignRecipientEventResponse(
            id=event.id,
            recipient_id=event.recipient_id,
            event_type=event.event_type,
            variant_key=event.variant_key,
            occurred_at=event.occurred_at,
        )

    async def record_calendly_tracking_click(self, token: str, settings: Settings) -> str:
        target_url = await self.record_campaign_tracking_link(
            token,
            settings,
            expected_event_type="calendly_clicked",
        )
        _require_calendly_target(target_url)
        return target_url

    async def record_campaign_tracking_link(
        self,
        token: str,
        settings: Settings,
        *,
        expected_event_type: str,
    ) -> str:
        claims = parse_campaign_tracking_token(token, settings)
        if claims.event_type != expected_event_type:
            raise DomainError(
                "Campaign tracking link has the wrong event type.",
                code="campaign_tracking_invalid",
            )
        await self.record_campaign_recipient_event(
            claims.recipient_id,
            CampaignRecipientEventCreateRequest(
                event_type=claims.event_type,  # type: ignore[arg-type]
                variant_key=claims.variant_key,
            ),
        )
        return claims.target_url

    async def get_email_ops_summary(self, *, owner_id: UUID | None = None) -> dict:
        repository = self._require_repository()
        session = repository.session

        from collections import defaultdict

        from sqlalchemy import false, func, select

        from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
        from codrut.modules.communications.models import EmailSend, EmailSendStatus
        from codrut.modules.communications.reminders import (
            DEFAULT_REMINDER_POLICY,
            reminder_candidates,
        )
        from codrut.modules.companies.models import (
            Company,
            CompanyMembership,
            ParticipantProfile,
        )

        # 1. Fetch all participants and their company details
        profiles_stmt = (
            select(ParticipantProfile, Company.name)
            .join(Company, ParticipantProfile.company_id == Company.id)
        )
        if owner_id is not None:
            profiles_stmt = profiles_stmt.join(
                CompanyMembership,
                CompanyMembership.company_id == Company.id,
            ).where(CompanyMembership.user_id == owner_id)
        profiles_result = await session.execute(profiles_stmt)
        profiles = []
        company_names = {}
        for profile, comp_name in profiles_result.all():
            profiles.append(profile)
            company_names[profile.id] = comp_name

        # 2. Fetch all assignments
        profile_ids = {profile.id for profile in profiles}
        assignments_stmt = select(QuestionnaireAssignment)
        if owner_id is not None:
            if profile_ids:
                assignments_stmt = assignments_stmt.where(
                    QuestionnaireAssignment.respondent_profile_id.in_(profile_ids)
                )
            else:
                assignments_stmt = assignments_stmt.where(false())
        assignments_result = await session.execute(assignments_stmt)
        assignments = list(assignments_result.scalars().all())

        profile_assignments = defaultdict(list)
        for a in assignments:
            profile_assignments[a.respondent_profile_id].append(a)

        # 3. Fetch latest delivery state per email without loading historical sends.
        ranked_sends = (
            select(
                EmailSend.recipient_email.label("recipient_email"),
                EmailSend.status.label("status"),
                func.row_number()
                .over(
                    partition_by=EmailSend.recipient_email,
                    order_by=EmailSend.created_at.desc(),
                )
                .label("row_number"),
            )
            .where(EmailSend.assignment_id.is_not(None))
            .subquery()
        )
        latest_sends_result = await session.execute(
            select(ranked_sends.c.recipient_email, ranked_sends.c.status).where(
                ranked_sends.c.row_number == 1
            )
        )
        latest_send_status_by_email = {
            recipient_email: send_status
            for recipient_email, send_status in latest_sends_result.all()
        }

        campaign_recipients = await repository.list_campaign_recipients(owner_id=owner_id)
        campaign_event_counts: dict[UUID, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        campaign_variant_by_recipient: dict[UUID, str] = {}
        campaign_recipient_ids = {recipient.id for recipient in campaign_recipients}
        if campaign_recipient_ids:
            campaign_event_counts_result = await session.execute(
                select(
                    CampaignRecipientEvent.recipient_id,
                    CampaignRecipientEvent.event_type,
                    func.count(CampaignRecipientEvent.id),
                )
                .where(CampaignRecipientEvent.recipient_id.in_(campaign_recipient_ids))
                .group_by(CampaignRecipientEvent.recipient_id, CampaignRecipientEvent.event_type)
            )
            for recipient_id, event_type, event_count in campaign_event_counts_result.all():
                campaign_event_counts[recipient_id][event_type] = int(event_count)
            campaign_variant_result = await session.execute(
                select(
                    CampaignRecipientEvent.recipient_id,
                    func.max(CampaignRecipientEvent.variant_key),
                )
                .where(CampaignRecipientEvent.recipient_id.in_(campaign_recipient_ids))
                .where(CampaignRecipientEvent.variant_key.is_not(None))
                .group_by(CampaignRecipientEvent.recipient_id)
            )
            campaign_variant_by_recipient = {
                recipient_id: variant_key
                for recipient_id, variant_key in campaign_variant_result.all()
                if variant_key
            }

        # 4. Process rows
        rows = []
        total_invites_sent = 0
        total_entered = 0
        total_completed = 0
        total_reminder_today = 0

        for profile in profiles:
            p_assignments = profile_assignments[profile.id]
            if not p_assignments:
                continue

            total_tasks = len(p_assignments)
            completed_tasks = sum(1 for a in p_assignments if a.status in {
                AssignmentStatus.submitted,
                AssignmentStatus.validated,
                AssignmentStatus.scored,
            })
            started_tasks = sum(1 for a in p_assignments if a.status == AssignmentStatus.started)

            tasks_str = f"{completed_tasks}/{total_tasks}"

            if completed_tasks == total_tasks:
                completion_state = "completed"
                total_completed += 1
            elif completed_tasks > 0 or started_tasks > 0:
                completion_state = "in_progress"
            else:
                completion_state = "not_started"

            latest_send_status = latest_send_status_by_email.get(profile.email)
            if latest_send_status is None:
                delivery_state = "draft"
            else:
                total_invites_sent += 1
                if latest_send_status == EmailSendStatus.failed:
                    delivery_state = "failed"
                elif latest_send_status == EmailSendStatus.accepted:
                    delivery_state = "sent"
                else:
                    delivery_state = latest_send_status.value

            has_entered = profile.user_id is not None or any(a.status in {
                AssignmentStatus.started,
                AssignmentStatus.submitted,
                AssignmentStatus.validated,
                AssignmentStatus.scored,
            } for a in p_assignments)
            if has_entered:
                total_entered += 1

            r_candidates = reminder_candidates(p_assignments, policy=DEFAULT_REMINDER_POLICY)
            is_reminder_due = len(r_candidates) > 0

            if completion_state == "completed":
                reminder_state = "none"
            elif is_reminder_due:
                reminder_state = "today"
                total_reminder_today += 1
            else:
                reminder_state = "tomorrow"

            if completion_state == "completed":
                next_action = "Completat"
            elif is_reminder_due:
                next_action = "Trimite reminder"
            elif latest_send_status is None:
                next_action = "Trimite invitatie"
            else:
                next_action = "Asteapta raspuns"

            audience_type = "leadership_account" if profile.user_id is not None else "secure_link"

            rows.append({
                "id": str(profile.id),
                "company_id": str(profile.company_id),
                "participant": profile.full_name,
                "email": profile.email,
                "audience": audience_type,
                "project": company_names.get(profile.id, "Pilot"),
                "tasks": tasks_str,
                "delivery": delivery_state,
                "reminder": reminder_state,
                "completion": completion_state,
                "nextAction": next_action,
            })

        metrics = [
            {
                "label": "Invitatii trimise",
                "value": str(total_invites_sent),
                "detail": "Conturi lideri si linkuri securizate membri.",
            },
            {
                "label": "Au intrat in app",
                "value": str(total_entered),
                "detail": "Click pe link sau autentificare cont.",
            },
            {
                "label": "Completate",
                "value": str(total_completed),
                "detail": "Toate sarcinile finalizate.",
            },
            {
                "label": "Reminder azi",
                "value": str(total_reminder_today),
                "detail": "Invitati sau inceputi fara submit.",
            },
        ]

        rules = [
            "Liderii primesc email de cont si pot reveni la sarcinile lor.",
            (
                "Membrii fara cont primesc link securizat per proiect, "
                "valabil pana la deadline."
            ),
            (
                "Reminderul se trimite pentru status invitat sau inceput, "
                "nu pentru sarcini finalizate."
            ),
            (
                "Emailurile nu includ raspunsuri confidentiale, "
                "doar linkuri si status operational."
            ),
        ]

        campaign_rows = [
            {
                "id": str(recipient.id),
                "company": recipient.organization_name or "Companie necompletată",
                "firstName": _first_name(recipient.contact_name),
                "lastName": _last_name(recipient.contact_name),
                "email": recipient.email or "",
                "clientType": _campaign_client_type(recipient.segment.value),
                "status": _campaign_recipient_status(recipient),
                "openRate": None,
                "clickRate": None,
                "viewRate": None,
                "openCount": campaign_event_counts[recipient.id]["opened"],
                "clickCount": campaign_event_counts[recipient.id]["clicked"],
                "viewCount": campaign_event_counts[recipient.id]["video_viewed"],
                "replyCount": campaign_event_counts[recipient.id]["replied"],
                "calendlyClickCount": campaign_event_counts[recipient.id]["calendly_clicked"],
                "emailVariant": campaign_variant_by_recipient.get(recipient.id) or recipient.source,
                "outcome": None,
            }
            for recipient in campaign_recipients
        ]

        campaign = {
            "videoHost": {
                "provider": "Vimeo sau pagină Codruț",
                "status": "ready",
                "note": (
                    "Emailul trimite thumbnail și CTA către linkul video. "
                    "Pagina Codruț este opțională când vrei tracking sau CTA-uri dedicate."
                ),
            },
            "template": {
                "subject": "O idee practică pentru echipa ta, ${first_name}",
                "personalization": "Prenumele se completează automat când există nume în bază.",
                "ctaPrimary": "Programează o discuție",
                "ctaSecondary": "Vreau să fiu contactat",
            },
            "recipients": campaign_rows,
            "weeklyReport": {
                "cadence": "Săptămânal",
                "metrics": [
                    "deschideri",
                    "clickuri",
                    "vizualizări video",
                    "reply-uri",
                    "clickuri Calendly",
                    "variantă email",
                ],
                "notification": "Andrei primește email/Telegram cu link către raport.",
            },
        }

        return {
            "metrics": metrics,
            "assessmentRows": rows,
            "rules": rules,
            "campaign": campaign,
        }


def _first_name(full_name: str | None) -> str | None:
    if not full_name:
        return None
    parts = full_name.strip().split()
    return parts[0] if parts else None


def _last_name(full_name: str | None) -> str | None:
    if not full_name:
        return None
    parts = full_name.strip().split()
    return " ".join(parts[1:]) if len(parts) > 1 else None


def _campaign_client_type(segment: str) -> str:
    return "tip_1" if segment == "past_customer" else "tip_2"


def _campaign_recipient_membership_row(
    recipient: CampaignRecipient,
) -> CampaignRecipientMembershipRowResponse:
    return CampaignRecipientMembershipRowResponse(
        id=str(recipient.id),
        company=recipient.organization_name or "Companie necompletată",
        firstName=_first_name(recipient.contact_name),
        lastName=_last_name(recipient.contact_name),
        email=recipient.email or "",
        clientType=_campaign_client_type(recipient.segment.value),
        status=_campaign_recipient_status(recipient),
        openRate=None,
        clickRate=None,
        viewRate=None,
        openCount=0,
        clickCount=0,
        viewCount=0,
        replyCount=0,
        calendlyClickCount=0,
        emailVariant=recipient.source,
        outcome=None,
        membershipSource=None,
    )


def _campaign_recipient_status(recipient: CampaignRecipient) -> str:
    if recipient.status == CampaignRecipientStatus.unsubscribed:
        return "unsubscribed"
    if recipient.status == CampaignRecipientStatus.suppressed:
        return "suppressed"
    if not recipient.contact_name:
        return "needs_contact_name"
    return "ready"


def _campaign_unsubscribe_url(recipient: CampaignRecipient, settings: Settings) -> str:
    token = create_campaign_recipient_action_token(
        CampaignRecipientActionClaims(
            recipient_id=recipient.id,
            action="unsubscribe",
        ),
        settings,
    )
    return build_campaign_unsubscribe_url(token, settings)


def _render_campaign_message(
    campaign: Campaign,
    recipient: CampaignRecipient,
    unsubscribe_url: str,
    settings: Settings,
) -> EmailMessage:
    contact_name = recipient.contact_name or ""
    calendly_tracking_url = _campaign_calendly_tracking_url(campaign, recipient, settings)
    context = {
        "first_name": _first_name(contact_name) or "",
        "last_name": _last_name(contact_name) or "",
        "contact_name": contact_name,
        "company_name": recipient.organization_name or "",
        "organization_name": recipient.organization_name or "",
        "email": recipient.email or "",
        "video_url": campaign.video_url or "",
        "thumbnail_url": campaign.thumbnail_url or "",
        "landing_page_url": campaign.landing_page_url or campaign.video_url or "",
        "calendly_url": calendly_tracking_url,
        "unsubscribe_url": unsubscribe_url,
    }

    subject = _render_campaign_template(campaign.subject, context)
    html_body = _render_campaign_template(campaign.html_body, context)
    text_body = _render_campaign_template(campaign.text_body, context)
    if not campaign.video_url and not campaign.thumbnail_url:
        html_body = _remove_empty_campaign_video_blocks(html_body)
        text_body = _remove_empty_campaign_video_lines(text_body)
    if not _campaign_message_has_calendly_link(html_body, calendly_tracking_url):
        html_body = _append_campaign_calendly_cta(html_body, calendly_tracking_url)
    html_body = _rewrite_campaign_tracking_links(
        html_body,
        campaign,
        recipient,
        settings,
        calendly_tracking_url=calendly_tracking_url,
    )
    if "font-family:Inter,Arial,sans-serif" not in html_body:
        html_body = (
            EMAIL_SHELL_OPEN
            + html_body
            + _render_campaign_template(PROMOTIONAL_SHELL_CLOSE, context)
        )
    html_body = _append_campaign_open_pixel(html_body, campaign, recipient, settings)
    if not _campaign_message_has_calendly_link(text_body, calendly_tracking_url):
        text_body = f"{text_body}\n\nAlege un slot în Calendly: {calendly_tracking_url}"
    if unsubscribe_url not in text_body:
        text_body = f"{text_body}\n\nDezabonare: {unsubscribe_url}"
    return EmailMessage(
        to=EmailAddress(recipient.email),
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


_EMPTY_CAMPAIGN_VIDEO_BLOCK_RE = re.compile(
    r'<p\b[^>]*>\s*<a\b[^>]*href=""[^>]*>.*?<img\b[^>]*src=""[^>]*>.*?</a>\s*</p>',
    re.IGNORECASE | re.DOTALL,
)
_EMPTY_CAMPAIGN_VIDEO_LINE_RE = re.compile(r"(?m)^[^\n]*(?:Video|video)[^\n]*:\s*$\n?")
_CAMPAIGN_HREF_RE = re.compile(r'href=(["\'])([^"\']+)\1', re.IGNORECASE)


def _remove_empty_campaign_video_blocks(html_body: str) -> str:
    return _EMPTY_CAMPAIGN_VIDEO_BLOCK_RE.sub("", html_body)


def _remove_empty_campaign_video_lines(text_body: str) -> str:
    return _EMPTY_CAMPAIGN_VIDEO_LINE_RE.sub("", text_body)


def _campaign_message_has_calendly_link(body: str, calendly_tracking_url: str) -> bool:
    normalized = body.lower()
    return (
        bool(calendly_tracking_url and calendly_tracking_url in body)
        or 'data-codrut-cta="calendly"' in normalized
        or "calendly.com" in normalized
    )


def _append_campaign_calendly_cta(html_body: str, calendly_url: str) -> str:
    cta = (
        '<p style="margin-top:24px;">'
        f'<a href="{calendly_url}" '
        'data-codrut-cta="calendly" '
        'style="display:inline-block;background:#890505;color:#ffffff;'
        'padding:12px 18px;border-radius:999px;text-decoration:none;font-weight:700;">'
        "Alege un slot în Calendly"
        "</a></p>"
    )
    footer_marker = '<div style="margin-top:24px;padding-top:24px;border-top:1px solid #eadfdb;'
    if footer_marker in html_body:
        return html_body.replace(footer_marker, cta + footer_marker, 1)
    shell_close = "</div></div>"
    stripped = html_body.rstrip()
    if stripped.endswith(shell_close):
        return stripped[: -len(shell_close)] + cta + shell_close
    return html_body + cta


def _append_campaign_open_pixel(
    html_body: str,
    campaign: Campaign,
    recipient: CampaignRecipient,
    settings: Settings,
) -> str:
    tracking_url = _campaign_tracking_url(
        campaign,
        recipient,
        settings,
        target_url=settings.public_app_url.rstrip("/") + "/",
        event_type="opened",
    )
    pixel = (
        f'<img src="{html_escape(tracking_url, quote=True)}" width="1" height="1" '
        'alt="" aria-hidden="true" style="display:none!important;opacity:0;'
        'width:1px;height:1px;border:0;" />'
    )
    shell_close = "</div></div>"
    stripped = html_body.rstrip()
    if stripped.endswith(shell_close):
        return stripped[: -len(shell_close)] + pixel + shell_close
    return html_body + pixel


def _rewrite_campaign_tracking_links(
    html_body: str,
    campaign: Campaign,
    recipient: CampaignRecipient,
    settings: Settings,
    *,
    calendly_tracking_url: str,
) -> str:
    video_targets = {
        target
        for target in (campaign.video_url, campaign.landing_page_url or campaign.video_url)
        if target
    }

    def replace_href(match: re.Match[str]) -> str:
        quote = match.group(1)
        raw_href = html_unescape(match.group(2)).strip()
        if not _should_track_campaign_href(raw_href, settings, calendly_tracking_url):
            return match.group(0)
        if _is_calendly_target(raw_href):
            event_type = "calendly_clicked"
        elif raw_href in video_targets:
            event_type = "video_viewed"
        else:
            event_type = "clicked"
        tracking_url = _campaign_tracking_url(
            campaign,
            recipient,
            settings,
            target_url=raw_href,
            event_type=event_type,
        )
        return f"href={quote}{html_escape(tracking_url, quote=True)}{quote}"

    return _CAMPAIGN_HREF_RE.sub(replace_href, html_body)


def _should_track_campaign_href(
    href: str,
    settings: Settings,
    calendly_tracking_url: str,
) -> bool:
    if not href or href == calendly_tracking_url:
        return False
    parsed = urlparse(href)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    public_base = settings.public_app_url.rstrip("/")
    tracking_prefix = f"{public_base}/api/communications/campaigns/"
    if href.startswith(tracking_prefix):
        return False
    return True


def _is_calendly_target(target_url: str) -> bool:
    hostname = urlparse(target_url).hostname
    return hostname == "calendly.com" or (hostname or "").endswith(".calendly.com")


def _campaign_calendly_tracking_url(
    campaign: Campaign,
    recipient: CampaignRecipient,
    settings: Settings,
) -> str:
    return _campaign_tracking_url(
        campaign,
        recipient,
        settings,
        target_url=CAMPAIGN_CALENDLY_URL,
        event_type="calendly_clicked",
    )


def _campaign_tracking_url(
    campaign: Campaign,
    recipient: CampaignRecipient,
    settings: Settings,
    *,
    target_url: str,
    event_type: str,
) -> str:
    token = create_campaign_tracking_token(
        CampaignTrackingClaims(
            recipient_id=recipient.id,
            target_url=target_url,
            event_type=event_type,
            variant_key=str(campaign.id),
            expires_at=datetime.now(UTC) + timedelta(days=30),
        ),
        settings,
    )
    return build_campaign_tracking_url(token, settings, event_type=event_type)


def _render_campaign_template(template: str, context: dict[str, str]) -> str:
    rendered = Template(template).safe_substitute(context)
    for key, value in context.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _require_calendly_target(target_url: str) -> None:
    if not _is_calendly_target(target_url):
        raise DomainError(
            "Campaign Calendly tracking link target is not allowed.",
            code="campaign_tracking_invalid_target",
        )


async def _remaining_email_sends_today(
    repository: CommunicationsRepository,
    settings: Settings,
) -> int:
    cap = max(settings.email_daily_send_cap, 0)
    if cap == 0:
        return 0
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if not hasattr(repository, "count_accepted_sends_since"):
        return cap
    already_sent = await repository.count_accepted_sends_since(day_start)
    return max(cap - already_sent, 0)


@dataclass(frozen=True)
class AssignmentInvitationContext:
    company_name: str
    trainer_name: str
    action_url: str
    task_count: int = 1


class TransactionalEmailService:
    def __init__(self, provider: EmailProvider, session: AsyncSession | None = None) -> None:
        self.provider = provider
        self.session = session
        self._template_cache: dict[str, EmailTemplate | None] = {}

    async def send_assignment_invitation(
        self,
        assignment: QuestionnaireAssignment,
        respondent: ParticipantProfile,
        context: AssignmentInvitationContext,
    ) -> EmailSendResult:
        template_key = _select_invitation_template(respondent)

        version = 1
        db_template = None
        if self.session is not None:
            if template_key.value not in self._template_cache:
                repository = CommunicationsRepository(self.session)
                self._template_cache[template_key.value] = await repository.get_template(
                    template_key.value
                )
            db_template = self._template_cache[template_key.value]
        if db_template is not None:
            subject = db_template.subject
            html_body = db_template.html_body
            text_body = db_template.text_body
            variables = db_template.variables
            version = db_template.version
        else:
            template = get_transactional_template(template_key)
            subject = template.subject
            html_body = template.html_body
            text_body = template.text_body
            variables = list(template.required_context)
            version = template.version

        message = render_template_content(
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            required_variables=variables,
            to=EmailAddress(respondent.email),
            context={
                "participant_name": respondent.full_name,
                "trainer_name": context.trainer_name,
                "company_name": context.company_name,
                "task_count": str(context.task_count),
                "action_url": context.action_url,
            },
        )

        email_send: EmailSend | None = None
        if self.session is not None:
            email_send = EmailSend(
                assignment_id=assignment.id,
                recipient_email=respondent.email,
                template_key=template_key.value,
                template_version=version,
                provider=str(getattr(self.provider, "key", "unknown")),
                provider_message_id=None,
                status=EmailSendStatus.queued,
                last_event_at=datetime.now(UTC),
            )
            self.session.add(email_send)
            await self.session.flush()

        result = await self.provider.send(message)

        if email_send is not None:
            send_status = EmailSendStatus.queued
            if result.status == EmailDeliveryStatus.accepted:
                send_status = EmailSendStatus.accepted
            elif result.status == EmailDeliveryStatus.failed:
                send_status = EmailSendStatus.failed

            email_send.provider = result.provider.value
            email_send.provider_message_id = result.message_id
            email_send.status = send_status
            email_send.error_details = result.error_details
            email_send.last_event_at = datetime.now(UTC)
            await self.session.flush()

        if (
            result.status == EmailDeliveryStatus.accepted
            and assignment.status == AssignmentStatus.assigned
        ):
            assignment.status = AssignmentStatus.invited
            assignment.invited_at = datetime.now(UTC)
        return result


def _select_invitation_template(respondent: ParticipantProfile) -> TransactionalTemplateKey:
    if (respondent.role_group or "").strip().casefold() == "leadership":
        return TransactionalTemplateKey.account_setup
    return TransactionalTemplateKey.assignment_bundle
