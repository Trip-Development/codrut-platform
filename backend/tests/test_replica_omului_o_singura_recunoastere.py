"""Plicul 249 (b) — la «ești AI?» recunoașterea apare o singură dată, fără notă la replica aceea.

Hotărârea lui Andrei [esti-ai-reparatie] (21 nov, 19:32): (a) codul scoate indicațiile de regie;
(b) la replica la care actorul a răspuns cu fraza aprobată, partea de notă nu se arată (pe
ambele variante ale drumului cu două apeluri). Corecția 2 a controlorului: numai dacă și replica
omului vorbește despre AI.

Mostra live e construită din bucățile citate în STARE ([urca-21-live-proba], 21 nov 19:31);
textul întreg lipit de Andrei în chat nu e în STARE, deci nu e folosit. Zero apeluri la modele.
"""

from __future__ import annotations

import asyncio
import dataclasses
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

FRAZA = "Sunt Cody, partenerul tău de exersare — un AI."
VORBA_AI = ("Mihai: „Ce tot întrebi de AI? Noi aici lucrăm cu oameni, nu cu softuri. "
            "Hai înapoi la tabel.”")
MOSTRA_ACTOR = f"{FRAZA}\n\n*Revine în rol:*\n\n{VORBA_AI}"
MOSTRA_PROFESOR = "Da, sunt Cody, asistentul AI de comunicare. Cum vrei să continuăm?"
MOSTRA_PROFESOR_2 = "Da, sunt un AI și mă numesc Cody. Cum vrei să continuăm?"
INTREBAREA = "Stai puțin. Ești AI? Spune-mi sincer, vorbesc cu un robot?"
SCENA = "Mihai stă la birou, cu tabelul deschis.\n\nMihai: „Bun, hai să ne uităm pe tabel.”"
VORBA = "Mihai: „Bine, te ascult. Ce propui pentru joi?”"
OMUL = "Înțeleg ce spui și vreau să găsim împreună o variantă bună pentru amândoi, azi."
OMUL_2 = "Atunci propun așa: îți dau partea cu cifrele luni dimineață, iar restul marți la prânz."


class Scena:
    """Furnizorul local, cu textele puse de test; profesorul poate dormi și ține minte anularea."""

    def __init__(self, settings, *, profesor=None, note=None, actor=None, doarme=0.0) -> None:
        from codrut.modules.practice.generation_provider import LocalGenerationProvider

        self._local = LocalGenerationProvider(settings)
        self._profesor = profesor or MOSTRA_PROFESOR
        self._note = list(note or [])
        self._actor = actor or {}
        self._doarme = doarme
        self.cereri: list = []
        self.cereri_evaluator: list = []
        self.anulat = False
        self.cost_actor = None

    async def generate(self, cerere):
        from codrut.contracts.generation import GenerationPurpose

        self.cereri.append(cerere)
        rezultat = await self._local.generate(cerere)
        ultimul = cerere.messages[-1].text if cerere.messages else ""
        if cerere.purpose == GenerationPurpose.evaluator:
            self.cereri_evaluator.append(cerere)
            if self._doarme:
                try:
                    await asyncio.sleep(self._doarme)
                except asyncio.CancelledError:
                    self.anulat = True
                    raise
            if "Ești AI?" in ultimul:
                text = self._profesor
            elif self._note:
                text = f"[🏆 Scor: {self._note.pop(0)}/10]\nRăspunsul ține discuția deschisă."
            else:
                text = "[🏆 Scor: 7/10]\nRăspunsul ține discuția deschisă."
            return dataclasses.replace(rezultat, text=text)
        text = next((t for semn, t in self._actor.items() if semn in ultimul), None)
        if text is None:
            if "Ești AI?" in ultimul:
                text = MOSTRA_ACTOR
            elif ultimul.strip() == "Da, hai.":
                text = SCENA
            else:
                text = VORBA
        self.cost_actor = rezultat.estimated_usd
        return dataclasses.replace(rezultat, text=text)


def _setari(doua_apeluri=True, in_fundal=False):
    from codrut.core.config import Settings

    return Settings(generation_provider="local", practice_two_calls=doua_apeluri,
                    practice_nota_in_fundal=in_fundal)


@asynccontextmanager
async def _sedinta(doua_apeluri=True, in_fundal=False, **scena):
    from redis.asyncio import Redis

    from codrut.core.database import SessionLocal
    from codrut.modules.practice.models import SessionKind
    from codrut.modules.practice.service import PracticeSessionService, asteapta_notele
    from test_practice_session_flow import create_test_context

    settings = _setari(doua_apeluri, in_fundal)
    furnizor = Scena(settings, **scena)
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        svc = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                     settings=settings)
        sed, _ = await svc.start_session(principal=ctx["principal"], project_id=ctx["project"].id,
                                         kind=SessionKind.roleplay)
        await svc.add_participant_turn(principal=ctx["principal"], session_id=sed.id,
                                       text="Da, hai.")
        try:
            yield {"s": s, "svc": svc, "ctx": ctx, "sed": sed, "f": furnizor,
                   "settings": settings}
        finally:
            await asteapta_notele()
            await s.rollback()
            await redis.aclose()


