from uuid import uuid4

import pytest
from sqlalchemy import select

from codrut.contracts.emails import EmailMessage, EmailProviderKey, EmailSendResult
from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
from codrut.modules.communications.models import EmailSend, EmailTemplate
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.service import (
    AssignmentInvitationContext,
    TransactionalEmailService,
    _select_invitation_template,
)
from codrut.modules.communications.templates import TransactionalTemplateKey
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    ParticipantProfile,
)
from codrut.modules.companies.schemas import (
    CompanyProjectUpdateRequest,
)
from codrut.modules.companies.service import CompanyService
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.modules.identity.models import User, UserRole


class MockProvider:
    key = EmailProviderKey.test

    async def send(self, message: EmailMessage) -> EmailSendResult:
        return EmailSendResult(
            status="queued",
            provider_message_id=f"msg_{uuid4().hex}",
        )


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await engine.dispose()


async def create_test_context(db_session, *, role_group: str = "leadership"):
    user = User(
        id=uuid4(),
        email=f"user_{uuid4().hex[:8]}@example.com",
        password_hash="test_password_hash",  # noqa: S106
        role=UserRole.trainer,
    )
    db_session.add(user)

    company = Company(
        id=uuid4(),
        name=f"Company {uuid4().hex[:8]}",
    )
    db_session.add(company)

    membership = CompanyMembership(
        company_id=company.id,
        user_id=user.id,
        role=CompanyMembershipRole.owner,
    )
    db_session.add(membership)

    participant = ParticipantProfile(
        id=uuid4(),
        company_id=company.id,
        full_name="Elena Popescu",
        email=f"elena_{uuid4().hex[:8]}@example.com",
        role_group=role_group,
    )
    db_session.add(participant)

    key = "icare"
    version = 10_000 + int.from_bytes(uuid4().bytes[:4], "big") % 1_000_000_000
    definition = QuestionnaireDefinition(
        id=uuid4(),
        key=key,
        version=version,
        title=f"Synthetic {key}",
        description="Synthetic test definition.",
        schema={
            "key": key,
            "version": version,
            "title": f"Synthetic {key}",
            "audience": "participant",
            "sections": [],
        },
        feedback_policy={},
        trainer_visibility_policy={"raw_responses": "hidden"},
        content_checksum=uuid4().hex * 2,
        active=True,
    )
    db_session.add(definition)
    await db_session.flush()

    assignment = QuestionnaireAssignment(
        id=uuid4(),
        company_id=company.id,
        respondent_profile_id=participant.id,
        questionnaire_key=key,
        questionnaire_definition_id=definition.id,
        target_type="self",
        status=AssignmentStatus.assigned,
    )
    db_session.add(assignment)
    await db_session.flush()
    return user, company, participant, assignment


def test_select_invitation_template_defaults():
    leadership_profile = ParticipantProfile(
        id=uuid4(),
        company_id=uuid4(),
        full_name="Alex Leader",
        email="leader@example.com",
        role_group="leadership",
    )
    member_profile = ParticipantProfile(
        id=uuid4(),
        company_id=uuid4(),
        full_name="Sam Member",
        email="member@example.com",
        role_group="member",
    )

    # Initial invites default behavior (zero regression)
    assert (
        _select_invitation_template(leadership_profile, reminder=False)
        == TransactionalTemplateKey.account_setup.value
    )
    assert (
        _select_invitation_template(member_profile, reminder=False)
        == TransactionalTemplateKey.assignment_bundle.value
    )

    # Reminders default behavior (Amendment 2: both default to assignment_reminder when null)
    assert (
        _select_invitation_template(leadership_profile, reminder=True)
        == TransactionalTemplateKey.assignment_reminder.value
    )
    assert (
        _select_invitation_template(member_profile, reminder=True)
        == TransactionalTemplateKey.assignment_reminder.value
    )


