from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from codrut.contracts.emails import EmailMessage, EmailProviderKey, EmailSendResult
from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleStatus,
    AssignmentStatus,
    QuestionnaireAssignment,
)
from codrut.modules.communications.models import EmailSend, EmailTemplate
from codrut.modules.communications.repository import CommunicationsRepository
from codrut.modules.communications.service import (
    AssignmentInvitationContext,
    TransactionalEmailService,
)
from codrut.modules.companies.manager_matching import manager_reference_key
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.companies.schemas import (
    CompanyProjectUpdateRequest,
    ParticipantInviteBatchRequest,
)
from codrut.modules.companies.service import (
    CompanyService,
    _resolve_participant_manager_name,
)
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.modules.identity.models import User, UserRole


class MockProvider:
    key = EmailProviderKey.test

    def __init__(self):
        self.sent_messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> EmailSendResult:
        self.sent_messages.append(message)
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
        password_hash="test_password_hash",
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


def test_manager_name_resolves_to_canonical_project_participant():
    manager_profile = ParticipantProfile(
        id=uuid4(),
        company_id=uuid4(),
        full_name="Ioan-Gabriel Brândușan",
        email="gabriel@example.com",
    )
    membership = ProjectMembership(
        id=uuid4(),
        project_id=uuid4(),
        company_id=manager_profile.company_id,
        participant_profile_id=uuid4(),
        reports_to_name="Ioan-GabrielBrandusan",
        active=True,
    )
    project_participants_by_key = {
        manager_reference_key(manager_profile.full_name): manager_profile
    }

    result = _resolve_participant_manager_name(
        membership=membership,
        project_participants_by_key=project_participants_by_key,
        duplicate_name_keys=set(),
        fallback_trainer_name="Andrei Văcaru",
    )
    assert result == "Ioan-Gabriel Brândușan"


def test_manager_name_unresolved_uses_cleaned_raw_text():
    membership = ProjectMembership(
        id=uuid4(),
        project_id=uuid4(),
        company_id=uuid4(),
        participant_profile_id=uuid4(),
        reports_to_name="   Manager Extern Nespecificat   ",
        active=True,
    )

    result = _resolve_participant_manager_name(
        membership=membership,
        project_participants_by_key={},
        duplicate_name_keys=set(),
        fallback_trainer_name="Andrei Văcaru",
    )
    assert result == "Manager Extern Nespecificat"


def test_manager_name_missing_or_top_level_falls_back_to_trainer_name():
    trainer = "Andrei Văcaru"
    for placeholder_value in [None, "", "   ", "fara manager", "top", "direct manager", "root", "na", "-"]:
        membership = (
            ProjectMembership(
                id=uuid4(),
                project_id=uuid4(),
                company_id=uuid4(),
                participant_profile_id=uuid4(),
                reports_to_name=placeholder_value,
                active=True,
            )
            if placeholder_value is not None
            else None
        )
        result = _resolve_participant_manager_name(
            membership=membership,
            project_participants_by_key={},
            duplicate_name_keys=set(),
            fallback_trainer_name=trainer,
        )
        assert result == trainer
        assert result != ""
        assert result is not None


def test_manager_name_profile_only_ignored_in_favor_of_trainer():
    """
    Cerință explicită de produs de la Andrei: 'Ce vede Andrei pe ecran, aia semnează.'
    Organigrama din aplicație (_project_participant_response, companies/service.py) citește
    exclusiv din ProjectMembership.reports_to_name, fără niciun fallback pe profilul general.
    Dacă un participant are manager setat pe ParticipantProfile, dar la nivel de proiect (ProjectMembership)
    este fără manager (None) sau lipsește ProjectMembership, organigrama îl arată fără manager.
    Prin urmare, emailul NU trebuie să folosească managerul din profil, ci trebuie să cadă pe trainer_name.
    """
    trainer = "Andrei Văcaru"
    # Cazul 1: Are ProjectMembership dar cu reports_to_name = None (deși profilul ar avea manager)
    membership_no_manager = ProjectMembership(
        id=uuid4(),
        project_id=uuid4(),
        company_id=uuid4(),
        participant_profile_id=uuid4(),
        reports_to_name=None,
        active=True,
    )
    result_with_empty_membership = _resolve_participant_manager_name(
        membership=membership_no_manager,
        project_participants_by_key={},
        duplicate_name_keys=set(),
        fallback_trainer_name=trainer,
    )
    assert result_with_empty_membership == trainer

    # Cazul 2: Nu are deloc ProjectMembership (membership is None)
    result_without_membership = _resolve_participant_manager_name(
        membership=None,
        project_participants_by_key={},
        duplicate_name_keys=set(),
        fallback_trainer_name=trainer,
    )
    assert result_without_membership == trainer


