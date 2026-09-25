"""Pasul de pornire nu mai otrăvește istoricul celor două apeluri — plicul 152.

Andrei, 25 septembrie, pe probă: la fiecare replică a lui, Elena reacționa DE DOUĂ ORI (o dată
sfidătoare, o dată împăciuitoare), iar nota apărea DE DOUĂ ORI („[🏆 Scor: 5/10]" lipit de
personaj și încă una după evaluare). Adică exact cele două defecte închise la 117–119: actorul dă
note, evaluatorul joacă personajul.

Cauza, dovedită pe ședința lui: la replica de confirmare („Da, hai.") aplicația făcea UN apel, cu
promptul combinat, deci replica ieșea în formatul vechi — scenă, „***", „[🏆 Scor: -/10]" — și se
salva FĂRĂ bucăți. La replica următoare rândul era luat drept „vechi" și textul lipit ajungea la
AMBELE apeluri ca propriul lor trecut.

Testul trece prin calea aplicației (pornire → „Da, hai." → o replică adevărată), nu prin unealta de
probe: la 119 unealta a dat 0/40 tocmai fiindcă nu trecea prin acest pas ca aplicația.
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
from codrut.modules.practice.service import SCENA_CELUILALT, PracticeSessionService
from test_practice_session_flow import create_test_context

SALUT = "Salut. Ești gata să începem un joc de rol?"
SCENA = ("Context: Elena Marin, din echipa ta, a întârziat din nou raportul.\n\n"
         "Obiectivul tău: să îi dai feedback asertiv.\n\n"
         "Elena Marin: „Știu, știu, raportul. A fost o săptămână nebună.”")
# ce scria Google cu promptul COMBINAT (un singur apel): scena, despărțitorul și nota goală
COMBINAT = f"{SCENA}\n\n***\n\n[🏆 Scor: -/10]"
EVALUARE = "Ai numit concret comportamentul și efectul lui.\n\n[🏆 Scor: 7/10]"


class CaGoogle(LocalGenerationProvider):
    """Răspunde cum a răspuns Google pe ședința lui Andrei, după promptul primit."""

    async def generate(self, request):
        primul = not self.recorded_requests
        rez = await super().generate(request)
        si = request.system_instruction or ""
        if primul:
            text = SALUT
        elif request.purpose == GenerationPurpose.evaluator:
            text = EVALUARE
        elif "PUNCTAJUL E OBLIGATORIU" in si:  # promptul combinat, cu regulile de evaluare
            text = COMBINAT
        else:  # promptul actorului singur
            text = SCENA
        return replace(rez, text=text)


async def _trei_pasi():
    settings = Settings(generation_provider="local", practice_two_calls=True)
    furnizor = CaGoogle(settings)
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                         settings=settings)
        sed, _ = await service.start_session(principal=ctx["principal"],
                                             project_id=ctx["project"].id,
                                             kind=SessionKind.roleplay)
        pornire = await service.add_participant_turn(principal=ctx["principal"],
                                                     session_id=sed.id, text="Da, hai.")
        cerere_pornire = furnizor.recorded_requests[-1]
        n = len(furnizor.recorded_requests)
        await service.add_participant_turn(
            principal=ctx["principal"], session_id=sed.id,
            text="Înțeleg că a fost greu, dar raportul a întârziat a treia oară și ne-a blocat.")
        de_joc = furnizor.recorded_requests[n:]
        rezultat = {
            "pornire_text": pornire.text,
            "pornire_text_actor": pornire.text_actor,
            "pornire_text_evaluator": pornire.text_evaluator,
            "cerere_pornire": cerere_pornire,
            "actor": next(r for r in de_joc if r.purpose == GenerationPurpose.actor),
            "evaluator": next(r for r in de_joc if r.purpose == GenerationPurpose.evaluator),
        }
        await s.rollback()
        await redis.aclose()
        return rezultat


def _ale_lui(cerere) -> list[str]:
    """Ce vede apelul ca PROPRIUL lui trecut."""
    return [m.text for m in cerere.messages if m.role == "model"]


@pytest.mark.asyncio
async def test_actorul_nu_se_vede_dand_note() -> None:
    r = await _trei_pasi()
    trecutul_actorului = "\n".join(_ale_lui(r["actor"]))
    assert "Scor" not in trecutul_actorului
    assert "***" not in trecutul_actorului
    assert "Elena Marin: „Știu, știu" in trecutul_actorului  # scena e a lui, rămâne


@pytest.mark.asyncio
async def test_evaluatorul_nu_se_vede_jucand_personajul() -> None:
    r = await _trei_pasi()
    assert not any("Elena Marin:" in t for t in _ale_lui(r["evaluator"]))
    # scena îi ajunge ca vorba celuilalt, pe rolul „user", cu eticheta — plicul 118
    ale_omului = "\n".join(m.text for m in r["evaluator"].messages if m.role == "user")
    assert SCENA_CELUILALT in ale_omului and "Elena Marin: „Știu, știu" in ale_omului


@pytest.mark.asyncio
async def test_pornirea_cheama_actorul_si_salveaza_bucata_lui() -> None:
    r = await _trei_pasi()
    # regula o pune aplicația: la pornire nu pleacă regulile de evaluare, deci nici nota
    assert "PUNCTAJUL E OBLIGATORIU" not in (r["cerere_pornire"].system_instruction or "")
    assert r["cerere_pornire"].purpose == GenerationPurpose.actor
    assert "[🏆" not in r["pornire_text"] and "***" not in r["pornire_text"]
    assert r["pornire_text_actor"] == SCENA
    assert r["pornire_text_evaluator"] is None