def test_select_invitation_template_custom_keys():
    leadership_profile = ParticipantProfile(
        id=uuid4(),
        company_id=uuid4(),
        full_name="Alex Leader",
        email="leader@example.com",
        role_group="leadership",
    )
    member_profile = ParticipantProfile(
        id=uuid4(),
        company_id=uuid4(),
        full_name="Sam Member",
        email="member@example.com",
        role_group="member",
    )

    # Custom initial invitation templates
    assert (
        _select_invitation_template(
            leadership_profile,
            reminder=False,
            leadership_invitation_template_key="custom_lead_invite",
            member_invitation_template_key="custom_member_invite",
        )
        == "custom_lead_invite"
    )
    assert (
        _select_invitation_template(
            member_profile,
            reminder=False,
            leadership_invitation_template_key="custom_lead_invite",
            member_invitation_template_key="custom_member_invite",
        )
        == "custom_member_invite"
    )

    # Custom reminder templates (Amendment 2)
    assert (
        _select_invitation_template(
            leadership_profile,
            reminder=True,
            leadership_reminder_template_key="custom_lead_reminder",
            member_reminder_template_key="custom_member_reminder",
        )
        == "custom_lead_reminder"
    )
    assert (
        _select_invitation_template(
            member_profile,
            reminder=True,
            leadership_reminder_template_key="custom_lead_reminder",
            member_reminder_template_key="custom_member_reminder",
        )
        == "custom_member_reminder"
    )


@pytest.mark.asyncio
async def test_enqueue_assignment_invitation_inactive_template_refusal():
    async with SessionLocal() as db_session:
        user, _company, participant, assignment = await create_test_context(
            db_session, role_group="leadership"
        )
        comm_repo = CommunicationsRepository(db_session)
        # Create an inactive custom template in DB
        inactive_template = EmailTemplate(
            key=f"custom_invite_inactive_{uuid4().hex[:8]}",
            owner_id=user.id,
            version=1,
            subject="Invitație ${participant_name}",
            html_body="<p>Accesează: <a href=\"${action_url}\">Click</a></p>",
            text_body="Accesează: ${action_url}",
            variables=["participant_name", "action_url"],
            audience="transactional",
            active=False,
        )
        await comm_repo.add_template(inactive_template)
        await db_session.flush()

        email_service = TransactionalEmailService(
            provider=MockProvider(),
            session=db_session,
            owner_id=user.id,
        )
        context = AssignmentInvitationContext(
            company_name="Test Company",
            trainer_name="Trainer Test",
            action_url="https://app.codrut.ro/t/sample-token",
            task_count=1,
        )

        # Must raise DomainError (Amendment 3: Layer B - No silent fallback)
        with pytest.raises(DomainError) as exc_info:
            await email_service.enqueue_assignment_invitation(
                assignment,
                participant,
                context,
                leadership_invitation_template_key=inactive_template.key,
            )
        assert exc_info.value.code in ("template_inactive", "template_not_found")


@pytest.mark.asyncio
async def test_enqueue_assignment_invitation_missing_template_refusal():
    async with SessionLocal() as db_session:
        user, _company, participant, assignment = await create_test_context(
            db_session, role_group="member"
        )
        email_service = TransactionalEmailService(
            provider=MockProvider(),
            session=db_session,
            owner_id=user.id,
        )
        context = AssignmentInvitationContext(
            company_name="Test Company",
            trainer_name="Trainer Test",
            action_url="https://app.codrut.ro/t/sample-token",
            task_count=1,
        )

        # Must raise DomainError when custom template is missing from DB (Amendment 3: Layer B)
        with pytest.raises(DomainError) as exc_info:
            await email_service.enqueue_assignment_invitation(
                assignment,
                participant,
                context,
                member_invitation_template_key="non_existent_template_key",
            )
        assert exc_info.value.code == "template_not_found"


