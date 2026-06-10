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

        campaign = {
            "videoHost": {
                "provider": "Codrut watch page + Cloudflare R2",
                "status": "needs_upload",
                "note": (
                    "Emailul trimite thumbnail si CTA catre pagina Codrut; "
                    "video-ul nu este redat direct in email."
                ),
            },
            "template": {
                "subject": "O idee practica pentru echipa ta, ${first_name}",
                "personalization": "Prenumele se completeaza automat cand exista nume in baza.",
                "ctaPrimary": "Programeaza o discutie",
                "ctaSecondary": "Vreau sa fiu contactat",
            },
            "recipients": [],
            "weeklyReport": {
                "cadence": "Saptamanal",
                "metrics": ["open rate", "click rate", "view rate"],
                "notification": "Andrei primeste email/Telegram cu link catre raport.",
            },
        }

        return {
            "metrics": metrics,
            "assessmentRows": rows,
            "rules": rules,
            "campaign": campaign,
        }



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
