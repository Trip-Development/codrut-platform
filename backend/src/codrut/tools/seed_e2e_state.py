import asyncio
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
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
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.modules.identity.models import AssignmentInvite, User, UserRole
from codrut.modules.identity.service import IdentityService
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.protected_content.package import canonical_checksum
from codrut.tools.local_preview import (
    PREVIEW_DEFINITION_VERSION,
    assert_local_preview_allowed,
    build_preview_questionnaire_definitions,
)

E2E_QUESTIONNAIRE_KEYS = ("distress_drivers", "lencioni")


async def _ensure_e2e_questionnaire_definitions(
    session: AsyncSession,
) -> dict[str, QuestionnaireDefinition]:
    previews = {
        definition.key: definition
        for definition in build_preview_questionnaire_definitions()
        if definition.key in E2E_QUESTIONNAIRE_KEYS
    }
    persisted: dict[str, QuestionnaireDefinition] = {}

    for key in E2E_QUESTIONNAIRE_KEYS:
        existing = (
            await session.execute(
                select(QuestionnaireDefinition).where(
                    QuestionnaireDefinition.key == key,
                    QuestionnaireDefinition.version == PREVIEW_DEFINITION_VERSION,
                    QuestionnaireDefinition.system_managed.is_(False),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            persisted[key] = existing
            continue

        preview = previews[key]
        content = {
            "key": preview.key,
            "version": PREVIEW_DEFINITION_VERSION,
            "title": preview.title,
            "description": preview.description,
            "schema": preview.schema,
            "feedback_policy": preview.feedback_policy,
            "trainer_visibility_policy": {},
        }
        definition = QuestionnaireDefinition(
            id=uuid.uuid4(),
            **content,
            content_checksum=canonical_checksum(content),
            system_managed=False,
            active=True,
        )
        session.add(definition)
        persisted[key] = definition

    await session.flush()
    return persisted


async def seed_e2e_state() -> None:
    settings = get_settings()
    assert_local_preview_allowed(settings)
    company_name = "E2E Test Company"

    async with SessionLocal() as session:
        questionnaire_definitions = await _ensure_e2e_questionnaire_definitions(session)

        # 1. Clean up old E2E Test Company data and users if exists
        test_emails = [
            "alice.popescu@example.com",
            "bob.ionescu@example.com",
            "charlie.vasilescu@example.com",
            "participant@example.com",
        ]
        await session.execute(delete(User).where(User.email.in_(test_emails)))
        await session.commit()

        stmt = select(Company).where(Company.name == company_name)
        result = await session.execute(stmt)
        old_company = result.scalar_one_or_none()
        if old_company is not None:
            # SQLAlchemy will cascade delete or we can delete manually
            # Delete assignments linked to old participants
            p_stmt = select(ParticipantProfile).where(
                ParticipantProfile.company_id == old_company.id
            )
            p_result = await session.execute(p_stmt)
            p_ids = [p.id for p in p_result.scalars().all()]
            if p_ids:
                await session.execute(
                    delete(QuestionnaireAssignment).where(
                        QuestionnaireAssignment.respondent_profile_id.in_(p_ids)
                    )
                )
                await session.execute(
                    delete(AssignmentInvite).where(
                        AssignmentInvite.respondent_profile_id.in_(p_ids)
                    )
                )
                await session.execute(
                    delete(ParticipantProfile).where(
                        ParticipantProfile.company_id == old_company.id
                    )
                )
            await session.delete(old_company)
            await session.commit()

        # 2. Create the company
        company = Company(id=uuid.uuid4(), name=company_name)
        session.add(company)
        await session.flush()

        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name="E2E Leadership Project",
            description="Project-scoped E2E workflow coverage.",
            project_type="leadership_program",
            status=CompanyProjectStatus.active,
        )
        session.add(project)
        await session.flush()

        # 2.5 Ensure and link the E2E trainer account used by Playwright.
        trainer_email = os.getenv("CODRUT_SEED_TRAINER_EMAIL", "trainer@example.com").lower()
        trainer_password = os.getenv(
            "CODRUT_SEED_TRAINER_PASSWORD",
            "replace-with-a-long-test-password",
        )
        t_stmt = select(User).where(User.email == trainer_email)
        t_result = await session.execute(t_stmt)
        trainer = t_result.scalar_one_or_none()
        if trainer is None:
            trainer = User(
                id=uuid.uuid4(),
                email=trainer_email,
                password_hash=hash_password(trainer_password),
                role=UserRole.trainer,
            )
            session.add(trainer)
        else:
            trainer.password_hash = hash_password(trainer_password)
            trainer.role = UserRole.trainer

        await session.flush()
        membership = CompanyMembership(
            id=uuid.uuid4(),
            company_id=company.id,
            user_id=trainer.id,
            role=CompanyMembershipRole.owner,
        )
        session.add(membership)
        await session.flush()

        # 3. Create three participants
        participants_data = [
            {
                "name": "Participant Demo",
                "email": "participant@example.com",
                "pcm": "Gânditor",
                "pcm_base": "Gânditor",
                "pcm_phase": "Perseverent",
                "anonymous_name": "CuriousSoap2121",
                "with_account": True,
            },
            {
                "name": "Alice Popescu",
                "email": "alice.popescu@example.com",
                "pcm": "Thinker",
                "pcm_base": "Gânditor",
                "pcm_phase": "Gânditor",
                "anonymous_name": "BrightCedar3184",
                "with_account": False,
            },
            {
                "name": "Bob Ionescu",
                "email": "bob.ionescu@example.com",
                "pcm": "Persister",
                "pcm_base": "Perseverent",
                "pcm_phase": "Promotor",
                "anonymous_name": "CalmHarbor5271",
                "with_account": False,
            },
            {
                "name": "Charlie Vasilescu",
                "email": "charlie.vasilescu@example.com",
                "pcm": "Harmonizer",
                "pcm_base": "Empatic",
                "pcm_phase": "Imaginator",
                "anonymous_name": "WarmSignal8032",
                "with_account": False,
            },
        ]

        identity_service = IdentityService(session)

        print("--- SEEDED E2E PARTICIPANTS ---")
        print(f"Project ID: {project.id}")
        for p_data in participants_data:
            user_id = None
            if p_data["with_account"]:
                demo_password = os.getenv(
                    "CODRUT_SEED_DEMO_PARTICIPANT_PASSWORD",
                    "replace-with-a-long-test-password",
                )
                demo_user = User(
                    id=uuid.uuid4(),
                    email=p_data["email"],
                    password_hash=hash_password(demo_password),
                    role=UserRole.participant,
                    terms_accepted_at=datetime.now(UTC),
                    terms_version=CURRENT_TERMS_VERSION,
                )
                session.add(demo_user)
                await session.flush()
                user_id = demo_user.id

            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user_id,
                full_name=p_data["name"],
                email=p_data["email"],
                reports_to_name=None,
                position="Member",
                location="Bucharest",
                pcm_profile=p_data["pcm"],
                pcm_base=p_data["pcm_base"],
                pcm_phase=p_data["pcm_phase"],
                anonymous_name=p_data["anonymous_name"],
            )
            session.add(profile)
            await session.flush()

            session.add(
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=profile.id,
                    reports_to_name=profile.reports_to_name,
                    position=profile.position,
                    location=profile.location,
                    role_group=profile.role_group,
                )
            )
            await session.flush()

            # Create Distress Drivers Assignment
            distress_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=profile.id,
                questionnaire_key="distress_drivers",
                questionnaire_definition_id=questionnaire_definitions["distress_drivers"].id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.assigned,
            )
            session.add(distress_assignment)
            await session.flush()

            # Create Lencioni Assignment
            lencioni_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=profile.id,
                questionnaire_key="lencioni",
                questionnaire_definition_id=questionnaire_definitions["lencioni"].id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.assigned,
            )
            session.add(lencioni_assignment)
            await session.flush()

            # Create Invite
            invite = await identity_service.create_invite(
                company_id=company.id,
                respondent_profile_id=profile.id,
                assignment_ids=[distress_assignment.id, lencioni_assignment.id],
                force_rotate=True,
            )

            # Update assignment status to invited
            distress_assignment.status = AssignmentStatus.invited
            lencioni_assignment.status = AssignmentStatus.invited

            invite_url = build_task_url(invite.token, settings)
            print(f"{p_data['name']} ({p_data['email']}): {invite_url}")

        await session.commit()
        print("-------------------------------")


def main() -> None:
    asyncio.run(seed_e2e_state())


if __name__ == "__main__":
    main()