@pytest.mark.asyncio
async def test_enqueue_assignment_invitation_campaign_template_refusal():
    async with SessionLocal() as db_session:
        user, _company, participant, assignment = await create_test_context(
            db_session, role_group="member"
        )
        comm_repo = CommunicationsRepository(db_session)
        campaign_tmpl = EmailTemplate(
            key=f"lead_gen_campaign_{uuid4().hex[:8]}",
            owner_id=user.id,
            version=1,
            subject="Noutăți ${company_name}",
            html_body="<p>Link: <a href=\"${action_url}\">Click</a></p>",
            text_body="Link: ${action_url}",
            variables=["company_name", "action_url"],
            audience="campaign:leads",
            active=True,
        )
        await comm_repo.add_template(campaign_tmpl)
        await db_session.flush()

        email_service = TransactionalEmailService(
            provider=MockProvider(),
            session=db_session,
            owner_id=user.id,
        )
        context = AssignmentInvitationContext(
            company_name="Test Company",
            trainer_name="Trainer Test",
            action_url="https://app.codrut.ro/t/sample-token",
            task_count=1,
        )

        # Must raise DomainError (Amendment 6: campaign templates not allowed)
        with pytest.raises(DomainError) as exc_info:
            await email_service.enqueue_assignment_invitation(
                assignment,
                participant,
                context,
                member_invitation_template_key=campaign_tmpl.key,
            )
        assert exc_info.value.code == "campaign_template_not_allowed"


@pytest.mark.asyncio
async def test_enqueue_assignment_invitation_missing_action_url_refusal():
    async with SessionLocal() as db_session:
        user, _company, participant, assignment = await create_test_context(
            db_session, role_group="leadership"
        )
        comm_repo = CommunicationsRepository(db_session)
        missing_url_tmpl = EmailTemplate(
            key=f"custom_invite_no_url_{uuid4().hex[:8]}",
            owner_id=user.id,
            version=1,
            subject="Invitație ${participant_name}",
            html_body="<p>Fără link de acces!</p>",
            text_body="Fără link de acces!",
            variables=["participant_name"],
            audience="transactional",
            active=True,
        )
        await comm_repo.add_template(missing_url_tmpl)
        await db_session.flush()

        email_service = TransactionalEmailService(
            provider=MockProvider(),
            session=db_session,
            owner_id=user.id,
        )
        context = AssignmentInvitationContext(
            company_name="Test Company",
            trainer_name="Trainer Test",
            action_url="https://app.codrut.ro/t/sample-token",
            task_count=1,
        )

        with pytest.raises(DomainError) as exc_info:
            await email_service.enqueue_assignment_invitation(
                assignment,
                participant,
                context,
                leadership_invitation_template_key=missing_url_tmpl.key,
            )
        assert exc_info.value.code == "email_template_missing_action_url"


@pytest.mark.asyncio
async def test_enqueue_assignment_invitation_custom_template_success():
    async with SessionLocal() as db_session:
        user, _company, participant, assignment = await create_test_context(
            db_session, role_group="leadership"
        )
        comm_repo = CommunicationsRepository(db_session)
        custom_key = f"custom_lead_{uuid4().hex[:8]}"
        valid_custom_tmpl = EmailTemplate(
            key=custom_key,
            owner_id=user.id,
            version=2,
            subject="Salut ${participant_name} de la ${trainer_name}",
            html_body=(
                "<p>Compania ${company_name}: aveți ${task_count} sarcini. "
                "<a href=\"${action_url}\">Completează</a></p>"
            ),
            text_body=(
                "Compania ${company_name}: aveți ${task_count} sarcini. "
                "Accesează: ${action_url}"
            ),
            variables=[
                "participant_name",
                "trainer_name",
                "company_name",
                "task_count",
                "action_url",
            ],
            audience="transactional",
            active=True,
        )
        await comm_repo.add_template(valid_custom_tmpl)
        await db_session.flush()

        email_service = TransactionalEmailService(
            provider=MockProvider(),
            session=db_session,
            owner_id=user.id,
        )
        context = AssignmentInvitationContext(
            company_name="Acme Corp",
            trainer_name="Codruț Vacaru",
            action_url="https://app.codrut.ro/t/secure-token-123",
            task_count=2,
        )

        result = await email_service.enqueue_assignment_invitation(
            assignment,
            participant,
            context,
            leadership_invitation_template_key=custom_key,
        )
        assert result.delivery.status.value in ("queued", "accepted")

        # Verify template key and version stored on EmailSend (Amendment 5)
        send = (
            await db_session.execute(
                select(EmailSend).where(EmailSend.assignment_id == assignment.id)
            )
        ).scalar_one_or_none()
        assert send is not None
        assert send.template_key == custom_key
        assert send.template_version == 2
        assert f"Salut {participant.full_name}" in send.message_payload["subject"]
        assert "https://app.codrut.ro/t/secure-token-123" in send.message_payload["html_body"]


