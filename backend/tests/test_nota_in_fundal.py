"""Nota vine în fundal — plicul 247 (S2).

La jocul de rol cu două apeluri, replica personajului pleacă la om imediat ce e gata actorul;
nota profesorului se termină în fundal, se scrie o singură dată pe aceeași replică și nu se mai
calculează a doua oară. Dacă profesorul cade, replica rămâne și se spune cinstit că nota lipsește.

Zero apeluri la modele: furnizorul local, cu un profesor prefăcut (`asyncio.sleep`).
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

LIMITA = 2.0
OMUL = "Înțeleg ce spui și vreau să găsim împreună o variantă bună pentru amândoi, azi."
OMUL_2 = "Atunci propun așa: îți dau partea cu cifrele luni dimineață, iar restul marți la prânz."
OMUL_3 = "Mulțumesc că ai ascultat. Îți scriu acum pe mail ce am stabilit, ca să fie clar."
SEMN_OM = "Semnul-omului-247"


def _setari(**altele):
    from codrut.core.config import Settings

    limita = altele.pop("limita", LIMITA)
    altele.setdefault("practice_two_calls", True)
    return Settings(generation_provider="local", **altele).model_copy(
        update={"vertex_timeout_evaluator_replica_seconds": limita}
    )


class Profesor:
    """Furnizorul local; purtarea profesorului (evaluatorul pe replică) o pune testul."""

    def __init__(self, settings, purtare=None) -> None:
        from codrut.modules.practice.generation_provider import LocalGenerationProvider

        self._local = LocalGenerationProvider(settings)
        self._purtare = purtare
        self.apeluri_evaluator = 0
        self.cereri: list = []
        self.cereri_evaluator: list = []
        self.cost_actor = None
        self.cost_evaluator = None

    async def generate(self, cerere):
        from codrut.contracts.generation import GenerationPurpose

        self.cereri.append(cerere)
        if cerere.purpose != GenerationPurpose.evaluator:
            rezultat = await self._local.generate(cerere)
            self.cost_actor = rezultat.estimated_usd
            return rezultat
        self.apeluri_evaluator += 1
        self.cereri_evaluator.append(cerere)
        if self._purtare is not None:
            await self._purtare(self.apeluri_evaluator)
        rezultat = await self._local.generate(cerere)
        self.cost_evaluator = rezultat.estimated_usd
        return rezultat


def doarme(secunde: float, numai_apelul: int | None = None):
    async def purtare(apel: int) -> None:
        if numai_apelul is None or apel == numai_apelul:
            await asyncio.sleep(secunde)
    return purtare


async def _pica_mereu(_apel: int) -> None:
    from codrut.contracts.generation import GenerationError

    raise GenerationError("eroare de probă", code="vertex_http_error")


@asynccontextmanager
async def _sedinta(purtare=None, **setari):
    """Ședință de joc de rol adusă peste pasul de pornire („Da, hai.”)."""
    from redis.asyncio import Redis

    from codrut.core.database import SessionLocal
    from codrut.modules.practice.models import SessionKind
    from codrut.modules.practice.service import PracticeSessionService
    from test_practice_session_flow import create_test_context

    settings = _setari(**setari)
    profesor = Profesor(settings, purtare)
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        svc = PracticeSessionService(session=s, redis=redis, generation_provider=profesor,
                                     settings=settings)
        sed, _ = await svc.start_session(principal=ctx["principal"], project_id=ctx["project"].id,
                                         kind=SessionKind.roleplay)
        await svc.add_participant_turn(principal=ctx["principal"], session_id=sed.id,
                                       text="Da, hai.")
        try:
            yield {"s": s, "svc": svc, "ctx": ctx, "sed": sed, "profesor": profesor,
                   "settings": settings}
        finally:
            from codrut.modules.practice.service import asteapta_notele

            await asteapta_notele()
            await s.rollback()
            await redis.aclose()


async def _replica(d, text=OMUL):
    return await d["svc"].add_participant_turn(principal=d["ctx"]["principal"],
                                               session_id=d["sed"].id, text=text)


async def _recitit(turn_id):
    from codrut.core.database import SessionLocal
    from codrut.modules.practice.models import PracticeTurn

    async with SessionLocal() as s:
        return await s.get(PracticeTurn, turn_id)


async def _rezervarea(session_id):
    from sqlalchemy import select

    from codrut.core.database import SessionLocal
    from codrut.modules.practice.models import PracticeBudgetReservation

    async with SessionLocal() as s:
        return (await s.execute(
            select(PracticeBudgetReservation)
            .where(PracticeBudgetReservation.session_id == session_id)
            .order_by(PracticeBudgetReservation.created_at.desc())
            .limit(1)
        )).scalar_one()


def _personaj() -> str:
    return "Local generation response for actor."


def _nota() -> str:
    return "Local generation response for evaluator."


# ---- 1. replica vine înaintea notei ----


@pytest.mark.asyncio
async def test_1_replica_vine_inaintea_notei() -> None:
    from codrut.modules.practice.schemas import PracticeTurnResponse

    async with _sedinta(doarme(1.0)) as d:
        t0 = time.monotonic()
        replica = await _replica(d)
        durata = time.monotonic() - t0
        assert durata < 0.5
        assert replica.evaluare_stare == "vine"
        assert "***" not in replica.text
        assert replica.text == _personaj()
        assert replica.text_evaluator is None
        assert replica.evaluare_vine is True
        assert PracticeTurnResponse.model_validate(replica).evaluare_vine is True


# ---- 2. nota apare o singură dată ----


@pytest.mark.asyncio
async def test_2_nota_apare_o_singura_data_si_e_identica_cu_drumul_vechi() -> None:
    from codrut.modules.practice.schemas import PracticeTurnResponse
    from codrut.modules.practice.service import asteapta_notele

    async with _sedinta(doarme(0.1), practice_nota_in_fundal=False) as vechi:
        replica_veche = await _replica(vechi)
        text_vechi = replica_veche.text

    async with _sedinta(doarme(0.1)) as d:
        replica = await _replica(d)
        await asteapta_notele()
        rand = await _recitit(replica.id)
        assert rand.evaluare_stare == "gata"
        assert rand.text == f"{_personaj()}\n\n***\n\n{_nota()}"
        assert rand.text == text_vechi
        assert rand.text_evaluator == _nota()
        assert rand.evaluare_vine is False
        assert PracticeTurnResponse.model_validate(rand).evaluare_vine is False
        assert d["profesor"].apeluri_evaluator == 1
        for _ in range(3):
            await d["svc"].get_session_history(principal=d["ctx"]["principal"],
                                               session_id=d["sed"].id)
        assert d["profesor"].apeluri_evaluator == 1

        # a doua scriere, cu altă notă, nu mai schimbă nimic
        from dataclasses import replace

        alt = replace(await d["profesor"]._local.generate(d["profesor"].cereri_evaluator[-1]),
                      text="ALTĂ NOTĂ")

        async def gata():
            return alt

        rezervare = await _rezervarea(d["sed"].id)
        await d["svc"]._scrie_nota(replica.id, rezervare.id, asyncio.create_task(gata()),
                                   _personaj(), d["profesor"].cost_actor, d["sed"].id,
                                   time.monotonic())
        din_nou = await _recitit(replica.id)
        assert din_nou.text == rand.text and din_nou.evaluare_stare == "gata"


# ---- 3. profesorul cade ----


@pytest.mark.asyncio
@pytest.mark.parametrize("purtare", ["eroare", "peste_limita"])
async def test_3_profesorul_cade_replica_ramane_si_nota_lipseste(purtare: str) -> None:
    from codrut.modules.practice.service import EVALUARE_NELIVRATA, asteapta_notele

    fel = _pica_mereu if purtare == "eroare" else doarme(LIMITA + 1.0)
    async with _sedinta(fel) as d:
        t0 = time.monotonic()
        replica = await _replica(d)
        assert time.monotonic() - t0 < 0.5
        assert replica.text == _personaj()
        await asteapta_notele()
        rand = await _recitit(replica.id)
        assert rand.evaluare_stare == "lipsa"
        assert rand.text == f"{_personaj()}\n\n***\n\n{EVALUARE_NELIVRATA}"
        assert rand.text_actor == _personaj()


def test_3_textul_de_lipsa_e_cel_de_azi() -> None:
    from codrut.modules.practice.service import EVALUARE_NELIVRATA

    assert EVALUARE_NELIVRATA == (
        "_Evaluare nelivrată. Replica ta e salvată; nota vine data viitoare._"
    )


# ---- 4. banii ----


def _estimarea(profesor, settings):
    from codrut.modules.practice.pricing import estimate_pessimistic_cost

    cerere = profesor.cereri_evaluator[-1]
    cuvinte = sum(len(m.text.split()) for m in cerere.messages) + len(
        cerere.system_instruction.split()
    )
    return estimate_pessimistic_cost(
        prompt_tokens=max(1, cuvinte),
        max_output_tokens=settings.vertex_max_output_tokens_evaluator,
        thinking_budget=settings.thinking_budget_evaluator,
        settings=settings,
    )


@pytest.mark.asyncio
async def test_4_banii_la_gata_costul_real() -> None:
    from codrut.modules.practice.service import asteapta_notele

    async with _sedinta(doarme(0.1)) as d:
        replica = await _replica(d)
        await asteapta_notele()
        p = d["profesor"]
        asteptat = p.cost_actor + p.cost_evaluator
        rezervare = await _rezervarea(d["sed"].id)
        # coloana rezervării ține 4 zecimale (ca la `settle` de azi), a replicii 6
        assert rezervare.actual_usd == asteptat.quantize(Decimal("0.0001"))
        assert (await _recitit(replica.id)).cost_usd == asteptat


@pytest.mark.asyncio
async def test_4_banii_la_lipsa_costul_pesimist() -> None:
    from codrut.modules.practice.service import asteapta_notele

    async with _sedinta(_pica_mereu) as d:
        replica = await _replica(d)
        await asteapta_notele()
        p = d["profesor"]
        asteptat = p.cost_actor + _estimarea(p, d["settings"])
        rezervare = await _rezervarea(d["sed"].id)
        assert rezervare.actual_usd == asteptat.quantize(Decimal("0.0001"))
        assert (await _recitit(replica.id)).cost_usd == asteptat


# ---- 5. închiderea așteaptă nota ----


@pytest.mark.asyncio
async def test_5_inchiderea_asteapta_nota() -> None:
    async with _sedinta(doarme(1.0, numai_apelul=3)) as d:
        await _replica(d, OMUL)
        await _replica(d, OMUL_2)
        await asyncio.sleep(0.2)
        replica = await _replica(d, OMUL_3)
        assert replica.evaluare_stare == "vine"
        await d["svc"].end_session(principal=d["ctx"]["principal"], session_id=d["sed"].id)
        sinteza = d["profesor"].cereri_evaluator[-1]
        assert d["profesor"].apeluri_evaluator == 4
        assert sinteza.messages[0].text.count(_nota()) == 3
        assert (await _recitit(replica.id)).evaluare_stare == "gata"


@pytest.mark.asyncio
async def test_5_inchiderea_inchide_randul_ramas_si_nota_tarzie_nu_il_mai_schimba() -> None:
    from sqlalchemy import update

    from codrut.core.database import SessionLocal, engine
    from codrut.modules.practice.models import PracticeTurn
    from codrut.modules.practice.service import EVALUARE_NELIVRATA, asteapta_notele

    async with _sedinta(doarme(0.05), limita=0.5) as d:
        replica = await _replica(d)
        await asteapta_notele()
        # rândul rămas „vine” fără sarcină (ca după o repornire), creat chiar acum
        async with SessionLocal() as s:
            await s.execute(update(PracticeTurn).where(PracticeTurn.id == replica.id).values(
                text=_personaj(), text_evaluator=None, evaluare_stare="vine",
            ))
            await s.commit()

        mostre: list[int] = []

        async def masoara():
            for _ in range(30):
                await asyncio.sleep(0.13)
                mostre.append(engine.pool.checkedout())

        t0 = time.monotonic()
        masurare = asyncio.create_task(masoara())
        await d["svc"].end_session(principal=d["ctx"]["principal"], session_id=d["sed"].id)
        await d["s"].commit()  # ca ruta: `end_session` face numai `flush`
        durata = time.monotonic() - t0
        await masurare
        assert durata >= 0.5 + 5 - 0.6
        rand = await _recitit(replica.id)
        assert rand.evaluare_stare == "lipsa"
        assert rand.text == f"{_personaj()}\n\n***\n\n{EVALUARE_NELIVRATA}"
        # în timpul așteptării, legătura cu baza se întoarce în bazin (corecția 2)
        assert mostre.count(0) >= len(mostre) - 2

        # nota târzie nu mai scrie peste „lipsa”
        alt = await d["profesor"]._local.generate(d["profesor"].cereri_evaluator[0])

        async def gata():
            return alt

        rezervare = await _rezervarea(d["sed"].id)
        await d["svc"]._scrie_nota(replica.id, rezervare.id, asyncio.create_task(gata()),
                                   _personaj(), d["profesor"].cost_actor, d["sed"].id,
                                   time.monotonic())
        assert (await _recitit(replica.id)).text == rand.text


# ---- 6. rândul rămas după repornire ----


@pytest.mark.asyncio
async def test_6_randul_ramas_dupa_repornire() -> None:
    from sqlalchemy import update

    from codrut.core.database import SessionLocal
    from codrut.modules.practice.models import PracticeTurn
    from codrut.modules.practice.service import EVALUARE_NELIVRATA, asteapta_notele

    async with _sedinta(doarme(0.05)) as d:
        replica = await _replica(d)
        await asteapta_notele()
        async with SessionLocal() as s:
            await s.execute(update(PracticeTurn).where(PracticeTurn.id == replica.id).values(
                text=_personaj(), text_evaluator=None, evaluare_stare="vine",
                created_at=datetime.now(UTC) - timedelta(minutes=10),
            ))
            await s.commit()
        assert (await _recitit(replica.id)).evaluare_vine is False
        await _replica(d, OMUL_2)
        await asteapta_notele()
        rand = await _recitit(replica.id)
        assert rand.evaluare_stare == "lipsa"
        assert rand.text == f"{_personaj()}\n\n***\n\n{EVALUARE_NELIVRATA}"


# ---- 7. omul răspunde înainte de notă ----


@pytest.mark.asyncio
async def test_7_omul_raspunde_inainte_de_nota(caplog) -> None:
    from codrut.modules.practice.service import asteapta_notele

    async with _sedinta(doarme(1.0, numai_apelul=1)) as d:
        with caplog.at_level("INFO"):
            prima = await _replica(d, OMUL)
            assert prima.evaluare_stare == "vine"
            a_doua = await _replica(d, OMUL_2)
            cererea_a_doua = d["profesor"].cereri_evaluator[-1]
            assert all(_nota() not in m.text for m in cererea_a_doua.messages)
            await asteapta_notele()
        assert "practice_nota_fara_cea_de_dinainte" in caplog.text
        assert (await _recitit(prima.id)).evaluare_stare == "gata"
        assert (await _recitit(a_doua.id)).evaluare_stare == "gata"
        assert d["profesor"].apeluri_evaluator == 2


# ---- 8. PAZE ----


@pytest.mark.asyncio
async def test_8_paza_comutatorul_oprit_e_drumul_de_azi() -> None:
    async with _sedinta(doarme(1.0), practice_nota_in_fundal=False) as d:
        t0 = time.monotonic()
        replica = await _replica(d)
        assert time.monotonic() - t0 >= 1.0
        assert replica.evaluare_stare is None
        assert replica.text == f"{_personaj()}\n\n***\n\n{_nota()}"


@pytest.mark.asyncio
async def test_8_paza_pornirea_si_feedback_raman_pe_loc() -> None:
    async with _sedinta(doarme(0.05)) as d:
        from sqlalchemy import select

        from codrut.core.database import SessionLocal
        from codrut.modules.practice.models import PracticeTurn, TurnRole

        async with SessionLocal() as s:
            pornirea = (await s.execute(
                select(PracticeTurn).where(PracticeTurn.session_id == d["sed"].id,
                                           PracticeTurn.role == TurnRole.actor)
                .order_by(PracticeTurn.ordinal.desc()).limit(1)
            )).scalar_one()
        assert pornirea.evaluare_stare is None
        feedback = await _replica(d, "/feedback")
        assert feedback.evaluare_stare is None
        assert feedback.text == _nota()


@pytest.mark.asyncio
async def test_8_paza_un_singur_apel() -> None:
    async with _sedinta(doarme(0.05), practice_two_calls=False) as d:
        replica = await _replica(d)
        assert replica.evaluare_stare is None
        assert d["profesor"].apeluri_evaluator == 0


def test_8_paza_setarea(monkeypatch) -> None:
    from codrut.core.config import Settings

    monkeypatch.delenv("CODRUT_PRACTICE_NOTA_IN_FUNDAL", raising=False)
    assert Settings().practice_nota_in_fundal is True
    monkeypatch.setenv("CODRUT_PRACTICE_NOTA_IN_FUNDAL", "false")
    assert Settings().practice_nota_in_fundal is False


@pytest.mark.asyncio
async def test_8_paza_jurnalul_n_are_textul_omului(caplog) -> None:
    from codrut.modules.practice.service import asteapta_notele

    async with _sedinta(doarme(0.05)) as d:
        with caplog.at_level("INFO"):
            await _replica(d, f"{OMUL} {SEMN_OM}")
            await asteapta_notele()
        assert "practice_replica_trimisa" in caplog.text
        assert "practice_nota sesiune=" in caplog.text
        assert SEMN_OM not in caplog.text


@pytest.mark.asyncio
async def test_8_paza_jurnalul_replicii_si_pe_drumul_vechi(caplog) -> None:
    async with _sedinta(doarme(0.05), practice_nota_in_fundal=False) as d:
        with caplog.at_level("INFO"):
            await _replica(d)
        assert "practice_replica_trimisa" in caplog.text

