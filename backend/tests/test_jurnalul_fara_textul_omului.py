"""Jurnalul serverului nu scrie ce tastează omul — plicul 217.

`service.py` scria în jurnal primele 80 de semne din replica omului (`ultima_replica_om=%r`).
Jurnalul ajunge în fotografia de stare de pe Mac; conținutul conversațiilor nu are voie să iasă
din bază. Acum rândul `practice_generare` poartă doar lungimea replicii.
"""

import logging

from redis.asyncio import Redis

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import SessionKind
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context

MARCAJ = "MARCAJ-PLIC217-xyz"
# marcajul stă în primele 80 de semne, acolo unde le tăia jurnalul de azi
REPLICA = f"{MARCAJ} Aș vrea să discutăm despre termenul de predare al raportului lunar."


async def _randurile_jurnalului(caplog) -> list[str]:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis,
            generation_provider=LocalGenerationProvider(settings), settings=settings,
        )
        sedinta, _ = await service.start_session(
            principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        with caplog.at_level(logging.INFO):
            await service.add_participant_turn(
                principal=ctx["principal"], session_id=sedinta.id, text=REPLICA
            )
        await session.rollback()
        await redis.aclose()
    return [r.getMessage() for r in caplog.records]


async def test_textul_omului_nu_apare_in_niciun_rand_din_jurnal(caplog) -> None:
    randuri = await _randurile_jurnalului(caplog)
    assert randuri, "drumul trebuia să scrie în jurnal"
    assert [r for r in randuri if MARCAJ in r] == []


async def test_randul_practice_generare_poarta_lungimea_replicii(caplog) -> None:
    randuri = [r for r in await _randurile_jurnalului(caplog) if "practice_generare" in r]
    assert len(randuri) == 1
    assert f"lungime_replica_om={len(REPLICA)}" in randuri[0]