@pytest.mark.asyncio
async def test_update_project_template_validations():
    async with SessionLocal() as db_session:
        user = User(
            id=uuid4(),
            email=f"user_{uuid4().hex[:8]}@example.com",
            password_hash="test_password_hash",  # noqa: S106
            role=UserRole.trainer,
        )
        db_session.add(user)

        company = Company(
            id=uuid4(),
            name=f"Test Corp {uuid4().hex[:8]}",
        )
        db_session.add(company)
        membership = CompanyMembership(
            company_id=company.id,
            user_id=user.id,
            role=CompanyMembershipRole.owner,
        )
        db_session.add(membership)
        await db_session.flush()

        company_service = CompanyService(session=db_session)
        project = CompanyProject(
            company_id=company.id,
            name="Project A",
        )
        db_session.add(project)
        await db_session.flush()

        # Create one valid and one inactive template
        comm_repo = CommunicationsRepository(db_session)
        valid_key = f"valid_lead_invite_{uuid4().hex[:8]}"
        inactive_key = f"inactive_lead_invite_{uuid4().hex[:8]}"
        await comm_repo.add_template(
            EmailTemplate(
                key=valid_key,
                owner_id=user.id,
                version=1,
                subject="Invitație ${participant_name}",
                html_body="<a href=\"${action_url}\">Link</a>",
                text_body="Link: ${action_url}",
                variables=["participant_name", "action_url"],
                audience="transactional",
                active=True,
            )
        )
        await comm_repo.add_template(
            EmailTemplate(
                key=inactive_key,
                owner_id=user.id,
                version=1,
                subject="Invitație ${participant_name}",
                html_body="<a href=\"${action_url}\">Link</a>",
                text_body="Link: ${action_url}",
                variables=["participant_name", "action_url"],
                audience="transactional",
                active=False,
            )
        )
        await db_session.flush()

        # Valid update
        updated = await company_service.update_project(
            user_id=user.id,
            company_id=company.id,
            project_id=project.id,
            payload=CompanyProjectUpdateRequest(
                leadership_invitation_template_key=valid_key,
                member_invitation_template_key=None,
            ),
        )
        assert updated.leadership_invitation_template_key == valid_key
        assert updated.member_invitation_template_key is None

        # Inactive template update must fail
        with pytest.raises(DomainError) as exc_info:
            await company_service.update_project(
                user_id=user.id,
                company_id=company.id,
                project_id=project.id,
                payload=CompanyProjectUpdateRequest(
                    leadership_invitation_template_key=inactive_key,
                ),
            )
        assert exc_info.value.code in ("template_inactive", "template_not_found")


