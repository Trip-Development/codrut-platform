from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import uuid
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from codrut.contracts.emails import (
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderKey,
    EmailSendResult,
)
from codrut.core.config import Settings, get_settings
from codrut.core.database import SessionLocal
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
    TeamMembership,
    TeamMembershipRole,
    TeamType,
)
from codrut.modules.communications.delivery_events import DeliveryEventService
from codrut.modules.communications.email_provider import EmailProvider
from codrut.modules.communications.models import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientStatus,
    EmailSend,
    EmailSendStatus,
)
from codrut.modules.communications.reminders import reminder_candidates
from codrut.modules.communications.schemas import (
    BrevoWebhookEvent,
    CampaignCreateRequest,
    CampaignRecipientBulkCreateRequest,
    CampaignRecipientMembershipUpdateRequest,
    CampaignSendRequest,
)
from codrut.modules.communications.service import (
    AssignmentInvitationContext,
    CommunicationsService,
    EmailOutboxProcessor,
    TransactionalEmailService,
)
from codrut.modules.communications.task_links import build_task_url
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireResponse,
)
from codrut.modules.forms.schemas import QuestionnaireResponseSaveRequest
from codrut.modules.forms.service import FormsService
from codrut.modules.identity.models import (
    AssignmentInvite,
    Session,
    User,
    UserAccountType,
    UserRole,
)
from codrut.modules.identity.schemas import RegisterRequest
from codrut.modules.identity.service import IdentityService
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.scoring.models import ResultPublication
from codrut.tools.local_preview import build_preview_questionnaire_definitions, build_sample_answers

SIMULATION_ACKNOWLEDGEMENT = "synthetic-controlled-pilot"
SIMULATION_DATABASE_SUFFIX = "_simulation"
SYNTHETIC_PASSWORD = "Synthetic pilot access phrase 2026!"  # noqa: S105


@dataclass(frozen=True)
class SimulationReport:
    database: str
    participants: int
    leadership_accounts: int
    secure_link_accounts: int
    assignments_scored: int
    responses_submitted: int
    result_publications: int
    invitations: int
    sessions: int
    invitation_delivered: int
    invitation_bounced: int
    transient_retries_recovered: int
    reminded_participants: int
    reminder_rounds: int
    campaign_recipients: int
    campaign_suppressed_before_dispatch: int
    campaign_delivered: int
    campaign_bounced: int
    campaign_unsubscribed: int
    campaign_suppressed: int
    duplicate_campaign_rows: int
    cancelled_before_dispatch: int
    provider_accepted_messages: int


class SimulationEmailProvider:
    key = EmailProviderKey.test

    def __init__(self, *, fail_once: set[str] | None = None) -> None:
        self.fail_once = {email.casefold() for email in fail_once or set()}
        self.attempts: Counter[str] = Counter()
        self.accepted_messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> EmailSendResult:
        email = message.to.value.casefold()
        self.attempts[email] += 1
        if email in self.fail_once and self.attempts[email] == 1:
            return EmailSendResult(
                provider=self.key,
                status=EmailDeliveryStatus.failed,
                message_id=f"simulation:retry:{email}",
                recipient=message.to,
                error_details="Synthetic transient provider failure.",
            )
        self.accepted_messages.append(message)
        return EmailSendResult(
            provider=self.key,
            status=EmailDeliveryStatus.accepted,
            message_id=f"simulation:{len(self.accepted_messages):06d}",
            recipient=message.to,
        )


def require_simulation_database(settings: Settings, acknowledgement: str | None) -> str:
    database = make_url(settings.database_url).database or ""
    if settings.is_production:
        raise RuntimeError("Controlled-pilot simulation cannot run in production.")
    if not database.endswith(SIMULATION_DATABASE_SUFFIX):
        raise RuntimeError(
            f"Simulation database must end with '{SIMULATION_DATABASE_SUFFIX}', received "
            f"'{database or '<missing>'}'."
        )
    if acknowledgement != SIMULATION_ACKNOWLEDGEMENT:
        raise RuntimeError(
            "Set CODRUT_PILOT_SIMULATION_ACK to the exact synthetic-only acknowledgement."
        )
    return database


