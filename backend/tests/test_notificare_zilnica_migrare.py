"""Migrarea `0078_daily_reminders` — plicul 252 (L3-P2), §6.5.

Structura pe fișier; baza reală (la `head` în suită) refuză o oră 22. Dus-întorsul pe o bază nouă
se face separat, în poarta M1.
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from codrut.core.database import SessionLocal

VERSIUNI = Path(__file__).resolve().parents[1] / "migrations" / "versions"
CALE = VERSIUNI / "0078_daily_reminders.py"


def test_un_singur_cap_0078_peste_0077() -> None:
    sursa = CALE.read_text(encoding="utf-8")
    assert 'revision = "0078_daily_reminders"' in sursa
    assert 'down_revision = "0077_reservation_profile"' in sursa
    urmasi = [p.name for p in VERSIUNI.glob("*.py")
              if 'down_revision = "0078_daily_reminders"' in p.read_text(encoding="utf-8")]
    assert urmasi == []


def test_fara_import_din_codrut_si_fara_date_mutate() -> None:
    arbore = ast.parse(CALE.read_text(encoding="utf-8"))
    for nod in ast.walk(arbore):
        if isinstance(nod, ast.ImportFrom):
            assert not (nod.module or "").startswith("codrut")
        if isinstance(nod, ast.Import):
            assert all(not a.name.startswith("codrut") for a in nod.names)
    sursa = CALE.read_text(encoding="utf-8")
    assert "op.execute" not in sursa and "bulk_insert" not in sursa


def test_numele_cheilor_au_cel_mult_63_de_caractere() -> None:
    sursa = CALE.read_text(encoding="utf-8")
    for nume in ("fk_practice_daily_reminders_profile", "fk_practice_daily_reminders_project",
                 "uq_practice_daily_reminders_endpoint", "pk_practice_daily_reminders",
                 "ck_practice_daily_reminders_ora_intre_7_si_21",
                 "ix_practice_daily_reminders_participant_profile_id"):
        assert nume in sursa and len(nume) <= 63


@pytest.mark.asyncio
async def test_baza_refuza_ora_22_si_adresa_dubla() -> None:
    from test_replica_zilei_profesor import proiect_legat

    async with SessionLocal() as s:
        ctx = await proiect_legat(s)
        await s.commit()
    profil, proiect = ctx["profile"].id, ctx["project"].id
    for ora in (22, 6):
        async with SessionLocal() as s:
            with pytest.raises(IntegrityError):
                await s.execute(text(
                    "insert into practice_daily_reminders (id, participant_profile_id, project_id,"
                    " endpoint, ora) values (:i, :p, :r, :e, :o)"
                ), {"i": uuid.uuid4(), "p": profil, "r": proiect,
                    "e": f"https://fcm.googleapis.com/{uuid.uuid4().hex}", "o": ora})
                await s.commit()
    e = f"https://fcm.googleapis.com/{uuid.uuid4().hex}"
    async with SessionLocal() as s:
        await s.execute(text(
            "insert into practice_daily_reminders (id, participant_profile_id, project_id,"
            " endpoint, ora) values (:i, :p, :r, :e, 9)"
        ), {"i": uuid.uuid4(), "p": profil, "r": proiect, "e": e})
        await s.commit()
    try:
        async with SessionLocal() as s:
            with pytest.raises(IntegrityError):
                await s.execute(text(
                    "insert into practice_daily_reminders (id, participant_profile_id, project_id,"
                    " endpoint, ora) values (:i, :p, :r, :e, 10)"
                ), {"i": uuid.uuid4(), "p": profil, "r": proiect, "e": e})
                await s.commit()
    finally:
        async with SessionLocal() as s:
            await s.execute(text("delete from practice_daily_reminders where endpoint = :e"),
                            {"e": e})
            await s.commit()