def test_invite_batch_error_messages_human_friendly():
    from codrut.modules.companies.service import _invite_batch_error_message

    # Inactive template messages by role
    msg_lead_inactive = _invite_batch_error_message("template_inactive", role_group="leadership")
    assert msg_lead_inactive == (
        "Șablonul ales pentru echipa de direcție este dezactivat. "
        "Activează-l din secțiunea Șabloane, apoi reia trimiterea."
    )

    msg_mem_inactive = _invite_batch_error_message("template_inactive", role_group="member")
    assert msg_mem_inactive == (
        "Șablonul ales pentru membrii echipei este dezactivat. "
        "Activează-l din secțiunea Șabloane, apoi reia trimiterea."
    )

    msg_gen_inactive = _invite_batch_error_message("template_inactive", role_group=None)
    assert msg_gen_inactive == (
        "Șablonul ales este dezactivat. "
        "Activează-l din secțiunea Șabloane, apoi reia trimiterea."
    )

    # Missing template
    msg_not_found = _invite_batch_error_message("template_not_found")
    assert msg_not_found == "Șablonul ales nu mai există. Alege altul din lista de la Șabloane."

    # Missing action url
    msg_no_link = _invite_batch_error_message("action_url_missing")
    assert msg_no_link == (
        "Șablonul ales nu conține butonul de acces. Fără el, destinatarii nu ar avea unde intra. "
        "Adaugă butonul și reia."
    )

    # Campaign template not allowed
    msg_campaign = _invite_batch_error_message("campaign_template_not_allowed")
    assert msg_campaign == (
        "Ai ales un șablon de campanie. "
        "Pentru invitații e nevoie de un șablon de sistem."
    )

    # Unsupported variables
    msg_unsupported = _invite_batch_error_message("unsupported_placeholders")
    assert msg_unsupported == (
        "Șablonul ales conține variabile nepermise. "
        "Verifică textul din secțiunea Șabloane și reia."
    )

    # Unknown / unexpected code fallback (informative, without misleading retry advice)
    msg_unknown = _invite_batch_error_message("some_unexpected_code")
    assert "Încearcă din nou" not in msg_unknown
    assert "Șabloane" in msg_unknown


@pytest.mark.asyncio
async def test_send_participant_invites_returns_human_friendly_error_message_on_inactive_template():
    from codrut.modules.companies.models import ProjectMembership
    from codrut.modules.companies.schemas import ParticipantInviteBatchRequest

    async with SessionLocal() as db_session:
        user, company, participant, assignment = await create_test_context(
            db_session,
            role_group="leadership",
        )
        comm_repo = CommunicationsRepository(db_session)
        inactive_key = f"inactive_{uuid4().hex[:8]}"

        await comm_repo.add_template(
            EmailTemplate(
                key=inactive_key,
                owner_id=user.id,
                version=1,
                subject="Invitație ${participant_name}",
                html_body="<a href=\"${action_url}\">Link</a>",
                text_body="Link: ${action_url}",
                variables=["participant_name", "action_url"],
                audience="transactional",
                active=False,
            )
        )
        project = CompanyProject(
            company_id=company.id,
            name="Test Project Error Msg",
            leadership_invitation_template_key=inactive_key,
        )
        db_session.add(project)
        await db_session.flush()

        assignment.project_id = project.id
        db_session.add(
            ProjectMembership(
                company_id=company.id,
                project_id=project.id,
                participant_profile_id=participant.id,
                role_group=participant.role_group,
                active=True,
            )
        )
        await db_session.flush()

        company_service = CompanyService(db_session)
        response = await company_service.send_participant_invites(
            user_id=user.id,
            company_id=company.id,
            payload=ParticipantInviteBatchRequest(
                participant_ids=[participant.id],
                mode="email",
                project_id=project.id,
                target_mode="selected",
            ),
        )

        assert response.emails_failed == 1
        assert response.emails_queued == 0
        assert len(response.results) == 1
        res = response.results[0]
        assert res.email_sent is False
        assert res.email_queued is False
        # Human friendly error message received
        assert res.error in (
            "Șablonul ales pentru echipa de direcție este dezactivat. "
            "Activează-l din secțiunea Șabloane, apoi reia trimiterea.",
            "Șablonul ales nu mai există. Alege altul din lista de la Șabloane.",
        )
