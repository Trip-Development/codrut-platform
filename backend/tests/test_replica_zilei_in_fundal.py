"""„O replică pe zi”: răspunsul profesorului vine din fundal, fără anulare la 15 s — plicul 267.

Replica omului se salvează pe loc, cu răspunsul gol („în lucru”); profesorul răspunde dintr-o
sarcină din fundal, numai cu limita generală `vertex_timeout_seconds`, iar răspunsul se scrie o
singură dată. O cădere șterge rândul, ca omul să poată trimite din nou.

Zero apeluri la modele: profesorul e mereu fals (`ProfesorFals` din 236, cu `asyncio.sleep`).
Numele noi se importă în corpul testelor, ca roșul pe bază să fie al testului.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.practice.models import (
    BudgetReservationState,
    PracticeBudgetReservation,
    PracticeDailyReply,
)
from test_replica_zilei_profesor import (
    ACUM,
    COST_FALS,
    ProfesorFals,
    proiect_legat,
    rezervarile,
    setari,
    trimite,
)

TEXT_BUN = "Ai spus clar ce poți. [🏆 Scor: 7,5/10]"
# coloana rezervării păstrează 4 zecimale
COST_REZERVARE = COST_FALS.quantize(Decimal("0.0001"))


def nou(**schimbari):
    """Setările de test cu calea nouă pornită (valoarea implicită după 267)."""
    schimbari.setdefault("replica_zilei_raspuns_in_fundal", True)
    return setari(**schimbari)


async def _asteapta():
    from codrut.modules.practice.replica_zilei import asteapta_raspunsurile

    await asteapta_raspunsurile()


async def _randurile(profil_id):
    async with SessionLocal() as s:
        return (await s.execute(
            select(PracticeDailyReply).where(PracticeDailyReply.participant_profile_id == profil_id)
            .order_by(PracticeDailyReply.created_at)
        )).scalars().all()


async def _rezervarile(program_settings_id):
    async with SessionLocal() as s:
        return await rezervarile(s, program_settings_id)


async def _starea(ctx, acum=ACUM):
    from codrut.modules.practice import replica_zilei as rz

    async with SessionLocal() as s:
        return await rz.starea_zilei(s, ctx["principal"], ctx["project"].id, acum=acum)


async def _context():
    async with SessionLocal() as s:
        ctx = await proiect_legat(s)
        await s.commit()
    return ctx


# ---- r1 ----


@pytest.mark.asyncio
async def test_replica_se_salveaza_inainte_de_raspuns() -> None:
    ctx = await _context()
    profesor = ProfesorFals(TEXT_BUN, intarziere=1.0)
    async with SessionLocal() as s:
        inceput = time.monotonic()
        stare = await trimite(s, ctx, profesor=profesor, settings=nou())
        durata = time.monotonic() - inceput
    try:
        assert durata < 0.5
        assert stare["azi"]["in_lucru"] is True
        assert stare["azi"]["raspuns"] == ""
        assert stare["azi"]["nota"] is None
        [rand] = await _randurile(ctx["profile"].id)
        assert rand.teacher_text == ""
    finally:
        await _asteapta()


# ---- r2 ----


@pytest.mark.asyncio
async def test_raspunsul_se_scrie_o_singura_data() -> None:
    from sqlalchemy import update

    ctx = await _context()
    profesor = ProfesorFals(TEXT_BUN, intarziere=0.1)
    async with SessionLocal() as s:
        await trimite(s, ctx, profesor=profesor, settings=nou())
    await _asteapta()
    for _ in range(3):
        stare = await _starea(ctx)
    assert stare["azi"].get("in_lucru", False) is False
    assert stare["azi"]["raspuns"] == TEXT_BUN
    assert stare["azi"]["nota"] == 7.5
    assert len(profesor.cereri) == 1
    [rand] = await _randurile(ctx["profile"].id)
    # al doilea UPDATE, cu aceeași condiție, nu mai schimbă rândul
    async with SessionLocal() as s:
        rez = await s.execute(
            update(PracticeDailyReply)
            .where(PracticeDailyReply.id == rand.id, PracticeDailyReply.teacher_text == "")
            .values(teacher_text="alt text [🏆 Scor: 2/10]")
        )
        await s.commit()
        assert rez.rowcount == 0
    [rand] = await _randurile(ctx["profile"].id)
    assert rand.teacher_text == TEXT_BUN and float(rand.score) == 7.5
    assert rand.cost_usd == COST_FALS
    [r] = await _rezervarile(ctx["program_settings"].id)
    assert r.state == BudgetReservationState.settled and r.actual_usd == COST_REZERVARE


# ---- r3 (miezul) ----


@pytest.mark.asyncio
async def test_peste_15s_nu_se_mai_anuleaza() -> None:
    ctx = await _context()
    # limita replicii întreagă: lacătul din Redis primește `limita + 10` și cere un număr întreg
    settings = nou(vertex_timeout_evaluator_replica_seconds=1, vertex_timeout_seconds=5)
    profesor = ProfesorFals(TEXT_BUN, intarziere=1.5)
    async with SessionLocal() as s:
        stare = await trimite(s, ctx, profesor=profesor, settings=settings)
    assert stare["azi"]["in_lucru"] is True
    await _asteapta()
    stare = await _starea(ctx)
    assert stare["azi"]["raspuns"] == TEXT_BUN and not stare["azi"].get("in_lucru")


# ---- r4 ----


@pytest.mark.asyncio
async def test_limita_generala_sterge_randul() -> None:
    ctx = await _context()
    settings = nou(vertex_timeout_seconds=0.3)
    async with SessionLocal() as s:
        await trimite(s, ctx, profesor=ProfesorFals(TEXT_BUN, intarziere=1.0), settings=settings)
    await _asteapta()
    assert await _randurile(ctx["profile"].id) == []
    assert (await _starea(ctx))["azi"] is None
    [r] = await _rezervarile(ctx["program_settings"].id)
    assert r.state == BudgetReservationState.settled and r.actual_usd == r.reserved_usd
    # a doua trimitere în aceeași zi merge
    async with SessionLocal() as s:
        await trimite(s, ctx, profesor=ProfesorFals(TEXT_BUN), settings=nou())
    await _asteapta()
    assert (await _starea(ctx))["azi"]["raspuns"] == TEXT_BUN


# ---- r5 ----


@pytest.mark.asyncio
@pytest.mark.parametrize("fel", ["exceptie", "gol"])
async def test_profesorul_cade_omul_poate_relua(fel) -> None:
    ctx = await _context()
    profesor = (ProfesorFals(exceptie=RuntimeError("cade")) if fel == "exceptie"
                else ProfesorFals("   "))
    async with SessionLocal() as s:
        await trimite(s, ctx, profesor=profesor, settings=nou())
    await _asteapta()
    assert await _randurile(ctx["profile"].id) == []
    [r] = await _rezervarile(ctx["program_settings"].id)
    if fel == "exceptie":
        assert r.state == BudgetReservationState.released
    else:
        assert r.state == BudgetReservationState.settled and r.actual_usd == COST_REZERVARE
    async with SessionLocal() as s:
        await trimite(s, ctx, profesor=ProfesorFals(TEXT_BUN), settings=nou())
    await _asteapta()
    assert (await _starea(ctx))["azi"]["raspuns"] == TEXT_BUN


# ---- r6 ----


@pytest.mark.asyncio
async def test_randul_ramas_dupa_repornire() -> None:
    from codrut.modules.practice import replica_zilei as rz

    ctx = await _context()
    stare0 = await _starea(ctx)
    acum = datetime.now(UTC)
    async with SessionLocal() as s:
        s.add(PracticeDailyReply(
            participant_profile_id=ctx["profile"].id, project_id=ctx["project"].id,
            situation_id=stare0["situatie"]["id"], day=rz.ziua_in_romania(acum),
            reply_text="rămasă", teacher_text="", created_at=acum - timedelta(seconds=200),
            expires_at=acum + timedelta(days=30),
        ))
        await s.commit()
    stare = await _starea(ctx, acum=acum)
    assert stare["azi"] is None and stare["serie"] == 0
    assert len(await _randurile(ctx["profile"].id)) == 1  # citirea nu șterge nimic
    async with SessionLocal() as s:
        await trimite(s, ctx, acum=acum, profesor=ProfesorFals(TEXT_BUN), settings=nou())
    await _asteapta()
    [rand] = await _randurile(ctx["profile"].id)
    assert rand.reply_text != "rămasă" and rand.teacher_text == TEXT_BUN


# ---- r7 ----


@pytest.mark.asyncio
async def test_a_doua_trimitere_cat_e_in_lucru() -> None:
    ctx = await _context()
    profesor = ProfesorFals(TEXT_BUN, intarziere=0.5)
    async with SessionLocal() as s:
        stare = await trimite(s, ctx, profesor=profesor, settings=nou())
    try:
        async with SessionLocal() as s:
            with pytest.raises(DomainError) as e:
                await trimite(s, ctx, profesor=profesor, settings=nou(),
                              situatie=stare["situatie"]["id"])
        assert e.value.code == "replica_zilei_facuta"
    finally:
        await _asteapta()
    assert len(profesor.cereri) == 1


# ---- r8 ----


@pytest.mark.asyncio
async def test_cererea_e_aceeasi_pe_ambele_cai() -> None:
    from codrut.modules.practice.alias import codul_omului

    cereri = []
    for in_fundal in (True, False):
        ctx = await _context()
        profesor = ProfesorFals(TEXT_BUN)
        async with SessionLocal() as s:
            await trimite(s, ctx, profesor=profesor,
                          settings=setari(replica_zilei_raspuns_in_fundal=in_fundal))
            cod = await codul_omului(s, ctx["profile"])
        await _asteapta()
        [c] = profesor.cereri
        # codul omului diferă de la un cont la altul; restul cererii trebuie să fie identic
        def fara_cod(t: str, cod=cod) -> str:
            t = t.replace(cod, "<cod>")
            return re.sub(r"„[^”]{1,40}”(?=\. Codul e o etichetă)", "„<cod>”", t)

        cereri.append(dataclasses.replace(
            c, system_instruction=fara_cod(c.system_instruction),
            messages=tuple(dataclasses.replace(m, text=fara_cod(m.text)) for m in c.messages),
        ))
    a, b = cereri
    from codrut.modules.practice.prompts import INCHEIERE_REPLICA_ZILEI

    assert a.system_instruction.endswith(INCHEIERE_REPLICA_ZILEI)  # încheierea lui 260
    for camp in ("system_instruction", "messages", "purpose", "temperature",
                 "max_output_tokens", "thinking_budget"):
        assert getattr(a, camp) == getattr(b, camp), camp
    # și calea nouă chiar a fost luată
    from codrut.modules.practice import replica_zilei as rz

    assert hasattr(rz, "asteapta_raspunsurile")


# ---- r9 (PAZĂ) ----


@pytest.mark.asyncio
async def test_calea_veche_neschimbata(monkeypatch) -> None:
    from codrut.core.config import Settings, get_settings

    vechi = setari(replica_zilei_raspuns_in_fundal=False)
    ctx = await _context()
    async with SessionLocal() as s:
        stare = await trimite(s, ctx, profesor=ProfesorFals(TEXT_BUN), settings=vechi)
    assert stare["azi"]["raspuns"] == TEXT_BUN
    assert stare["azi"].get("in_lucru", False) is False
    ctx = await _context()
    lent = setari(replica_zilei_raspuns_in_fundal=False,
                  vertex_timeout_evaluator_replica_seconds=1)
    async with SessionLocal() as s:
        with pytest.raises(DomainError) as e:
            await trimite(s, ctx, profesor=ProfesorFals(TEXT_BUN, intarziere=1.5), settings=lent)
    assert e.value.code == "profesor_indisponibil"
    assert e.value.message == (
        "Cody nu poate răspunde acum. Replica ta nu s-a salvat; încearcă din nou."
    )
    assert await _randurile(ctx["profile"].id) == []
    # setarea: pornită implicit, oprită din mediu
    assert Settings(generation_provider="local").replica_zilei_raspuns_in_fundal is True
    monkeypatch.setenv("CODRUT_REPLICA_ZILEI_RASPUNS_IN_FUNDAL", "false")
    get_settings.cache_clear()
    try:
        assert get_settings().replica_zilei_raspuns_in_fundal is False
    finally:
        monkeypatch.delenv("CODRUT_REPLICA_ZILEI_RASPUNS_IN_FUNDAL")
        get_settings.cache_clear()


# ---- r10 (PAZĂ) ----


@pytest.mark.asyncio
async def test_nimic_in_jurnal(caplog) -> None:
    replica = "Semn-replica-267: azi pot doar până la 18."
    raspuns = "Semn-raspuns-267. [🏆 Scor: 6/10]"
    with caplog.at_level(logging.DEBUG):
        for profesor, settings in (
            (ProfesorFals(raspuns), nou()),
            (ProfesorFals(exceptie=RuntimeError("cade")), nou()),
            (ProfesorFals(raspuns, intarziere=0.5), nou(vertex_timeout_seconds=0.1)),
        ):
            ctx = await _context()
            async with SessionLocal() as s:
                await trimite(s, ctx, profesor=profesor, text=replica, settings=settings)
            await _asteapta()
    assert not [r for r in caplog.records if r.name == "codrut.modules.practice.replica_zilei"]
    assert "Semn-replica-267" not in caplog.text
    assert "Semn-raspuns-267" not in caplog.text


# ---- r11 (PAZĂ, ambele drumuri) ----


async def _exersarea(*, two_calls: bool, in_fundal: bool, limita: float | None = None):
    """Pornire + «Da, hai.» + 2 replici; întoarce ce s-a cerut și ce s-a salvat, fără nume."""
    from redis.asyncio import Redis

    from codrut.core.config import Settings
    from codrut.modules.practice.alias import codul_omului
    from codrut.modules.practice.generation_provider import LocalGenerationProvider
    from codrut.modules.practice.models import PracticeTurn, SessionKind
    from codrut.modules.practice.service import PracticeSessionService, asteapta_notele
    from test_practice_session_flow import create_test_context

    schimbari = {"replica_zilei_raspuns_in_fundal": in_fundal}
    if limita is not None:
        schimbari["vertex_timeout_evaluator_replica_seconds"] = limita
    settings = Settings(generation_provider="local", practice_two_calls=two_calls).model_copy(
        update=schimbari
    )

    class Inregistreaza:
        def __init__(self) -> None:
            self._local = LocalGenerationProvider(settings)
            self.cereri: list = []

        async def generate(self, cerere):
            from codrut.contracts.generation import GenerationPurpose

            self.cereri.append(cerere)
            if limita is not None and cerere.purpose == GenerationPurpose.evaluator:
                await asyncio.sleep(limita * 3)
            return await self._local.generate(cerere)

    furnizor = Inregistreaza()
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            svc = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                         settings=settings)
            sed, _ = await svc.start_session(principal=ctx["principal"],
                                             project_id=ctx["project"].id,
                                             kind=SessionKind.roleplay)
            for text in ("Da, hai.", "Înțeleg ce spui și vreau să găsim o variantă bună.",
                         "Atunci propun așa: îți dau cifrele luni dimineață."):
                await svc.add_participant_turn(principal=ctx["principal"], session_id=sed.id,
                                               text=text)
            await asteapta_notele()
            cod = await codul_omului(s, ctx["profile"])
        finally:
            await redis.aclose()
    sufix = ctx["profile"].full_name.split()[-1]
    curat = lambda t: (t or "").replace(cod, "<cod>").replace(sufix, "<sufix>")  # noqa: E731
    async with SessionLocal() as s:
        ture = (await s.execute(
            select(PracticeTurn).where(PracticeTurn.session_id == sed.id)
            .order_by(PracticeTurn.ordinal)
        )).scalars().all()
    return (
        [(curat(c.system_instruction), tuple(curat(m.text) for m in c.messages))
         for c in furnizor.cereri],
        [(curat(t.text), t.evaluare_stare) for t in ture],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("two_calls", [True, False])
async def test_exersarea_nu_vede_setarea(two_calls) -> None:
    cu = await _exersarea(two_calls=two_calls, in_fundal=True)
    fara = await _exersarea(two_calls=two_calls, in_fundal=False)
    assert cu == fara
    if two_calls:
        # limita de 15 s rămâne la nota exersării: profesorul peste ea → nota „lipsa”
        _, ture = await _exersarea(two_calls=True, in_fundal=True, limita=0.2)
        assert "lipsa" in [stare for _, stare in ture]


# ---- r12 ----


def test_setarea_sta_intr_un_singur_loc() -> None:
    import inspect

    from codrut.modules.practice import replica_zilei as rz

    radacina = Path(__file__).resolve().parents[1] / "src" / "codrut"
    unde = sorted(
        str(p.relative_to(radacina)) for p in radacina.rglob("*.py")
        if "replica_zilei_raspuns_in_fundal" in p.read_text(encoding="utf-8")
    )
    assert unde == ["core/config.py", "modules/practice/replica_zilei.py",
                    "tools/banca/replica_zilei_banca.py"]
    assert inspect.getsource(rz.trimite_replica).count("replica_zilei_raspuns_in_fundal") == 1
    service = (radacina / "modules" / "practice" / "service.py").read_text(encoding="utf-8")
    assert "replica_zilei_raspuns_in_fundal" not in service


# ---- r13 (corecția 3) ----


@pytest.mark.asyncio
async def test_ruta_cale_noua(monkeypatch, caplog) -> None:
    """POST pe rută cu setarea pornită: «în lucru»; după răspuns, GET dă nota; nimic în jurnal."""
    from httpx import ASGITransport, AsyncClient

    from codrut.api.dependencies import current_principal
    from codrut.core.config import get_settings
    from codrut.main import create_app
    from codrut.modules.practice import router as ruta

    ctx = await _context()
    stare0 = await _starea(ctx, acum=datetime.now(UTC))
    monkeypatch.setattr(ruta, "build_generation_provider",
                        lambda _settings: ProfesorFals("Semn-ruta-267. [🏆 Scor: 8/10]"))
    app = create_app()
    app.dependency_overrides[current_principal] = lambda: ctx["principal"]
    app.dependency_overrides[get_settings] = lambda: nou()
    url = f"/api/practice/projects/{ctx['project'].id}/replica-zilei"
    with caplog.at_level(logging.DEBUG):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(url, json={"situation_id": str(stare0["situatie"]["id"]),
                                        "replica": "Semn-replica-ruta-267."})
            assert r.status_code == 200, r.text
            assert r.json()["azi"]["in_lucru"] is True
            await _asteapta()
            r = await c.get(url)
            assert r.status_code == 200
            assert r.json()["azi"]["in_lucru"] is False and r.json()["azi"]["nota"] == 8.0
    assert "Semn-ruta-267" not in caplog.text and "Semn-replica-ruta-267" not in caplog.text


# ---- r14 (corecția 4) ----


@pytest.mark.asyncio
async def test_doua_trimiteri_deodata() -> None:
    from codrut.modules.practice import replica_zilei as rz

    ctx = await _context()
    stare0 = await _starea(ctx)
    profesor = ProfesorFals(TEXT_BUN, intarziere=0.3)

    async def una():
        async with SessionLocal() as s:
            return await trimite(s, ctx, profesor=profesor, settings=nou(),
                                 situatie=stare0["situatie"]["id"])

    rezultate = await asyncio.gather(una(), una(), return_exceptions=True)
    await _asteapta()
    erori = [r for r in rezultate if isinstance(r, BaseException)]
    assert len(erori) <= 1
    for e in erori:
        assert isinstance(e, DomainError), repr(e)
        assert e.code in ("replica_zilei_facuta", "practice_busy"), e.code
    assert len(await _randurile(ctx["profile"].id)) == 1
    assert len(profesor.cereri) == 1
    async with SessionLocal() as s:
        ramase = (await s.execute(
            select(PracticeBudgetReservation).where(
                PracticeBudgetReservation.program_settings_id == ctx["program_settings"].id,
                PracticeBudgetReservation.state == BudgetReservationState.reserved,
            )
        )).scalars().all()
    assert ramase == []
    assert rz.asteapta_raspunsurile
