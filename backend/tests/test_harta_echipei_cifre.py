"""Harta echipei — cum se socotesc cifrele (plicul 240, §3 și §6).

`acum` fix = joi 19 nov 2026 12:00 UTC. Calculul se cheamă direct (`harta_echipei`), nu prin
rută, ca datele să poată sta în trecut. Mediile sunt rotunjite la număr întreg (corecția 1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.practice.conturi_test import CONTURI_DE_TEST
from codrut.modules.practice.models import SessionKind
from harta_echipei_fixturi import (
    COMPETENTE,
    adauga_om,
    alege,
    nota,
    proiect_cu_oameni,
    sedinta,
    setari_noi,
)

ACUM = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
A = COMPETENTE[0]


async def _harta(s, ctx, acum=ACUM) -> dict:
    from codrut.modules.practice.harta_echipei import harta_echipei

    return await harta_echipei(s, ctx["project"].id, acum=acum)


def _val(cifra):
    return cifra["valoare"]


@pytest.mark.asyncio
async def test_duminica_seara_utc_e_luni_la_bucuresti() -> None:
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 5)
        for om in ctx["oameni"]:
            await sedinta(s, ctx, om, datetime(2026, 11, 15, 22, 30, tzinfo=UTC))
        h = await _harta(s, ctx)
        assert [(w["saptamana"], _val(w["au_exersat"])) for w in h["pe_saptamani"]] == [
            ("2026-11-16", 5)
        ]
        await s.rollback()


@pytest.mark.asyncio
async def test_sedinta_fara_replica_omului_nu_se_numara() -> None:
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 6)
        start = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
        for om in ctx["oameni"][:5]:
            await sedinta(s, ctx, om, start, replici_minute=(0.0, 4.0))
        # al șaselea: numai actorul a vorbit, de mai multe ori
        await sedinta(s, ctx, ctx["oameni"][5], start, replici_minute=(0.0, 30.0), cu_omul=False)
        await sedinta(s, ctx, ctx["oameni"][0], start, replici_minute=(0.0, 50.0), cu_omul=False)
        h = await _harta(s, ctx)
        assert _val(h["au_exersat"]) == 5
        assert _val(h["sesiuni"]) == 5
        assert _val(h["minute"]) == 20
        assert [_val(w["au_exersat"]) for w in h["pe_saptamani"]] == [5]
        await s.rollback()


@pytest.mark.asyncio
async def test_durata_plafonata_la_60_si_suma_rotunjita() -> None:
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 5)
        start = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
        oameni = ctx["oameni"]
        await sedinta(s, ctx, oameni[0], start, replici_minute=(0.0, 10.0, 25.0))   # 25
        await sedinta(s, ctx, oameni[1], start, replici_minute=(0.0, 180.0))        # 3 ore → 60
        await sedinta(s, ctx, oameni[2], start, replici_minute=(0.0,))              # numai omul → 0
        await sedinta(s, ctx, oameni[3], start, replici_minute=(0.0, 10.0))         # 10
        await sedinta(s, ctx, oameni[4], start, replici_minute=(0.0, 10 + 20 / 60))  # 10 min 20 s
        h = await _harta(s, ctx)
        assert _val(h["sesiuni"]) == 5
        assert _val(h["minute"]) == 105        # 25 + 60 + 0 + 10 + 10,33 = 105,33 → 105
        await s.rollback()


@pytest.mark.asyncio
async def test_lista_de_saptamani_cu_gol_la_mijloc_pana_la_acum() -> None:
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 5)
        for om in ctx["oameni"]:
            await sedinta(s, ctx, om, datetime(2026, 11, 3, 10, 0, tzinfo=UTC))
        h = await _harta(s, ctx)
        assert [(w["saptamana"], _val(w["au_exersat"])) for w in h["pe_saptamani"]] == [
            ("2026-11-02", 5), ("2026-11-09", None), ("2026-11-16", None),
        ]
        assert h["pe_saptamani"][1]["au_exersat"]["motiv"] == "prea_putini"
        h_gol = await _harta(s, {"project": (await proiect_cu_oameni(s, 5))["project"]})
        assert h_gol["pe_saptamani"] == []
        await s.rollback()


@pytest.mark.asyncio
async def test_notele_din_afara_role_play_ului_proiectului_nu_intra() -> None:
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 5)
        alt_proiect, alt_pachet, alte_setari = await setari_noi(s, ctx["company"].id)
        z1 = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
        z2 = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
        for om in ctx["oameni"]:
            s1 = await sedinta(s, ctx, om, z1)
            s2 = await sedinta(s, ctx, om, z2)
            await nota(s, ctx, om, s1, A, 50, z1)
            await nota(s, ctx, om, s2, A, 70, z2)
            coaching = await sedinta(s, ctx, om, z2, kind=SessionKind.coaching)
            alta = await sedinta(s, ctx, om, z2, setari=alte_setari, pachet=alt_pachet)
            await nota(s, ctx, om, s2, A, 0, z2, source_type="quiz")
            await nota(s, ctx, om, coaching, A, 0, z2)
            await nota(s, ctx, om, alta, A, 0, z2)
            await nota(s, ctx, om, "arhiva-inventata", A, 0, z2)
            await nota(s, ctx, om, s1, A, 100, z1, source_type="test_in")
        h = await _harta(s, ctx)
        a = h["competente"][0]
        assert (_val(a["oameni"]), _val(a["inceput"]), _val(a["acum"])) == (5, 50, 70)
        await s.rollback()


@pytest.mark.asyncio
async def test_inceput_si_acum_pe_om_apoi_media_grupului() -> None:
    note = [  # (zi, scor)
        [(1, 40), (1, 60), (3, 80)],     # început 50, acum 80
        [(1, 55), (2, 65)],
        [(1, 61), (2, 70)],
        [(1, 47), (4, 90)],
        [(1, 52), (2, 52)],
        [(2, 99)],                       # o singură zi: nu intră
    ]
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, len(note))
        for om, ale_lui in zip(ctx["oameni"], note, strict=True):
            sid = await sedinta(s, ctx, om, datetime(2026, 11, 16, 8, 0, tzinfo=UTC))
            for zi, scor in ale_lui:
                await nota(s, ctx, om, sid, A, scor,
                           datetime(2026, 11, 15, 9, 0, tzinfo=UTC) + timedelta(days=zi))
        h = await _harta(s, ctx)
        a = h["competente"][0]
        assert _val(a["oameni"]) == 5
        assert _val(a["inceput"]) == 53          # (50 + 55 + 61 + 47 + 52) / 5 = 53
        assert _val(a["acum"]) == 71             # (80 + 65 + 70 + 90 + 52) / 5 = 71,4 → 71
        await s.rollback()


@pytest.mark.asyncio
async def test_contul_de_test_nu_se_numara_nicaieri() -> None:
    z1 = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
    z2 = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 5)
        test = await adauga_om(s, ctx, email=next(iter(CONTURI_DE_TEST)), nume="Contul De Test")
        for om in ctx["oameni"]:
            e_test = om is test
            s1 = await sedinta(s, ctx, om, z1, replici_minute=(0.0, 50.0 if e_test else 5.0))
            s2 = await sedinta(s, ctx, om, z2, replici_minute=(0.0, 5.0))
            await nota(s, ctx, om, s1, A, 0 if e_test else 50, z1)
            await nota(s, ctx, om, s2, A, 100 if e_test else 70, z2)
            await alege(s, ctx, om, 7 if e_test else 3)
        h = await _harta(s, ctx)
        assert _val(h["invitati"]) == 5
        assert _val(h["au_exersat"]) == 5
        assert _val(h["sesiuni"]) == 10
        assert _val(h["minute"]) == 50
        a = h["competente"][0]
        assert (_val(a["oameni"]), _val(a["inceput"]), _val(a["acum"])) == (5, 50, 70)
        assert _val(h["obiective"]["si_au_ales"]) == 5
        assert [(o["nr"], o["oameni"]) for o in h["obiective"]["cele_mai_alese"]] == [(3, 5)]
        await s.rollback()


@pytest.mark.asyncio
async def test_cele_mai_slabe_dupa_acum_egalitatea_dupa_ordinea_proiectului() -> None:
    acum_pe_comp = {COMPETENTE[0]: 80, COMPETENTE[1]: 50, COMPETENTE[2]: 40, COMPETENTE[3]: 40}
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 5)
        for om in ctx["oameni"]:
            sid = await sedinta(s, ctx, om, datetime(2026, 11, 16, 8, 0, tzinfo=UTC))
            for comp, scor in acum_pe_comp.items():
                await nota(s, ctx, om, sid, comp, 30, datetime(2026, 11, 16, 9, 0, tzinfo=UTC))
                await nota(s, ctx, om, sid, comp, scor, datetime(2026, 11, 18, 9, 0, tzinfo=UTC))
        h = await _harta(s, ctx)
        assert h["cele_mai_slabe"] == {"nume": [COMPETENTE[2], COMPETENTE[3]], "motiv": None}
        await s.rollback()


@pytest.mark.asyncio
async def test_obiectivele_curente_ordinea_si_proiectul_fara_catalog() -> None:
    grupuri = [(5, 6), (2, 5), (3, 5), (4, 5)]   # (nr, câți) — 21 de oameni
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, sum(c for _, c in grupuri))
        oameni = iter(ctx["oameni"])
        for nr, cati in grupuri:
            for _ in range(cati):
                om = next(oameni)
                if nr == 5:
                    await alege(s, ctx, om, 2, inlocuita=True)   # alegere veche, nu se numără
                await alege(s, ctx, om, nr)
        h = await _harta(s, ctx)
        ob = h["obiective"]
        assert _val(ob["si_au_ales"]) == 21
        assert [(o["nr"], o["oameni"]) for o in ob["cele_mai_alese"]] == [(5, 6), (2, 5), (3, 5)]
        assert ob["motiv"] is None

        fara = await proiect_cu_oameni(s, 5, catalog=None)
        for om in fara["oameni"]:
            await alege(s, fara, om, 3)
        h = await _harta(s, fara)
        assert h["obiective"] == {"si_au_ales": {"valoare": None, "motiv": "prea_putini"},
                                  "cele_mai_alese": [], "motiv": "fara_obiective"}
        await s.rollback()


@pytest.mark.asyncio
async def test_numarul_de_note_e_cel_din_evolutie() -> None:
    from codrut.modules.practice.evolution_service import PracticeEvolutionService
    from codrut.modules.practice.harta_echipei import notele_pe_competenta

    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 5)
        for i, om in enumerate(ctx["oameni"]):
            sid = await sedinta(s, ctx, om, datetime(2026, 11, 16, 8, 0, tzinfo=UTC))
            for k, comp in enumerate(COMPETENTE[: i + 2]):
                for zi in range(k % 3 + 1):
                    await nota(s, ctx, om, sid, comp, 60,
                               datetime(2026, 11, 16, 9, 0, tzinfo=UTC) + timedelta(days=zi))
        pe_comp = await notele_pe_competenta(s, ctx["project"].id)
        evolutie = await PracticeEvolutionService(s).project_evolution(ctx["project"].id)
        assert {c["name"]: c["scores_count"] for c in evolutie["competencies"]} == {
            nume: len(lst) for nume, lst in pe_comp.items()
        }
        assert sum(len(lst) for lst in pe_comp.values()) > 0
        await s.rollback()
