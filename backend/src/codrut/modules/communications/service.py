import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from codrut.contracts.emails import EmailAddress, EmailDeliveryStatus, EmailMessage, EmailSendResult
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
from codrut.modules.communications.email_provider import EmailProvider
from codrut.modules.communications.models import EmailTemplate
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.schemas import (
    EmailTemplateCreateRequest,
    EmailTemplateResponse,
    EmailTemplateUpdateRequest,
)
from codrut.modules.communications.templates import (
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
        template.active = False
        return EmailTemplateResponse.model_validate(template)

    def _require_repository(self) -> CommunicationsRepository:
        if self.repository is None:
            raise RuntimeError("CommunicationsService requires a database session")
        return self.repository

    async def _seed_catalog_templates(self, repository: CommunicationsRepository) -> None:
        for k, catalog_template in TRANSACTIONAL_TEMPLATES.items():
            existing = await repository.get_template(
                key=k.value,
                version=catalog_template.version,
            )
            if existing is not None:
                continue
            await repository.add_template(
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

    async def send_assignment_invitation(
        self,
        assignment: QuestionnaireAssignment,
        respondent: ParticipantProfile,
        context: AssignmentInvitationContext,
    ) -> EmailSendResult:
        template_key = _select_invitation_template(respondent)

        version = 1
        if self.session is not None:
            comm_service = CommunicationsService(self.session)
            db_template = await comm_service.get_template(template_key.value)
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
    if respondent.user_id is None:
        return TransactionalTemplateKey.account_setup
    return TransactionalTemplateKey.assignment_bundle