async def run_simulation(*, participants: int, leadership: int) -> SimulationReport:
    settings = get_settings()
    database = require_simulation_database(
        settings,
        os.getenv("CODRUT_PILOT_SIMULATION_ACK"),
    )
    if participants != 195 or leadership != 17:
        raise RuntimeError(
            "The controlled-pilot proof must run with exactly 195 people and 17 leaders."
        )
    if settings.email_daily_send_cap < 750:
        raise RuntimeError(
            "The controlled-pilot simulation requires an email allowance of at least 750."
        )

    async with SessionLocal() as session:
        existing_companies = await session.scalar(select(func.count(Company.id)))
        if int(existing_companies or 0) != 0:
            raise RuntimeError("Simulation database must not contain application data.")

        now = datetime.now(UTC)
        trainer = User(
            id=uuid.uuid4(),
            email="trainer.pilot-simulation@example.com",
            password_hash=hash_password(SYNTHETIC_PASSWORD),
            role=UserRole.trainer,
        )
        company = Company(id=uuid.uuid4(), name="Synthetic Controlled Pilot")
        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Synthetic Leadership Programme",
            description="Synthetic launch-capacity and recovery proof.",
            project_type="controlled_pilot_simulation",
            status=CompanyProjectStatus.active,
            starts_at=now - timedelta(days=1),
            due_at=now + timedelta(days=30),
            form_opens_at=now - timedelta(days=1),
            form_closes_at=now + timedelta(days=30),
        )
        session.add_all([trainer, company])
        await session.flush()
        session.add(project)
        await session.flush()
        session.add(
            CompanyMembership(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=trainer.id,
                role=CompanyMembershipRole.owner,
            )
        )

        definition = _synthetic_definition()
        session.add(definition)
        leadership_team = Team(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Leadership",
            type=TeamType.leadership,
        )
        session.add(leadership_team)
        await session.flush()

        profiles: list[ParticipantProfile] = []
        assignments: list[QuestionnaireAssignment] = []
        assignment_round_id = uuid.uuid4()
        for index in range(participants):
            display_number = index + 1
            full_name = f"Synthetic Participant {display_number:03d}"
            reports_to_name = None
            if index > 0:
                manager_number = 1 if index < leadership else 2 + ((index - leadership) % 16)
                reports_to_name = f"Synthetic Participant {manager_number:03d}"
            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name=full_name,
                email=f"pilot-sim-{display_number:03d}@example.com",
                reports_to_name=reports_to_name,
                position="Leadership" if index < leadership else "Participant",
                location="Synthetic",
                role_group="Leadership" if index < leadership else "Programme",
            )
            session.add(profile)
            await session.flush()
            profiles.append(profile)
            session.add(
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=profile.id,
                    reports_to_name=reports_to_name,
                    position=profile.position,
                    location=profile.location,
                    role_group=profile.role_group,
                    active=True,
                )
            )
            if index < leadership:
                session.add(
                    TeamMembership(
                        id=uuid.uuid4(),
                        team_id=leadership_team.id,
                        participant_profile_id=profile.id,
                        role=(
                            TeamMembershipRole.leader
                            if index == 0
                            else TeamMembershipRole.member
                        ),
                    )
                )
            assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                assignment_round_id=assignment_round_id,
                respondent_profile_id=profile.id,
                questionnaire_key=definition.key,
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.assigned,
                due_at=project.due_at,
            )
            session.add(assignment)
            assignments.append(assignment)
        await session.commit()

        transient_addresses = {profile.email for profile in profiles[:3] if profile.email}
        provider = SimulationEmailProvider(fail_once=transient_addresses)
        identity = IdentityService(session)
        invitation_delivery = TransactionalEmailService(
            provider,
            session,
            owner_id=trainer.id,
        )
        invites: list[AssignmentInvite] = []
        for profile, assignment in zip(profiles, assignments, strict=True):
            invite = await identity.create_invite(
                company.id,
                profile.id,
                assignment_ids=[assignment.id],
                project_id=project.id,
                expires_at=project.due_at,
            )
            replayed_invite = await identity.create_invite(
                company.id,
                profile.id,
                assignment_ids=[assignment.id],
                project_id=project.id,
                expires_at=project.due_at,
            )
            if replayed_invite.id != invite.id:
                raise RuntimeError("Invitation idempotency failed during simulation.")
            invites.append(invite)
            context = AssignmentInvitationContext(
                company_name=company.name,
                trainer_name="Synthetic Trainer",
                action_url=build_task_url(invite.token, settings),
                task_count=1,
            )
            idempotency_key = f"pilot-invite:{profile.id}"
            await invitation_delivery.send_assignment_invitation(
                assignment,
                profile,
                context,
                idempotency_key=idempotency_key,
                assignment_ids=[assignment.id],
            )
            await invitation_delivery.send_assignment_invitation(
                assignment,
                profile,
                context,
                idempotency_key=idempotency_key,
                assignment_ids=[assignment.id],
            )
        await session.commit()

        first_delivery = await EmailOutboxProcessor(session, provider).process_due(
            limit=participants + 10
        )
        if first_delivery.retried != len(transient_addresses):
            raise RuntimeError("Synthetic transient failures were not scheduled for retry.")
        queued_retries = list(
            (
                await session.execute(
                    select(EmailSend).where(EmailSend.status == EmailSendStatus.queued)
                )
            ).scalars()
        )
        for send in queued_retries:
            send.next_attempt_at = now - timedelta(seconds=1)
        await session.commit()
        recovered_delivery = await EmailOutboxProcessor(session, provider).process_due(
            limit=participants + 10
        )
        if recovered_delivery.accepted != len(transient_addresses):
            raise RuntimeError("Synthetic transient retries did not recover.")

        invitation_sends = list(
            (
                await session.execute(
                    select(EmailSend)
                    .where(EmailSend.assignment_id.is_not(None))
                    .where(EmailSend.template_key != "assignment_reminder")
                    .order_by(EmailSend.recipient_email)
                )
            ).scalars()
        )
        await _apply_delivery_events(
            session,
            invitation_sends,
            bounced=5,
        )

        for index, (profile, invite) in enumerate(zip(profiles, invites, strict=True)):
            if index < leadership:
                await IdentityService(session).register(
                    RegisterRequest(
                        email=profile.email or "",
                        password=SYNTHETIC_PASSWORD,
                        token=invite.token,
                        terms_accepted=True,
                        terms_version=CURRENT_TERMS_VERSION,
                    )
                )
            else:
                exchange = await IdentityService(session).verify_invite_token_and_create_session(
                    invite.token
                )
                if exchange.session_token is None:
                    raise RuntimeError("Secure-link participant session was not created.")
        await session.commit()

        reminded_assignments = assignments[-20:]
        for assignment in reminded_assignments:
            assignment.reminder_due_at = now - timedelta(seconds=1)
        await session.commit()
        first_candidates = reminder_candidates(reminded_assignments, now=now)
        if len(first_candidates) != len(reminded_assignments):
            raise RuntimeError("First reminder round did not select every due assignment.")
        await _send_reminder_round(
            session,
            provider,
            company,
            profiles[-20:],
            reminded_assignments,
            invites[-20:],
            owner_id=trainer.id,
            round_number=1,
            settings=settings,
        )

        reminder_now = datetime.now(UTC)
        for assignment in reminded_assignments:
            assignment.last_reminder_sent_at = reminder_now - timedelta(days=3)
            assignment.reminder_due_at = reminder_now - timedelta(seconds=1)
        await session.commit()
        second_candidates = reminder_candidates(reminded_assignments, now=reminder_now)
        if len(second_candidates) != len(reminded_assignments):
            raise RuntimeError("Second reminder round did not select every due assignment.")
        await _send_reminder_round(
            session,
            provider,
            company,
            profiles[-20:],
            reminded_assignments,
            invites[-20:],
            owner_id=trainer.id,
            round_number=2,
            settings=settings,
        )
        for assignment in reminded_assignments:
            assignment.reminder_due_at = datetime.now(UTC) - timedelta(seconds=1)
        if reminder_candidates(reminded_assignments):
            raise RuntimeError("Assignments remained remindable after the bounded second round.")

        participant_schema = definition.schema
        forms = FormsService(session)
        for index, (profile, assignment) in enumerate(zip(profiles, assignments, strict=True)):
            if profile.user_id is None:
                raise RuntimeError("Participant account/session exchange did not link the profile.")
            answers = build_sample_answers(participant_schema, offset=index)
            await forms.save_assignment_response(
                profile.user_id,
                assignment.id,
                QuestionnaireResponseSaveRequest(answers=answers),
                submit=True,
            )
            if (index + 1) % 50 == 0:
                await session.commit()
        await session.commit()

        communications = CommunicationsService(session)
        recipient_payload = CampaignRecipientBulkCreateRequest.model_validate(
            {
                "recipients": [
                    {
                        "email": profile.email,
                        "contact_name": profile.full_name,
                        "organization_name": company.name,
                        "segment": "past_customer",
                        "source": "controlled_pilot_simulation",
                    }
                    for profile in profiles
                ]
            }
        )
        import_result = await communications.bulk_create_campaign_recipients_with_result(
            recipient_payload,
            owner_id=trainer.id,
        )
        recipients = import_result.recipients
        campaign = await communications.create_campaign(
            CampaignCreateRequest(
                name="Synthetic launch campaign",
                segment="past_customer",
                subject="Mesaj sintetic pentru ${first_name}",
                html_body="<p>Mesaj de verificare pentru ${organization_name}.</p>",
                text_body="Mesaj de verificare pentru ${organization_name}.",
            ),
            owner_id=trainer.id,
        )
        await communications.replace_campaign_recipient_memberships(
            campaign.id,
            CampaignRecipientMembershipUpdateRequest(
                recipient_ids=[recipient.id for recipient in recipients]
            ),
            owner_id=trainer.id,
        )
        dry_run = await communications.send_campaign(
            campaign.id,
            CampaignSendRequest(mode="all", dry_run=True),
            provider=provider,
            settings=settings,
            owner_id=trainer.id,
        )
        if dry_run.total != participants or not dry_run.dry_run:
            raise RuntimeError("Campaign audience dry-run did not cover the full synthetic cohort.")
        first_campaign_send = await communications.send_campaign(
            campaign.id,
            CampaignSendRequest(mode="all"),
            provider=provider,
            settings=settings,
            owner_id=trainer.id,
            idempotency_key="controlled-pilot-campaign",
        )
        replayed_campaign_send = await communications.send_campaign(
            campaign.id,
            CampaignSendRequest(mode="all"),
            provider=provider,
            settings=settings,
            owner_id=trainer.id,
            idempotency_key="controlled-pilot-campaign",
        )
        if (
            first_campaign_send.queued != participants
            or replayed_campaign_send.total != participants
        ):
            raise RuntimeError(
                "Campaign enqueue or idempotent replay did not cover the full cohort."
            )
        await session.commit()
        campaign_outbox = await EmailOutboxProcessor(session, provider).process_due(
            limit=participants + 10
        )
        if (
            campaign_outbox.accepted != participants - 5
            or campaign_outbox.cancelled != 5
        ):
            raise RuntimeError(
                "Campaign outbox did not enforce the invitation bounce suppression list."
            )
        campaign_sends = list(
            (
                await session.execute(
                    select(EmailSend)
                    .where(EmailSend.campaign_id == campaign.id)
                    .order_by(EmailSend.recipient_email)
                )
            ).scalars()
        )
        accepted_campaign_sends = [
            send for send in campaign_sends if send.status == EmailSendStatus.accepted
        ]
        await _apply_delivery_events(session, accepted_campaign_sends, bounced=5)
        await _apply_suppression_events(session, accepted_campaign_sends)

        campaign_send_count_before_replay = int(
            await session.scalar(
                select(func.count(EmailSend.id)).where(EmailSend.campaign_id == campaign.id)
            )
            or 0
        )
        await communications.send_campaign(
            campaign.id,
            CampaignSendRequest(mode="all"),
            provider=provider,
            settings=settings,
            owner_id=trainer.id,
            idempotency_key="controlled-pilot-campaign",
        )
        campaign_send_count_after_replay = int(
            await session.scalar(
                select(func.count(EmailSend.id)).where(EmailSend.campaign_id == campaign.id)
            )
            or 0
        )

        cancellation_campaign = await communications.create_campaign(
            CampaignCreateRequest(
                name="Synthetic cancellation campaign",
                segment="past_customer",
                subject="Mesaj sintetic de anulare",
                html_body="<p>Acest mesaj nu trebuie livrat.</p>",
                text_body="Acest mesaj nu trebuie livrat.",
            ),
            owner_id=trainer.id,
        )
        await communications.replace_campaign_recipient_memberships(
            cancellation_campaign.id,
            CampaignRecipientMembershipUpdateRequest(
                recipient_ids=[recipient.id for recipient in recipients[-10:]]
            ),
            owner_id=trainer.id,
        )
        cancellation_send = await communications.send_campaign(
            cancellation_campaign.id,
            CampaignSendRequest(mode="all"),
            provider=provider,
            settings=settings,
            owner_id=trainer.id,
            idempotency_key="controlled-pilot-cancel",
        )
        if cancellation_send.queued != 10:
            raise RuntimeError("Cancellation rehearsal did not queue ten synthetic messages.")
        cancelled = await communications.cancel_campaign_delivery(
            cancellation_campaign.id,
            owner_id=trainer.id,
        )
        await session.commit()
        post_cancel = await EmailOutboxProcessor(session, provider).process_due(limit=20)
        if cancelled != 10 or post_cancel.claimed != 0:
            raise RuntimeError("Pre-dispatch campaign cancellation did not prevent delivery.")

        report = await _build_report(
            session,
            database=database,
            participants=participants,
            leadership=leadership,
            campaign=campaign,
            campaign_send_count_before_replay=campaign_send_count_before_replay,
            campaign_send_count_after_replay=campaign_send_count_after_replay,
            cancelled=cancelled,
            provider=provider,
            transient_retries=len(transient_addresses),
            reminded_participants=len(reminded_assignments),
        )
        _assert_report(report)
        return report


