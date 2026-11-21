"""„O replică pe zi”: alegerea situației zilei — plicul 236 (L2-P1), testul 2.

Fără repetare până se termină lista, apoi de la capăt; din obiectivul omului, sau, fără obiectiv,
din toată lista proiectului (întâi toate „ordinea 1”, apoi „ordinea 2”, apoi „ordinea 3”).
Profesorul e fals; ziua se dă din test.
"""

from __future__ import annotations

from collections import namedtuple
from datetime import timedelta

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.modules.practice.models import PracticeObjective
from test_replica_zilei_profesor import ACUM, al_doilea_om, proiect_legat, trimite

Cand = namedtuple("Cand", "id")


def test_functia_pura_alege_cel_mai_putin_folosit_iar_la_egalitate_primul() -> None:
    from codrut.modules.practice.replica_zilei import alege_situatia

    a, b, c = Cand("a"), Cand("b"), Cand("c")
    assert alege_situatia([], {}) is None
    assert alege_situatia([a, b, c], {}) is a
    assert alege_situatia([a, b, c], {"a": 1}) is b
    assert alege_situatia([a, b, c], {"a": 1, "b": 1}) is c
    assert alege_situatia([a, b, c], {"a": 1, "b": 1, "c": 1}) is a
    assert alege_situatia([a, b, c], {"a": 2, "b": 1, "c": 2}) is b


async def _obiectivul(session, nr: int) -> PracticeObjective:
    return (await session.execute(
        select(PracticeObjective)
        .where(PracticeObjective.catalog == "comunicare-asertiva",
               PracticeObjective.order_index == nr)
    )).scalar_one()


async def _alege(session, ctx, nr: int, principal=None) -> None:
    from codrut.modules.practice import objective_service as svc

    obiectiv = await _obiectivul(session, nr)
    await svc.alege(session, principal or ctx["principal"], ctx["project"].id, obiectiv.id)
    await session.commit()


async def _situatia(session, ctx, zi: int, principal=None) -> tuple[int, int]:
    from codrut.modules.practice import replica_zilei as rz

    stare = await rz.starea_zilei(
        session, principal or ctx["principal"], ctx["project"].id,
        acum=ACUM + timedelta(days=zi),
    )
    s = stare["situatie"]
    return (s["obiectiv_nr"], await _ordinea(session, s["id"]))


async def _ordinea(session, situatie_id) -> int:
    from codrut.modules.practice.models import PracticeDailySituation

    return (await session.get(PracticeDailySituation, situatie_id)).order_index


async def _o_zi(session, ctx, zi: int, principal=None) -> tuple[int, int]:
    """Situația zilei `zi`, apoi replica omului pe ea."""
    alesa = await _situatia(session, ctx, zi, principal)
    await trimite(session, ctx, acum=ACUM + timedelta(days=zi), principal=principal)
    return alesa


@pytest.mark.asyncio
async def test_a_din_obiectivul_ales_fara_repetare_apoi_de_la_capat() -> None:
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        await _alege(session, ctx, 3)
        zile = [await _o_zi(session, ctx, z) for z in range(5)]
        assert zile == [(3, 1), (3, 2), (3, 3), (3, 1), (3, 2)]


@pytest.mark.asyncio
async def test_b_doua_citiri_in_aceeasi_zi_dau_aceeasi_situatie() -> None:
    from codrut.modules.practice import replica_zilei as rz

    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        await _alege(session, ctx, 5)
        unu = await rz.starea_zilei(session, ctx["principal"], ctx["project"].id, acum=ACUM)
        doi = await rz.starea_zilei(
            session, ctx["principal"], ctx["project"].id, acum=ACUM + timedelta(hours=5)
        )
        assert unu["situatie"] == doi["situatie"]
        assert unu["din_obiectivul_meu"] is True and unu["motiv"] is None
        assert unu["azi"] is None
        assert set(unu["situatie"]) == {"id", "text", "obiectiv_nr", "obiectiv_titlu"}
        # după replica de azi, situația de azi e a replicii și `azi` e completat
        await trimite(session, ctx)
        trei = await rz.starea_zilei(
            session, ctx["principal"], ctx["project"].id, acum=ACUM + timedelta(hours=1)
        )
        assert trei["situatie"] == unu["situatie"]
        assert trei["azi"]["situatie_id"] == unu["situatie"]["id"]
        assert set(trei["azi"]) == {"situatie_id", "replica", "raspuns", "nota", "trimisa_la"}


@pytest.mark.asyncio
async def test_c_schimbarea_obiectivului_trece_la_lista_noua() -> None:
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        await _alege(session, ctx, 3)
        assert await _o_zi(session, ctx, 0) == (3, 1)
        await _alege(session, ctx, 7)
        assert await _situatia(session, ctx, 1) == (7, 1)


@pytest.mark.asyncio
async def test_d_fara_obiectiv_toata_lista_pe_ordini_apoi_de_la_capat() -> None:
    from codrut.modules.practice import replica_zilei as rz

    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        stare = await rz.starea_zilei(session, ctx["principal"], ctx["project"].id, acum=ACUM)
        assert stare["din_obiectivul_meu"] is False
        zile = [await _o_zi(session, ctx, z) for z in range(37)]
        asteptat = [(nr, o) for o in (1, 2, 3) for nr in range(1, 13)]
        assert zile == asteptat + [(1, 1)]


@pytest.mark.asyncio
async def test_e_replicile_fara_obiectiv_conteaza_dupa_alegere() -> None:
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        assert await _o_zi(session, ctx, 0) == (1, 1)
        await _alege(session, ctx, 1)
        assert await _situatia(session, ctx, 1) == (1, 2)


@pytest.mark.asyncio
async def test_f_fara_catalog_si_catalog_fara_situatii() -> None:
    from codrut.modules.practice import replica_zilei as rz

    async with SessionLocal() as session:
        for catalog, motiv in ((None, "fara_obiective"), ("feedback", "fara_situatii")):
            ctx = await proiect_legat(session, catalog=catalog)
            await session.commit()
            stare = await rz.starea_zilei(session, ctx["principal"], ctx["project"].id, acum=ACUM)
            assert stare["situatie"] is None and stare["motiv"] == motiv, catalog
            assert stare["azi"] is None and stare["serie"] == 0


@pytest.mark.asyncio
async def test_g_doi_oameni_nu_se_influenteaza() -> None:
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        _, al_doilea = await al_doilea_om(session, ctx)
        await session.commit()
        await _alege(session, ctx, 2)
        await _alege(session, ctx, 2, principal=al_doilea)
        assert await _o_zi(session, ctx, 0) == (2, 1)
        assert await _o_zi(session, ctx, 1) == (2, 2)
        # al doilea om începe de la capăt, oricât ar fi făcut primul
        assert await _situatia(session, ctx, 1, principal=al_doilea) == (2, 1)
