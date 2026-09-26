"""Omul primește toate schimburile plătite — plicul 123, partea A.

Hotărârea lui Andrei, 20 septembrie: **salutul nu se numără** printre cele 10 schimburi.

Până azi se număra: replica de deschidere, generată la pornire, creștea `turn_count`, iar poarta
compara `turn_count >= max_turns_per_session`. Cu plafonul pus pe 10, al zecelea mesaj al omului
îi închidea ședința fără răspuns — tăcut, fără ca cineva să afle de ce.

Al doilea test apără pasul de pornire de la plicul 119: reparația de aici n-a avut voie să-l miște,
și nu l-a mișcat.
"""

from __future__ import annotations

import pytest
from redis.asyncio import Redis

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import (
    OutcomeKind,
    PracticeOutcome,
    PracticeTurn,
    SessionKind,
    SessionState,
    TurnRole,
)
from codrut.modules.practice.prompts import REPLICA_DE_CONFIRMARE
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context


@pytest.mark.asyncio
async def test_omul_primeste_toate_schimburile_platite() -> None:
    """Cu plafonul pe 3, omul primește 3 răspunsuri; al patrulea mesaj închide ședința."""
    from sqlalchemy import func, select

    settings = Settings(generation_provider="local")
    provider = LocalGenerationProvider(settings)

    async with SessionLocal() as session:
        ctx = await create_test_context(session, max_turns_per_session=3)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=provider, settings=settings
        )

        practice_session, _ = await service.start_session(
            principal=ctx["principal"],
            project_id=ctx["project"].id,
            kind=SessionKind.roleplay,
        )

        # sesiunea se deschide cu salutul lui Cody — el NU e unul dintre cele trei schimburi
        assert practice_session.turn_count == 1

        for i in (1, 2, 3):
            raspuns = await service.add_participant_turn(
                principal=ctx["principal"],
                session_id=practice_session.id,
                text=f"Replica omului {i}",
            )
            assert raspuns is not None, f"la schimbul {i} omul a rămas fără răspuns"
            assert raspuns.role == TurnRole.actor

        # al patrulea mesaj: aici se închide, nu mai devreme
        al_patrulea = await service.add_participant_turn(
            principal=ctx["principal"],
            session_id=practice_session.id,
            text="Replica omului 4",
        )
        assert al_patrulea is None
        assert practice_session.state == SessionState.closed

        outcome = (
            await session.execute(
                select(PracticeOutcome).where(
                    PracticeOutcome.session_id == practice_session.id
                )
            )
        ).scalar_one()
        assert outcome.kind == OutcomeKind.turn_limit

        replici_ale_omului = (
            await session.execute(
                select(func.count(PracticeTurn.id)).where(
                    PracticeTurn.session_id == practice_session.id,
                    PracticeTurn.role == TurnRole.participant,
                )
            )
        ).scalar_one()
        assert replici_ale_omului == 3

        await session.rollback()
        await redis.aclose()


@pytest.mark.asyncio
async def test_pasul_de_pornire_nu_s_a_miscat() -> None:
    """Plicul 119: la pasul de pornire nu se cheamă evaluatorul, recunoscut după istoric.

    Reparația de la partea A numără replicile omului și NU atinge `turn_count`, iar
    `history_length` se calculează din replicile din bază (`len(existing_turns) + 1`) — deci
    pasul de pornire rămâne exact unde era. Asta se verifică aici pe o ședință adevărată.
    """
    settings = Settings(generation_provider="local")
    provider = LocalGenerationProvider(settings)

    async with SessionLocal() as session:
        ctx = await create_test_context(session, max_turns_per_session=10)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=provider, settings=settings
        )

        practice_session, _ = await service.start_session(
            principal=ctx["principal"],
            project_id=ctx["project"].id,
            kind=SessionKind.roleplay,
        )

        from sqlalchemy import select

        replici = (
            (
                await session.execute(
                    select(PracticeTurn)
                    .where(PracticeTurn.session_id == practice_session.id)
                    .order_by(PracticeTurn.ordinal.asc())
                )
            )
            .scalars()
            .all()
        )
        # exact ce calculează `add_participant_turn`: `len(existing_turns) + 1`
        history_length_la_confirmare = len(replici) + 1
        assert history_length_la_confirmare == REPLICA_DE_CONFIRMARE, (
            "pasul de pornire s-a mutat: evaluatorul ar fi chemat în alt moment decât la 119"
        )

        await session.rollback()
        await redis.aclose()
