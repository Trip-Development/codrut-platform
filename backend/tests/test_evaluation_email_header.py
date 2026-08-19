from uuid import uuid4

import pytest
from sqlalchemy import select

from codrut.contracts.emails import EmailMessage, EmailProviderKey, EmailSendResult
from codrut.core.config import Settings
from codrut.core.database import SessionLocal, engine
from codrut.modules.assignments.models import AssignmentStatus, QuestionnaireAssignment
from codrut.modules.communications.models import (
    Campaign,
    CampaignRecipient,
    EmailSend,
    EmailTemplate,
)
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.service import (
    AssignmentInvitationContext,
    TransactionalEmailService,
    _render_campaign_message,
)
from codrut.modules.communications.templates import (
    EMAIL_SHELL_CLOSE,
    EMAIL_SHELL_OPEN,
    TRANSACTIONAL_EMAIL_SHELL_OPEN,
    TransactionalTemplateKey,
    get_transactional_template,
)
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    ParticipantProfile,
)
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


async def create_test_context(db_session, *, role_group: str = "member"):
    user = User(
        id=uuid4(),
        email=f"trainer_{uuid4().hex[:8]}@example.com",
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
        id=uuid4(),
        user_id=user.id,
        company_id=company.id,
        role=CompanyMembershipRole.owner,
    )
    db_session.add(membership)

    project = CompanyProject(
        id=uuid4(),
        company_id=company.id,
        name="Test Project",
    )
    db_session.add(project)

    participant = ParticipantProfile(
        id=uuid4(),
        company_id=company.id,
        full_name="Ion Popescu",
        email=f"ion_{uuid4().hex[:8]}@example.com",
        role_group=role_group,
    )
    db_session.add(participant)

    key = "icare"
    version = 10_000 + int.from_bytes(uuid4().bytes[:4], "big") % 1_000_000_000
    form = QuestionnaireDefinition(
        id=uuid4(),
        key=key,
        version=version,
        title="Chestionar Test",
        description="Synthetic test definition.",
        schema={"key": key, "version": version, "sections": []},
        feedback_policy={},
        trainer_visibility_policy={"raw_responses": "hidden"},
        content_checksum=uuid4().hex * 2,
        active=True,
    )
    db_session.add(form)
    await db_session.flush()

    assignment = QuestionnaireAssignment(
        id=uuid4(),
        company_id=company.id,
        respondent_profile_id=participant.id,
        questionnaire_key=key,
        questionnaire_definition_id=form.id,
        target_type="self",
        status=AssignmentStatus.assigned,
    )
    db_session.add(assignment)
    await db_session.commit()

    return {
        "user": user,
        "company": company,
        "project": project,
        "participant": participant,
        "assignment": assignment,
    }


@pytest.mark.asyncio
async def test_team_invitation_email_has_no_header_and_preserves_manager_signature():
    """Test 1: Email de invitație pentru echipe -> fără antet, semnătura cu manager intactă."""
    async with SessionLocal() as db_session:
        ctx = await create_test_context(db_session, role_group="member")
        comm_repo = CommunicationsRepository(db_session)

        team_template = EmailTemplate(
            id=uuid4(),
            key="evaluation_team_invite",
            version=1,
            subject="Avem nevoie de părerea ta",
            html_body=(
                TRANSACTIONAL_EMAIL_SHELL_OPEN
                + '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">'
                + "Avem nevoie de părerea ta</h1>"
                + '<p>Deschide: <a href="${action_url}">Link</a></p>'
                + "<p>Cu mulțumiri,<br />${manager_name}</p>"
                + EMAIL_SHELL_CLOSE
            ),
            text_body=(
                "Avem nevoie de părerea ta\n"
                "Link: ${action_url}\n"
                "Cu mulțumiri,\n${manager_name}"
            ),
            variables=["action_url", "manager_name"],
            audience="transactional",
            active=True,
            owner_id=ctx["user"].id,
        )
        await comm_repo.add_template(team_template)
        await db_session.commit()

        service = TransactionalEmailService(
            provider=MockProvider(),
            session=db_session,
            owner_id=ctx["user"].id,
        )
        await service.enqueue_assignment_invitation(
            assignment=ctx["assignment"],
            respondent=ctx["participant"],
            context=AssignmentInvitationContext(
                company_name=ctx["company"].name,
                trainer_name="Andrei Văcaru",
                manager_name="Zoltan Claudiu Suloman",
                action_url="https://cody.andreivacaru.ro/invite/test-token",
                task_count=1,
            ),
            member_invitation_template_key="evaluation_team_invite",
        )

        result = await db_session.execute(
            select(EmailSend).where(EmailSend.assignment_id == ctx["assignment"].id)
        )
        send_record = result.scalar_one()

        html = send_record.message_payload["html_body"]
        text = send_record.message_payload["text_body"]

        # Header is absent
        assert "text-transform:uppercase" not in html
        assert "letter-spacing:.08em" not in html
        assert "letter-spacing:0.08em" not in html
        assert "Andrei Văcaru" not in html

        # Manager signature is intact
        assert "Zoltan Claudiu Suloman" in html
        assert "Cu mulțumiri," in html
        assert "Cu mulțumiri,\nZoltan Claudiu Suloman" in text

        # Shell frame is intact
        assert "font-family:Inter" in html
        assert "border:1px solid #eadfdb" in html
        assert html.endswith("</div></div>")