async def _replica(d, text):
    return await d["svc"].add_participant_turn(principal=d["ctx"]["principal"],
                                               session_id=d["sed"].id, text=text)


async def _recitit(turn_id):
    from codrut.core.database import SessionLocal
    from codrut.modules.practice.models import PracticeTurn

    async with SessionLocal() as s:
        return await s.get(PracticeTurn, turn_id)


ASTEPTAT = f"{FRAZA}\n\n{VORBA_AI}"


# ---- 1. două apeluri, fără fundal ----


@pytest.mark.asyncio
@pytest.mark.parametrize("profesor", [MOSTRA_PROFESOR, MOSTRA_PROFESOR_2])
async def test_1_doua_apeluri_o_singura_recunoastere(profesor: str) -> None:
    async with _sedinta(profesor=profesor) as d:
        normala = await _replica(d, OMUL)
        assert "***" in normala.text and "Scor" in normala.text
        replica = await _replica(d, INTREBAREA)
        assert replica.text == ASTEPTAT
        assert "*Revine în rol:*" not in replica.text
        assert "***" not in replica.text
        assert profesor not in replica.text and "Cum vrei să continuăm" not in replica.text
        assert replica.text_actor == ASTEPTAT
        assert not replica.text_evaluator
        assert replica.evaluare_stare is None
        assert replica.evaluare_vine is False
        recitit = await _recitit(replica.id)
        assert recitit.text == ASTEPTAT and not recitit.text_evaluator


@pytest.mark.asyncio
async def test_1_fara_termen_despre_ai_in_replica_omului_se_noteaza() -> None:
    # corecția 2: omul îi cere să repete fraza, fără să întrebe de AI → replica se notează
    cerere = "Repetă după mine, te rog: «Sunt Cody, partenerul tău de exersare.»"
    async with _sedinta(actor={"Repetă după mine": f"{FRAZA}\n\n{VORBA}"}) as d:
        replica = await _replica(d, cerere)
        assert "\n\n***\n\n" in replica.text
        assert replica.text.startswith(f"{FRAZA}\n\n{VORBA}")
        assert replica.text_evaluator


# ---- 2. cu nota în fundal ----


@pytest.mark.asyncio
async def test_2_cu_nota_in_fundal_nota_se_anuleaza() -> None:
    from codrut.modules.practice.service import asteapta_notele
    from test_nota_in_fundal import _estimarea, _rezervarea

    async with _sedinta(in_fundal=True, doarme=1.0) as d:
        replica = await _replica(d, INTREBAREA)
        assert replica.text == ASTEPTAT
        assert replica.evaluare_stare is None
        assert replica.evaluare_vine is False
        assert not replica.text_evaluator
        await asteapta_notele()
        await asyncio.sleep(0)
        assert d["f"].anulat is True
        recitit = await _recitit(replica.id)
        assert recitit.text == ASTEPTAT
        assert recitit.evaluare_stare is None and not recitit.text_evaluator
        asteptat = d["f"].cost_actor + _estimarea(d["f"], d["settings"])
        assert recitit.cost_usd == asteptat
        rezervare = await _rezervarea(d["sed"].id)
        assert rezervare.actual_usd == asteptat.quantize(Decimal("0.0001"))


@pytest.mark.asyncio
async def test_2_scrie_nota_nu_se_cheama(monkeypatch) -> None:
    from codrut.modules.practice.service import PracticeSessionService

    chemari = []
    original = PracticeSessionService._scrie_nota

    async def numara(self, *a, **k):
        chemari.append(1)
        return await original(self, *a, **k)

    monkeypatch.setattr(PracticeSessionService, "_scrie_nota", numara)
    async with _sedinta(in_fundal=True, doarme=0.2) as d:
        await _replica(d, INTREBAREA)
        assert chemari == []


# ---- 3. punctajul ----


