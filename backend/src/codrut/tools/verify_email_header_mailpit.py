import asyncio
import os
import sys
import time
from uuid import uuid4

import httpx

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleStatus,
    AssignmentStatus,
    QuestionnaireAssignment,
)
from codrut.modules.communications.models import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientMembership,
    CampaignRecipientSegment,
    CampaignRecipientStatus,
    CampaignStatus,
    EmailTemplate,
)
from codrut.modules.communications.schemas import CampaignSendRequest
from codrut.modules.communications.service import CommunicationsService
from codrut.modules.communications.templates import (
    EMAIL_SHELL_CLOSE,
    TRANSACTIONAL_EMAIL_SHELL_OPEN,
)
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.companies.schemas import ParticipantInviteBatchRequest
from codrut.modules.companies.service import CompanyService
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.modules.identity.models import User, UserRole


def _mailpit_api_url() -> str:
    return os.getenv("CODRUT_MAILPIT_API_URL", "http://mailpit:8025").rstrip("/")


async def run_mailpit_proof() -> None:
    settings = get_settings()
    if settings.is_production:
        print("ERROR: Refusing to run Mailpit proof in production.")
        sys.exit(1)

    print("=" * 70)
    print("DOVADĂ LOCALĂ PRIN MAILPIT: ELIMINARE ANTET EMAIL EVALUĂRI")
    print("=" * 70)

    run_id = uuid4().hex[:6]

    async with SessionLocal() as db_session:
        print(f"\n[0] Configurare date de test pentru rularea {run_id}...")

        # 1. Create Trainer User
        trainer_user = User(
            id=uuid4(),
            email=f"trainer.header.{run_id}@example.com",
            password_hash=hash_password("SuperSecretPass123!"),
            role=UserRole.trainer,
        )
        db_session.add(trainer_user)

        # 2. Create Company, Project, Cycle, Participants
        company = Company(
            id=uuid4(),
            name=f"Companie Test Antet {run_id}",
        )
        db_session.add(company)
        await db_session.flush()

        membership = CompanyMembership(
            id=uuid4(),
            user_id=trainer_user.id,
            company_id=company.id,
            role=CompanyMembershipRole.owner,
        )
        db_session.add(membership)

        project = CompanyProject(
            id=uuid4(),
            company_id=company.id,
            name=f"Proiect Evaluare {run_id}",
            status=CompanyProjectStatus.active,
            member_invitation_template_key="evaluation_team_invite",
            leadership_invitation_template_key="evaluation_leadership_invite",
        )
        db_session.add(project)
        await db_session.flush()

        cycle = AssessmentCycle(
            id=uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="Ciclul 1",
            status=AssessmentCycleStatus.active,
        )
        db_session.add(cycle)

        # Team member: with manager name in ProjectMembership
        team_member = ParticipantProfile(
            id=uuid4(),
            company_id=company.id,
            full_name="Ana Ionescu",
            email=f"ana.ionescu+{run_id}@example.com",
            role_group="member",
        )
        db_session.add(team_member)

        # Leadership member
        leadership_member = ParticipantProfile(
            id=uuid4(),
            company_id=company.id,
            full_name="Mihai Director",
            email=f"mihai.director+{run_id}@example.com",
            role_group="leadership",
        )
        db_session.add(leadership_member)
        await db_session.flush()

        # ProjectMemberships
        pm_team = ProjectMembership(
            id=uuid4(),
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=team_member.id,
            reports_to_name="Zoltan Claudiu Suloman",
            role_group="member",
        )
        db_session.add(pm_team)

        pm_lead = ProjectMembership(
            id=uuid4(),
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=leadership_member.id,
            role_group="leadership",
        )
        db_session.add(pm_lead)

        # 3. Create Questionnaire Definition & Assignments
        form_key = f"icare_header_{run_id}"
        form = QuestionnaireDefinition(
            id=uuid4(),
            key=form_key,
            version=1,
            title="Evaluare iCARE",
            description="Evaluare echipă",
            schema={"key": form_key, "version": 1, "sections": []},
            feedback_policy={},
            trainer_visibility_policy={"raw_responses": "hidden"},
            content_checksum=uuid4().hex * 2,
            active=True,
        )
        db_session.add(form)
        await db_session.flush()

        team_assignment = QuestionnaireAssignment(
            id=uuid4(),
            company_id=company.id,
            project_id=project.id,
            assessment_cycle_id=cycle.id,
            respondent_profile_id=team_member.id,
            questionnaire_key=form.key,
            questionnaire_definition_id=form.id,
            target_type="self",
            status=AssignmentStatus.assigned,
        )
        db_session.add(team_assignment)

        lead_assignment = QuestionnaireAssignment(
            id=uuid4(),
            company_id=company.id,
            project_id=project.id,
            assessment_cycle_id=cycle.id,
            respondent_profile_id=leadership_member.id,
            questionnaire_key=form.key,
            questionnaire_definition_id=form.id,
            target_type="self",
            status=AssignmentStatus.assigned,
        )
        db_session.add(lead_assignment)

        # 4. Custom Templates in DB saved with the new TRANSACTIONAL_EMAIL_SHELL_OPEN
        # (without uppercase header)
        team_invite_template = EmailTemplate(
            id=uuid4(),
            key="evaluation_team_invite",
            version=2,
            subject="Invitație evaluare echipă",
            html_body=(
                TRANSACTIONAL_EMAIL_SHELL_OPEN
                + '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">'
                + "Invitație Echipă</h1>"
                + "<p>Bună ${participant_name}, te rugăm să completezi chestionarul.</p>"
                + '<p><a href="${action_url}" style="background:#890505;color:#fff;'
                + 'padding:12px 18px;text-decoration:none;border-radius:8px;">Deschide</a></p>'
                + "<p>Cu mulțumiri,<br />${manager_name}</p>"
                + EMAIL_SHELL_CLOSE
            ),
            text_body=(
                "Bună ${participant_name},\n"
                "Deschide: ${action_url}\n"
                "Cu mulțumiri,\n${manager_name}"
            ),
            variables=["participant_name", "action_url", "manager_name"],
            audience="transactional",
            active=True,
            owner_id=trainer_user.id,
        )
        db_session.add(team_invite_template)

        lead_invite_template = EmailTemplate(
            id=uuid4(),
            key="evaluation_leadership_invite",
            version=2,
            subject="Invitație evaluare conducere",
            html_body=(
                TRANSACTIONAL_EMAIL_SHELL_OPEN
                + '<h1 style="margin:0 0 16px;font-size:24px;line-height:1.25;">'
                + "Radiografia Conducerii</h1>"
                + "<p>Bună ${participant_name}, accesează platforma.</p>"
                + '<p><a href="${action_url}" style="background:#890505;color:#fff;'
                + 'padding:12px 18px;text-decoration:none;border-radius:8px;">Deschide</a></p>'
                + EMAIL_SHELL_CLOSE
            ),
            text_body="Bună ${participant_name},\nDeschide: ${action_url}",
            variables=["participant_name", "action_url"],
            audience="transactional",
            active=True,
            owner_id=trainer_user.id,
        )
        db_session.add(lead_invite_template)

        # 5. Create Campaign + Recipient
        campaign = Campaign(
            id=uuid4(),
            owner_id=trainer_user.id,
            name=f"Campanie Promovare {run_id}",
            subject="Noutăți și Programe Noi",
            html_body="<p>Stimate client, vă prezentăm noul nostru program de training.</p>",
            text_body="Stimate client, vă prezentăm noul nostru program de training.",
            status=CampaignStatus.ready,
        )
        db_session.add(campaign)
        await db_session.flush()

        recipient = CampaignRecipient(
            id=uuid4(),
            owner_id=trainer_user.id,
            email=f"client.contact+{run_id}@example.com",
            contact_name="Client Important",
            organization_name="Client SRL",
            segment=CampaignRecipientSegment.potential_customer,
            status=CampaignRecipientStatus.active,
        )
        db_session.add(recipient)
        await db_session.flush()

        membership = CampaignRecipientMembership(
            campaign_id=campaign.id,
            recipient_id=recipient.id,
        )
        db_session.add(membership)
        await db_session.commit()

        # 6. Send evaluation invitations via CompanyService
        company_service = CompanyService(db_session)
        print("\n[1] Trimitere invitații evaluare (echipe & conducere)...")
        batch_res = await company_service.send_participant_invites(
            user_id=trainer_user.id,
            company_id=company.id,
            payload=ParticipantInviteBatchRequest(
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                participant_ids=[team_member.id, leadership_member.id],
                mode="email",
            ),
        )
        print(
            f"  - Rezultat creare invitații: total={batch_res.total}, "
            f"queued={batch_res.emails_queued}"
        )

        # 7. Send campaign email via CommunicationsService
        campaign_service = CommunicationsService(db_session)
        print("\n[2] Trimitere email campanie...")
        camp_res = await campaign_service.send_campaign(
            campaign_id=campaign.id,
            payload=CampaignSendRequest(mode="all"),
            settings=settings,
            owner_id=trainer_user.id,
        )
        print(
            f"  - Rezultat trimitere campanie: total={camp_res.total}, "
            f"queued={camp_res.queued}, sent={camp_res.sent}"
        )
        await db_session.commit()

        # 8. Drain outbox to Mailpit SMTP
        from codrut.workers.main import process_email_outbox

        print("\n[3] Procesare outbox (livrare SMTP către Mailpit)...")
        drain_result = await process_email_outbox({})
        print(f"  - Rezultat procesare outbox: {drain_result}")

    # 9. Verify in Mailpit via HTTP API
    print(f"\n[4] Interogare Mailpit API la {_mailpit_api_url()}...")
    time.sleep(1.0)  # Wait for SMTP delivery

    async with httpx.AsyncClient(base_url=_mailpit_api_url(), timeout=10.0) as client:
        res = await client.get("/api/v1/messages")
        res.raise_for_status()
        messages_data = res.json().get("messages", [])

        checks = [
            {
                "type": "Invitație Echipe",
                "recipient": team_member.email,
                "name": team_member.full_name,
                "should_have_header": False,
                "expected_signature": "Zoltan Claudiu Suloman",
            },
            {
                "type": "Invitație Conducere",
                "recipient": leadership_member.email,
                "name": leadership_member.full_name,
                "should_have_header": False,
                "expected_signature": None,
            },
            {
                "type": "Email Campanie / Promovare",
                "recipient": recipient.email,
                "name": "Client Important",
                "should_have_header": True,
                "expected_signature": None,
            },
        ]

        all_passed = True
        print("\n" + "=" * 70)
        print("VERIFICARE REZULTATE ÎN MAILPIT")
        print("=" * 70)

        for check in checks:
            matching = [
                m
                for m in messages_data
                if any(
                    check["recipient"].lower() in to_obj.get("Address", "").lower()
                    for to_obj in m.get("To", [])
                )
            ]

            if not matching:
                print(f"\n[FAIL] Nu s-a găsit niciun mesaj în Mailpit pentru {check['recipient']}")
                all_passed = False
                continue

            msg_id = matching[0]["ID"]
            msg_res = await client.get(f"/api/v1/message/{msg_id}")
            msg_res.raise_for_status()
            msg_full = msg_res.json()

            html_body = msg_full.get("HTML", "")
            text_body = msg_full.get("Text", "")
            subject = msg_full.get("Subject", "")

            has_uppercase_header = (
                "text-transform:uppercase" in html_body
                or "letter-spacing:0.08em" in html_body
                or "letter-spacing:.08em" in html_body
            )
            has_andrei_vacaru = "Andrei Văcaru" in html_body or "ANDREI VĂCARU" in html_body

            print(f"\n--- Tip Email: {check['type']} ---")
            print(f"  Destinatar: {check['recipient']}")
            print(f"  Subiect: {subject}")
            print(f"  Mailpit ID: {msg_id}")

            # Header verification
            if check["should_have_header"]:
                if has_andrei_vacaru:
                    print(
                        "  [PASS] Antetul 'Andrei Văcaru' este PREZENT "
                        "(așa cum se cere pentru campanii)."
                    )
                else:
                    print("  [FAIL] Antetul 'Andrei Văcaru' LIPSEȘTE de pe emailul de campanie!")
                    all_passed = False
            else:
                is_clean = not has_uppercase_header and not (
                    has_andrei_vacaru and "Cu mulțumiri" not in html_body
                )
                if is_clean:
                    print(
                        "  [PASS] Antetul 'Andrei Văcaru' a fost ELIMINAT "
                        "cu succes de pe emailul de evaluare."
                    )
                else:
                    print("  [FAIL] Antetul 'Andrei Văcaru' încă apare pe emailul de evaluare!")
                    all_passed = False

            # Signature verification
            if check["expected_signature"]:
                sig = check["expected_signature"]
                if sig in html_body and sig in text_body:
                    print(f"  [PASS] Semnătura cu managerul '{sig}' este PREZENTĂ și intactă.")
                else:
                    print(f"  [FAIL] Semnătura cu managerul '{sig}' lipsește sau e alterată!")
                    all_passed = False

            # Shell frame verification
            if "font-family:Inter" in html_body and "border:1px solid #eadfdb" in html_body:
                print("  [PASS] Rama emailului (shell, border, typography) este intactă.")
            else:
                print("  [FAIL] Rama emailului este deteriorată!")
                all_passed = False

            # Print HTML extract
            print("\n  Extras HTML din mesajul recepționat în Mailpit:")
            print("  " + "-" * 50)
            for line in html_body.splitlines()[:15]:
                print(f"    {line}")
            if len(html_body.splitlines()) > 15:
                print("    ...")
            print("  " + "-" * 50)

        print("\n" + "=" * 70)
        if all_passed:
            print("REZULTAT DOVADĂ MAILPIT: TOATE CELE 3 CONFIRMATE CU SUCCES!")
        else:
            print("REZULTAT DOVADĂ MAILPIT: UNELE VERIFICĂRI AU EȘUAT!")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_mailpit_proof())
