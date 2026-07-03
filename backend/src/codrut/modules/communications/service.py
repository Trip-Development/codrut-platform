import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
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
    build_campaign_unsubscribe_url,
    create_campaign_recipient_action_token,
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
    TRANSACTIONAL_TEMPLATES,
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

    async def list_templates(self, *, active_only: bool = True) -> list[EmailTemplateResponse]:
        repository = self._require_repository()
        await self._seed_catalog_templates(repository)
        templates = await repository.list_templates(active_only=active_only)
        return [EmailTemplateResponse.model_validate(t) for t in templates]

    async def get_template(self, key: str, *, version: int | None = None) -> EmailTemplateResponse:
        repository = self._require_repository()
        template = await repository.get_template(key, version=version)
        if template is None:
            await self._seed_catalog_templates(repository)
            template = await repository.get_template(key, version=version)
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
            await repository.deactivate_templates_for_key(payload.key)
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
    ) -> EmailTemplateResponse:
        repository = self._require_repository()
        template = await repository.get_template(key, version=version)
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
        if has_sends:
            next_version = await repository.get_latest_version(key) + 1
            await repository.deactivate_templates_for_key(key)
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
                    owner_id=template.owner_id,
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
            await repository.deactivate_templates_for_key(key, except_version=template.version)

        return EmailTemplateResponse.model_validate(template)

    async def activate_template(self, key: str, version: int) -> EmailTemplateResponse:
        repository = self._require_repository()
        template = await repository.get_template(key, version=version)
        if template is None:
            raise DomainError("Email template not found.", code="email_template_not_found")
        await repository.deactivate_templates_for_key(key, except_version=template.version)
        template.active = True
        return EmailTemplateResponse.model_validate(template)

    async def retire_template(
        self,
        key: str,
        *,
        version: int | None = None,
    ) -> EmailTemplateResponse:
        repository = self._require_repository()
        template = await repository.get_template(key, version=version)
        if template is None:
            raise DomainError("Email template not found.", code="email_template_not_found")
        if version is None:
            await repository.deactivate_templates_for_key(key)
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
        for k, catalog_template in TRANSACTIONAL_TEMPLATES.items():
            existing = existing_templates.get((k.value, catalog_template.version))
            if existing is None:
                existing = await repository.add_template(
                    EmailTemplate(
                        key=k.value,
                        version=catalog_template.version,
                        subject=catalog_template.subject,
                        html_body=catalog_template.html_body,
                        text_body=catalog_template.text_body,
                        variables=list(catalog_template.required_context),
                        audience="participant",
                        active=True,
                    )
                )
                existing_templates[(k.value, catalog_template.version)] = existing
                await repository.deactivate_templates_for_key(
                    k.value,
                    except_version=catalog_template.version,
                )
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
    ) -> list[CampaignRecipient]:
        repository = self._require_repository()

        recipients_by_email: dict[str, CampaignRecipient] = {}
        for req in payload.recipients:
            normalized_email = req.email.lower()
            recipients_by_email.setdefault(
                normalized_email,
                CampaignRecipient(
                    email=normalized_email,
                    contact_name=req.contact_name,
                    organization_name=req.organization_name,
                    segment=req.segment,
                    source=req.source,
                ),
            )

        existing = await repository.list_campaign_recipients_by_emails(
            set(recipients_by_email),
        )
        existing_by_email = {recipient.email.lower(): recipient for recipient in existing}
        recipients_to_create = [
            recipient
            for email, recipient in recipients_by_email.items()
            if email not in existing_by_email
        ]
        if recipients_to_create:
            await repository.add_campaign_recipients(recipients_to_create)
        return [*existing, *recipients_to_create]

    async def update_campaign_recipient(
        self,
        recipient_id: UUID,
        payload: CampaignRecipientUpdateRequest,
    ) -> CampaignRecipient:
        repository = self._require_repository()
        recipient = await repository.get_campaign_recipient(recipient_id)
        if recipient is None:
            raise DomainError("Campaign recipient not found.", code="campaign_recipient_not_found")

        if payload.email is not None:
            normalized_email = str(payload.email).lower()
            existing_email_recipient = await repository.get_campaign_recipient_by_email(
                normalized_email,
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
                recipient.status = CampaignRecipientStatus(payload.status)
            except ValueError as exc:
                raise DomainError(
                    "Invalid campaign recipient status.",
                    code="campaign_recipient_status_invalid",
                ) from exc
        if payload.source is not None:
            recipient.source = payload.source.strip() or None

        await repository.flush()
        return recipient

    async def delete_campaign_recipient(self, recipient_id: UUID) -> None:
        repository = self._require_repository()
        recipient = await repository.get_campaign_recipient(recipient_id)
        if recipient is None:
            raise DomainError("Campaign recipient not found.", code="campaign_recipient_not_found")
        if recipient.status == CampaignRecipientStatus.active:
            recipient.status = CampaignRecipientStatus.suppressed
        await repository.flush()

    async def create_campaign(
        self,
        payload: CampaignCreateRequest,
    ) -> Campaign:
        repository = self._require_repository()

        campaign = Campaign(
            name=payload.name,
            segment=payload.segment,
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
    ) -> Campaign:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")

        provided_fields = payload.model_fields_set
        if "name" in provided_fields and payload.name is not None:
            campaign.name = payload.name.strip()
        if "segment" in provided_fields and payload.segment is not None:
            try:
                campaign.segment = CampaignRecipientSegment(payload.segment)
            except ValueError as exc:
                raise DomainError(
                    "Invalid campaign segment.",
                    code="campaign_segment_invalid",
                ) from exc
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

    async def list_campaigns(self) -> list[Campaign]:
        repository = self._require_repository()
        return await repository.list_campaigns()

    async def delete_campaign(self, campaign_id: UUID) -> None:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")
        await repository.delete_campaign(campaign)

    async def send_campaign(
        self,
        campaign_id: UUID,
        payload: CampaignSendRequest,
        *,
        provider: EmailProvider,
        settings: Settings,
    ) -> CampaignSendResponse:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")
        if campaign.status not in {CampaignStatus.ready, CampaignStatus.completed}:
            raise DomainError(
                "Campaign must be ready before sending.",
                code="campaign_not_ready",
            )

        recipients = await self._campaign_send_recipients(campaign, payload)
        if not recipients:
            raise DomainError("Campaign has no matching recipients.", code="campaign_no_recipients")

        results: list[CampaignSendRecipientResult] = []
        remaining_sends = await _remaining_email_sends_today(repository, settings)
        for recipient in recipients:
            if recipient.segment != campaign.segment:
                results.append(
                    CampaignSendRecipientResult(
                        recipient_id=recipient.id,
                        email=recipient.email,
                        status="skipped",
                        error="Recipient segment does not match campaign segment.",
                    )
                )
                continue
            if recipient.status != CampaignRecipientStatus.active:
                results.append(
                    CampaignSendRecipientResult(
                        recipient_id=recipient.id,
                        email=recipient.email,
                        status="skipped",
                        error="Recipient is suppressed or unsubscribed.",
                    )
                )
                continue

            if not payload.dry_run and remaining_sends <= 0:
                results.append(
                    CampaignSendRecipientResult(
                        recipient_id=recipient.id,
                        email=recipient.email,
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
            message = _render_campaign_message(campaign, recipient, unsubscribe_url)

            if payload.dry_run:
                results.append(
                    CampaignSendRecipientResult(
                        recipient_id=recipient.id,
                        email=recipient.email,
                        status="dry_run",
                    )
                )
                continue

            result = await provider.send(message)
            send_status = (
                EmailSendStatus.accepted
                if result.status == EmailDeliveryStatus.accepted
                else EmailSendStatus.failed
            )
            await repository.add_email_send(
                EmailSend(
                    assignment_id=None,
                    campaign_id=campaign.id,
                    campaign_recipient_id=recipient.id,
                    recipient_email=recipient.email,
                    template_key="campaign",
                    template_version=1,
                    provider=result.provider.value,
                    provider_message_id=result.message_id,
                    status=send_status,
                    error_details=result.error_details,
                    last_event_at=datetime.now(UTC),
                )
            )
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

    async def unsubscribe_campaign_recipient(
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
        recipient.status = CampaignRecipientStatus.unsubscribed
        await repository.flush()
        return recipient

    async def _campaign_send_recipients(
        self,
        campaign: Campaign,
        payload: CampaignSendRequest,
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
            return await repository.list_campaign_recipients_by_ids(payload.recipient_ids)
        recipients = await repository.list_campaign_recipients()
        matching = [recipient for recipient in recipients if recipient.segment == campaign.segment]
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
    ) -> CampaignRecipientEventResponse:
        repository = self._require_repository()
        recipient = await repository.get_campaign_recipient(recipient_id)
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
        claims = parse_campaign_tracking_token(token, settings)
        if claims.event_type != "calendly_clicked":
            raise DomainError(
                "Campaign tracking link has the wrong event type.",
                code="campaign_tracking_invalid",
            )
        _require_calendly_target(claims.target_url)
        await self.record_campaign_recipient_event(
            claims.recipient_id,
            CampaignRecipientEventCreateRequest(
                event_type="calendly_clicked",
                variant_key=claims.variant_key,
            ),
        )
        return claims.target_url

    async def get_email_ops_summary(self) -> dict:
        repository = self._require_repository()
        session = repository.session

        from collections import defaultdict

        from sqlalchemy import select

        from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
        from codrut.modules.communications.models import EmailSend, EmailSendStatus
        from codrut.modules.communications.reminders import (
            DEFAULT_REMINDER_POLICY,
            reminder_candidates,
        )
        from codrut.modules.companies.models import Company, ParticipantProfile

        # 1. Fetch all participants and their company details
        profiles_result = await session.execute(
            select(ParticipantProfile, Company.name)
            .join(Company, ParticipantProfile.company_id == Company.id)
        )
        profiles = []
        company_names = {}
        for profile, comp_name in profiles_result.all():
            profiles.append(profile)
            company_names[profile.id] = comp_name

        # 2. Fetch all assignments
        assignments_result = await session.execute(select(QuestionnaireAssignment))
        assignments = list(assignments_result.scalars().all())

        profile_assignments = defaultdict(list)
        for a in assignments:
            profile_assignments[a.respondent_profile_id].append(a)

        # 3. Fetch all EmailSend records
        sends_result = await session.execute(
            select(EmailSend).order_by(EmailSend.created_at.desc())
        )
        sends = list(sends_result.scalars().all())

        latest_send_by_email = {}
        for s in sends:
            if s.recipient_email not in latest_send_by_email:
                latest_send_by_email[s.recipient_email] = s

        campaign_recipients = await repository.list_campaign_recipients()
        campaign_events = await repository.list_campaign_recipient_events()
        campaign_event_counts: dict[UUID, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        campaign_variant_by_recipient: dict[UUID, str] = {}
        for event in campaign_events:
            campaign_event_counts[event.recipient_id][event.event_type] += 1
            if event.variant_key and event.recipient_id not in campaign_variant_by_recipient:
                campaign_variant_by_recipient[event.recipient_id] = event.variant_key

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

            latest_send = latest_send_by_email.get(profile.email)
            if latest_send is None:
                delivery_state = "draft"
            else:
                total_invites_sent += 1
                if latest_send.status == EmailSendStatus.failed:
                    delivery_state = "failed"
                elif latest_send.status == EmailSendStatus.accepted:
                    delivery_state = "sent"
                else:
                    delivery_state = latest_send.status.value

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
            elif latest_send is None:
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
                "email": recipient.email,
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
            if recipient.status == CampaignRecipientStatus.active
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


def _campaign_recipient_status(recipient: CampaignRecipient) -> str:
    if recipient.status.value in {"suppressed", "unsubscribed"}:
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
) -> EmailMessage:
    contact_name = recipient.contact_name or ""
    context = {
        "first_name": _first_name(contact_name) or "",
        "last_name": _last_name(contact_name) or "",
        "contact_name": contact_name,
        "company_name": recipient.organization_name or "",
        "organization_name": recipient.organization_name or "",
        "email": recipient.email,
        "video_url": campaign.video_url or "",
        "thumbnail_url": campaign.thumbnail_url or "",
        "landing_page_url": campaign.landing_page_url or campaign.video_url or "",
        "unsubscribe_url": unsubscribe_url,
    }

    subject = _render_campaign_template(campaign.subject, context)
    html_body = _render_campaign_template(campaign.html_body, context)
    text_body = _render_campaign_template(campaign.text_body, context)
    if "font-family:Inter,Arial,sans-serif" not in html_body:
        html_body = (
            EMAIL_SHELL_OPEN
            + html_body
            + _render_campaign_template(PROMOTIONAL_SHELL_CLOSE, context)
        )
    text_body = f"{text_body}\n\nDezabonare: {unsubscribe_url}"
    return EmailMessage(
        to=EmailAddress(recipient.email),
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


def _render_campaign_template(template: str, context: dict[str, str]) -> str:
    rendered = Template(template).safe_substitute(context)
    for key, value in context.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _require_calendly_target(target_url: str) -> None:
    hostname = urlparse(target_url).hostname
    if hostname != "calendly.com" and not (hostname or "").endswith(".calendly.com"):
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

        result = await self.provider.send(message)

        if self.session is not None:
            from codrut.modules.communications.models import EmailSend, EmailSendStatus
            send_status = EmailSendStatus.queued
            if result.status == EmailDeliveryStatus.accepted:
                send_status = EmailSendStatus.accepted
            elif result.status == EmailDeliveryStatus.failed:
                send_status = EmailSendStatus.failed

            email_send = EmailSend(
                assignment_id=assignment.id,
                recipient_email=respondent.email,
                template_key=template_key.value,
                template_version=version,
                provider=result.provider.value,
                provider_message_id=result.message_id,
                status=send_status,
                error_details=result.error_details,
                last_event_at=datetime.now(UTC),
            )
            self.session.add(email_send)
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