def test_manager_name_duplicate_ambiguous_keeps_cleaned_raw_text():
    """
    Dacă un nume de manager este duplicat/ambiguu în rosterul proiectului (două persoane cu același nume normalizat),
    nu se alege un participant arbitrar în tăcere, ci se păstrează textul brut curățat.
    """
    membership = ProjectMembership(
        id=uuid4(),
        project_id=uuid4(),
        company_id=uuid4(),
        participant_profile_id=uuid4(),
        reports_to_name="Radu Popescu",
        active=True,
    )
    duplicate_keys = {manager_reference_key("Radu Popescu")}
    result = _resolve_participant_manager_name(
        membership=membership,
        project_participants_by_key={},
        duplicate_name_keys=duplicate_keys,
        fallback_trainer_name="Andrei Văcaru",
    )
    assert result == "Radu Popescu"


@pytest.mark.asyncio
async def test_enqueue_assignment_invitation_renders_manager_name():
    async with SessionLocal() as db_session:
        user, _company, participant, assignment = await create_test_context(
            db_session, role_group="member"
        )
        comm_repo = CommunicationsRepository(db_session)
        custom_key = f"custom_tmpl_{uuid4().hex[:8]}"
        tmpl = EmailTemplate(
            key=custom_key,
            owner_id=user.id,
            version=1,
            subject="Salut ${participant_name} de la ${manager_name}",
            html_body="<p>Managerul tău: ${manager_name}. <a href=\"${action_url}\">Deschide</a></p>",
            text_body="Managerul tău: ${manager_name}. Deschide: ${action_url}",
            variables=["participant_name", "manager_name", "action_url"],
            audience="transactional",
            active=True,
        )
        await comm_repo.add_template(tmpl)
        await db_session.flush()

        email_service = TransactionalEmailService(
            provider=MockProvider(),
            session=db_session,
            owner_id=user.id,
        )
        context = AssignmentInvitationContext(
            company_name="Test Company",
            trainer_name="Andrei Văcaru",
            manager_name="Frederic Cauquil",
            action_url="https://cody.andreivacaru.ro/invite/token-123",
            task_count=1,
        )

        result = await email_service.enqueue_assignment_invitation(
            assignment,
            participant,
            context,
            member_invitation_template_key=custom_key,
        )
        assert result.delivery.status.value in ("queued", "accepted")

        send = (
            await db_session.execute(
                select(EmailSend).where(EmailSend.assignment_id == assignment.id)
            )
        ).scalar_one_or_none()
        assert send is not None
        assert send.message_payload["subject"] == f"Salut {participant.full_name} de la Frederic Cauquil"
        assert "Managerul tău: Frederic Cauquil." in send.message_payload["html_body"]

        await db_session.execute(delete(EmailSend).where(EmailSend.id == send.id))
        await db_session.commit()


@pytest.mark.asyncio
async def test_existing_template_without_manager_name_renders_identically():
    async with SessionLocal() as db_session:
        user, _company, participant, assignment = await create_test_context(
            db_session, role_group="leadership"
        )
        email_service = TransactionalEmailService(
            provider=MockProvider(),
            session=db_session,
            owner_id=user.id,
        )
        context = AssignmentInvitationContext(
            company_name="Test Company",
            trainer_name="Andrei Văcaru",
            action_url="https://cody.andreivacaru.ro/invite/token-123",
            task_count=1,
        )
        result = await email_service.enqueue_assignment_invitation(
            assignment,
            participant,
            context,
        )
        assert result.delivery.status.value in ("queued", "accepted")
        send = (
            await db_session.execute(
                select(EmailSend).where(EmailSend.assignment_id == assignment.id)
            )
        ).scalar_one_or_none()
        assert send is not None
        assert "${manager_name}" not in send.message_payload["subject"]
        assert "${manager_name}" not in send.message_payload["html_body"]