@pytest.mark.asyncio
async def test_leadership_invitation_email_has_no_header():
    """Test 2: Email de invitație pentru conducere -> fără antet, restul neschimbat."""
    async with SessionLocal() as db_session:
        ctx = await create_test_context(db_session, role_group="leadership")
        comm_repo = CommunicationsRepository(db_session)

        leadership_template = EmailTemplate(
            id=uuid4(),
            key="evaluation_leadership_invite",
            version=1,
            subject="Primul pas pe drumul nostru",
            html_body=(
                TRANSACTIONAL_EMAIL_SHELL_OPEN
                + '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">'
                + "Radiografia echipei</h1>"
                + '<p>Deschide: <a href="${action_url}">Link</a></p>'
                + EMAIL_SHELL_CLOSE
            ),
            text_body="Radiografia echipei\nLink: ${action_url}",
            variables=["action_url"],
            audience="transactional",
            active=True,
            owner_id=ctx["user"].id,
        )
        await comm_repo.add_template(leadership_template)
        await db_session.commit()

        service = TransactionalEmailService(
            provider=MockProvider(),
            session=db_session,
            owner_id=ctx["user"].id,
        )
        await service.enqueue_assignment_invitation(
            assignment=ctx["assignment"],
            respondent=ctx["participant"],
            context=AssignmentInvitationContext(
                company_name=ctx["company"].name,
                trainer_name="Andrei Văcaru",
                action_url="https://cody.andreivacaru.ro/invite/test-token",
                task_count=1,
            ),
            leadership_invitation_template_key="evaluation_leadership_invite",
        )

        result = await db_session.execute(
            select(EmailSend).where(EmailSend.assignment_id == ctx["assignment"].id)
        )
        send_record = result.scalar_one()

        html = send_record.message_payload["html_body"]

        # Header is absent
        assert "text-transform:uppercase" not in html
        assert "Andrei Văcaru" not in html
        assert "Radiografia echipei" in html
        assert "font-family:Inter" in html
        assert "border:1px solid #eadfdb" in html


@pytest.mark.asyncio
async def test_reminder_emails_have_no_header():
    """Test 3: Email de reminder, ambele roluri -> la fel, fără antet."""
    async with SessionLocal() as db_session:
        ctx = await create_test_context(db_session, role_group="member")
        comm_repo = CommunicationsRepository(db_session)

        reminder_template = EmailTemplate(
            id=uuid4(),
            key="evaluation_team_reminder",
            version=1,
            subject="Mai e puțin timp",
            html_body=(
                TRANSACTIONAL_EMAIL_SHELL_OPEN
                + '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">'
                + "Reminder Evaluare</h1>"
                + '<p>Deschide: <a href="${action_url}">Link</a></p>'
                + "<p>Cu mulțumiri,<br />${manager_name}</p>"
                + EMAIL_SHELL_CLOSE
            ),
            text_body=(
                "Reminder Evaluare\n"
                "Link: ${action_url}\n"
                "Cu mulțumiri,\n${manager_name}"
            ),
            variables=["action_url", "manager_name"],
            audience="transactional",
            active=True,
            owner_id=ctx["user"].id,
        )
        await comm_repo.add_template(reminder_template)
        await db_session.commit()

        service = TransactionalEmailService(
            provider=MockProvider(),
            session=db_session,
            owner_id=ctx["user"].id,
        )
        await service.enqueue_assignment_invitation(
            assignment=ctx["assignment"],
            respondent=ctx["participant"],
            context=AssignmentInvitationContext(
                company_name=ctx["company"].name,
                trainer_name="Andrei Văcaru",
                manager_name="Veronica Grecu",
                action_url="https://cody.andreivacaru.ro/invite/test-token",
                task_count=1,
            ),
            reminder_assignment_ids=[ctx["assignment"].id],
            member_reminder_template_key="evaluation_team_reminder",
        )

        result = await db_session.execute(
            select(EmailSend).where(EmailSend.assignment_id == ctx["assignment"].id)
        )
        send_record = result.scalar_one()

        html = send_record.message_payload["html_body"]

        assert "text-transform:uppercase" not in html
        assert "Andrei Văcaru" not in html
        assert "Veronica Grecu" in html
        assert "Reminder Evaluare" in html