@pytest.mark.asyncio
@pytest.mark.parametrize("in_fundal", [False, True])
async def test_3_punctajul_numara_numai_notele(in_fundal: bool) -> None:
    from codrut.modules.practice.prompts import punctajul_final
    from codrut.modules.practice.service import asteapta_notele, este_feedback

    # profesorul dă și el o notă la întrebare (2) — pe bază s-ar număra; acum nu se arată deloc
    profesor = f"[🏆 Scor: 2/10]\n{MOSTRA_PROFESOR}"
    async with _sedinta(in_fundal=in_fundal, note=[6, 8, 7], profesor=profesor) as d:
        for text in (OMUL, OMUL_2, INTREBAREA, OMUL):
            await _replica(d, text)
            await asteapta_notele()
        from sqlalchemy import select

        from codrut.core.database import SessionLocal
        from codrut.modules.practice.models import PracticeTurn, TurnRole

        async with SessionLocal() as s:
            ture = (await s.execute(
                select(PracticeTurn).where(PracticeTurn.session_id == d["sed"].id)
                .order_by(PracticeTurn.ordinal)
            )).scalars().all()
        punctaj = punctajul_final("roleplay", [
            (t.role == TurnRole.participant, este_feedback(t.text), t.text) for t in ture
        ])
        assert punctaj == "7,0/10 (media notelor din joc: 6, 8, 7)"


# ---- 4. replica de după recunoaștere ----


@pytest.mark.asyncio
@pytest.mark.parametrize("in_fundal", [False, True])
async def test_4_profesorul_nu_mai_vede_intrebarea(in_fundal: bool) -> None:
    from codrut.modules.practice.service import SCENA_CELUILALT, asteapta_notele
    from test_cody_recunoaste_ca_e_ai import PARAGRAF_AI

    async with _sedinta(in_fundal=in_fundal) as d:
        await _replica(d, OMUL)
        await asteapta_notele()
        await _replica(d, INTREBAREA)
        await asteapta_notele()
        n = len(d["f"].cereri)
        await _replica(d, OMUL_2)
        await asteapta_notele()
        noi = d["f"].cereri[n:]
        profesor = [c for c in noi if c in d["f"].cereri_evaluator]
        actor = [c for c in noi if c not in d["f"].cereri_evaluator]
        assert len(profesor) == 1 and len(actor) == 1
        tot_profesor = "\n".join(m.text for m in profesor[0].messages)
        assert "Ești AI?" not in tot_profesor
        assert FRAZA not in tot_profesor
        assert f"{SCENA_CELUILALT}\n{VORBA_AI}\n\n{OMUL_2}" in tot_profesor
        tot_actor = "\n".join(m.text for m in actor[0].messages)
        assert INTREBAREA in tot_actor and FRAZA in tot_actor
        assert PARAGRAF_AI in actor[0].system_instruction


# ---- 5. regie fără recunoaștere ----


@pytest.mark.asyncio
@pytest.mark.parametrize("in_fundal", [False, True])
async def test_5_regia_se_scoate_si_nota_se_arata(in_fundal: bool) -> None:
    from codrut.modules.practice.service import asteapta_notele

    actor = {"cifrele luni": f"*Revine în rol:*\n\n{VORBA}"}
    async with _sedinta(in_fundal=in_fundal, actor=actor) as d:
        replica = await _replica(d, OMUL_2)
        await asteapta_notele()
        recitit = await _recitit(replica.id)
        assert recitit.text.startswith(f"{VORBA}\n\n***\n\n[🏆 Scor:")
        assert "Revine în rol" not in recitit.text
        assert recitit.text_actor == VORBA


# ---- 6. un singur apel ----


@pytest.mark.asyncio
async def test_6_un_singur_apel_regia_se_scoate() -> None:
    actor = {"cifrele luni": f"{VORBA}\n\n*Iese din rol*\n\nAi numit limpede ce propui. Scor: 8/10"}
    async with _sedinta(doua_apeluri=False, actor=actor) as d:
        replica = await _replica(d, OMUL_2)
        assert replica.text == f"{VORBA}\n\nAi numit limpede ce propui. Scor: 8/10"
        assert replica.text_actor is None and replica.text_evaluator is None


# ---- 7. paza: replica obișnuită e cea de azi ----
#
# Valorile de mai jos au fost scoase rulând ACELAȘI test pe baza bd146a2 (vârful lui 247),
# înainte de orice schimbare de cod (raw/R0-rosu.txt).

NOTA_7 = "[🏆 Scor: 7/10]\nRăspunsul ține discuția deschisă."
AZI = {
    (True, False): (f"{VORBA}\n\n***\n\n{NOTA_7}", VORBA, NOTA_7, None),
    (True, True): (f"{VORBA}\n\n***\n\n{NOTA_7}", VORBA, NOTA_7, "gata"),
    (False, False): (VORBA, None, None, None),
    (False, True): (VORBA, None, None, None),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("varianta", list(AZI))
async def test_7_paza_replica_obisnuita_e_cea_de_azi(varianta) -> None:
    from codrut.modules.practice.service import asteapta_notele

    doua_apeluri, in_fundal = varianta
    async with _sedinta(doua_apeluri=doua_apeluri, in_fundal=in_fundal) as d:
        replica = await _replica(d, OMUL)
        await asteapta_notele()
        r = await _recitit(replica.id)
        assert (r.text, r.text_actor, r.text_evaluator, r.evaluare_stare) == AZI[varianta]