@pytest.mark.asyncio
async def test_project_template_validation_accepts_manager_name():
    async with SessionLocal() as db_session:
        user = User(
            id=uuid4(),
            email=f"trainer_{uuid4().hex[:8]}@example.com",
            password_hash="test_pwd",
            role=UserRole.trainer,
        )
        db_session.add(user)
        company = Company(id=uuid4(), name=f"Company {uuid4().hex[:8]}")
        db_session.add(company)
        await db_session.flush()

        db_session.add(
            CompanyMembership(
                company_id=company.id,
                user_id=user.id,
                role=CompanyMembershipRole.owner,
            )
        )
        project = CompanyProject(
            id=uuid4(),
            company_id=company.id,
            name="Project Valid",
            status=CompanyProjectStatus.active,
        )
        db_session.add(project)
        await db_session.flush()

        comm_repo = CommunicationsRepository(db_session)
        valid_tmpl_key = f"tmpl_valid_{uuid4().hex[:8]}"
        valid_tmpl = EmailTemplate(
            key=valid_tmpl_key,
            owner_id=user.id,
            version=1,
            subject="Invitație de la ${manager_name} pentru ${participant_name}",
            html_body="<p>Manager: ${manager_name} la ${company_name}. <a href=\"${action_url}\">Click</a></p>",
            text_body="Manager: ${manager_name} la ${company_name}. Link: ${action_url}",
            variables=["participant_name", "manager_name", "company_name", "action_url"],
            audience="transactional",
            active=True,
        )
        await comm_repo.add_template(valid_tmpl)
        await db_session.flush()

        service = CompanyService(db_session)
        updated_project = await service.update_project(
            user_id=user.id,
            company_id=company.id,
            project_id=project.id,
            payload=CompanyProjectUpdateRequest(
                member_invitation_template_key=valid_tmpl_key,
            ),
        )
        assert updated_project.member_invitation_template_key == valid_tmpl_key

        invalid_tmpl_key = f"tmpl_invalid_{uuid4().hex[:8]}"
        invalid_tmpl = EmailTemplate(
            key=invalid_tmpl_key,
            owner_id=user.id,
            version=1,
            subject="Subiect invalid ${hacked_var}",
            html_body="<p>Corp invalid ${hacked_var} ${action_url}</p>",
            text_body="Corp invalid ${hacked_var} ${action_url}",
            variables=["hacked_var", "action_url"],
            audience="transactional",
            active=True,
        )
        await comm_repo.add_template(invalid_tmpl)
        await db_session.flush()

        with pytest.raises(DomainError) as exc_info:
            await service.update_project(
                user_id=user.id,
                company_id=company.id,
                project_id=project.id,
                payload=CompanyProjectUpdateRequest(
                    member_invitation_template_key=invalid_tmpl_key,
                ),
            )
        assert exc_info.value.code == "email_template_unsupported_variables"