def test_campaign_email_preserves_uppercase_header():
    """Test 4: Email de campanie / promovare -> antetul APARE neschimbat."""
    campaign = Campaign(
        id=uuid4(),
        owner_id=uuid4(),
        name="Campanie Test",
        subject="Departamentul de Reconectări",
        html_body="<p>Bună ziua, avem o ofertă pentru voi.</p>",
        text_body="Bună ziua, avem o ofertă pentru voi.",
    )
    recipient = CampaignRecipient(
        id=uuid4(),
        owner_id=campaign.owner_id,
        email="contact@example.com",
        contact_name="Client Test",
        organization_name="Companie Client",
    )
    settings = Settings(
        _env_file=None,
        frontend_url="https://cody.andreivacaru.ro",
    )

    msg = _render_campaign_message(
        campaign=campaign,
        recipient=recipient,
        unsubscribe_url="https://cody.andreivacaru.ro/unsubscribe/test-token",
        settings=settings,
    )

    # Header MUST appear in campaign emails
    assert "Andrei Văcaru" in msg.html_body
    assert "Dezabonare" in msg.html_body
    assert "font-family:Inter" in msg.html_body


def test_code_fallback_templates_have_no_header():
    """Test 5: Cele trei șabloane de rezervă din cod -> antetul nu mai apare."""
    for key in (
        TransactionalTemplateKey.account_setup,
        TransactionalTemplateKey.assignment_bundle,
        TransactionalTemplateKey.assignment_reminder,
    ):
        tmpl = get_transactional_template(key)
        assert "text-transform:uppercase" not in tmpl.html_body
        assert "letter-spacing:.08em" not in tmpl.html_body
        assert '<p style="margin:0 0 8px;font-size:13px;' not in tmpl.html_body
        assert "Andrei Văcaru</p>" not in tmpl.html_body


def test_non_regression_email_shell_frame():
    """Test 6: Test de non-regresie care demonstrează că restul ramei e neschimbat."""
    # Transactional shell
    assert "font-family:Inter,Arial,sans-serif;" in TRANSACTIONAL_EMAIL_SHELL_OPEN
    assert "border:1px solid #eadfdb;" in TRANSACTIONAL_EMAIL_SHELL_OPEN
    assert "Andrei Văcaru" not in TRANSACTIONAL_EMAIL_SHELL_OPEN

    # Promotional shell
    assert "font-family:Inter,Arial,sans-serif;" in EMAIL_SHELL_OPEN
    assert "border:1px solid #eadfdb;" in EMAIL_SHELL_OPEN
    assert "Andrei Văcaru" in EMAIL_SHELL_OPEN


@pytest.mark.asyncio
async def test_resaved_evaluation_template_stores_no_header_in_db():
    """Test 7: Confirmare că un șablon de evaluare salvat din nou nu mai conține antetul."""
    async with SessionLocal() as db_session:
        ctx = await create_test_context(db_session, role_group="member")
        comm_repo = CommunicationsRepository(db_session)

        # Simulating saving a template with the updated transactional shell
        resaved_html_body = (
            TRANSACTIONAL_EMAIL_SHELL_OPEN
            + '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">'
            + "Invitație Actualizată</h1>"
            + "<p>Bună ${participant_name}, te invităm să completezi chestionarul.</p>"
            + '<p><a href="${action_url}">Deschide chestionarul</a></p>'
            + "<p>Cu mulțumiri,<br />${manager_name}</p>"
            + EMAIL_SHELL_CLOSE
        )

        template = EmailTemplate(
            id=uuid4(),
            key="evaluation_team_invite_resaved",
            version=2,
            subject="Invitație nouă",
            html_body=resaved_html_body,
            text_body="Invitație nouă\nLink: ${action_url}\nCu mulțumiri,\n${manager_name}",
            variables=["participant_name", "action_url", "manager_name"],
            audience="transactional",
            active=True,
            owner_id=ctx["user"].id,
        )
        await comm_repo.add_template(template)
        await db_session.commit()

        # Read back from database
        stored = await comm_repo.get_template(template.key, owner_id=ctx["user"].id)
        assert stored is not None
        assert "text-transform:uppercase" not in stored.html_body
        assert "Andrei Văcaru" not in stored.html_body
        assert "font-family:Inter" in stored.html_body
        assert "border:1px solid #eadfdb" in stored.html_body
        assert "${manager_name}" in stored.html_body
