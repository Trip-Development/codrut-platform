"""Harta echipei — pragul de 5 oameni, pe fiecare cifră (plicul 240, §6).

Câte o pereche 4/5: cu 4 oameni orice cifră e `null` cu `motiv = "prea_putini"`, cu 5 are
valoare. Totul prin rută, cu trainerul alocat al fixturii.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.modules.practice.models import PracticeObjective
from harta_echipei_fixturi import CATALOG, COMPETENTE, alege, nota, proiect_cu_oameni, sedinta
from test_practice_router import make_test_client

# miercuri, 14:00 la București: departe de granița săptămânii (plicul 255)
ACUM = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
NUL = {"valoare": None, "motiv": "prea_putini"}


def _v(valoare):
    return {"valoare": valoare, "motiv": None}


@pytest.fixture
def ceas_fix(monkeypatch):
    """Ruta vede `ACUM`, nu ceasul calculatorului (plicul 255). Paza, calculul și răspunsul
    rămân cele adevărate; se înlocuiește doar ora pe care ruta o dă calculului."""
    from codrut.modules.practice import harta_router

    calculul_adevarat = harta_router.harta_echipei

    async def la_ora_fixa(session, project_id, *, acum):
        return await calculul_adevarat(session, project_id, acum=ACUM)

    monkeypatch.setattr(harta_router, "harta_echipei", la_ora_fixa)


async def _harta(ctx) -> dict:
    async with make_test_client(ctx["trainer"]) as client:
        r = await client.get(f"/api/practice/projects/{ctx['project'].id}/harta-echipei")
    assert r.status_code == 200, r.text
    return r.json()


async def _complet(n: int) -> dict:
    """`n` oameni: câte 2 ședințe (în săptămâna lui `ACUM` (miercuri), ca lista de săptămâni
    să nu depindă de ziua rulării (plicul 255)), note în două zile diferite (acum−3 zile,
    acum−1 zi) la toate cele 7 competențe (ziua 1: 40+i+k, ziua 2: 60+i+k), toți cu
    obiectivul 3."""
    acum = ACUM
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, n)
        for i, om in enumerate(ctx["oameni"]):
            for j, (zi, baza) in enumerate(
                ((acum - timedelta(days=3), 40), (acum - timedelta(days=1), 60))
            ):
                sid = await sedinta(s, ctx, om, acum - timedelta(minutes=10 + j))
                for k, comp in enumerate(COMPETENTE):
                    await nota(s, ctx, om, sid, comp, baza + i + k, zi)
            await alege(s, ctx, om, 3)
        await s.commit()
    return ctx


@pytest.mark.asyncio
async def test_patru_oameni_nicio_cifra(ceas_fix) -> None:
    h = await _harta(await _complet(4))
    for cheie in ("invitati", "au_exersat", "sesiuni", "minute"):
        assert h[cheie] == NUL, cheie
    assert h["pe_saptamani"], "lista de săptămâni există, doar valorile sunt ascunse"
    for sapt in h["pe_saptamani"]:
        assert sapt["au_exersat"] == NUL
    assert [c["nume"] for c in h["competente"]] == COMPETENTE
    for c in h["competente"]:
        assert c["oameni"] == NUL and c["inceput"] == NUL and c["acum"] == NUL
    assert h["cele_mai_slabe"] == {"nume": None, "motiv": "prea_putini"}
    assert h["obiective"]["si_au_ales"] == NUL
    assert h["obiective"]["cele_mai_alese"] == []
    assert h["obiective"]["motiv"] == "prea_putini"


@pytest.mark.asyncio
async def test_cinci_oameni_toate_cifrele_socotite_de_mana(ceas_fix) -> None:
    h = await _harta(await _complet(5))
    assert h["prag_oameni"] == 5
    assert h["calculat_la"].replace("Z", "+00:00") == ACUM.isoformat()
    assert h["pe_saptamani"] == [{"saptamana": "2026-11-16", "au_exersat": _v(5)}]
    assert h["invitati"] == _v(5)
    assert h["au_exersat"] == _v(5)
    assert h["sesiuni"] == _v(10)
    assert h["minute"] == _v(10)            # fiecare ședință: replica actorului la 1 minut
    for sapt in h["pe_saptamani"]:
        assert sapt["au_exersat"] == _v(5)
    for k, c in enumerate(h["competente"]):
        # media pe oameni a lui 40+i+k (i = 0..4) = 42+k; a lui 60+i+k = 62+k
        assert c == {"nume": COMPETENTE[k], "oameni": _v(5), "inceput": _v(42 + k),
                     "acum": _v(62 + k)}
    assert h["cele_mai_slabe"] == {"nume": COMPETENTE[:2], "motiv": None}
    async with SessionLocal() as s:
        titlu = (await s.execute(select(PracticeObjective.title).where(
            PracticeObjective.catalog == CATALOG, PracticeObjective.order_index == 3,
        ))).scalar_one()
    assert h["obiective"] == {"si_au_ales": _v(5),
                              "cele_mai_alese": [{"nr": 3, "titlu": titlu, "oameni": 5}],
                              "motiv": None}


@pytest.mark.asyncio
async def test_sase_invitati_patru_au_exersat() -> None:
    acum = datetime.now(UTC)
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 6)
        for om in ctx["oameni"][:4]:
            await sedinta(s, ctx, om, acum - timedelta(hours=2))
        await s.commit()
    h = await _harta(ctx)
    assert h["invitati"] == _v(6)
    assert h["au_exersat"] == NUL
    assert h["sesiuni"] == NUL
    assert h["minute"] == NUL


@pytest.mark.asyncio
async def test_o_saptamana_cu_cinci_si_una_cu_patru(ceas_fix) -> None:
    acum = ACUM
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 5)
        for i, om in enumerate(ctx["oameni"]):
            await sedinta(s, ctx, om, acum - timedelta(days=7))
            if i < 4:
                await sedinta(s, ctx, om, acum - timedelta(minutes=1), replici_minute=(0.0,))
        await s.commit()
    h = await _harta(ctx)
    assert [sapt["au_exersat"] for sapt in h["pe_saptamani"]] == [_v(5), NUL]
    assert [s["saptamana"] for s in h["pe_saptamani"]] == ["2026-11-09", "2026-11-16"]


@pytest.mark.asyncio
async def test_o_competenta_cu_cinci_oameni_si_una_cu_patru() -> None:
    acum = datetime.now(UTC)
    z1, z2 = acum - timedelta(days=3), acum - timedelta(days=1)
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 5)
        for i, om in enumerate(ctx["oameni"]):
            s1 = await sedinta(s, ctx, om, z1)
            s2 = await sedinta(s, ctx, om, z2)
            await nota(s, ctx, om, s1, COMPETENTE[0], 50, z1)
            await nota(s, ctx, om, s2, COMPETENTE[0], 70, z2)
            await nota(s, ctx, om, s1, COMPETENTE[1], 30, z1)
            if i < 4:                       # al cincilea are o singură zi la B
                await nota(s, ctx, om, s2, COMPETENTE[1], 40, z2)
        await s.commit()
    h = await _harta(ctx)
    a, b = h["competente"][0], h["competente"][1]
    assert a["oameni"] == _v(5) and a["inceput"] == _v(50) and a["acum"] == _v(70)
    assert b["oameni"] == NUL and b["inceput"] == NUL and b["acum"] == NUL
    assert h["cele_mai_slabe"] == {"nume": [COMPETENTE[0]], "motiv": None}


@pytest.mark.asyncio
async def test_obiectivul_ales_de_patru_nu_apare() -> None:
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 9)
        for i, om in enumerate(ctx["oameni"]):
            await alege(s, ctx, om, 3 if i < 5 else 7)
        await s.commit()
    h = await _harta(ctx)
    assert h["obiective"]["si_au_ales"] == _v(9)
    assert [(o["nr"], o["oameni"]) for o in h["obiective"]["cele_mai_alese"]] == [(3, 5)]
    assert h["obiective"]["motiv"] is None


def test_functia_de_prag() -> None:
    from codrut.modules.practice.harta_echipei import PRAG_OAMENI, cifra

    assert PRAG_OAMENI == 5
    assert cifra(0, 0) == NUL
    assert cifra(4, 4) == NUL
    assert cifra(5, 5) == _v(5)
    assert cifra(12, 5) == _v(12)
    assert cifra(12, 4) == NUL