@pytest.mark.asyncio
async def test_company_service_send_invitations_end_to_end_manager_resolution():
    async with SessionLocal() as db_session:
        user = User(
            id=uuid4(),
            email="andrei.vacaru@example.com",
            password_hash="test_pwd",
            role=UserRole.trainer,
        )
        db_session.add(user)
        company = Company(id=uuid4(), name=f"Company E2E {uuid4().hex[:8]}")
        db_session.add(company)
        await db_session.flush()

        db_session.add(CompanyMembership(company_id=company.id, user_id=user.id, role=CompanyMembershipRole.owner))
        project = CompanyProject(
            id=uuid4(),
            company_id=company.id,
            name="Project E2E",
            status=CompanyProjectStatus.active,
        )
        db_session.add(project)
        await db_session.flush()

        cycle = AssessmentCycle(
            id=uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="Cycle 1",
            status=AssessmentCycleStatus.active,
        )
        db_session.add(cycle)
        await db_session.flush()

        # 4 participants
        titus = ParticipantProfile(
            id=uuid4(),
            company_id=company.id,
            full_name="Titus Botis",
            email="titus@example.com",
            reports_to_name="fara manager",
            role_group="leadership",
        )
        frederic = ParticipantProfile(
            id=uuid4(),
            company_id=company.id,
            full_name="Frederic Cauquil",
            email="frederic@example.com",
            reports_to_name="Titus Botis",
            role_group="leadership",
        )
        remy = ParticipantProfile(
            id=uuid4(),
            company_id=company.id,
            full_name="Remy Bedu",
            email="remy@example.com",
            reports_to_name="FredericCauquil",
            role_group="leadership",
        )
        ioana = ParticipantProfile(
            id=uuid4(),
            company_id=company.id,
            full_name="Ioana Pop",
            email="ioana@example.com",
            reports_to_name="Manager Necunoscut",
            role_group="member",
        )
        for p in [titus, frederic, remy, ioana]:
            db_session.add(p)

        db_session.add(ProjectMembership(id=uuid4(), project_id=project.id, company_id=company.id, participant_profile_id=titus.id, reports_to_name="fara manager", active=True))
        db_session.add(ProjectMembership(id=uuid4(), project_id=project.id, company_id=company.id, participant_profile_id=frederic.id, reports_to_name="Titus Botis", active=True))
        db_session.add(ProjectMembership(id=uuid4(), project_id=project.id, company_id=company.id, participant_profile_id=remy.id, reports_to_name="FredericCauquil", active=True))
        db_session.add(ProjectMembership(id=uuid4(), project_id=project.id, company_id=company.id, participant_profile_id=ioana.id, reports_to_name="Manager Necunoscut", active=True))

        key = "icare"
        definition = QuestionnaireDefinition(
            id=uuid4(),
            key=key,
            version=1,
            title="ICARE",
            description="ICARE",
            schema={"key": key, "version": 1, "sections": []},
            feedback_policy={},
            trainer_visibility_policy={"raw_responses": "hidden"},
            content_checksum=uuid4().hex * 2,
            active=True,
        )
        db_session.add(definition)
        await db_session.flush()

        for p in [titus, frederic, remy, ioana]:
            db_session.add(QuestionnaireAssignment(
                id=uuid4(),
                company_id=company.id,
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                respondent_profile_id=p.id,
                questionnaire_key=key,
                questionnaire_definition_id=definition.id,
                target_type="self",
                status=AssignmentStatus.assigned,
            ))

        comm_repo = CommunicationsRepository(db_session)
        tmpl_key = f"e2e_tmpl_{uuid4().hex[:8]}"
        tmpl = EmailTemplate(
            key=tmpl_key,
            owner_id=user.id,
            version=1,
            subject="Invitatie pentru ${participant_name} de la ${manager_name}",
            html_body="<p>Managerul tau: ${manager_name}. <a href=\"${action_url}\">Deschide</a></p>",
            text_body="Managerul tau: ${manager_name}. Deschide: ${action_url}",
            variables=["participant_name", "manager_name", "action_url"],
            audience="transactional",
            active=True,
        )
        await comm_repo.add_template(tmpl)
        project.member_invitation_template_key = tmpl_key
        project.leadership_invitation_template_key = tmpl_key
        await db_session.flush()

        service = CompanyService(db_session)
        batch_res = await service.send_participant_invites(
            user_id=user.id,
            company_id=company.id,
            payload=ParticipantInviteBatchRequest(
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                participant_ids=[titus.id, frederic.id, remy.id, ioana.id],
                mode="email",
            ),
        )
        assert len(batch_res.results) == 4
        assert batch_res.emails_queued == 4 or batch_res.emails_sent == 4

        # Verify each rendered email send in database
        target_emails = ["remy@example.com", "frederic@example.com", "ioana@example.com", "titus@example.com"]
        sends = (
            await db_session.execute(
                select(EmailSend).where(EmailSend.recipient_email.in_(target_emails)).order_by(EmailSend.created_at.desc())
            )
        ).scalars().all()
        sends_by_email = {s.recipient_email: s for s in sends}

        # 1. Remy -> manager resolves to Frederic Cauquil (canonical)
        assert "Frederic Cauquil" in sends_by_email["remy@example.com"].message_payload["subject"]
        assert "Managerul tau: Frederic Cauquil." in sends_by_email["remy@example.com"].message_payload["html_body"]

        # 2. Frederic -> manager resolves to Titus Botis (canonical)
        assert "Titus Botis" in sends_by_email["frederic@example.com"].message_payload["subject"]
        assert "Managerul tau: Titus Botis." in sends_by_email["frederic@example.com"].message_payload["html_body"]

        # 3. Ioana -> manager is unresolvable "Manager Necunoscut" -> raw cleaned string
        assert "Manager Necunoscut" in sends_by_email["ioana@example.com"].message_payload["subject"]
        assert "Managerul tau: Manager Necunoscut." in sends_by_email["ioana@example.com"].message_payload["html_body"]

        # 4. Titus -> top level without manager -> falls back to trainer "andrei.vacaru"
        assert "andrei.vacaru" in sends_by_email["titus@example.com"].message_payload["subject"]
        assert "Managerul tau: andrei.vacaru." in sends_by_email["titus@example.com"].message_payload["html_body"]

        # Clean up test sends
        send_ids = [s.id for s in sends]
        if send_ids:
            await db_session.execute(delete(EmailSend).where(EmailSend.id.in_(send_ids)))
            await db_session.commit()
