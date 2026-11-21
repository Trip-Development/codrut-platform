"""„O replică pe zi”: cele 36 de situații, pe baza migrată — plicul 236 (L2-P1), testul 1.

Textele vin din `obiective/situatii-comunicare-asertiva.json` (amprenta fixată aici, întreagă):
ordinea 1 = situația obiectivului din L1; ordinile 2 și 3 = textele aprobate de Andrei.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.modules.practice.models import PracticeObjective

AMPRENTA_SITUATII = "aaca6c5d2e8312defc5e6f4ff41bad0ef9049bb8ed918008443f34e5c39fb325"
FISIER = (
    Path(__file__).resolve().parents[1] / "src" / "codrut" / "modules" / "practice"
    / "obiective" / "situatii-comunicare-asertiva.json"
)


def test_amprenta_json_ului_din_pachet() -> None:
    assert hashlib.sha256(FISIER.read_bytes()).hexdigest() == AMPRENTA_SITUATII


@pytest.mark.asyncio
async def test_pe_baza_migrata_36_de_situatii_cate_3_pe_obiectiv_cu_textele_din_json() -> None:
    from codrut.modules.practice.models import PracticeDailySituation

    date = json.loads(FISIER.read_text(encoding="utf-8"))
    asteptat = {(s["obiectiv_nr"], s["ordine"]): s["text"] for s in date["situatii"]}
    async with SessionLocal() as session:
        randuri = (await session.execute(
            select(PracticeDailySituation, PracticeObjective)
            .join(PracticeObjective, PracticeObjective.id == PracticeDailySituation.objective_id)
            .where(PracticeDailySituation.is_active.is_(True))
        )).all()
    assert len(randuri) == 36
    gasit = {}
    for situatie, obiectiv in randuri:
        assert obiectiv.catalog == "comunicare-asertiva"
        gasit[(obiectiv.order_index, situatie.order_index)] = situatie.text
    assert gasit == asteptat
    assert sorted(gasit) == [(nr, o) for nr in range(1, 13) for o in (1, 2, 3)]
    # ordinea 1 = situația obiectivului
    for situatie, obiectiv in randuri:
        if situatie.order_index == 1:
            assert situatie.text == obiectiv.situation


@pytest.mark.asyncio
async def test_feedback_nu_are_situatii() -> None:
    from codrut.modules.practice.models import PracticeDailySituation

    async with SessionLocal() as session:
        numar = len((await session.execute(
            select(PracticeDailySituation.id)
            .join(PracticeObjective, PracticeObjective.id == PracticeDailySituation.objective_id)
            .where(PracticeObjective.catalog == "feedback")
        )).all())
    assert numar == 0