def _synthetic_definition() -> QuestionnaireDefinition:
    preview = next(
        item for item in build_preview_questionnaire_definitions() if item.key == "lencioni"
    )
    full_schema = deepcopy(preview.schema)
    participant_schema = deepcopy(full_schema)
    participant_schema.pop("scoring", None)
    dimensions = [group["id"] for group in full_schema["scoring"]["groups"]]
    checksum = hashlib.sha256(
        json.dumps(full_schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return QuestionnaireDefinition(
        id=uuid.uuid4(),
        key=preview.key,
        version=1,
        title=preview.title,
        description=preview.description,
        schema=participant_schema,
        private_config={"schema": full_schema},
        feedback_policy={
            "participant_results": {
                "publication": "scores_and_interpretation",
                "dimension_ids": dimensions,
                "target_types": ["self"],
                "require_self_target": False,
                "include_primary_result": True,
            }
        },
        trainer_visibility_policy={"raw_responses": True},
        content_checksum=checksum,
        system_managed=True,
        active=True,
    )


async def _send_reminder_round(
    session,
    provider: EmailProvider,
    company: Company,
    profiles: list[ParticipantProfile],
    assignments: list[QuestionnaireAssignment],
    invites: list[AssignmentInvite],
    *,
    owner_id: UUID,
    round_number: int,
    settings: Settings,
) -> None:
    delivery = TransactionalEmailService(provider, session, owner_id=owner_id)
    for profile, assignment, invite in zip(profiles, assignments, invites, strict=True):
        context = AssignmentInvitationContext(
            company_name=company.name,
            trainer_name="Synthetic Trainer",
            action_url=build_task_url(invite.token, settings),
            task_count=1,
        )
        key = f"pilot-reminder:{round_number}:{profile.id}"
        await delivery.send_assignment_invitation(
            assignment,
            profile,
            context,
            idempotency_key=key,
            assignment_ids=[assignment.id],
            reminder_assignment_ids=[assignment.id],
        )
        await delivery.send_assignment_invitation(
            assignment,
            profile,
            context,
            idempotency_key=key,
            assignment_ids=[assignment.id],
            reminder_assignment_ids=[assignment.id],
        )
    await session.commit()
    outcome = await EmailOutboxProcessor(session, provider).process_due(limit=len(assignments) + 5)
    if outcome.accepted != len(assignments):
        raise RuntimeError(f"Reminder round {round_number} did not deliver exactly once.")


async def _apply_delivery_events(session, sends: list[EmailSend], *, bounced: int) -> None:
    event_time = int(datetime.now(UTC).timestamp())
    service = DeliveryEventService(session)
    for index, send in enumerate(sends):
        if send.provider_message_id is None:
            raise RuntimeError("Accepted synthetic delivery is missing a provider message ID.")
        event = "hard_bounce" if index < bounced else "delivered"
        payload = BrevoWebhookEvent.model_validate(
            {
                "event": event,
                "email": send.recipient_email,
                "message-id": send.provider_message_id,
                "ts_event": event_time + index,
                "reason": "Synthetic mailbox rejection." if event == "hard_bounce" else None,
            }
        )
        result = await service.apply_brevo_event(payload)
        if result.status != "applied":
            raise RuntimeError("Synthetic provider event was not applied.")
        if index == 0:
            replay = await service.apply_brevo_event(payload)
            if replay.status != "duplicate":
                raise RuntimeError("Synthetic provider event replay was not idempotent.")


async def _apply_suppression_events(session, campaign_sends: list[EmailSend]) -> None:
    service = DeliveryEventService(session)
    now = int(datetime.now(UTC).timestamp()) + len(campaign_sends) + 10
    for index, event in enumerate(("unsubscribed", "unsubscribed", "spam"), start=5):
        send = campaign_sends[index]
        if send.provider_message_id is None:
            raise RuntimeError("Campaign delivery is missing a provider message ID.")
        result = await service.apply_brevo_event(
            BrevoWebhookEvent.model_validate(
                {
                    "event": event,
                    "email": send.recipient_email,
                    "message-id": send.provider_message_id,
                    "ts_event": now + index,
                }
            )
        )
        if result.status != "applied":
            raise RuntimeError("Synthetic suppression event was not applied.")


async def _build_report(
    session,
    *,
    database: str,
    participants: int,
    leadership: int,
    campaign: Campaign,
    campaign_send_count_before_replay: int,
    campaign_send_count_after_replay: int,
    cancelled: int,
    provider: SimulationEmailProvider,
    transient_retries: int,
    reminded_participants: int,
) -> SimulationReport:
    shadow_accounts = int(
        await session.scalar(
            select(func.count(User.id)).where(User.account_type == UserAccountType.guest)
        )
        or 0
    )
    participant_accounts = int(
        await session.scalar(select(func.count(User.id)).where(User.role == UserRole.participant))
        or 0
    )
    campaign_status_counts = dict(
        (
            await session.execute(
                select(EmailSend.status, func.count(EmailSend.id))
                .where(EmailSend.campaign_id == campaign.id)
                .group_by(EmailSend.status)
            )
        ).all()
    )
    recipient_status_counts = dict(
        (
            await session.execute(
                select(CampaignRecipient.status, func.count(CampaignRecipient.id)).group_by(
                    CampaignRecipient.status
                )
            )
        ).all()
    )
    invitation_status_counts = dict(
        (
            await session.execute(
                select(EmailSend.status, func.count(EmailSend.id))
                .where(EmailSend.assignment_id.is_not(None))
                .where(EmailSend.template_key != "assignment_reminder")
                .group_by(EmailSend.status)
            )
        ).all()
    )
    return SimulationReport(
        database=database,
        participants=participants,
        leadership_accounts=participant_accounts - shadow_accounts,
        secure_link_accounts=shadow_accounts,
        assignments_scored=int(
            await session.scalar(
                select(func.count(QuestionnaireAssignment.id)).where(
                    QuestionnaireAssignment.status == AssignmentStatus.scored
                )
            )
            or 0
        ),
        responses_submitted=int(
            await session.scalar(select(func.count(QuestionnaireResponse.id))) or 0
        ),
        result_publications=int(
            await session.scalar(
                select(func.count(ResultPublication.id)).where(
                    ResultPublication.revoked_at.is_(None)
                )
            )
            or 0
        ),
        invitations=int(await session.scalar(select(func.count(AssignmentInvite.id))) or 0),
        sessions=int(await session.scalar(select(func.count(Session.id))) or 0),
        invitation_delivered=int(invitation_status_counts.get(EmailSendStatus.delivered, 0)),
        invitation_bounced=int(invitation_status_counts.get(EmailSendStatus.bounced, 0)),
        transient_retries_recovered=transient_retries,
        reminded_participants=reminded_participants,
        reminder_rounds=int(
            await session.scalar(
                select(func.sum(QuestionnaireAssignment.reminder_count)).where(
                    QuestionnaireAssignment.reminder_count > 0
                )
            )
            or 0
        ),
        campaign_recipients=int(
            await session.scalar(select(func.count(CampaignRecipient.id))) or 0
        ),
        campaign_suppressed_before_dispatch=int(
            campaign_status_counts.get(EmailSendStatus.cancelled, 0)
        ),
        campaign_delivered=int(campaign_status_counts.get(EmailSendStatus.delivered, 0)),
        campaign_bounced=int(campaign_status_counts.get(EmailSendStatus.bounced, 0)),
        campaign_unsubscribed=int(
            recipient_status_counts.get(CampaignRecipientStatus.unsubscribed, 0)
        ),
        campaign_suppressed=int(
            recipient_status_counts.get(CampaignRecipientStatus.suppressed, 0)
        ),
        duplicate_campaign_rows=(
            campaign_send_count_after_replay - campaign_send_count_before_replay
        ),
        cancelled_before_dispatch=cancelled,
        provider_accepted_messages=len(provider.accepted_messages),
    )


def _assert_report(report: SimulationReport) -> None:
    expected = {
        "participants": 195,
        "leadership_accounts": 17,
        "secure_link_accounts": 178,
        "assignments_scored": 195,
        "responses_submitted": 195,
        "result_publications": 195,
        "invitations": 195,
        "sessions": 195,
        "invitation_delivered": 190,
        "invitation_bounced": 5,
        "transient_retries_recovered": 3,
        "reminded_participants": 20,
        "reminder_rounds": 40,
        "campaign_recipients": 195,
        "campaign_suppressed_before_dispatch": 5,
        "campaign_delivered": 185,
        "campaign_bounced": 5,
        "campaign_unsubscribed": 2,
        "campaign_suppressed": 6,
        "duplicate_campaign_rows": 0,
        "cancelled_before_dispatch": 10,
        "provider_accepted_messages": 425,
    }
    actual = asdict(report)
    mismatches = {
        key: {"expected": value, "actual": actual.get(key)}
        for key, value in expected.items()
        if actual.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"Controlled-pilot simulation mismatch: {json.dumps(mismatches)}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the destructive synthetic-only controlled-pilot launch proof."
    )
    parser.add_argument("--participants", type=int, default=195)
    parser.add_argument("--leadership", type=int, default=17)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = asyncio.run(
        run_simulation(
            participants=args.participants,
            leadership=args.leadership,
        )
    )
    print(json.dumps(asdict(report), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
