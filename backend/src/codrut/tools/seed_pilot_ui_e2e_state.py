import asyncio
import os
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.core.security import hash_password
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User, UserRole
from codrut.tools.local_preview import assert_local_preview_allowed


async def seed_pilot_ui_e2e_state() -> None:
    assert_local_preview_allowed(get_settings())
    run_id = os.getenv("CODRUT_E2E_PILOT_RUN_ID", uuid.uuid4().hex[:8])
    company_name = f"E2E Pilot UI Company {run_id}"
    project_name = f"E2E Pilot UI Project {run_id}"

    trainer_email = os.getenv("CODRUT_SEED_TRAINER_EMAIL", "trainer@example.com").lower()
    trainer_password = os.getenv(
        "CODRUT_SEED_TRAINER_PASSWORD",
        "replace-with-a-long-test-password",
    )
    participant_email_domain = f"{run_id}.pilot-ui.example.com"

    async with SessionLocal() as session:
        old_companies = await session.execute(
            select(Company).where(Company.name.like("E2E Pilot UI Company %"))
        )
        for company in old_companies.scalars().all():
            await session.delete(company)
        await session.commit()

        await session.execute(delete(User).where(User.email.like(f"%@{participant_email_domain}")))

        trainer_result = await session.execute(select(User).where(User.email == trainer_email))
        trainer = trainer_result.scalar_one_or_none()
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

        company = Company(id=uuid.uuid4(), name=company_name)
        session.add(company)
        await session.flush()

        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name=project_name,
            description="Project-scoped pilot UI E2E workflow coverage.",
            project_type="pilot_ui_e2e",
            status=CompanyProjectStatus.active,
            starts_at=datetime(2026, 7, 2, tzinfo=UTC),
            due_at=datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC),
            form_opens_at=datetime(2026, 7, 2, tzinfo=UTC),
            form_closes_at=datetime(2026, 7, 31, 23, 59, 59, tzinfo=UTC),
        )
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

        roster = [
            ("Alex Dima QA", None, "Director general", "Leadership"),
            ("Mara Ionescu QA", "Alex Dima QA", "Manager operațional", "Leadership"),
            ("Sorin Pavel QA", "Alex Dima QA", "Manager comercial", "Leadership"),
            ("Diana Luca QA", "Mara Ionescu QA", "Specialist HR", "Membru"),
            ("Tudor Stan QA", "Mara Ionescu QA", "Consultant intern", "Membru"),
            ("Ioana Rusu QA", "Sorin Pavel QA", "Analist vânzări", "Membru"),
        ]

        for full_name, reports_to_name, position, role_group in roster:
            email = (
                full_name.lower()
                .replace(" ", ".")
                .replace("ă", "a")
                .replace("â", "a")
                .replace("î", "i")
                .replace("ș", "s")
                .replace("ț", "t")
            )
            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name=full_name,
                email=f"{email}@{participant_email_domain}",
                reports_to_name=reports_to_name,
                position=position,
                location="București",
                role_group=role_group,
                pcm_profile=None,
                pcm_base=None,
                pcm_phase=None,
            )
            session.add(profile)
            await session.flush()

            session.add(
                ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=profile.id,
                    reports_to_name=reports_to_name,
                    position=position,
                    location=profile.location,
                    role_group=role_group,
                    active=True,
                )
            )

        await session.commit()

    print(f"Run ID: {run_id}")
    print(f"Company ID: {company.id}")
    print(f"Company Name: {company_name}")
    print(f"Project ID: {project.id}")
    print(f"Project Name: {project_name}")


def main() -> None:
    asyncio.run(seed_pilot_ui_e2e_state())


if __name__ == "__main__":
    main()
