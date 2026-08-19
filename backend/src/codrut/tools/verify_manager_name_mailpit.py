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
from codrut.modules.communications.models import EmailTemplate
from codrut.modules.communications.repository import CommunicationsRepository
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
    print("DOVADĂ LOCALĂ PRIN MAILPIT: VARIABILA manager_name")
    print("=" * 70)

    run_id = uuid4().hex[:6]
    test_domain = "example.com"

    async with SessionLocal() as db_session:
        # 1. Create Trainer user
        trainer_user = User(
            id=uuid4(),
            email=f"andrei.vacaru+{run_id}@codrut.ro",
            password_hash=hash_password("trainer-password-123"),
            role=UserRole.trainer,
        )
        db_session.add(trainer_user)

        # 2. Create Test Company and Project
        company = Company(
            id=uuid4(),
            name=f"Companie Pilot Test {run_id}",
        )
        db_session.add(company)
        await db_session.flush()

        db_session.add(
            CompanyMembership(
                company_id=company.id,
                user_id=trainer_user.id,
                role=CompanyMembershipRole.owner,
            )
        )
        project = CompanyProject(
            id=uuid4(),
            company_id=company.id,
            name=f"Proiect Evaluare {run_id}",
            status=CompanyProjectStatus.active,
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
        await db_session.flush()

        # 3. Create 4 Participants representing all hierarchy scenarios
        frederic = ParticipantProfile(
            id=uuid4(),
            company_id=company.id,
            full_name="Frederic Cauquil",
            email=f"frederic.cauquil+{run_id}@{test_domain}",
            reports_to_name="Titus Botis",
            role_group="leadership",
        )
        remy = ParticipantProfile(
            id=uuid4(),
            company_id=company.id,
            full_name="Remy Bedu",
            email=f"remy.bedu+{run_id}@{test_domain}",
            reports_to_name="FredericCauquil",
            role_group="leadership",
        )
        ioana = ParticipantProfile(
            id=uuid4(),
            company_id=company.id,
            full_name="Ioana Pop",
            email=f"ioana.pop+{run_id}@{test_domain}",
            reports_to_name="   Manager Necunoscut Extern   ",
            role_group="member",
        )
        titus = ParticipantProfile(
            id=uuid4(),
            company_id=company.id,
            full_name="Titus Botis",
            email=f"titus.botis+{run_id}@{test_domain}",
            reports_to_name="fara manager",
            role_group="leadership",
        )

        participants = [frederic, remy, ioana, titus]
        for p in participants:
            db_session.add(p)

        db_session.add(
            ProjectMembership(
                id=uuid4(),
                project_id=project.id,
                company_id=company.id,
                participant_profile_id=frederic.id,
                reports_to_name="Titus Botis",
                active=True,
            )
        )
        db_session.add(
            ProjectMembership(
                id=uuid4(),
                project_id=project.id,
                company_id=company.id,
                participant_profile_id=remy.id,
                reports_to_name="FredericCauquil",
                active=True,
            )
        )
        db_session.add(
            ProjectMembership(
                id=uuid4(),
                project_id=project.id,
                company_id=company.id,
                participant_profile_id=ioana.id,
                reports_to_name="   Manager Necunoscut Extern   ",
                active=True,
            )
        )
        db_session.add(
            ProjectMembership(
                id=uuid4(),
                project_id=project.id,
                company_id=company.id,
                participant_profile_id=titus.id,
                reports_to_name="fara manager",
                active=True,
            )
        )

        # Create questionnaire definition and assignments
        key = f"icare_proof_{run_id}"
        definition = QuestionnaireDefinition(
            id=uuid4(),
            key=key,
            version=1,
            title="ICARE Proof",
            description="Chestionar test pentru dovada locală.",
            schema={"key": key, "version": 1, "sections": []},
            feedback_policy={},
            trainer_visibility_policy={"raw_responses": "hidden"},
            content_checksum=uuid4().hex * 2,
            active=True,
        )
        db_session.add(definition)
        await db_session.flush()

        for p in participants:
            db_session.add(
                QuestionnaireAssignment(
                    id=uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    assessment_cycle_id=cycle.id,
                    respondent_profile_id=p.id,
                    questionnaire_key=key,
                    questionnaire_definition_id=definition.id,
                    target_type="self",
                    status=AssignmentStatus.assigned,
                )
            )

        # 4. Create custom template using ${manager_name}
        comm_repo = CommunicationsRepository(db_session)
        tmpl_key = f"invitation_manager_proof_{run_id}"
        tmpl = EmailTemplate(
            key=tmpl_key,
            owner_id=trainer_user.id,
            version=1,
            subject="Invitație evaluare pentru ${participant_name} [semnat: ${manager_name}]",
            html_body=(
                "<div>"
                "<p>Salut <strong>${participant_name}</strong>,</p>"
                "<p>Ai fost invitat să completezi evaluarea pentru ${company_name}.</p>"
                "<p>Pentru întrebări, te rugăm să iei legătura cu managerul tău direct: "
                "<strong>${manager_name}</strong>.</p>"
                '<p><a href="${action_url}">Deschide chestionarele</a></p>'
                "<p>Cu stimă,<br />${manager_name}</p>"
                "</div>"
            ),
            text_body=(
                "Salut ${participant_name},\n\n"
                "Ai fost invitat să completezi evaluarea pentru ${company_name}.\n"
                "Manager direct: ${manager_name}\n"
                "Link: ${action_url}\n\n"
                "Cu stimă,\n${manager_name}"
            ),
            variables=["participant_name", "manager_name", "company_name", "action_url"],
            audience="transactional",
            active=True,
        )
        await comm_repo.add_template(tmpl)
        project.member_invitation_template_key = tmpl_key
        project.leadership_invitation_template_key = tmpl_key
        await db_session.flush()

        print("\n[1] Configurare proiect test creată:")
        print(f"  - ID Companie: {company.id}")
        print(f"  - ID Proiect: {project.id}")
        print(f"  - Șablon utilizat: {tmpl_key} (conține ${{manager_name}})")
        print("  - Participanți:")
        print(f"    * {frederic.full_name} ({frederic.email}) -> reports_to: 'Titus Botis'")
        print(f"    * {remy.full_name} ({remy.email}) -> reports_to: 'FredericCauquil'")
        print(f"    * {ioana.full_name} ({ioana.email}) -> reports_to: 'Manager Necunoscut Extern'")
        print(f"    * {titus.full_name} ({titus.email}) -> reports_to: 'fara manager' (top level)")

        # 5. Dispatch invitations
        print("\n[2] Trimitere invitații prin CompanyService.send_participant_invites...")
        service = CompanyService(db_session)
        batch_res = await service.send_participant_invites(
            user_id=trainer_user.id,
            company_id=company.id,
            payload=ParticipantInviteBatchRequest(
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                participant_ids=[p.id for p in participants],
                mode="email",
            ),
        )
        await db_session.commit()

        print(
            f"  - Rezultat creare invitații: total={batch_res.total}, "
            f"emails_sent={batch_res.emails_sent}, emails_queued={batch_res.emails_queued}"
        )

        # Drain outbox to Mailpit SMTP
        from codrut.workers.main import process_email_outbox

        print("\n[2.1] Procesare outbox (trimitere SMTP către Mailpit)...")
        drain_result = await process_email_outbox({})
        print(f"  - Rezultat procesare outbox: {drain_result}")

    # 6. Verify in Mailpit via HTTP API
    print(f"\n[3] Interogare Mailpit API la {_mailpit_api_url()}...")
    time.sleep(1.0)  # Wait for SMTP delivery

    async with httpx.AsyncClient(base_url=_mailpit_api_url(), timeout=10.0) as client:
        res = await client.get("/api/v1/messages")
        res.raise_for_status()
        messages_data = res.json().get("messages", [])

        expected_checks = [
            {
                "recipient": remy.email,
                "name": remy.full_name,
                "scenario": "Manager real din proiect (FredericCauquil -> Frederic Cauquil)",
                "expected_manager": "Frederic Cauquil",
            },
            {
                "recipient": frederic.email,
                "name": frederic.full_name,
                "scenario": "Manager real din proiect (Titus Botis)",
                "expected_manager": "Titus Botis",
            },
            {
                "recipient": ioana.email,
                "name": ioana.full_name,
                "scenario": "Manager extern nerezolvabil (text brut curățat)",
                "expected_manager": "Manager Necunoscut Extern",
            },
            {
                "recipient": titus.email,
                "name": titus.full_name,
                "scenario": "Fără manager / top-level (fallback la trainer)",
                "expected_manager": trainer_user.email.split("@", 1)[0],
            },
        ]

        print("\n" + "=" * 70)
        print("VERIFICARE MESAJE RECEPTIONATE ÎN MAILPIT")
        print("=" * 70)

        all_passed = True
        for check in expected_checks:
            matched_msg = None
            for msg in messages_data:
                to_addresses = [item.get("Address", "").lower() for item in msg.get("To", [])]
                if check["recipient"].lower() in to_addresses:
                    matched_msg = msg
                    break

            if not matched_msg:
                print(f"\n[FAIL] Nu s-a găsit niciun mesaj în Mailpit pentru {check['recipient']}")
                all_passed = False
                continue

            msg_id = matched_msg["ID"]
            detail_res = await client.get(f"/api/v1/message/{msg_id}")
            detail_res.raise_for_status()
            detail = detail_res.json()

            subject = detail.get("Subject", "")
            html_content = detail.get("HTML", "")
            text_content = detail.get("Text", "")

            expected_mgr = check["expected_manager"]
            in_subject = expected_mgr in subject
            in_html = expected_mgr in html_content
            in_text = expected_mgr in text_content

            status = "VERIFIED [OK]" if (in_subject and in_html and in_text) else "FAIL"
            if status == "FAIL":
                all_passed = False

            print(f"\nScenariu: {check['scenario']}")
            print(f"  Destinatar: {check['name']} <{check['recipient']}>")
            print(f"  Mailpit Message ID: {msg_id}")
            print(f"  Subiect primit: {subject}")
            print(f"  Manager așteptat: {expected_mgr}")
            print(f"  Prezent în Subiect: {in_subject} | HTML: {in_html} | Text: {in_text}")
            print(f"  Semnătură extrasă din corp: '{expected_mgr}'")
            print(f"  Verdict: {status}")

    print("\n" + "=" * 70)
    if all_passed:
        print("REZULTAT DOVADĂ MAILPIT: TOATE CELE 4 MESAJE AU FOST CONFIRMATE CU SUCCES!")
    else:
        print("REZULTAT DOVADĂ MAILPIT: UNELE VERIFICĂRI AU EȘUAT!")
    print("=" * 70)


def main():
    asyncio.run(run_mailpit_proof())


if __name__ == "__main__":
    main()
