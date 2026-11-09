"""Conversațiile goale nu se numără la limita pe zi și se refolosesc — plicul 208.

Raportul P55 (6 nov): un om a pornit 5 conversații, a vorbit numai în prima, iar limita de 5 l-a
oprit. Sesiunea deschisă trăiește numai în starea paginii, deci după reîncărcare „Începe” crea
una nouă. Acum: goala se refolosește, iar la limită se numără numai conversațiile în care omul a
scris ceva.
"""

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import PracticeSession, SessionKind
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context


async def _randuri(session, ctx) -> int:
    return (
        await session.execute(
            select(func.count(PracticeSession.id)).where(
                PracticeSession.participant_profile_id == ctx["profile"].id
            )
        )
    ).scalar_one()


async def _porneste(service, ctx, kind=SessionKind.roleplay):
    return await service.start_session(
        principal=ctx["principal"], project_id=ctx["project"].id, kind=kind
    )


async def _vorbeste(service, ctx, sesiune) -> None:
    await service.add_participant_turn(
        principal=ctx["principal"], session_id=sesiune.id, text="Replica omului, scrisă de el."
    )


def _serviciu(session, settings, redis) -> PracticeSessionService:
    return PracticeSessionService(
        session=session,
        redis=redis,
        generation_provider=LocalGenerationProvider(settings),
        settings=settings,
    )


@pytest.mark.asyncio
async def test_t1_doua_porniri_fara_replica_dau_aceeasi_sesiune() -> None:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = _serviciu(session, settings, redis)

        s1, prima1 = await _porneste(service, ctx)
        s2, prima2 = await _porneste(service, ctx)

        assert s2.id == s1.id
        assert await _randuri(session, ctx) == 1
        assert prima1 is not None and prima2 is not None
        assert prima2.id == prima1.id
        assert prima2.text == prima1.text

        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_t2_la_limita_se_numara_numai_conversatiile_cu_replica() -> None:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session, max_sessions_per_day=2)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = _serviciu(session, settings, redis)

        s1, _ = await _porneste(service, ctx)
        await _vorbeste(service, ctx, s1)

        # trei porniri goale la rând: nicio respingere, o singură conversație nouă
        goale = [(await _porneste(service, ctx))[0].id for _ in range(3)]
        assert len(set(goale)) == 1
        assert goale[0] != s1.id

        # a doua conversație cu replică merge
        s2 = await session.get(PracticeSession, goale[0])
        await _vorbeste(service, ctx, s2)

        # a treia, nouă, după ce și a doua are replică: limita
        with pytest.raises(DomainError) as exc:
            await _porneste(service, ctx)
        assert exc.value.code == "practice_daily_limit"

        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_t3_alt_tip_de_conversatie_e_alta_sesiune() -> None:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = _serviciu(session, settings, redis)

        s1, _ = await _porneste(service, ctx, SessionKind.roleplay)
        s2, _ = await _porneste(service, ctx, SessionKind.coaching)

        assert s2.id != s1.id

        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_t4_conversatia_cu_replica_nu_se_refoloseste() -> None:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = _serviciu(session, settings, redis)

        s1, _ = await _porneste(service, ctx)
        await _vorbeste(service, ctx, s1)
        s2, _ = await _porneste(service, ctx)

        assert s2.id != s1.id

        await redis.aclose()
        await session.rollback()
