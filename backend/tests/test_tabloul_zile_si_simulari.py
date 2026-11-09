"""Tabloul: „zile la rând cu activitate” și „N simulări făcute” — plicul 201.

Andrei, 1 oct: „Nr de zile dar trebuie să și facă ceva. simulare sau quiz sau strategie” ·
„Sau rămân amândouă.” 18 oct: numărul = total, de la prima ședință; eticheta = „simulări
făcute”. Se numără ședințele ÎNCHISE ale omului care au note în cuprinsul Tabloului, de orice
fel; nu cele începute și lăsate, nici cele prea scurte (fără note), nici cele de pe alt proiect.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.practice.models import PracticeSession, SessionKind, SessionState
from test_tabloul_numai_pe_proiect import _fixture, _note, _sedinta, _tablou

ZI = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
O_NOTA = {"Feedback constructiv": 60}


@pytest.mark.asyncio
async def test_simulari_facute_numai_sedintele_inchise_cu_note_pe_proiect() -> None:
    async with SessionLocal() as s:
        ctx, p, setari, _sed_a, _sed_b = await _fixture(s)
        # pe A, fixture-ul are deja o ședință închisă cu note (role-play + rezumat) → 1
        assert (await _tablou(s, ctx, p["A"]))["sessions_completed"] == 1

        # un quiz închis, cu note → se numără
        quiz = await _sedinta(s, ctx, setari["A"], ZI, kind=SessionKind.knowledge)
        await _note(s, ctx, p["A"], str(quiz.id), O_NOTA, ZI, "knowledge")
        # o strategie începută, lăsată deschisă, fără note → nu se numără
        deschisa = PracticeSession(
            program_settings_id=setari["A"].id, participant_profile_id=ctx["profile"].id,
            pack_id=ctx["pack"].id, kind=SessionKind.coaching, state=SessionState.open,
            started_at=ZI,
        )
        s.add(deschisa)
        # una închisă, dar prea scurtă — fără nicio notă → nu se numără
        await _sedinta(s, ctx, setari["A"], ZI)
        await s.flush()

        assert (await _tablou(s, ctx, p["A"]))["sessions_completed"] == 2
        # pe B: numai ședința lui B; quizul de pe A nu se vede aici
        assert (await _tablou(s, ctx, p["B"]))["sessions_completed"] == 1
        # proiectul fără nicio ședință
        assert (await _tablou(s, ctx, p["C"]))["sessions_completed"] == 0
        await s.rollback()


@pytest.mark.asyncio
async def test_o_sedinta_neinchisa_cu_note_nu_se_numara() -> None:
    async with SessionLocal() as s:
        ctx, p, setari, _sed_a, _sed_b = await _fixture(s)
        neinchisa = PracticeSession(
            program_settings_id=setari["A"].id, participant_profile_id=ctx["profile"].id,
            pack_id=ctx["pack"].id, kind=SessionKind.roleplay, state=SessionState.open,
            started_at=ZI,
        )
        s.add(neinchisa)
        await s.flush()
        await _note(s, ctx, p["A"], str(neinchisa.id), O_NOTA, ZI, "roleplay")
        assert (await _tablou(s, ctx, p["A"]))["sessions_completed"] == 1
        await s.rollback()
