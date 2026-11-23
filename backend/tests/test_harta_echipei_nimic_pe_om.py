"""Harta echipei — nimic pe om (plicul 240, §6).

Răspunsul are numai cifre de grup: niciun id de om, ședință, notă, alegere sau obiectiv,
niciun nume, adresă sau alias; cheile sunt exact cele din §4; nicio listă pe om; nimic în
jurnalul serverului; codul nu atinge 360, chestionarele, PCM, replica zilei sau modelele.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.modules.practice.conturi_test import CONTURI_DE_TEST
from codrut.modules.practice.models import (
    CompetencyScore,
    PracticeObjective,
    PracticeObjectiveChoice,
    PracticeSession,
)
from harta_echipei_fixturi import COMPETENTE, adauga_om, alege, nota, proiect_cu_oameni, sedinta
from test_practice_router import make_test_client

SRC = Path(__file__).resolve().parents[1] / "src" / "codrut" / "modules" / "practice"
FISIERE = [SRC / "harta_echipei.py", SRC / "harta_router.py"]
# miercuri, 14:00 la București: departe de granița săptămânii (plicul 255)
ACUM = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

CHEI_PERMISE = {
    "project_id", "calculat_la", "prag_oameni", "invitati", "au_exersat", "pe_saptamani",
    "saptamana", "sesiuni", "minute", "competente", "nume", "oameni", "inceput", "acum",
    "cele_mai_slabe", "obiective", "si_au_ales", "cele_mai_alese", "nr", "titlu", "motiv",
    "valoare",
}


@pytest.fixture
def ceas_fix(monkeypatch):
    """Ruta vede `ACUM`, nu ceasul calculatorului (plicul 255). Paza, calculul și răspunsul
    rămân cele adevărate; se înlocuiește doar ora pe care ruta o dă calculului."""
    from codrut.modules.practice import harta_router

    calculul_adevarat = harta_router.harta_echipei

    async def la_ora_fixa(session, project_id, *, acum):
        return await calculul_adevarat(session, project_id, acum=ACUM)

    monkeypatch.setattr(harta_router, "harta_echipei", la_ora_fixa)


async def _sase_oameni_cu_de_toate() -> tuple[dict, list[str]]:
    """6 oameni cu ședințe, note și obiective + contul de test în proiect. Întoarce
    contextul și toate valorile care nu au voie să apară (id-uri, nume, adrese, aliasuri)."""
    acum = ACUM
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 6)
        await adauga_om(s, ctx, email=next(iter(CONTURI_DE_TEST)), nume="Contul De Test")
        for i, om in enumerate(ctx["oameni"]):
            s1 = await sedinta(s, ctx, om, acum - timedelta(minutes=30))
            s2 = await sedinta(s, ctx, om, acum - timedelta(minutes=20))
            for comp in COMPETENTE:
                await nota(s, ctx, om, s1, comp, 50 + i, acum - timedelta(days=2))
                await nota(s, ctx, om, s2, comp, 60 + i, acum - timedelta(days=1))
            await alege(s, ctx, om, 3)
        await s.commit()
        ids_profil = [om["profil_id"] for om in ctx["oameni"]]
        secrete: list[str] = []
        for om in ctx["oameni"]:
            secrete += [str(om["profil_id"]), str(om["user_id"]), str(om["membru_id"]),
                        om["email"], om["cont_email"], om["nume"], om["alias"]]
        secrete += [str(ctx["trainer_user"].id), ctx["trainer_user"].email,
                    str(ctx["company"].id), str(ctx["settings"].id)]
        for tabel, coloana in (
            (PracticeSession.id, PracticeSession.participant_profile_id),
            (PracticeObjectiveChoice.id, PracticeObjectiveChoice.participant_profile_id),
            (PracticeObjectiveChoice.objective_id, PracticeObjectiveChoice.participant_profile_id),
        ):
            secrete += [str(x) for x in (await s.execute(
                select(tabel).where(coloana.in_(ids_profil))
            )).scalars().all()]
        secrete += [str(x) for x in (await s.execute(
            select(CompetencyScore.id).where(
                CompetencyScore.user_id.in_([om["user_id"] for om in ctx["oameni"]])
            )
        )).scalars().all()]
        secrete += [str(x) for x in (await s.execute(
            select(PracticeObjective.id).where(PracticeObjective.catalog == "comunicare-asertiva")
        )).scalars().all()]
    return ctx, secrete


async def _cere(ctx):
    async with make_test_client(ctx["trainer"]) as client:
        r = await client.get(f"/api/practice/projects/{ctx['project'].id}/harta-echipei")
    assert r.status_code == 200, r.text
    return r


@pytest.mark.asyncio
async def test_raspunsul_nu_contine_nimic_despre_un_om(caplog, ceas_fix) -> None:
    ctx, secrete = await _sase_oameni_cu_de_toate()
    caplog.set_level(logging.DEBUG, logger="codrut")
    inainte = len(caplog.records)
    r = await _cere(ctx)
    text = r.text
    for valoare in secrete:
        assert valoare not in text, valoare
    assert set(UUID_RE.findall(text)) == {str(ctx["project"].id)}
    # 4: nimic nou în jurnal cu id-urile sau numele de mai sus
    for rec in caplog.records[inainte:]:
        mesaj = rec.getMessage()
        for valoare in secrete:
            assert valoare not in mesaj, (rec.name, valoare)
    # cifrele sunt chiar ale celor 6 (contul de test nu intră)
    assert r.json()["invitati"]["valoare"] == 6


def _chei(obiect, adunate: set) -> set:
    if isinstance(obiect, dict):
        for k, v in obiect.items():
            adunate.add(k)
            _chei(v, adunate)
    elif isinstance(obiect, list):
        for v in obiect:
            _chei(v, adunate)
    return adunate


@pytest.mark.asyncio
async def test_cheile_sunt_exact_cele_din_plic_si_nicio_lista_pe_om(ceas_fix) -> None:
    ctx, _ = await _sase_oameni_cu_de_toate()
    h = (await _cere(ctx)).json()
    assert _chei(h, set()) == CHEI_PERMISE
    assert len(h["pe_saptamani"]) == 1                  # o săptămână, nu 6 oameni
    assert h["pe_saptamani"][0]["saptamana"] == "2026-11-16"
    assert len(h["competente"]) == len(COMPETENTE)
    assert len(h["obiective"]["cele_mai_alese"]) <= 3
    assert len(json.dumps(h)) < 5000


INTERZISE_IMPORT = (
    "codrut.modules.forms", "codrut.modules.scoring", "codrut.modules.assignments",
    "codrut.modules.practice.generation_provider", "codrut.modules.practice.motoare",
    "codrut.modules.practice.replica_zilei", "logging",
)
INTERZISE_TEXT = (
    "getLogger", "full_name", "cody_alias", "anonymous_name", "pcm", "PracticeTurn.text",
    "text_actor", "text_evaluator", "justification", "PracticeFeedback", "ParticipantMemory",
    "InsightMoment", "SessionSample", "PracticeSessionSample", "PracticeDaily",
)


@pytest.mark.parametrize("fisier", FISIERE, ids=lambda p: p.name)
def test_paza_de_cod(fisier: Path) -> None:
    sursa = fisier.read_text(encoding="utf-8")
    for nod in ast.walk(ast.parse(sursa)):
        if isinstance(nod, ast.Import):
            module = [a.name for a in nod.names]
        elif isinstance(nod, ast.ImportFrom):
            module = [nod.module or ""]
        else:
            continue
        for m in module:
            for interzis in INTERZISE_IMPORT:
                assert m != interzis and not m.startswith(interzis + "."), (fisier.name, m)
    for cuvant in INTERZISE_TEXT:
        assert cuvant.lower() not in sursa.lower(), (fisier.name, cuvant)
