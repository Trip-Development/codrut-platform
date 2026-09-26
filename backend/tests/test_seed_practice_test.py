import pytest
from sqlalchemy import select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.companies.models import Company, CompanyProject
from codrut.modules.practice.models import (
    KnowledgePackState,
    PracticeKnowledgePack,
    PracticeProgramSettings,
    PracticeScenario,
    PracticeTheme,
    ScenarioState,
)
from codrut.tools.seed_practice_test import seed_practice_test


@pytest.mark.asyncio
async def test_seed_practice_test_refuses_when_trainer_direct_entry_disabled(monkeypatch):
    test_settings = Settings(
        generation_provider="local",
        practice_trainer_direct_entry=False,
    )
    monkeypatch.setattr("codrut.tools.seed_practice_test.get_settings", lambda: test_settings)

    with pytest.raises(RuntimeError, match="Refusing to seed practice test"):
        await seed_practice_test()


@pytest.mark.asyncio
async def test_seed_practice_test_idempotent_execution(monkeypatch):
    test_settings = Settings(
        generation_provider="local",
        practice_trainer_direct_entry=True,
    )
    monkeypatch.setattr("codrut.tools.seed_practice_test.get_settings", lambda: test_settings)

    # First run
    res1 = await seed_practice_test()
    assert res1["scenario_title"] == "Raportul de vineri netrimis"

    # Second run (idempotency check)
    res2 = await seed_practice_test()
    assert res2 == res1

    # Verify database state
    async with SessionLocal() as session:
        # Check company & project
        stmt_comp = select(Company).where(Company.name == "Companie Proba Cody")
        company = (await session.execute(stmt_comp)).scalar_one_or_none()
        assert company is not None

        stmt_proj = select(CompanyProject).where(CompanyProject.company_id == company.id)
        project = (await session.execute(stmt_proj)).scalar_one_or_none()
        assert project is not None
        assert project.name == "Exercitiu Raport Vineri"

        # Check theme & scenario
        stmt_theme = select(PracticeTheme).where(PracticeTheme.slug == "feedback")
        theme = (await session.execute(stmt_theme)).scalar_one_or_none()
        assert theme is not None

        stmt_scen = select(PracticeScenario).where(PracticeScenario.slug == "raport-vineri")
        scen = (await session.execute(stmt_scen)).scalar_one_or_none()
        assert scen is not None
        assert scen.state == ScenarioState.validated
        assert scen.roles["actor"]["name"] == "Cody"

        # Check pack
        stmt_pack = select(PracticeKnowledgePack).where(PracticeKnowledgePack.theme_id == theme.id)
        pack = (await session.execute(stmt_pack)).scalar_one_or_none()
        assert pack is not None
        assert pack.state == KnowledgePackState.approved

        # Check settings
        stmt_sett = select(PracticeProgramSettings).where(
            PracticeProgramSettings.project_id == project.id
        )
        settings_obj = (await session.execute(stmt_sett)).scalar_one_or_none()
        assert settings_obj is not None
        assert settings_obj.is_enabled is True
        assert settings_obj.max_turns_per_session == 20
        assert settings_obj.max_sessions_per_day == 5
        assert settings_obj.max_chars_per_turn == 1200
