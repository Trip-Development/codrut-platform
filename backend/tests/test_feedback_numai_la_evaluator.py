"""La două apeluri, „/feedback” cheamă numai evaluatorul — plicul 164, partea B.

Andrei, pe live, 27 septembrie: a scris „/feedback. de ce dai replica mea?” și a primit AMÂNDOUĂ —
întâi personajul, ieșit din rol („Ai dreptate. M-am grăbit și am încălcat protocolul…”), apoi `***`
și evaluatorul. Regula „la un mesaj cu /feedback, personajul nu răspunde” stă numai în
`evaluare.md`; la două apeluri actorul n-o primește, deci răspundea și el. Regresie a despărțirii.

Acum hotărăște aplicația, nu modelul: mesajul care începe cu „/feedback” (după spații, oricum ar fi
scris) nu mai ajunge la actor, iar perechea (mesajul + răspunsul evaluatorului) nu intră niciodată
în istoricul personajului.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from redis.asyncio import Redis

from codrut.contracts.generation import GenerationPurpose
from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import SessionKind
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context

SALUT = "Salut. Ești gata să începem un joc de rol?"
SCENA = ("Tudor Crețu e colegul tău.\n\nObiectivul tău: să îi dai feedback asertiv.\n\n"
         "Tudor Crețu: „Gata, am terminat toată documentația.”")
PERSONAJ = "Tudor Crețu: „Poftim? Ce-i cu tonul ăsta?”"
EVALUARE = "Ai numit concret ce s-a întâmplat.\n\n[🏆 Scor: 7/10]"
RASPUNS_FEEDBACK = "Nota a venit din faptul că ai numit comportamentul, dar n-ai cerut nimic."
FEEDBACK = "  /Feedback de ce mi-ai dat nota asta?"


class Scena(LocalGenerationProvider):
    async def generate(self, request):
        primul = not self.recorded_requests
        rez = await super().generate(request)
        if primul:
            text = SALUT
        elif request.purpose == GenerationPurpose.evaluator:
            ultima = request.messages[-1].text if request.messages else ""
            text = RASPUNS_FEEDBACK if "/feedback" in ultima.casefold() else EVALUARE
        elif len(self.recorded_requests) == 2:
            text = SCENA
        else:
            text = PERSONAJ
        return replace(rez, text=text)


@pytest.mark.asyncio
async def test_feedback_cheama_numai_evaluatorul_si_nu_intra_in_istoricul_personajului() -> None:
    settings = Settings(generation_provider="local", practice_two_calls=True)
    furnizor = Scena(settings)
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        svc = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                     settings=settings)
        pr = ctx["principal"]
        sed, _ = await svc.start_session(principal=pr, project_id=ctx["project"].id,
                                         kind=SessionKind.roleplay)
        await svc.add_participant_turn(principal=pr, session_id=sed.id, text="Da, hai.")
        await svc.add_participant_turn(principal=pr, session_id=sed.id,
                                       text="Tudor, am lucrat singur la ea două seri.")

        n = len(furnizor.recorded_requests)
        raspuns = await svc.add_participant_turn(principal=pr, session_id=sed.id, text=FEEDBACK)
        la_feedback = furnizor.recorded_requests[n:]

        # 1 · un singur apel, al evaluatorului — personajul nu răspunde
        assert [r.purpose for r in la_feedback] == [GenerationPurpose.evaluator]
        # 2 · pe ecran numai răspunsul evaluatorului, fără despărțitor; rândul: actorul gol
        assert raspuns.text == RASPUNS_FEEDBACK
        assert "***" not in raspuns.text
        assert not raspuns.text_actor
        assert raspuns.text_evaluator == RASPUNS_FEEDBACK

        # 3 · replica următoare: personajul continuă, fără să vadă discuția despre notă
        n = len(furnizor.recorded_requests)
        await svc.add_participant_turn(principal=pr, session_id=sed.id,
                                       text="Te rog să spui echipei că eu am redactat materialul.")
        urmatoarea = furnizor.recorded_requests[n:]
        actor = [r for r in urmatoarea if r.purpose == GenerationPurpose.actor]
        evaluator = [r for r in urmatoarea if r.purpose == GenerationPurpose.evaluator]
        assert len(actor) == 1 and len(evaluator) == 1
        istoric_actor = "\n".join(m.text for m in actor[0].messages)
        assert "/feedback" not in istoric_actor.casefold()
        assert RASPUNS_FEEDBACK not in istoric_actor
        assert PERSONAJ in istoric_actor  # scena de dinainte rămâne
        # evaluatorul își vede discuția
        istoric_evaluator = "\n".join(m.text for m in evaluator[0].messages)
        assert "/feedback" in istoric_evaluator.casefold()
        await s.rollback()
        await redis.aclose()


@pytest.mark.asyncio
async def test_la_un_singur_apel_nimic_nu_se_schimba() -> None:
    """Drumul cu un singur apel: /feedback merge tot la apelul combinat, ca până acum."""
    settings = Settings(generation_provider="local", practice_two_calls=False)
    furnizor = Scena(settings)
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        svc = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                     settings=settings)
        pr = ctx["principal"]
        sed, _ = await svc.start_session(principal=pr, project_id=ctx["project"].id,
                                         kind=SessionKind.roleplay)
        await svc.add_participant_turn(principal=pr, session_id=sed.id, text="Da, hai.")
        n = len(furnizor.recorded_requests)
        await svc.add_participant_turn(principal=pr, session_id=sed.id, text=FEEDBACK)
        assert [r.purpose for r in furnizor.recorded_requests[n:]] == [GenerationPurpose.actor]
        await s.rollback()
        await redis.aclose()
