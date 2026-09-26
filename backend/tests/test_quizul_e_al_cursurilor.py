"""„Verificăm cât ai reținut" e al cursurilor — plicul 128, partea E.

Hotărârea lui Andrei, 22 septembrie: *„La proiectul Michelin, partea de «verificăm cât ai
reținut» trebuie să fie inaccesibilă, la fel ca cercetare. Trebuie să fie activă doar la cursuri,
nu la team coaching, unde nu predau nimic."*

Butonul e **stins la orice proiect** până îl aprinde trainerul, iar refuzul stă în backend, nu
doar în meniu: un buton ascuns se ocolește cu o cerere scrisă de mână.
"""

from __future__ import annotations

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import PracticeProgramSettings, SessionKind
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context


async def _setari(session, ctx) -> PracticeProgramSettings:
    return (
        await session.execute(
            select(PracticeProgramSettings).where(
                PracticeProgramSettings.project_id == ctx["project"].id
            )
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_un_proiect_nou_are_quizul_stins() -> None:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        assert (await _setari(session, ctx)).quiz_enabled is False
        await session.rollback()
        del settings


@pytest.mark.asyncio
async def test_quizul_stins_e_refuzat_de_server_nu_doar_de_meniu() -> None:
    settings = Settings(generation_provider="local")
    provider = LocalGenerationProvider(settings)
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=provider, settings=settings
        )

        with pytest.raises(DomainError) as refuzul:
            await service.start_session(
                principal=ctx["principal"],
                project_id=ctx["project"].id,
                kind=SessionKind.knowledge,
            )
        assert refuzul.value.code == "quiz_not_enabled"

        await session.rollback()
        await redis.aclose()


@pytest.mark.asyncio
async def test_celelalte_doua_moduri_nu_sunt_atinse() -> None:
    """Role-play și strategie pornesc pe un proiect cu quizul stins, ca până acum."""
    settings = Settings(generation_provider="local")
    provider = LocalGenerationProvider(settings)
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=provider, settings=settings
        )

        for fel in (SessionKind.roleplay, SessionKind.coaching):
            sedinta, _ = await service.start_session(
                principal=ctx["principal"], project_id=ctx["project"].id, kind=fel
            )
            assert sedinta is not None, fel

        await session.rollback()
        await redis.aclose()


@pytest.mark.asyncio
async def test_aprins_de_trainer_quizul_porneste() -> None:
    settings = Settings(generation_provider="local")
    provider = LocalGenerationProvider(settings)
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        setari = await _setari(session, ctx)
        setari.quiz_enabled = True
        await session.flush()

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=provider, settings=settings
        )
        sedinta, _ = await service.start_session(
            principal=ctx["principal"],
            project_id=ctx["project"].id,
            kind=SessionKind.knowledge,
        )
        assert sedinta is not None

        await session.rollback()
        await redis.aclose()
