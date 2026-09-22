"""Apelul de închidere trece prin buget — plicul 129, partea E.

Găsit la plicul 128, partea G: apelul de la închidere — cel care citește tot transcriptul — **nu
avea rezervare și nu scria cost nicăieri**. Măsurat pe cinci ședințe închise: zero rezervări după
ultima replică. Deci plafonul pe participant nu-l vedea, iar costul unei ședințe ieșea mai mic
decât adevărul.

Al doilea test apără omul: dacă plafonul se atinge chiar la închidere, ședința se închide oricum.
Altfel ar apăsa butonul la nesfârșit și ar primi de fiecare dată același refuz.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import (
    BudgetReservationState,
    PracticeBudgetReservation,
    PracticeProgramSettings,
    PracticeSession,
    PracticeTurn,
    SessionKind,
    SessionState,
)
from codrut.modules.practice.service import MOTIV_PESTE_PLAFON, PracticeSessionService
from test_practice_session_flow import create_test_context


async def _o_sedinta(session, ctx, settings):
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    service = PracticeSessionService(
        session=session,
        redis=redis,
        generation_provider=LocalGenerationProvider(settings),
        settings=settings,
    )
    sedinta, _ = await service.start_session(
        principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
    )
    await service.add_participant_turn(
        principal=ctx["principal"], session_id=sedinta.id, text="Da, hai."
    )
    return service, sedinta, redis


@pytest.mark.asyncio
async def test_inchiderea_are_rezervare_si_cost() -> None:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        service, sedinta, redis = await _o_sedinta(session, ctx, settings)

        def _rezervari():
            return (
                select(PracticeBudgetReservation)
                .where(PracticeBudgetReservation.session_id == sedinta.id)
                .order_by(PracticeBudgetReservation.created_at)
            )

        inainte = (await session.execute(_rezervari())).scalars().all()
        replici_inainte = len(
            (
                await session.execute(
                    select(PracticeTurn).where(PracticeTurn.session_id == sedinta.id)
                )
            ).scalars().all()
        )

        await service.end_session(principal=ctx["principal"], session_id=sedinta.id)

        dupa = (await session.execute(_rezervari())).scalars().all()
        assert len(dupa) == len(inainte) + 1, "închiderea nu și-a luat rezervarea ei"

        a_inchiderii = dupa[-1]
        assert a_inchiderii.state == BudgetReservationState.settled
        assert a_inchiderii.actual_usd is not None, "costul închiderii nu s-a scris nicăieri"

        # rezervarea e a închiderii, nu a unei replici: numărul de replici n-a crescut
        replici_dupa = len(
            (
                await session.execute(
                    select(PracticeTurn).where(PracticeTurn.session_id == sedinta.id)
                )
            ).scalars().all()
        )
        assert replici_dupa == replici_inainte

        await session.rollback()
        await redis.aclose()


@pytest.mark.asyncio
async def test_plafonul_atins_la_inchidere_nu_blocheaza_sedinta() -> None:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        service, sedinta, redis = await _o_sedinta(session, ctx, settings)

        # plafonul se închide CHIAR înainte de închidere
        setari = (
            await session.execute(
                select(PracticeProgramSettings).where(
                    PracticeProgramSettings.project_id == ctx["project"].id
                )
            )
        ).scalar_one()
        setari.usd_cap_per_participant = Decimal("0.00")
        await session.flush()

        sedinta_inchisa, rezumat = await service.end_session(
            principal=ctx["principal"], session_id=sedinta.id
        )

        assert sedinta_inchisa.state == SessionState.closed, "omul a rămas cu ședința deschisă"
        assert rezumat is None

        proaspata = (
            await session.execute(
                select(PracticeSession).where(PracticeSession.id == sedinta.id)
            )
        ).scalar_one()
        assert proaspata.ended_at is not None

        from codrut.modules.practice.models import PracticeOutcome

        rezultat = (
            await session.execute(
                select(PracticeOutcome).where(PracticeOutcome.session_id == sedinta.id)
            )
        ).scalars().first()
        assert rezultat is not None
        assert rezultat.note == MOTIV_PESTE_PLAFON

        await session.rollback()
        await redis.aclose()
