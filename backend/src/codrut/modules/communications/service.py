import hashlib
import json
import re
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from html import escape as html_escape
from html import unescape as html_unescape
from string import Template
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.contracts.emails import (
    EmailAddress,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
    EmailSendResult,
)
from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
from codrut.modules.communications.assets import delete_campaign_asset, store_campaign_asset
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
from codrut.modules.communications.html_sanitizer import sanitize_email_html
from codrut.modules.communications.models import (
    Campaign,
    CampaignAsset,
    CampaignContactTombstone,
    CampaignRecipient,
    CampaignRecipientEvent,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
    EmailEventType,
    EmailSend,
    EmailSendStatus,
    EmailSuppressionReview,
    EmailTemplate,
)
from codrut.modules.communications.reminders import DEFAULT_REMINDER_POLICY
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.schemas import (
    CampaignAssetUploadResponse,
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
from codrut.modules.communications.suppression import (
    email_suppression_fingerprint,
    provider_event_fingerprint,
    provider_message_fingerprint,
)
from codrut.modules.communications.templates import (
    EMAIL_SHELL_OPEN,
    PROMOTIONAL_SHELL_CLOSE,
    TransactionalTemplateKey,
    get_transactional_template,
)
from codrut.modules.companies.models import ParticipantProfile

TEMPLATE_VARIABLE_PATTERN = re.compile(r"(?a:[_a-z][_a-z0-9]*)", re.IGNORECASE)

SYSTEM_TEMPLATE_REQUIRED_VARS = {
    "account_setup": {"participant_name", "trainer_name", "company_name", "action_url"},
    "assignment_bundle": {"participant_name", "company_name", "task_count", "action_url"},
    "assignment_reminder": {"participant_name", "company_name", "action_url"},
}
CAMPAIGN_TEMPLATE_VARIABLES = frozenset(
    {
        "calendly_url",
        "company_name",
        "contact_name",
        "email",
        "first_name",
        "landing_page_url",
        "last_name",
        "legal_address",
        "organization_name",
        "thumbnail_url",
        "unsubscribe_url",
        "video_url",
    }
)


def _require_delivery_owner_id(owner_id: UUID | None) -> UUID:
    if owner_id is None:
        raise DomainError(
            "Delivery owner is required.",
            code="email_delivery_owner_required",
        )
    return owner_id


def _require_campaign_delivery_ownership(
    campaign: Campaign,
    recipient: CampaignRecipient,
    *,
    owner_id: UUID,
) -> None:
    if campaign.owner_id != owner_id or recipient.owner_id != owner_id:
        raise DomainError(
            "Campaign recipient not found.",
            code="campaign_recipient_not_found",
        )


def _require_email_send_ownership(send: EmailSend, *, owner_id: UUID) -> None:
    if send.owner_id != owner_id:
        raise DomainError(
            "Campaign recipient not found.",
            code="campaign_recipient_not_found",
        )


def _is_managed_campaign_asset_url(value: str | None, settings: Settings | None) -> bool:
    if not value:
        return False
    configured_path = settings.campaign_asset_public_path if settings else "/api/campaign-assets"
    public_path = configured_path.rstrip("/")
    return urlparse(value).path.startswith(f"{public_path}/")


async def _bind_campaign_asset(
    repository: CommunicationsRepository,
    campaign: Campaign,
    *,
    previous_url: str | None,
    next_url: str | None,
    owner_id: UUID,
    settings: Settings | None,
) -> None:
    if previous_url == next_url:
        return

    if _is_managed_campaign_asset_url(previous_url, settings):
        previous_asset = await repository.get_campaign_asset_by_url(
            previous_url or "",
            owner_id=owner_id,
            for_update=True,
        )
        if previous_asset is not None and previous_asset.campaign_id == campaign.id:
            previous_asset.campaign_id = None
            previous_asset.status = "staged"

    if not _is_managed_campaign_asset_url(next_url, settings):
        return
    asset: CampaignAsset | None = await repository.get_campaign_asset_by_url(
        next_url or "",
        owner_id=owner_id,
        for_update=True,
    )
    if asset is None:
        raise DomainError(
            "Campaign asset does not belong to this trainer.",
            code="campaign_asset_not_owned",
        )
    if asset.campaign_id not in {None, campaign.id}:
        raise DomainError(
            "Campaign asset is already attached to another campaign.",
            code="campaign_asset_already_attached",
        )
    asset.campaign_id = campaign.id
    asset.status = "attached"


CAMPAIGN_CALENDLY_URL = "https://calendly.com/andreivacaru/intalnire-de-apropiere"
EMAIL_OUTBOX_LEASE_DURATION = timedelta(minutes=5)
EMAIL_OUTBOX_MAX_ATTEMPTS = 5
EMAIL_OUTBOX_RETRY_BASE_SECONDS = 30
EMAIL_OUTBOX_RETRY_MAX_SECONDS = 15 * 60


@dataclass(frozen=True)
class CampaignRecipientBulkCreateResult:
    recipients: list[CampaignRecipient]
    created: int
    updated: int


@dataclass(frozen=True)
class CampaignRecipientArchiveResult:
    recipient: CampaignRecipient
    memberships_removed: int
    cancelled: int
    in_flight: int


@dataclass(frozen=True)
class CampaignRecipientPurgeResult:
    recipient_id: UUID
    cancelled: int
    anonymized_sends: int


@dataclass(frozen=True)
class CampaignRecipientPurgeBatchResult:
    examined: int
    purged: int
    deferred: int


@dataclass(frozen=True)
class CampaignRecipientDeliveryReconciliation:
    cancelled: int
    provider_unresolved: list[EmailSend]
    unsafe_unresolved: list[EmailSend]


@dataclass(frozen=True)
class EmailSuppressionReviewBatchResult:
    examined: int
    retained: int
    needs_review: int
    deleted: int


@dataclass(frozen=True)
class CampaignUnsubscribeTarget:
    recipient: CampaignRecipient | None = None
    tombstone: CampaignContactTombstone | None = None

    @property
    def id(self) -> UUID:
        if self.recipient is not None:
            return self.recipient.id
        if self.tombstone is None:
            raise RuntimeError("Unsubscribe target is empty.")
        return self.tombstone.former_recipient_id

    @property
    def email(self) -> str | None:
        return self.recipient.email if self.recipient is not None else None


def extract_placeholders(text: str) -> set[str]:
    placeholders: set[str] = set()
    for match in Template.pattern.finditer(text):
        if match.group("invalid") is not None:
            raise DomainError(
                "Template contains malformed placeholder syntax.",
                code="email_template_malformed_placeholder",
            )
        identifier = match.group("named") or match.group("braced")
        if identifier is not None:
            placeholders.add(identifier)
    return placeholders


def validate_template_placeholders(
    subject: str,
    html_body: str,
    text_body: str,
    declared_variables: list[str],
    key: str,
) -> None:
    invalid_variables = sorted(
        {
            variable
            for variable in declared_variables
            if TEMPLATE_VARIABLE_PATTERN.fullmatch(variable) is None
        }
    )
    if invalid_variables:
        raise DomainError(
            f"Invalid template variable names: {', '.join(invalid_variables)}",
            code="email_template_invalid_variables",
        )

    seen_variables: set[str] = set()
    duplicate_variables: set[str] = set()
    for variable in declared_variables:
        if variable in seen_variables:
            duplicate_variables.add(variable)
        seen_variables.add(variable)
    if duplicate_variables:
        raise DomainError(
            f"Duplicate template variables: {', '.join(sorted(duplicate_variables))}",
            code="email_template_duplicate_variables",
        )

    all_placeholders = (
        extract_placeholders(subject)
        | extract_placeholders(html_body)
        | extract_placeholders(text_body)
    )

    required = SYSTEM_TEMPLATE_REQUIRED_VARS.get(key, set())
    declared_set = set(declared_variables)
    missing_declared = required - declared_set
    if missing_declared:
        msg = (
            f"Missing required variables for system template: {', '.join(sorted(missing_declared))}"
        )
        raise DomainError(
            msg,
            code="email_template_missing_required_variables",
        )

    undeclared = all_placeholders - declared_set
    if undeclared:
        raise DomainError(
            f"Template contains undeclared variables: {', '.join(sorted(undeclared))}",
            code="email_template_undeclared_variables",
        )

    missing_required_placeholders = required - all_placeholders
    if missing_required_placeholders:
        raise DomainError(
            "Required system variables are absent from template content: "
            f"{', '.join(sorted(missing_required_placeholders))}",
            code="email_template_missing_required_placeholders",
        )


def validate_campaign_placeholders(subject: str, html_body: str, text_body: str) -> None:
    placeholders = (
        extract_placeholders(subject)
        | extract_placeholders(html_body)
        | extract_placeholders(text_body)
    )
    unsupported = placeholders - CAMPAIGN_TEMPLATE_VARIABLES
    if unsupported:
        raise DomainError(
            f"Campaign contains unsupported variables: {', '.join(sorted(unsupported))}",
            code="campaign_template_unsupported_variables",
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

    rendered_html = Template(html_body).substitute(context)
    return EmailMessage(
        to=to,
        subject=Template(subject).substitute(context),
        html_body=sanitize_email_html(rendered_html),
        text_body=Template(text_body).substitute(context),
    )


class CommunicationsService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.repository = CommunicationsRepository(session) if session is not None else None

    async def upload_campaign_asset(
        self,
        *,
        settings: Settings,
        content: bytes,
        content_type: str | None,
        original_file_name: str | None,
        owner_id: UUID,
    ) -> CampaignAssetUploadResponse:
        repository = self._require_repository()
        session = self._require_session()
        stored_asset = store_campaign_asset(
            settings=settings,
            content=content,
            content_type=content_type,
            original_file_name=original_file_name,
            owner_id=owner_id,
        )
        try:
            await repository.add_campaign_asset(
                CampaignAsset(
                    owner_id=owner_id,
                    file_name=stored_asset.file_name,
                    public_url=stored_asset.url,
                    content_type=stored_asset.content_type,
                    size_bytes=stored_asset.size_bytes,
                    status="staged",
                )
            )
            await session.commit()
        except Exception:
            await session.rollback()
            delete_campaign_asset(
                settings=settings,
                file_name=stored_asset.file_name,
                owner_id=owner_id,
            )
            raise
        return CampaignAssetUploadResponse(
            url=stored_asset.url,
            file_name=stored_asset.file_name,
            content_type=stored_asset.content_type,
            size_bytes=stored_asset.size_bytes,
        )

    async def remove_campaign_asset(
        self,
        *,
        settings: Settings,
        file_name: str,
        owner_id: UUID,
    ) -> bool:
        repository = self._require_repository()
        session = self._require_session()
        asset = await repository.get_campaign_asset_by_file_name(
            file_name,
            owner_id=owner_id,
            for_update=True,
        )
        if asset is not None and asset.campaign_id is not None:
            raise DomainError(
                "Campaign asset is still attached to a campaign.",
                code="campaign_asset_attached",
            )
        deleted = delete_campaign_asset(
            settings=settings,
            file_name=file_name,
            owner_id=owner_id,
        )
        if asset is not None:
            await repository.delete_campaign_asset_record(asset)
            await session.commit()
        return deleted or asset is not None

    async def list_templates(
        self,
        *,
        active_only: bool = True,
        owner_id: UUID | None = None,
    ) -> list[EmailTemplateResponse]:
        repository = self._require_repository()
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
        version = await repository.get_latest_version(payload.key, owner_id=owner_id) + 1
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

        has_sends = await repository.has_sent_emails(
            key,
            template.version,
            owner_id=owner_id,
        )
        if has_sends or (owner_id is not None and template.owner_id is None):
            owner_latest_version = await repository.get_latest_version(
                key,
                owner_id=owner_id,
            )
            next_version = max(template.version, owner_latest_version) + 1
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
                        payload.audience if payload.audience is not None else template.audience
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
                    version=await repository.get_latest_version(key, owner_id=owner_id) + 1,
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

    def _require_session(self) -> AsyncSession:
        if self.session is None:
            raise RuntimeError("CommunicationsService requires a database session")
        return self.session

    async def bulk_create_campaign_recipients(
        self,
        payload: CampaignRecipientBulkCreateRequest,
        *,
        owner_id: UUID | None = None,
        settings: Settings | None = None,
    ) -> list[CampaignRecipient]:
        result = await self.bulk_create_campaign_recipients_with_result(
            payload,
            owner_id=owner_id,
            settings=settings,
        )
        return result.recipients

    async def bulk_create_campaign_recipients_with_result(
        self,
        payload: CampaignRecipientBulkCreateRequest,
        *,
        owner_id: UUID | None = None,
        settings: Settings | None = None,
    ) -> CampaignRecipientBulkCreateResult:
        repository = self._require_repository()
        delivery_owner_id = _require_delivery_owner_id(owner_id)

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
                        owner_id=delivery_owner_id,
                        email=None,
                        contact_name=req.contact_name,
                        organization_name=req.organization_name,
                        segment=CampaignRecipientSegment(req.segment),
                        source=req.source,
                        status=recipient_status,
                    )
                )
                continue
            status_provided_by_email[normalized_email] = req.status is not None
            recipients_by_email[normalized_email] = CampaignRecipient(
                owner_id=delivery_owner_id,
                email=normalized_email,
                contact_name=req.contact_name,
                organization_name=req.organization_name,
                segment=CampaignRecipientSegment(req.segment),
                source=req.source,
                status=recipient_status,
            )

        existing = await repository.list_campaign_recipients_by_emails(
            set(recipients_by_email),
            owner_id=delivery_owner_id,
            include_archived=True,
            for_update=True,
        )
        archived_emails = sorted(
            recipient.email
            for recipient in existing
            if recipient.archived_at is not None and recipient.email is not None
        )
        if archived_emails:
            raise DomainError(
                "Restore archived contacts before importing them again.",
                code="campaign_recipient_archived",
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
        active_email_fingerprints = {
            email_suppression_fingerprint(
                owner_id=delivery_owner_id,
                email=recipient.email,
                secret=(settings or Settings()).effective_email_suppression_fingerprint_secret,
            )
            for email, recipient in recipients_by_email.items()
            if recipient.status == CampaignRecipientStatus.active
            and recipient.email is not None
            and (
                email not in existing_by_email
                or status_provided_by_email.get(email, False)
            )
        }
        if active_email_fingerprints:
            suppressions = await repository.list_email_suppressions_by_fingerprints(
                owner_id=delivery_owner_id,
                email_fingerprints=active_email_fingerprints,
            )
            if suppressions:
                raise DomainError(
                    "A bounced or unsubscribed address cannot be reactivated.",
                    code="campaign_recipient_email_suppressed",
                )
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
            await repository.add_campaign_recipients(
                recipients_to_create,
                owner_id=delivery_owner_id,
            )
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
        settings: Settings | None = None,
    ) -> CampaignRecipient:
        repository = self._require_repository()
        recipient = await repository.get_campaign_recipient(
            recipient_id,
            owner_id=owner_id,
            for_update=True,
        )
        if recipient is None:
            raise DomainError("Campaign recipient not found.", code="campaign_recipient_not_found")

        if payload.email is not None:
            normalized_email = str(payload.email).lower()
            existing_email_recipient = await repository.get_campaign_recipient_by_email(
                normalized_email,
                owner_id=owner_id,
            )
            if existing_email_recipient is not None and existing_email_recipient.id != recipient.id:
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
            if (
                next_status == CampaignRecipientStatus.active
                and recipient.email is not None
                and await repository.get_email_suppression(
                    owner_id=_require_delivery_owner_id(owner_id),
                    email=recipient.email,
                    email_fingerprint=email_suppression_fingerprint(
                        owner_id=_require_delivery_owner_id(owner_id),
                        email=recipient.email,
                        secret=(
                            settings or Settings()
                        ).effective_email_suppression_fingerprint_secret,
                    ),
                )
            ):
                raise DomainError(
                    "A bounced or unsubscribed address cannot be reactivated.",
                    code="campaign_recipient_email_suppressed",
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
        settings: Settings | None = None,
    ) -> "CampaignRecipientArchiveResult":
        return await self.archive_campaign_recipient(
            recipient_id,
            owner_id=owner_id,
            settings=settings or Settings(),
        )

    async def archive_campaign_recipient(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID | None,
        settings: Settings,
    ) -> "CampaignRecipientArchiveResult":
        repository = self._require_repository()
        delivery_owner_id = _require_delivery_owner_id(owner_id)
        recipient = await repository.get_campaign_recipient(
            recipient_id,
            owner_id=delivery_owner_id,
            catalog_scope="any",
            for_update=True,
        )
        if recipient is None:
            raise DomainError("Campaign recipient not found.", code="campaign_recipient_not_found")
        now = datetime.now(UTC)
        if recipient.archived_at is None:
            recipient.status_before_archive = recipient.status
            if recipient.status == CampaignRecipientStatus.active:
                # The previous application image does not understand archived_at.
                # Keeping archived contacts non-sendable makes an image rollback safe.
                recipient.status = CampaignRecipientStatus.suppressed
            recipient.archived_at = now
            recipient.purge_after = now + timedelta(
                days=settings.campaign_recipient_archive_retention_days
            )
        memberships_removed = await repository.delete_campaign_recipient_memberships(
            recipient.id,
            owner_id=delivery_owner_id,
        )
        cancelled, in_flight = await repository.cancel_unsent_campaign_recipient_sends(
            recipient.id,
            owner_id=delivery_owner_id,
            now=now,
        )
        await repository.flush()
        return CampaignRecipientArchiveResult(
            recipient=recipient,
            memberships_removed=memberships_removed,
            cancelled=cancelled,
            in_flight=in_flight,
        )

    async def restore_campaign_recipient(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID | None,
        settings: Settings,
    ) -> CampaignRecipient:
        repository = self._require_repository()
        recipient = await repository.get_campaign_recipient(
            recipient_id,
            owner_id=owner_id,
            catalog_scope="archived",
            for_update=True,
        )
        if recipient is None:
            raise DomainError("Archived contact not found.", code="campaign_recipient_not_found")
        restored_status = recipient.status_before_archive or recipient.status
        if recipient.status == CampaignRecipientStatus.unsubscribed:
            restored_status = CampaignRecipientStatus.unsubscribed
        elif (
            restored_status == CampaignRecipientStatus.active
            and recipient.email is not None
        ):
            fingerprint = email_suppression_fingerprint(
                owner_id=recipient.owner_id,
                email=recipient.email,
                secret=settings.effective_email_suppression_fingerprint_secret,
            )
            if await repository.get_email_suppression(
                owner_id=recipient.owner_id,
                email_fingerprint=fingerprint,
                email=recipient.email,
            ):
                restored_status = CampaignRecipientStatus.suppressed
        recipient.status = restored_status
        recipient.archived_at = None
        recipient.purge_after = None
        recipient.status_before_archive = None
        await repository.flush()
        return recipient

    async def permanently_delete_campaign_recipient(
        self,
        recipient_id: UUID,
        *,
        owner_id: UUID | None,
        settings: Settings,
    ) -> "CampaignRecipientPurgeResult":
        repository = self._require_repository()
        if not settings.campaign_recipient_purge_enabled:
            raise DomainError(
                "Permanent deletion is temporarily unavailable while the privacy "
                "migration is being completed.",
                code="campaign_recipient_purge_disabled",
            )
        delivery_owner_id = _require_delivery_owner_id(owner_id)
        recipient = await repository.get_campaign_recipient(
            recipient_id,
            owner_id=delivery_owner_id,
            catalog_scope="archived",
            for_update=True,
        )
        if recipient is None:
            raise DomainError(
                "Permanent deletion is available only from Archive.",
                code="campaign_recipient_archive_required",
            )
        delete_time = datetime.now(UTC)
        reconciliation = await self._classify_campaign_recipient_unresolved_deliveries(
            recipient,
            owner_id=delivery_owner_id,
            settings=settings,
            now=delete_time,
        )
        if reconciliation.unsafe_unresolved:
            raise DomainError(
                "Some email deliveries have already reached the provider. "
                "Try permanent deletion again after their reconciliation window.",
                code="campaign_recipient_delivery_in_flight",
            )
        await self._create_campaign_contact_tombstones(
            recipient,
            settings=settings,
        )
        anonymized_sends = await repository.anonymize_campaign_recipient_history(
            recipient.id,
            owner_id=delivery_owner_id,
            allow_provider_unresolved=bool(reconciliation.provider_unresolved),
        )
        await repository.delete_campaign_recipient_record(recipient)
        return CampaignRecipientPurgeResult(
            recipient_id=recipient_id,
            cancelled=reconciliation.cancelled,
            anonymized_sends=anonymized_sends,
        )

    async def purge_due_campaign_recipients(
        self,
        *,
        settings: Settings,
        now: datetime | None = None,
        limit: int = 100,
    ) -> "CampaignRecipientPurgeBatchResult":
        repository = self._require_repository()
        if not settings.campaign_recipient_purge_enabled:
            return CampaignRecipientPurgeBatchResult(
                examined=0,
                purged=0,
                deferred=0,
            )
        purge_time = now or datetime.now(UTC)
        due_recipients = await repository.list_due_archived_campaign_recipients(
            now=purge_time,
            limit=limit,
        )
        purged = 0
        deferred = 0
        for recipient in due_recipients:
            reconciliation = (
                await self._classify_campaign_recipient_unresolved_deliveries(
                    recipient,
                    owner_id=recipient.owner_id,
                    settings=settings,
                    now=purge_time,
                )
            )
            if reconciliation.unsafe_unresolved:
                recipient.purge_after = purge_time + timedelta(days=1)
                deferred += 1
                continue
            await self._create_campaign_contact_tombstones(
                recipient,
                settings=settings,
            )
            await repository.anonymize_campaign_recipient_history(
                recipient.id,
                owner_id=recipient.owner_id,
                allow_provider_unresolved=bool(
                    reconciliation.provider_unresolved
                ),
            )
            await repository.delete_campaign_recipient_record(recipient)
            purged += 1
        return CampaignRecipientPurgeBatchResult(
            examined=len(due_recipients),
            purged=purged,
            deferred=deferred,
        )

    async def _classify_campaign_recipient_unresolved_deliveries(
        self,
        recipient: CampaignRecipient,
        *,
        owner_id: UUID,
        settings: Settings,
        now: datetime,
    ) -> CampaignRecipientDeliveryReconciliation:
        repository = self._require_repository()
        cancelled, _ = await repository.cancel_unsent_campaign_recipient_sends(
            recipient.id,
            owner_id=owner_id,
            now=now,
        )
        unresolved = await repository.list_unresolved_campaign_recipient_sends(
            recipient.id,
            owner_id=owner_id,
        )
        stale_before = now - timedelta(
            days=settings.campaign_recipient_delivery_reconciliation_days
        )
        provider_unresolved = [
            send
            for send in unresolved
            if send.status
            in {EmailSendStatus.accepted, EmailSendStatus.indeterminate}
        ]
        unsafe_unresolved = [
            send
            for send in unresolved
            if send.status
            in {EmailSendStatus.queued, EmailSendStatus.dispatching}
            or (
                (
                    send.last_event_at
                    or send.provider_request_started_at
                    or send.updated_at
                    or send.created_at
                )
                > stale_before
            )
        ]
        return CampaignRecipientDeliveryReconciliation(
            cancelled=cancelled,
            provider_unresolved=provider_unresolved,
            unsafe_unresolved=unsafe_unresolved,
        )

    async def _create_campaign_contact_tombstones(
        self,
        recipient: CampaignRecipient,
        *,
        settings: Settings,
    ) -> CampaignContactTombstone | None:
        if recipient.email is None:
            return None
        fingerprint = email_suppression_fingerprint(
            owner_id=recipient.owner_id,
            email=recipient.email,
            secret=settings.effective_email_suppression_fingerprint_secret,
        )
        repository = self._require_repository()
        sends = await repository.list_campaign_recipient_sends(
            recipient.id,
            owner_id=recipient.owner_id,
        )
        provider_event_ids = await repository.list_campaign_recipient_provider_event_ids(
            recipient.id,
            owner_id=recipient.owner_id,
        )
        suppression = await repository.get_email_suppression(
            owner_id=recipient.owner_id,
            email_fingerprint=fingerprint,
            email=recipient.email,
        )
        suppression_reason = (
            getattr(suppression, "reason", None)
            or getattr(suppression, "do_not_contact_reason", None)
        )
        status_before_archive = (
            recipient.status_before_archive
            if recipient.archived_at is not None
            and recipient.status_before_archive is not None
            else recipient.status
        )
        reason: str | None = None
        if (
            recipient.status == CampaignRecipientStatus.unsubscribed
            or status_before_archive == CampaignRecipientStatus.unsubscribed
        ):
            reason = CampaignRecipientStatus.unsubscribed.value
        elif suppression_reason is not None:
            reason = str(suppression_reason)
        elif status_before_archive == CampaignRecipientStatus.suppressed:
            reason = CampaignRecipientStatus.suppressed.value
        delivery_fingerprints = [
            (
                provider_message_fingerprint(
                    message_id=send.provider_message_id,
                    secret=settings.effective_email_suppression_fingerprint_secret,
                ),
                send.campaign_id,
            )
            for send in sends
            if send.provider_message_id
        ]
        provider_event_fingerprints = [
            (
                provider_message_fingerprint(
                    message_id=provider_message_id,
                    secret=settings.effective_email_suppression_fingerprint_secret,
                ),
                provider_event_fingerprint(
                    provider_event_id=provider_event_id,
                    secret=settings.effective_email_suppression_fingerprint_secret,
                ),
            )
            for provider_message_id, provider_event_id in provider_event_ids
        ]
        now = datetime.now(UTC)
        delivery_expires_at = now + timedelta(
            days=settings.campaign_delivery_tombstone_retention_days
        )
        review_after = now + timedelta(days=settings.email_suppression_review_days)
        if reason is None:
            review_after = max(review_after, delivery_expires_at)
        return await repository.create_campaign_contact_tombstones(
            owner_id=recipient.owner_id,
            email_fingerprint=fingerprint,
            former_recipient_id=recipient.id,
            do_not_contact_reason=reason,
            suppressed_at=now if reason is not None else None,
            review_after=review_after,
            delivery_fingerprints=delivery_fingerprints,
            delivery_expires_at=delivery_expires_at,
            provider_event_fingerprints=provider_event_fingerprints,
        )

    async def review_due_email_suppressions(
        self,
        *,
        settings: Settings,
        now: datetime | None = None,
        limit: int = 100,
    ) -> "EmailSuppressionReviewBatchResult":
        repository = self._require_repository()
        review_time = now or datetime.now(UTC)
        suppressions = await repository.list_due_email_suppressions(
            now=review_time,
            limit=limit,
        )
        delivery_tombstones = (
            await repository.list_due_campaign_delivery_tombstones(
                now=review_time,
                limit=max(0, limit - len(suppressions)),
            )
            if hasattr(repository, "list_due_campaign_delivery_tombstones")
            and len(suppressions) < limit
            else []
        )
        tombstones = (
            await repository.list_due_campaign_contact_tombstones(
                now=review_time,
                limit=max(
                    0,
                    limit - len(suppressions) - len(delivery_tombstones),
                ),
            )
            if hasattr(repository, "list_due_campaign_contact_tombstones")
            and len(suppressions) + len(delivery_tombstones) < limit
            else []
        )
        retained = 0
        needs_review = 0
        deleted = 0
        protected_reasons = {
            "blocked",
            "complained",
            "hard_bounce",
            "invalid_email",
            "spam",
            "suppressed",
            "unsubscribed",
        }
        for suppression in suppressions:
            retain = suppression.reason in protected_reasons
            next_review_at = review_time + timedelta(
                days=(
                    settings.email_suppression_review_days
                    if retain
                    else 30
                )
            )
            await repository.add_email_suppression_review(
                EmailSuppressionReview(
                    owner_id=suppression.owner_id,
                    suppression_id=suppression.id,
                    reason=suppression.reason,
                    decision="retained" if retain else "needs_review",
                    reviewer="system-policy",
                    basis=(
                        "Prevent repeat delivery after a permanent provider rejection "
                        "or explicit do-not-contact request."
                        if retain
                        else "Unknown restriction reason requires an authorized "
                        "human decision before deletion."
                    ),
                    reviewed_at=review_time,
                    next_review_at=next_review_at,
                )
            )
            suppression.last_reviewed_at = review_time
            suppression.review_after = next_review_at
            if retain:
                retained += 1
            else:
                needs_review += 1
        for delivery_tombstone in delivery_tombstones:
            await repository.delete_campaign_delivery_tombstone(delivery_tombstone)
            deleted += 1
        for tombstone in tombstones:
            reason = tombstone.do_not_contact_reason
            retain = reason in protected_reasons
            mapping_expired = reason is None
            next_review_at = (
                review_time
                + timedelta(
                    days=(
                        settings.email_suppression_review_days
                        if retain
                        else 30
                    )
                )
                if not mapping_expired
                else None
            )
            await repository.add_email_suppression_review(
                EmailSuppressionReview(
                    owner_id=tombstone.owner_id,
                    suppression_id=None,
                    tombstone_id=tombstone.id,
                    reason=reason or "token_provider_mapping",
                    decision=(
                        "mapping_expired"
                        if mapping_expired
                        else ("retained" if retain else "needs_review")
                    ),
                    reviewer="system-policy",
                    basis=(
                        "The defined late-event and unsubscribe-link mapping window ended."
                        if mapping_expired
                        else (
                            "Prevent repeat delivery after a permanent provider rejection "
                            "or explicit do-not-contact request."
                            if retain
                            else "Unknown restriction reason requires an authorized "
                            "human decision before deletion."
                        )
                    ),
                    reviewed_at=review_time,
                    next_review_at=next_review_at,
                )
            )
            if mapping_expired:
                await repository.delete_campaign_contact_tombstone(tombstone)
                deleted += 1
            else:
                tombstone.last_reviewed_at = review_time
                tombstone.review_after = next_review_at or tombstone.review_after
                if retain:
                    retained += 1
                else:
                    needs_review += 1
        return EmailSuppressionReviewBatchResult(
            examined=(
                len(suppressions)
                + len(delivery_tombstones)
                + len(tombstones)
            ),
            retained=retained,
            needs_review=needs_review,
            deleted=deleted,
        )

    async def create_campaign(
        self,
        payload: CampaignCreateRequest,
        *,
        owner_id: UUID | None = None,
        settings: Settings | None = None,
    ) -> Campaign:
        repository = self._require_repository()
        validate_campaign_placeholders(
            payload.subject,
            payload.html_body,
            payload.text_body,
        )

        campaign = Campaign(
            owner_id=owner_id,
            name=payload.name,
            segment=(
                CampaignRecipientSegment(payload.segment) if payload.segment is not None else None
            ),
            status=(
                CampaignStatus.draft
                if payload.video_url and not payload.thumbnail_url
                else CampaignStatus.ready
            ),
            subject=payload.subject,
            html_body=payload.html_body,
            text_body=payload.text_body,
            video_url=payload.video_url,
            thumbnail_url=payload.thumbnail_url,
            landing_page_url=payload.landing_page_url,
        )
        campaign = await repository.add_campaign(campaign)
        if _is_managed_campaign_asset_url(campaign.thumbnail_url, settings):
            await _bind_campaign_asset(
                repository,
                campaign,
                previous_url=None,
                next_url=campaign.thumbnail_url,
                owner_id=_require_delivery_owner_id(owner_id),
                settings=settings,
            )
        return campaign

    async def update_campaign(
        self,
        campaign_id: UUID,
        payload: CampaignUpdateRequest,
        *,
        owner_id: UUID | None = None,
        settings: Settings | None = None,
    ) -> Campaign:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")

        provided_fields = payload.model_fields_set
        previous_thumbnail_url = campaign.thumbnail_url
        updated_subject = (
            payload.subject
            if "subject" in provided_fields and payload.subject is not None
            else campaign.subject
        )
        updated_html_body = (
            payload.html_body
            if "html_body" in provided_fields and payload.html_body is not None
            else campaign.html_body
        )
        updated_text_body = (
            payload.text_body
            if "text_body" in provided_fields and payload.text_body is not None
            else campaign.text_body
        )
        validate_campaign_placeholders(
            updated_subject,
            updated_html_body,
            updated_text_body,
        )

        if "name" in provided_fields and payload.name is not None:
            campaign.name = payload.name.strip()
        if "segment" in provided_fields:
            campaign.segment = (
                CampaignRecipientSegment(payload.segment) if payload.segment is not None else None
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

        asset_reference_changed = previous_thumbnail_url != campaign.thumbnail_url and (
            _is_managed_campaign_asset_url(previous_thumbnail_url, settings)
            or _is_managed_campaign_asset_url(campaign.thumbnail_url, settings)
        )
        if asset_reference_changed:
            await _bind_campaign_asset(
                repository,
                campaign,
                previous_url=previous_thumbnail_url,
                next_url=campaign.thumbnail_url,
                owner_id=_require_delivery_owner_id(owner_id or campaign.owner_id),
                settings=settings,
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
        if hasattr(repository, "cancel_queued_campaign_sends"):
            await repository.cancel_queued_campaign_sends(campaign.id, now=datetime.now(UTC))
        if owner_id is not None and hasattr(repository, "list_campaign_assets_for_campaign"):
            for asset in await repository.list_campaign_assets_for_campaign(
                campaign.id,
                owner_id=owner_id,
            ):
                asset.campaign_id = None
                asset.status = "staged"
        await repository.delete_campaign(campaign)

    async def cancel_campaign_delivery(
        self,
        campaign_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> int:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")
        return await repository.cancel_queued_campaign_sends(
            campaign.id,
            now=datetime.now(UTC),
        )

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
        delivery_by_recipient_id = await _campaign_delivery_by_recipient_id(
            repository,
            campaign.id,
            recipients,
            owner_id=owner_id,
        )
        return [
            _campaign_recipient_membership_row(
                recipient,
                campaign_delivery=delivery_by_recipient_id.get(recipient.id, "not_sent"),
            )
            for recipient in recipients
        ]

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
        recipients = await repository.lock_campaign_recipients_for_send(
            recipient_ids,
            owner_id=owner_id,
        )
        recipients_by_id = {recipient.id: recipient for recipient in recipients}
        missing_ids = [
            recipient_id for recipient_id in recipient_ids if recipient_id not in recipients_by_id
        ]
        if missing_ids:
            raise DomainError(
                "Campaign recipient membership includes unknown contacts.",
                code="campaign_membership_recipient_not_found",
            )
        await repository.replace_campaign_memberships(
            campaign.id,
            recipient_ids,
            source="manual",
            owner_id=owner_id,
        )
        campaign.recipient_memberships_initialized = True
        ordered_recipients = [recipients_by_id[recipient_id] for recipient_id in recipient_ids]
        delivery_by_recipient_id = await _campaign_delivery_by_recipient_id(
            repository,
            campaign.id,
            ordered_recipients,
            owner_id=owner_id,
        )
        return [
            _campaign_recipient_membership_row(
                recipient,
                campaign_delivery=delivery_by_recipient_id.get(recipient.id, "not_sent"),
            )
            for recipient in ordered_recipients
        ]

    async def send_campaign(
        self,
        campaign_id: UUID,
        payload: CampaignSendRequest,
        *,
        provider: EmailProvider | None = None,
        settings: Settings,
        owner_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> CampaignSendResponse:
        repository = self._require_repository()
        campaign = await repository.get_campaign(campaign_id, owner_id=owner_id)
        if campaign is None:
            raise DomainError("Campaign not found.", code="campaign_not_found")
        delivery_owner_id = _require_delivery_owner_id(owner_id or campaign.owner_id)
        if campaign.owner_id != delivery_owner_id:
            raise DomainError("Campaign not found.", code="campaign_not_found")
        if campaign.video_url and not campaign.thumbnail_url:
            raise DomainError(
                "Add a thumbnail before sending this video campaign.",
                code="campaign_video_assets_incomplete",
            )
        if campaign.status not in {CampaignStatus.ready, CampaignStatus.completed}:
            raise DomainError(
                "Campaign must be ready before sending.",
                code="campaign_not_ready",
            )

        recipients = await self._campaign_send_recipients(
            campaign,
            payload,
            owner_id=delivery_owner_id,
        )
        if not recipients:
            raise DomainError("Campaign has no matching recipients.", code="campaign_no_recipients")
        if hasattr(repository, "lock_campaign_recipients_for_send"):
            locked_recipients = await repository.lock_campaign_recipients_for_send(
                [recipient.id for recipient in recipients],
                owner_id=delivery_owner_id,
            )
            locked_by_id = {recipient.id: recipient for recipient in locked_recipients}
            if payload.mode == "selected" and len(locked_by_id) != len(recipients):
                raise DomainError(
                    "Campaign recipient not found.",
                    code="campaign_recipient_not_found",
                )
            recipients = [
                locked_by_id[recipient.id]
                for recipient in recipients
                if recipient.id in locked_by_id
            ]
            if not recipients:
                raise DomainError(
                    "Campaign has no matching recipients.",
                    code="campaign_no_recipients",
                )

        results: list[CampaignSendRecipientResult] = []
        remaining_sends = await _remaining_email_sends_today(repository, settings)
        for recipient in recipients:
            _require_campaign_delivery_ownership(
                campaign,
                recipient,
                owner_id=delivery_owner_id,
            )
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

            suppression = await repository.get_email_suppression(
                owner_id=delivery_owner_id,
                email=recipient.email,
                email_fingerprint=email_suppression_fingerprint(
                    owner_id=delivery_owner_id,
                    email=recipient.email,
                    secret=settings.effective_email_suppression_fingerprint_secret,
                ),
            )
            if suppression is not None:
                results.append(
                    CampaignSendRecipientResult(
                        recipient_id=recipient.id,
                        email=recipient.email,
                        status="skipped",
                        error="Recipient is protected by the do-not-contact list.",
                    )
                )
                continue

            unsubscribe_url = _campaign_unsubscribe_url(
                recipient,
                settings,
                owner_id=delivery_owner_id,
            )
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

            message_payload = _email_outbox_payload(
                message,
                default_from_address=settings.email_from_address,
            )
            payload_fingerprint = _campaign_delivery_payload_fingerprint(
                campaign,
                recipient,
                settings,
            )
            delivery_key = _email_send_idempotency_key(
                idempotency_key or payload_fingerprint,
                f"campaign:{campaign.id}:{recipient.id}",
            )
            existing_send = await repository.get_email_send_by_idempotency_key(delivery_key)
            if existing_send is not None:
                _require_email_send_ownership(existing_send, owner_id=delivery_owner_id)
                _require_matching_email_send_payload(existing_send, payload_fingerprint)
                results.append(_campaign_result_from_existing_send(existing_send, recipient))
                continue

            if remaining_sends <= 0:
                results.append(
                    CampaignSendRecipientResult(
                        recipient_id=recipient.id,
                        email=recipient.email or "",
                        status="skipped",
                        error="Daily email send cap reached.",
                    )
                )
                continue

            now = datetime.now(UTC)
            candidate = EmailSend(
                owner_id=delivery_owner_id,
                assignment_id=None,
                campaign_id=campaign.id,
                campaign_recipient_id=recipient.id,
                recipient_email=recipient.email,
                template_key="campaign",
                template_version=1,
                provider=str(getattr(provider, "key", settings.email_provider)),
                provider_message_id=None,
                idempotency_key=delivery_key,
                payload_fingerprint=payload_fingerprint,
                message_payload=message_payload,
                attempt_count=0,
                max_attempts=EMAIL_OUTBOX_MAX_ATTEMPTS,
                next_attempt_at=now,
                lease_token=None,
                lease_expires_at=None,
                status=EmailSendStatus.queued,
                last_event_at=now,
            )
            email_send, created = await _enqueue_email_send(repository, candidate)
            _require_email_send_ownership(email_send, owner_id=delivery_owner_id)
            _require_matching_email_send_payload(email_send, payload_fingerprint)
            if not created:
                results.append(_campaign_result_from_existing_send(email_send, recipient))
                continue
            results.append(
                CampaignSendRecipientResult(
                    recipient_id=recipient.id,
                    email=recipient.email,
                    status="queued",
                )
            )
            remaining_sends -= 1

        return CampaignSendResponse(
            campaign_id=campaign.id,
            total=len(results),
            queued=sum(1 for result in results if result.status == "queued"),
            sent=sum(1 for result in results if result.status == "accepted"),
            failed=sum(1 for result in results if result.status == "failed"),
            skipped=sum(
                1 for result in results if result.status in {"skipped", "dry_run", "cancelled"}
            ),
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
    ) -> CampaignUnsubscribeTarget:
        target = await self.get_campaign_unsubscribe_recipient(
            token,
            settings,
            for_update=True,
        )
        repository = self._require_repository()
        if target.recipient is not None:
            target.recipient.status = CampaignRecipientStatus.unsubscribed
            if target.recipient.archived_at is not None:
                target.recipient.status_before_archive = (
                    CampaignRecipientStatus.unsubscribed
                )
        if target.recipient is not None and target.recipient.email is not None:
            await repository.suppress_email(
                owner_id=target.recipient.owner_id,
                email=target.recipient.email,
                email_fingerprint=email_suppression_fingerprint(
                    owner_id=target.recipient.owner_id,
                    email=target.recipient.email,
                    secret=settings.effective_email_suppression_fingerprint_secret,
                ),
                reason="unsubscribed",
                source_email_send_id=None,
                review_after=datetime.now(UTC)
                + timedelta(days=settings.email_suppression_review_days),
            )
        elif target.tombstone is not None:
            target.tombstone.do_not_contact_reason = "unsubscribed"
            target.tombstone.suppressed_at = datetime.now(UTC)
            target.tombstone.review_after = datetime.now(UTC) + timedelta(
                days=settings.email_suppression_review_days
            )
        await repository.flush()
        return target

    async def get_campaign_unsubscribe_recipient(
        self,
        token: str,
        settings: Settings,
        *,
        for_update: bool = False,
    ) -> CampaignUnsubscribeTarget:
        repository = self._require_repository()
        claims = parse_campaign_recipient_action_token(token, settings)
        if claims.action != "unsubscribe":
            raise DomainError(
                "Invalid campaign recipient action link.",
                code="campaign_recipient_action_invalid",
            )
        recipient = await repository.get_campaign_recipient(
            claims.recipient_id,
            owner_id=claims.owner_id,
            catalog_scope="any",
            for_update=for_update,
        )
        if recipient is not None:
            return CampaignUnsubscribeTarget(recipient=recipient)
        tombstone = await repository.get_campaign_contact_tombstone(
            owner_id=claims.owner_id,
            former_recipient_id=claims.recipient_id,
            for_update=for_update,
        )
        if tombstone is None:
            raise DomainError("Campaign recipient not found.", code="campaign_recipient_not_found")
        return CampaignUnsubscribeTarget(tombstone=tombstone)

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
            recipients = await repository.list_campaign_recipients_by_ids(
                payload.recipient_ids,
                owner_id=owner_id,
            )
            if {recipient.id for recipient in recipients} != set(payload.recipient_ids):
                raise DomainError(
                    "Campaign recipient not found.",
                    code="campaign_recipient_not_found",
                )
            return recipients
        await self._ensure_default_campaign_memberships(campaign, owner_id=owner_id)
        matching = await repository.list_campaign_member_recipients(
            campaign.id,
            owner_id=owner_id,
        )
        if payload.mode == "all":
            return matching
        if not hasattr(repository, "list_accepted_campaign_recipient_ids"):
            return matching
        sent_recipient_ids = await repository.list_accepted_campaign_recipient_ids(
            campaign.id,
            owner_id=owner_id,
        )
        return [recipient for recipient in matching if recipient.id not in sent_recipient_ids]

    async def record_campaign_recipient_event(
        self,
        recipient_id: UUID,
        payload: CampaignRecipientEventCreateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> CampaignRecipientEventResponse:
        repository = self._require_repository()
        recipient = await repository.get_campaign_recipient(
            recipient_id,
            owner_id=owner_id,
            catalog_scope="any",
            for_update=True,
        )
        if recipient is None:
            raise DomainError("Campaign recipient not found.", code="campaign_recipient_not_found")

        campaign_id = _event_campaign_id(payload.variant_key)
        if (
            campaign_id is not None
            and await repository.get_campaign(campaign_id, owner_id=owner_id) is None
        ):
            raise DomainError("Campaign not found.", code="campaign_not_found")
        event = await repository.add_campaign_recipient_event(
            CampaignRecipientEvent(
                id=uuid.uuid4(),
                owner_id=_require_delivery_owner_id(owner_id),
                campaign_id=campaign_id,
                recipient_id=recipient.id,
                event_type=payload.event_type,
                variant_key=payload.variant_key,
                occurred_at=payload.occurred_at or datetime.now(UTC),
            ),
            owner_id=owner_id,
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
            owner_id=claims.owner_id,
        )
        return claims.target_url

    async def get_email_ops_summary(
        self,
        *,
        owner_id: UUID | None = None,
        catalog_scope: Literal["active", "archived"] = "active",
    ) -> dict:
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
        profiles_stmt = select(ParticipantProfile, Company.name).join(
            Company, ParticipantProfile.company_id == Company.id
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
        ranked_sends_statement = select(
            EmailSend.recipient_email.label("recipient_email"),
            EmailSend.status.label("status"),
            func.row_number()
            .over(
                partition_by=(EmailSend.owner_id, func.lower(EmailSend.recipient_email)),
                order_by=EmailSend.created_at.desc(),
            )
            .label("row_number"),
        ).where(EmailSend.assignment_id.is_not(None))
        if owner_id is not None:
            ranked_sends_statement = ranked_sends_statement.where(
                EmailSend.owner_id == owner_id
            )
        ranked_sends = ranked_sends_statement.subquery()
        latest_sends_result = await session.execute(
            select(ranked_sends.c.recipient_email, ranked_sends.c.status).where(
                ranked_sends.c.row_number == 1
            )
        )
        latest_send_status_by_email = {
            recipient_email: send_status
            for recipient_email, send_status in latest_sends_result.all()
        }

        campaign_recipients = await repository.list_campaign_recipients(
            owner_id=owner_id,
            catalog_scope=catalog_scope,
        )
        retained_aggregates = await repository.list_campaign_contact_aggregates(
            owner_id=_require_delivery_owner_id(owner_id),
        )
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
            completed_tasks = sum(
                1
                for a in p_assignments
                if a.status
                in {
                    AssignmentStatus.submitted,
                    AssignmentStatus.validated,
                    AssignmentStatus.scored,
                }
            )
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

            has_entered = profile.user_id is not None or any(
                a.status
                in {
                    AssignmentStatus.started,
                    AssignmentStatus.submitted,
                    AssignmentStatus.validated,
                    AssignmentStatus.scored,
                }
                for a in p_assignments
            )
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

            rows.append(
                {
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
                }
            )

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
            ("Membrii fara cont primesc link securizat per proiect, valabil pana la deadline."),
            (
                "Reminderul se trimite pentru status invitat sau inceput, "
                "nu pentru sarcini finalizate."
            ),
            ("Emailurile nu includ raspunsuri confidentiale, doar linkuri si status operational."),
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
                "source": recipient.source,
                "emailVariant": campaign_variant_by_recipient.get(recipient.id),
                "outcome": None,
                "archivedAt": recipient.archived_at,
                "purgeAfter": recipient.purge_after,
            }
            for recipient in campaign_recipients
        ]

        campaign = {
            "videoHost": {
                "provider": "Vimeo sau pagină Cody",
                "status": "ready",
                "note": (
                    "Emailul trimite thumbnail și CTA către linkul video. "
                    "Pagina Cody este opțională când vrei tracking sau CTA-uri dedicate."
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
            "retainedAggregates": [
                {
                    "campaignId": aggregate.campaign_id,
                    "metric": aggregate.metric,
                    "count": aggregate.count,
                }
                for aggregate in retained_aggregates
            ],
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
    *,
    campaign_delivery: str = "not_sent",
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
        source=recipient.source,
        emailVariant=None,
        outcome=None,
        membershipSource=None,
        campaignDelivery=campaign_delivery,
    )


async def _campaign_delivery_by_recipient_id(
    repository: object,
    campaign_id: UUID,
    recipients: list[CampaignRecipient],
    *,
    owner_id: UUID | None,
) -> dict[UUID, str]:
    if not recipients or not hasattr(repository, "list_campaign_delivery_status_by_recipient_ids"):
        return {}
    recipient_ids = [recipient.id for recipient in recipients]
    return await repository.list_campaign_delivery_status_by_recipient_ids(
        campaign_id,
        recipient_ids,
        owner_id=owner_id,
    )


def _campaign_recipient_status(recipient: CampaignRecipient) -> str:
    if recipient.archived_at is not None:
        return "archived"
    if recipient.status == CampaignRecipientStatus.unsubscribed:
        return "unsubscribed"
    if recipient.status == CampaignRecipientStatus.suppressed:
        return "suppressed"
    if not recipient.contact_name:
        return "needs_contact_name"
    return "ready"


def _event_campaign_id(variant_key: str | None) -> UUID | None:
    if variant_key is None:
        return None
    try:
        return UUID(variant_key)
    except ValueError:
        return None


def _campaign_unsubscribe_url(
    recipient: CampaignRecipient,
    settings: Settings,
    *,
    owner_id: UUID,
) -> str:
    token = create_campaign_recipient_action_token(
        CampaignRecipientActionClaims(
            recipient_id=recipient.id,
            owner_id=owner_id,
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
        "legal_address": settings.email_legal_address,
    }

    subject = _render_campaign_template(campaign.subject, context)
    html_body = _render_campaign_template(campaign.html_body, context)
    text_body = _render_campaign_template(campaign.text_body, context)
    if campaign.video_url and campaign.thumbnail_url:
        html_body = _ensure_campaign_video_block(html_body, campaign)
    if not campaign.video_url and not campaign.thumbnail_url:
        html_body = _remove_empty_campaign_video_blocks(html_body)
        text_body = _remove_empty_campaign_video_lines(text_body)
    html_body = _remove_redundant_campaign_rich_action_links(
        html_body,
        campaign,
        calendly_tracking_url,
    )
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
    html_body = _ensure_campaign_html_unsubscribe(html_body, unsubscribe_url)
    html_body = sanitize_email_html(html_body)
    html_body = _append_campaign_open_pixel(html_body, campaign, recipient, settings)
    if not _campaign_text_has_calendly_link(text_body, calendly_tracking_url):
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
_CAMPAIGN_TEXT_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_CAMPAIGN_BODY_CLOSE_RE = re.compile(r"</body\s*>", re.IGNORECASE)
_CAMPAIGN_PARAGRAPH_RE = re.compile(r"<p\b[^>]*>.*?</p>", re.IGNORECASE | re.DOTALL)
_CAMPAIGN_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _remove_empty_campaign_video_blocks(html_body: str) -> str:
    return _EMPTY_CAMPAIGN_VIDEO_BLOCK_RE.sub("", html_body)


def _remove_empty_campaign_video_lines(text_body: str) -> str:
    return _EMPTY_CAMPAIGN_VIDEO_LINE_RE.sub("", text_body)


def _remove_redundant_campaign_rich_action_links(
    html_body: str,
    campaign: Campaign,
    calendly_tracking_url: str,
) -> str:
    video_targets = {
        target
        for target in (campaign.video_url, campaign.landing_page_url or campaign.video_url)
        if target and campaign.thumbnail_url
    }
    redundant_paragraphs = {
        f"{label}: {target}"
        for label, targets in (
            ("Link platformă", video_targets | {calendly_tracking_url}),
            ("Material video", video_targets),
            ("Video", video_targets),
            ("Alege un slot", {calendly_tracking_url}),
            ("Alege un slot în Calendly", {calendly_tracking_url}),
        )
        for target in targets
    }

    def remove_redundant_paragraph(match: re.Match[str]) -> str:
        visible_text = html_unescape(
            _CAMPAIGN_HTML_TAG_RE.sub("", match.group(0))
        )
        normalized_text = " ".join(visible_text.split())
        if normalized_text in redundant_paragraphs:
            return ""
        return match.group(0)

    return _CAMPAIGN_PARAGRAPH_RE.sub(remove_redundant_paragraph, html_body)


def _campaign_message_has_calendly_link(body: str, calendly_tracking_url: str) -> bool:
    for match in _CAMPAIGN_HREF_RE.finditer(body):
        href = html_unescape(match.group(2)).strip()
        if href == calendly_tracking_url or _is_calendly_target(href):
            return True
    return False


def _campaign_text_has_calendly_link(body: str, calendly_tracking_url: str) -> bool:
    if calendly_tracking_url and calendly_tracking_url in body:
        return True
    return any(
        _is_calendly_target(match.group(0).rstrip(".,;:!?)]}"))
        for match in _CAMPAIGN_TEXT_URL_RE.finditer(body)
    )


def _ensure_campaign_video_block(html_body: str, campaign: Campaign) -> str:
    if not campaign.video_url or not campaign.thumbnail_url:
        return html_body

    escaped_thumbnail_url = html_escape(campaign.thumbnail_url, quote=True)
    if (
        f'src="{escaped_thumbnail_url}"' in html_body
        or f"src='{escaped_thumbnail_url}'" in html_body
    ):
        return html_body

    target_url = html_escape(
        campaign.landing_page_url or campaign.video_url,
        quote=True,
    )
    video_block = (
        '<p style="margin:24px 0;">'
        f'<a href="{target_url}" style="display:block;text-decoration:none;color:inherit;">'
        '<span style="display:block;max-width:420px;border-radius:14px;'
        'overflow:hidden;background:#2b211f;">'
        f'<img src="{escaped_thumbnail_url}" alt="Previzualizare video" '
        'style="display:block;width:100%;max-width:420px;height:auto;'
        'border:0;border-radius:14px;" />'
        "</span></a></p>"
    )
    footer_marker = (
        '</div><div style="margin-top:24px;padding-top:24px;'
        'border-top:1px solid #eadfdb;'
    )
    if footer_marker in html_body:
        return html_body.replace(footer_marker, video_block + footer_marker, 1)
    shell_close = "</div></div>"
    stripped = html_body.rstrip()
    if stripped.endswith(shell_close):
        return stripped[: -len(shell_close)] + video_block + shell_close
    return html_body + video_block


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


def _ensure_campaign_html_unsubscribe(html_body: str, unsubscribe_url: str) -> str:
    escaped_url = html_escape(unsubscribe_url, quote=True)
    standard_footer_present = "Ai primit acest email deoarece" in html_body and (
        f'href="{escaped_url}"' in html_body or f"href='{escaped_url}'" in html_body
    )
    if standard_footer_present:
        return html_body

    footer = (
        '<p style="margin:24px 0 0;font-size:12px;line-height:1.5;text-align:center;">'
        f'<a href="{escaped_url}" data-codrut-cta="unsubscribe" '
        'style="color:#6d5f5b;text-decoration:underline;">Dezabonare</a></p>'
    )
    body_close = _CAMPAIGN_BODY_CLOSE_RE.search(html_body)
    if body_close is None:
        return html_body + footer
    return html_body[: body_close.start()] + footer + html_body[body_close.start() :]


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
    owner_id = _require_delivery_owner_id(campaign.owner_id)
    token = create_campaign_tracking_token(
        CampaignTrackingClaims(
            recipient_id=recipient.id,
            owner_id=owner_id,
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
    def __init__(
        self,
        provider: EmailProvider,
        session: AsyncSession | None = None,
        *,
        owner_id: UUID | None = None,
    ) -> None:
        self.provider = provider
        self.session = session
        self.owner_id = owner_id
        self._template_cache: dict[tuple[UUID, str], EmailTemplate | None] = {}

    async def send_assignment_invitation(
        self,
        assignment: QuestionnaireAssignment,
        respondent: ParticipantProfile,
        context: AssignmentInvitationContext,
        *,
        idempotency_key: str | None = None,
        assignment_ids: list[UUID] | None = None,
        reminder_assignment_ids: list[UUID] | None = None,
    ) -> EmailSendResult:
        if self.session is None:
            raise RuntimeError("Durable invitation delivery requires a database session")
        owner_id = _require_delivery_owner_id(self.owner_id)
        is_reminder = bool(reminder_assignment_ids)
        template_key = _select_invitation_template(respondent, reminder=is_reminder)

        version = 1
        db_template = None
        if self.session is not None:
            cache_key = (owner_id, template_key.value)
            if cache_key not in self._template_cache:
                repository = CommunicationsRepository(self.session)
                self._template_cache[cache_key] = await repository.get_template(
                    template_key.value,
                    owner_id=owner_id,
                )
            db_template = self._template_cache[cache_key]
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

        related_assignment_ids = assignment_ids or [assignment.id]
        message_payload = _email_outbox_payload(
            message,
            assignment_ids=related_assignment_ids,
            reminder_assignment_ids=reminder_assignment_ids,
            delivery_kind="reminder" if is_reminder else "invitation",
            default_from_address=getattr(
                getattr(self.provider, "from_address", None),
                "value",
                None,
            ),
        )
        payload_fingerprint = _email_outbox_payload_fingerprint(message_payload)
        automatic_key = (
            f"{payload_fingerprint}:reminder:{datetime.now(UTC).date().isoformat()}"
            if is_reminder
            else payload_fingerprint
        )
        stable_key = _email_send_idempotency_key(
            idempotency_key or automatic_key,
            f"assignment:{assignment.id}:{respondent.id}",
        )
        now = datetime.now(UTC)
        repository = CommunicationsRepository(self.session)
        email_send, _created = await _enqueue_email_send(
            repository,
            EmailSend(
                owner_id=owner_id,
                assignment_id=assignment.id,
                recipient_email=respondent.email,
                template_key=template_key.value,
                template_version=version,
                provider=str(getattr(self.provider, "key", "unknown")),
                provider_message_id=None,
                idempotency_key=stable_key,
                payload_fingerprint=payload_fingerprint,
                message_payload=message_payload,
                attempt_count=0,
                max_attempts=EMAIL_OUTBOX_MAX_ATTEMPTS,
                next_attempt_at=now,
                lease_token=None,
                lease_expires_at=None,
                status=EmailSendStatus.queued,
                last_event_at=now,
            ),
        )
        _require_matching_email_send_payload(email_send, payload_fingerprint)
        return _email_result_from_existing_send(email_send, respondent.email)

    async def enqueue_transactional_message(
        self,
        message: EmailMessage,
        *,
        template_key: str,
        template_version: int,
        idempotency_key: str,
        delivery_kind: str,
    ) -> EmailSendResult:
        if self.session is None:
            raise RuntimeError("Durable transactional delivery requires a database session")
        owner_id = _require_delivery_owner_id(self.owner_id)
        message_payload = _email_outbox_payload(
            message,
            delivery_kind=delivery_kind,
            default_from_address=getattr(
                getattr(self.provider, "from_address", None),
                "value",
                None,
            ),
        )
        payload_fingerprint = _email_outbox_payload_fingerprint(message_payload)
        stable_key = _email_send_idempotency_key(idempotency_key, f"owner:{owner_id}")
        now = datetime.now(UTC)
        email_send, _created = await _enqueue_email_send(
            CommunicationsRepository(self.session),
            EmailSend(
                owner_id=owner_id,
                recipient_email=message.to.value,
                template_key=template_key,
                template_version=template_version,
                provider=str(getattr(self.provider, "key", "unknown")),
                idempotency_key=stable_key,
                payload_fingerprint=payload_fingerprint,
                message_payload=message_payload,
                attempt_count=0,
                max_attempts=EMAIL_OUTBOX_MAX_ATTEMPTS,
                next_attempt_at=now,
                status=EmailSendStatus.queued,
                last_event_at=now,
            ),
        )
        _require_matching_email_send_payload(email_send, payload_fingerprint)
        return _email_result_from_existing_send(email_send, message.to.value)


@dataclass(frozen=True)
class EmailOutboxBatchResult:
    claimed: int = 0
    accepted: int = 0
    retried: int = 0
    failed: int = 0
    cancelled: int = 0
    indeterminate: int = 0


class EmailOutboxProcessor:
    def __init__(
        self,
        session: AsyncSession,
        provider: EmailProvider,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.provider = provider
        self.settings = settings or Settings()
        self.repository = CommunicationsRepository(session)

    async def process_due(self, *, limit: int = 10) -> EmailOutboxBatchResult:
        now = datetime.now(UTC)
        indeterminate_sends = await self.repository.mark_stale_provider_requests_indeterminate(
            now=now
        )
        exhausted = await self.repository.fail_exhausted_stale_email_sends(now=now)
        for campaign_id in {send.campaign_id for send in exhausted if send.campaign_id is not None}:
            await self._complete_campaign_if_idle(campaign_id)
        claimed = await self.repository.claim_due_email_sends(
            now=now,
            lease_duration=EMAIL_OUTBOX_LEASE_DURATION,
            limit=limit,
        )
        await self.session.commit()

        accepted = 0
        retried = 0
        failed = len(exhausted)
        cancelled = 0
        indeterminate = len(indeterminate_sends)
        for send in claimed:
            outcome = await self._process_claimed(send)
            accepted += outcome == "accepted"
            retried += outcome == "retried"
            failed += outcome == "failed"
            cancelled += outcome == "cancelled"
            indeterminate += outcome == "indeterminate"
        return EmailOutboxBatchResult(
            claimed=len(claimed),
            accepted=accepted,
            retried=retried,
            failed=failed,
            cancelled=cancelled,
            indeterminate=indeterminate,
        )

    async def _process_claimed(self, send: EmailSend) -> str:
        send_id = send.id
        lease_token = send.lease_token
        if lease_token is None:
            return "failed"

        if (
            send.campaign_recipient_id is not None
            and (
                send.owner_id is None
                or not await self.repository.campaign_recipient_is_active(
                    send.campaign_recipient_id,
                    owner_id=send.owner_id,
                )
            )
        ):
            current = await self.repository.get_claimed_email_send(send.id, lease_token)
            if current is None:
                await self.session.rollback()
                return "cancelled"
            await self.repository.mark_email_send_cancelled(current, now=datetime.now(UTC))
            await self.session.commit()
            return "cancelled"

        if send.owner_id is not None and await self.repository.get_email_suppression(
            owner_id=send.owner_id,
            email=send.recipient_email,
            email_fingerprint=email_suppression_fingerprint(
                owner_id=send.owner_id,
                email=send.recipient_email,
                secret=self.settings.effective_email_suppression_fingerprint_secret,
            ),
        ):
            current = await self.repository.get_claimed_email_send(send.id, lease_token)
            if current is None:
                await self.session.rollback()
                return "cancelled"
            current.error_details = "Recipient is suppressed after a permanent delivery failure."
            await self.repository.mark_email_send_cancelled(current, now=datetime.now(UTC))
            await self.session.commit()
            return "cancelled"

        try:
            message = _email_message_from_outbox_payload(send.message_payload)
        except (DomainError, TypeError, ValueError) as exc:
            return await self._record_failure(
                send.id,
                lease_token,
                f"Invalid immutable outbox payload: {type(exc).__name__}",
                retryable=False,
            )

        provider_idempotency_key = _provider_idempotency_key(send)
        started = await self.repository.begin_email_provider_request(
            send.id,
            lease_token,
            provider_idempotency_key=provider_idempotency_key,
            now=datetime.now(UTC),
        )
        if started is None:
            await self.session.rollback()
            return "failed"
        await self.session.commit()
        message = replace(message, provider_idempotency_key=provider_idempotency_key)

        try:
            result = await self.provider.send(message)
        except Exception as exc:  # noqa: BLE001
            return await self._record_indeterminate(
                send_id,
                lease_token,
                f"Provider request failed: {type(exc).__name__}",
            )

        if result.status != EmailDeliveryStatus.accepted:
            if result.delivery_uncertain:
                return await self._record_indeterminate(
                    send_id,
                    lease_token,
                    result.error_details or "Provider request outcome is uncertain.",
                    provider=result.provider,
                    provider_message_id=result.message_id,
                )
            return await self._record_failure(
                send_id,
                lease_token,
                result.error_details or "Email provider rejected the message.",
                retryable=result.retryable,
                retry_after_seconds=result.retry_after_seconds,
                provider=result.provider,
                provider_message_id=result.message_id,
            )

        current = await self.repository.get_claimed_email_send(send_id, lease_token)
        if current is None:
            await self.session.rollback()
            return "failed"
        try:
            now = datetime.now(UTC)
            current.provider = result.provider.value
            current.provider_message_id = result.message_id
            current.status = EmailSendStatus.accepted
            current.error_details = None
            current.lease_token = None
            current.lease_expires_at = None
            current.next_attempt_at = None
            current.last_event_at = now
            await self.repository.add_email_event(
                current.id,
                EmailEventType.accepted,
                occurred_at=now,
            )
            await self._mark_invitation_assignments_accepted(current, now=now)
            await self.session.flush()
            await self._complete_campaign_if_idle(current.campaign_id)
            await self.session.commit()
        except Exception:  # noqa: BLE001
            await self.session.rollback()
            return await self._record_indeterminate(
                send_id,
                lease_token,
                "Provider accepted the message, but local persistence failed.",
                provider=result.provider,
                provider_message_id=result.message_id,
            )
        return "accepted"

    async def _record_failure(
        self,
        send_id: UUID,
        lease_token: str,
        error_details: str,
        *,
        retryable: bool,
        provider: EmailProviderKey | None = None,
        provider_message_id: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> str:
        current = await self.repository.get_claimed_email_send(send_id, lease_token)
        if current is None:
            await self.session.rollback()
            return "failed"
        now = datetime.now(UTC)
        if provider is not None:
            current.provider = provider.value
        if provider_message_id:
            current.provider_message_id = provider_message_id
        current.error_details = error_details[:2000]
        current.lease_token = None
        current.lease_expires_at = None
        current.last_event_at = now

        if retryable and current.attempt_count < current.max_attempts:
            current.status = EmailSendStatus.queued
            retry_delay = _email_outbox_retry_delay(current.attempt_count)
            if retry_after_seconds is not None:
                retry_delay = max(retry_delay, timedelta(seconds=retry_after_seconds))
            current.next_attempt_at = now + retry_delay
            current.provider_request_started_at = None
            await self.repository.add_email_event(
                current.id,
                EmailEventType.retry_scheduled,
                occurred_at=now,
            )
            await self.session.commit()
            return "retried"

        current.status = EmailSendStatus.failed
        current.next_attempt_at = None
        if not retryable:
            current.attempt_count = current.max_attempts
        await self.repository.add_email_event(
            current.id,
            EmailEventType.failed,
            occurred_at=now,
        )
        await self._complete_campaign_if_idle(current.campaign_id)
        await self.session.commit()
        return "failed"

    async def _record_indeterminate(
        self,
        send_id: UUID,
        lease_token: str,
        error_details: str,
        *,
        provider: EmailProviderKey | None = None,
        provider_message_id: str | None = None,
    ) -> str:
        current = await self.repository.get_claimed_email_send(send_id, lease_token)
        if current is None:
            await self.session.rollback()
            current = await self.session.get(EmailSend, send_id, with_for_update=True)
        if current is None:
            return "indeterminate"
        now = datetime.now(UTC)
        if provider is not None:
            current.provider = provider.value
        if provider_message_id:
            current.provider_message_id = provider_message_id
        current.status = EmailSendStatus.indeterminate
        current.error_details = error_details[:2000]
        current.lease_token = None
        current.lease_expires_at = None
        current.next_attempt_at = None
        current.last_event_at = now
        await self.repository.add_email_event(
            current.id,
            EmailEventType.indeterminate,
            occurred_at=now,
        )
        await self.session.commit()
        return "indeterminate"

    async def _mark_invitation_assignments_accepted(
        self,
        send: EmailSend,
        *,
        now: datetime,
    ) -> None:
        assignment_ids = _email_outbox_assignment_ids(send.message_payload)
        if not assignment_ids and send.assignment_id is not None:
            assignment_ids = [send.assignment_id]
        if not assignment_ids:
            return
        reminder_ids = _email_outbox_reminder_assignment_ids(send.message_payload)
        assignments_result = await self.session.execute(
            select(QuestionnaireAssignment)
            .where(QuestionnaireAssignment.id.in_(assignment_ids))
            .with_for_update()
        )
        for assignment in assignments_result.scalars().all():
            if assignment.id in reminder_ids:
                assignment.reminder_count = min(2, (assignment.reminder_count or 0) + 1)
                assignment.last_reminder_sent_at = now
                assignment.reminder_due_at = now + DEFAULT_REMINDER_POLICY.minimum_interval
            elif assignment.status == AssignmentStatus.assigned:
                assignment.status = AssignmentStatus.invited
                assignment.invited_at = now

    async def _complete_campaign_if_idle(self, campaign_id: UUID | None) -> None:
        if campaign_id is None:
            return
        outstanding = await self.session.execute(
            select(func.count(EmailSend.id)).where(
                EmailSend.campaign_id == campaign_id,
                EmailSend.status.in_(
                    (
                        EmailSendStatus.queued,
                        EmailSendStatus.dispatching,
                        EmailSendStatus.indeterminate,
                    )
                ),
            )
        )
        if int(outstanding.scalar_one() or 0) != 0:
            return
        accepted = await self.session.execute(
            select(func.count(EmailSend.id)).where(
                EmailSend.campaign_id == campaign_id,
                EmailSend.status.in_((EmailSendStatus.accepted, EmailSendStatus.delivered)),
            )
        )
        if int(accepted.scalar_one() or 0) == 0:
            return
        campaign = await self.repository.get_campaign(campaign_id)
        if campaign is not None:
            campaign.status = CampaignStatus.completed


def _email_outbox_payload(
    message: EmailMessage,
    *,
    assignment_ids: list[UUID] | None = None,
    reminder_assignment_ids: list[UUID] | None = None,
    delivery_kind: str | None = None,
    default_from_address: str | None = None,
) -> dict[str, object]:
    from_address = (
        message.from_address.value if message.from_address is not None else default_from_address
    )
    return {
        "version": 1,
        "to": message.to.value,
        "subject": message.subject,
        "html_body": message.html_body,
        "text_body": message.text_body,
        "from_address": from_address,
        "reply_to": message.reply_to.value if message.reply_to is not None else None,
        "assignment_ids": [str(value) for value in (assignment_ids or [])],
        "reminder_assignment_ids": [str(value) for value in (reminder_assignment_ids or [])],
        "delivery_kind": delivery_kind,
    }


def _email_message_from_outbox_payload(payload: dict[str, object] | None) -> EmailMessage:
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise DomainError("Unsupported outbox payload.", code="email_outbox_payload_invalid")
    required = ("to", "subject", "html_body", "text_body")
    if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
        raise DomainError("Incomplete outbox payload.", code="email_outbox_payload_invalid")
    from_address = payload.get("from_address")
    reply_to = payload.get("reply_to")
    if from_address is not None and not isinstance(from_address, str):
        raise DomainError("Invalid outbox sender.", code="email_outbox_payload_invalid")
    if reply_to is not None and not isinstance(reply_to, str):
        raise DomainError("Invalid outbox reply-to.", code="email_outbox_payload_invalid")
    return EmailMessage(
        to=EmailAddress(str(payload["to"])),
        subject=str(payload["subject"]),
        html_body=str(payload["html_body"]),
        text_body=str(payload["text_body"]),
        from_address=EmailAddress(from_address) if from_address else None,
        reply_to=EmailAddress(reply_to) if reply_to else None,
    )


def _email_outbox_assignment_ids(payload: dict[str, object] | None) -> list[UUID]:
    if not isinstance(payload, dict):
        return []
    raw_ids = payload.get("assignment_ids")
    if not isinstance(raw_ids, list):
        return []
    assignment_ids: list[UUID] = []
    for raw_id in raw_ids:
        try:
            assignment_ids.append(UUID(str(raw_id)))
        except ValueError:
            continue
    return assignment_ids


def _email_outbox_reminder_assignment_ids(
    payload: dict[str, object] | None,
) -> set[UUID]:
    if not isinstance(payload, dict):
        return set()
    raw_ids = payload.get("reminder_assignment_ids")
    if not isinstance(raw_ids, list):
        return set()
    assignment_ids: set[UUID] = set()
    for raw_id in raw_ids:
        try:
            assignment_ids.add(UUID(str(raw_id)))
        except ValueError:
            continue
    return assignment_ids


def _email_outbox_payload_fingerprint(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _email_outbox_retry_delay(attempt_count: int) -> timedelta:
    exponent = max(attempt_count - 1, 0)
    seconds = min(
        EMAIL_OUTBOX_RETRY_BASE_SECONDS * (2**exponent),
        EMAIL_OUTBOX_RETRY_MAX_SECONDS,
    )
    return timedelta(seconds=seconds)


async def _enqueue_email_send(
    repository: object,
    candidate: EmailSend,
) -> tuple[EmailSend, bool]:
    if hasattr(repository, "enqueue_email_send"):
        return await repository.enqueue_email_send(candidate)
    existing = await repository.get_email_send_by_idempotency_key(candidate.idempotency_key)
    if existing is not None:
        return existing, False
    return await repository.add_email_send(candidate), True


def _email_send_idempotency_key(request_key: str, scope: str) -> str:
    return hashlib.sha256(f"{request_key}:{scope}".encode()).hexdigest()


def _provider_idempotency_key(send: EmailSend) -> str:
    source = send.idempotency_key or str(send.id)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"codrut:email-send:{source}"))


def _campaign_delivery_payload_fingerprint(
    campaign: Campaign,
    recipient: CampaignRecipient,
    settings: Settings,
) -> str:
    payload = {
        "campaign": {
            "html_body": campaign.html_body,
            "id": str(campaign.id),
            "landing_page_url": campaign.landing_page_url,
            "name": campaign.name,
            "segment": campaign.segment.value if campaign.segment is not None else None,
            "subject": campaign.subject,
            "text_body": campaign.text_body,
            "thumbnail_url": campaign.thumbnail_url,
            "video_url": campaign.video_url,
        },
        "recipient": {
            "contact_name": recipient.contact_name,
            "email": recipient.email,
            "id": str(recipient.id),
            "organization_name": recipient.organization_name,
            "owner_id": str(recipient.owner_id) if recipient.owner_id is not None else None,
            "segment": recipient.segment.value,
        },
        "render_context": {
            "calendly_url": CAMPAIGN_CALENDLY_URL,
            "legal_address": settings.email_legal_address,
            "public_app_url": str(settings.public_app_url),
        },
        "version": 1,
    }
    serialized = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _require_matching_email_send_payload(send: EmailSend, payload_fingerprint: str) -> None:
    if send.payload_fingerprint != payload_fingerprint:
        raise DomainError(
            "Idempotency key was already used for a different email payload.",
            code="email_send_idempotency_payload_conflict",
        )


def _email_provider_key(value: object) -> EmailProviderKey:
    try:
        return EmailProviderKey(str(value))
    except ValueError:
        return EmailProviderKey.test


def _email_result_from_existing_send(
    send: EmailSend,
    recipient_email: str,
) -> EmailSendResult:
    if send.status in {EmailSendStatus.queued, EmailSendStatus.dispatching}:
        status = EmailDeliveryStatus.queued
    elif send.status in {EmailSendStatus.accepted, EmailSendStatus.delivered}:
        status = EmailDeliveryStatus.accepted
    else:
        status = EmailDeliveryStatus.failed
    return EmailSendResult(
        provider=_email_provider_key(send.provider),
        status=status,
        message_id=send.provider_message_id or "",
        recipient=EmailAddress(recipient_email),
        error_details=send.error_details,
    )


def _campaign_result_from_existing_send(
    send: EmailSend,
    recipient: CampaignRecipient,
) -> CampaignSendRecipientResult:
    if send.status in {EmailSendStatus.queued, EmailSendStatus.dispatching}:
        return CampaignSendRecipientResult(
            recipient_id=recipient.id,
            email=recipient.email or "",
            status="queued",
        )
    if send.status in {EmailSendStatus.accepted, EmailSendStatus.delivered}:
        status = "accepted"
    elif send.status == EmailSendStatus.cancelled:
        status = "cancelled"
    else:
        status = "failed"
    return CampaignSendRecipientResult(
        recipient_id=recipient.id,
        email=recipient.email or "",
        status=status,
        message_id=send.provider_message_id,
        error=send.error_details,
    )


def _select_invitation_template(
    respondent: ParticipantProfile,
    *,
    reminder: bool = False,
) -> TransactionalTemplateKey:
    if reminder:
        return TransactionalTemplateKey.assignment_reminder
    if (respondent.role_group or "").strip().casefold() == "leadership":
        return TransactionalTemplateKey.account_setup
    return TransactionalTemplateKey.assignment_bundle
