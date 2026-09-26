import asyncio
import os
import uuid
from decimal import Decimal

from sqlalchemy import select

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User
from codrut.modules.practice.models import (
    KnowledgePackState,
    PracticeKnowledgePack,
    PracticeProgramSettings,
    PracticeScenario,
    PracticeTheme,
    ProgramMode,
    ScenarioState,
)


async def seed_practice_test() -> dict[str, str]:
    settings = get_settings()
    if not settings.practice_trainer_direct_entry:
        raise RuntimeError(
            "Refusing to seed practice test: practice_trainer_direct_entry is disabled in settings."
        )

    company_name = os.getenv("CODRUT_PRACTICE_TEST_COMPANY_NAME", "Companie Proba Cody").strip()
    project_name = os.getenv("CODRUT_PRACTICE_TEST_PROJECT_NAME", "Exercitiu Raport Vineri").strip()
    theme_slug = "feedback"
    scenario_slug = "raport-vineri"

    async with SessionLocal() as session:
        # 1. Company
        stmt_comp = select(Company).where(Company.name == company_name)
        company = (await session.execute(stmt_comp)).scalar_one_or_none()
        if company is None:
            company = Company(id=uuid.uuid4(), name=company_name)
            session.add(company)
            await session.flush()

        # 2. CompanyProject
        stmt_proj = (
            select(CompanyProject)
            .where(CompanyProject.company_id == company.id)
            .where(CompanyProject.name == project_name)
        )
        project = (await session.execute(stmt_proj)).scalar_one_or_none()
        if project is None:
            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name=project_name,
                status=CompanyProjectStatus.active,
                description="Proiect dedicat probelor de conversație cu Cody",
            )
            session.add(project)
            await session.flush()
        else:
            project.status = CompanyProjectStatus.active

        # 3. PracticeTheme
        stmt_theme = select(PracticeTheme).where(PracticeTheme.slug == theme_slug)
        theme = (await session.execute(stmt_theme)).scalar_one_or_none()
        if theme is None:
            theme = PracticeTheme(
                id=uuid.uuid4(),
                slug=theme_slug,
                name="Conversații de Feedback",
                description="Tema de exersare a conversațiilor de feedback direct și aliniere",
                is_active=True,
            )
            session.add(theme)
            await session.flush()
        else:
            theme.is_active = True

        # 4. PracticeKnowledgePack
        stmt_pack = (
            select(PracticeKnowledgePack)
            .where(PracticeKnowledgePack.theme_id == theme.id)
            .where(PracticeKnowledgePack.version == 1)
        )
        pack = (await session.execute(stmt_pack)).scalar_one_or_none()
        if pack is None:
            pack = PracticeKnowledgePack(
                id=uuid.uuid4(),
                theme_id=theme.id,
                version=1,
                state=KnowledgePackState.approved,
                checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                manifest={"title": "Pachet de Bază Feedback", "version": "1.0"},
                content_uri="memory://pack-feedback-v1",
                word_count=500,
            )
            session.add(pack)
            await session.flush()
        else:
            pack.state = KnowledgePackState.approved

        # 5. PracticeScenario (Andrei's opening #5)
        stmt_scen = (
            select(PracticeScenario)
            .where(PracticeScenario.theme_id == theme.id)
            .where(PracticeScenario.slug == scenario_slug)
            .where(PracticeScenario.version == 1)
        )
        scenario = (await session.execute(stmt_scen)).scalar_one_or_none()
        if scenario is None:
            scenario = PracticeScenario(
                id=uuid.uuid4(),
                theme_id=theme.id,
                slug=scenario_slug,
                title="Raportul de vineri netrimis",
                version=1,
                state=ScenarioState.validated,
                difficulty=2,
                shared_brief=(
                    "Andrei este managerul care a cerut raportul de vineri, iar Cody este "
                    "omul din echipă care nu l-a predat la termen. Scopul conversației este "
                    "clarificarea motivelor, alinierea responsabilității și stabilirea unui "
                    "termen ferm de livrare."
                ),
                roles={
                    "participant": {
                        "name": "Andrei",
                        "role": "Manager direct",
                    },
                    "actor": {
                        "name": "Cody",
                        "role": "Membru echipă",
                        "opening_line": (
                            "Bună Andrei, am văzut că ai vrut să vorbim despre raportul de vineri."
                        ),
                    },
                },
                exits={
                    "success": "S-a agreat o nouă dată fermă și asumarea responsabilității.",
                    "abandon": "Conversația a fost întreruptă fără un plan concret.",
                },
                criteria={
                    "fapte_concrete": "Referire la termenul ratat fără etichetări generale",
                    "responsabilitate_50_50": "Păstrarea responsabilității pe livrabil",
                    "plan_actiune": "Stabilirea unui termen și a pașilor următori",
                },
                debrief_questions=[
                    "Cum a răspuns Cody când ai adus în discuție termenul ratat?",
                    "Ce ai fi putut face diferit pentru a obține un angajament mai ferm?",
                ],
                max_turns=20,
            )
            session.add(scenario)
            await session.flush()
        else:
            scenario.state = ScenarioState.validated

        # 6. PracticeProgramSettings
        stmt_sett = select(PracticeProgramSettings).where(
            PracticeProgramSettings.project_id == project.id
        )
        prog_sett = (await session.execute(stmt_sett)).scalar_one_or_none()
        if prog_sett is None:
            prog_sett = PracticeProgramSettings(
                id=uuid.uuid4(),
                project_id=project.id,
                mode=ProgramMode.training,
                theme_id=theme.id,
                active_pack_id=pack.id,
                is_enabled=True,
                max_turns_per_session=20,
                max_sessions_per_day=5,
                max_chars_per_turn=1200,
                turn_retention_days=30,
                usd_cap_per_participant=Decimal("3.00"),
            )
            session.add(prog_sett)
        else:
            prog_sett.is_enabled = True
            prog_sett.mode = ProgramMode.training
            prog_sett.theme_id = theme.id
            prog_sett.active_pack_id = pack.id
            prog_sett.max_turns_per_session = 20
            prog_sett.max_sessions_per_day = 5
            prog_sett.max_chars_per_turn = 1200
            prog_sett.usd_cap_per_participant = Decimal("3.00")

        # 7. Trainer profile and project membership
        trainer_email = (
            os.getenv("CODRUT_SEED_TRAINER_EMAIL", "andrei@andreivacaru.ro").strip().lower()
        )
        stmt_user = select(User).where(User.email == trainer_email)
        user = (await session.execute(stmt_user)).scalar_one_or_none()
        if user is not None:
            stmt_prof = select(ParticipantProfile).where(
                ParticipantProfile.company_id == company.id,
                ParticipantProfile.email == trainer_email,
            )
            profile = (await session.execute(stmt_prof)).scalar_one_or_none()
            if profile is None:
                profile = ParticipantProfile(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    user_id=user.id,
                    full_name="Andrei Vacaru",
                    email=trainer_email,
                )
                session.add(profile)
                await session.flush()

            stmt_mem = select(ProjectMembership).where(
                ProjectMembership.project_id == project.id,
                ProjectMembership.participant_profile_id == profile.id,
            )
            membership = (await session.execute(stmt_mem)).scalar_one_or_none()
            if membership is None:
                membership = ProjectMembership(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=profile.id,
                    active=True,
                )
                session.add(membership)
            else:
                membership.active = True

        await session.commit()

    summary = {
        "company_id": str(company.id),
        "company_name": company.name,
        "project_id": str(project.id),
        "project_name": project.name,
        "theme_id": str(theme.id),
        "pack_id": str(pack.id),
        "scenario_id": str(scenario.id),
        "scenario_title": scenario.title,
    }
    print("Seeded practice test environment successfully:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return summary


def main() -> None:
    asyncio.run(seed_practice_test())


if __name__ == "__main__":
    main()
