"""O generare picată nu-l costă pe om un schimb — plicul 124, partea B.

Reparația de la plicul 123 a închis o pierdere tăcută (salutul mănâncă un schimb) și a deschis
alta, mai rară: poarta numără toate rândurile omului, iar când modelul nu răspunde **replica lui
rămâne salvată** — el mai apasă o dată, se salvează încă un rând, și plafonul scade degeaba. În
ședința auditorului au fost șase rânduri la rând, fără niciun răspuns între ele.

Regula de azi: **omul primește `max_turns_per_session` schimburi REUȘITE.** Un schimb reușit e o
replică a actorului venită după ce omul a vorbit măcar o dată — de unde iese, din aceeași regulă,
și salutul nescăzut, și rândurile orfane nenumărate.
"""

from __future__ import annotations

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.practice.generation_provider import (
    GenerationRequest,
    GenerationResult,
    LocalGenerationProvider,
)
from codrut.modules.practice.models import (
    PracticeTurn,
    SessionKind,
    SessionState,
    TurnRole,
)
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context


class FurnizorCarePicaOData:
    """Furnizorul local, cu o singură cădere pusă la un apel anume.

    Nu e o cădere inventată: e exact `vertex_network_error`, codul cu care pică azi generarea
    când Vertex nu răspunde în pragul de timp.
    """

    def __init__(self, settings: Settings, pica_la_apelul: int) -> None:
        self._local = LocalGenerationProvider(settings)
        self._pica_la = pica_la_apelul
        self.apeluri = 0

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.apeluri += 1
        if self.apeluri == self._pica_la:
            raise DomainError("Vertex AI timeout", code="vertex_network_error")
        return await self._local.generate(request)


@pytest.mark.asyncio
async def test_o_generare_picata_nu_mananca_un_schimb() -> None:
    """Plafon 3, prima generare după o replică a omului pică, el reîncearcă: primește 3 răspunsuri."""
    settings = Settings(generation_provider="local")
    # apelul 1 e salutul de la pornire; apelul 2 e primul schimb al omului — acolo cade
    provider = FurnizorCarePicaOData(settings, pica_la_apelul=2)

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
        assert practice_session.turn_count == 1, "salutul de la pornire trebuia să iasă"

        # omul scrie, modelul nu răspunde. Replica lui rămâne salvată — asta e purtarea de azi,
        # nu o schimbăm aici; ea e chiar cauza pierderii pe care o închidem.
        with pytest.raises(DomainError) as caderea:
            await service.add_participant_turn(
                principal=ctx["principal"],
                session_id=practice_session.id,
                text="Replica omului 1 — asta cade",
            )
        assert caderea.value.code == "vertex_network_error"

        orfane = (
            await session.execute(
                select(func.count(PracticeTurn.id)).where(
                    PracticeTurn.session_id == practice_session.id,
                    PracticeTurn.role == TurnRole.participant,
                )
            )
        ).scalar_one()
        assert orfane == 1, "rândul rămas fără răspuns trebuie să fie în baza de date"

        # omul mai apasă o dată, și de aici încolo merge: cele TREI schimburi plătite
        for i in (1, 2, 3):
            raspuns = await service.add_participant_turn(
                principal=ctx["principal"],
                session_id=practice_session.id,
                text=f"Replica omului {i}",
            )
            assert raspuns is not None, (
                f"la schimbul {i} omul a rămas fără răspuns: căderea de dinainte l-a costat un schimb"
            )
            assert raspuns.role == TurnRole.actor

        assert practice_session.state == SessionState.open

        # al patrulea mesaj închide ședința — nici mai devreme, nici mai târziu
        al_patrulea = await service.add_participant_turn(
            principal=ctx["principal"],
            session_id=practice_session.id,
            text="Replica omului 4",
        )
        assert al_patrulea is None
        assert practice_session.state == SessionState.closed

        await session.rollback()
        await redis.aclose()
