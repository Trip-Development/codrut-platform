"""Catalogul de obiective de aplicare — plicul 230 (L1-P1), testele 1, 2 și 7.

Cele 12 obiective de comunicare asertivă sunt aprobate de Andrei (17–18 nov 2026, situația
obiectivului 4 pe 20 nov). Textul stă în `obiective/comunicare-asertiva.json`; amprenta lui e fixată
aici: cine schimbă textul fără o migrare nouă primește roșu.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest
from sqlalchemy import String, func, select

from codrut.core.database import SessionLocal

# shasum -a 256 pe fișierul aprobat (SPEC-CODY/FISE/L1-obiective-comunicare-asertiva.json)
AMPRENTA_COMUNICARE_ASERTIVA = "073eb142a813ea162c1cd15af548b1ed484c1ba3c3fbe0fb95f365151a718a73"


def _cale_json():
    from codrut.modules.practice import obiective

    return obiective.DOSAR / "comunicare-asertiva.json"


def test_amprenta_json_ului_aprobat_e_fixata() -> None:
    assert hashlib.sha256(_cale_json().read_bytes()).hexdigest() == AMPRENTA_COMUNICARE_ASERTIVA


async def _randurile(session, catalog: str):
    from codrut.modules.practice.models import PracticeObjective

    return (await session.execute(
        select(PracticeObjective)
        .where(PracticeObjective.catalog == catalog, PracticeObjective.is_active.is_(True))
        .order_by(PracticeObjective.order_index)
    )).scalars().all()


@pytest.mark.asyncio
async def test_incarcarea_pune_cele_12_in_ordine_si_nu_dubleaza() -> None:
    from codrut.modules.practice.obiective import citeste_catalog, incarca_catalog

    date = json.loads(_cale_json().read_text(encoding="utf-8"))
    async with SessionLocal() as session:
        for _ in range(2):  # a doua încărcare nu dublează nimic
            scrise = await session.run_sync(
                lambda s: incarca_catalog(s.connection(), citeste_catalog("comunicare-asertiva"))
            )
            assert scrise == 12
            randuri = await _randurile(session, "comunicare-asertiva")
            assert len(randuri) == 12
        assert [r.order_index for r in randuri] == list(range(1, 13))
        for rand, o in zip(randuri, date["obiective"], strict=True):
            assert rand.catalog_name == date["nume"]
            assert rand.title == o["titlu"]
            assert rand.situation == o["situatie"]
            assert rand.success_sign == o["semn_de_reusita"]
            assert rand.competencies == o["competente"]
        await session.rollback()


@pytest.mark.asyncio
async def test_o_competenta_din_afara_celor_7_e_refuzata_si_nu_scrie_nimic() -> None:
    from codrut.modules.practice.models import PracticeObjective
    from codrut.modules.practice.obiective import CatalogInvalid, citeste_catalog, incarca_catalog

    date = copy.deepcopy(citeste_catalog("comunicare-asertiva"))
    date["catalog"] = "catalog-de-test-gresit"
    date["obiective"][11]["competente"] = ["Feedback constructiv", "Negociere"]
    async with SessionLocal() as session:
        with pytest.raises(CatalogInvalid):
            await session.run_sync(lambda s: incarca_catalog(s.connection(), date))
        numar = (await session.execute(
            select(func.count()).select_from(PracticeObjective)
            .where(PracticeObjective.catalog == "catalog-de-test-gresit")
        )).scalar_one()
        assert numar == 0
        await session.rollback()


def _coloane_text(model) -> set[str]:
    return {c.name for c in model.__table__.columns if isinstance(c.type, String)}


def test_tabelele_noi_nu_au_nume_email_sau_text_liber() -> None:
    from codrut.modules.practice.models import PracticeObjective, PracticeObjectiveChoice

    assert _coloane_text(PracticeObjectiveChoice) == set()
    assert _coloane_text(PracticeObjective) == {
        "catalog", "catalog_name", "title", "situation", "success_sign",
    }
    for model in (PracticeObjective, PracticeObjectiveChoice):
        for coloana in model.__table__.columns:
            assert "email" not in coloana.name
            assert coloana.name in {"catalog_name"} or "name" not in coloana.name
