"""Punctajul nou, pe drumul întreg: notă → ședință → tipul interlocutorului → Tablou — plicul 165 B.

Tipul nu e salvat pe ședință: se deduce din rotația de la pornire (al k-lea role-play al profilului
→ `rotatie[k % len]`). Nota unei ședințe care nu e role-play nu intră, oricum ar fi scris
`source_type` (rezumatul de la închidere scrie „session” la orice fel de ședință).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.competency_aliases import CANONICAL_COMPETENCIES
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.interlocutor import sedintele_notelor
from codrut.modules.practice.models import (
    CompetencyScore,
    PracticeSession,
    SessionKind,
    SessionState,
)
from test_practice_session_flow import create_test_context

COMP = CANONICAL_COMPETENCIES[0]


async def _context_cu_cont(s, grup):
    ctx = await create_test_context(s)
    cont = User(email=f"punctaj-{uuid.uuid4().hex[:6]}@example.com", password_hash="x",  # noqa: S106
                role=UserRole.participant)
    s.add(cont)
    await s.flush()
    ctx["profile"].user_id = cont.id
    ctx["profile"].role_group = grup
    await s.flush()
    ctx["principal"] = ctx["principal"].model_copy(update={"user_id": cont.id, "email": cont.email})
    return ctx


async def _sedinta(s, ctx, kind, cand):
    sed = PracticeSession(
        program_settings_id=ctx["program_settings"].id,
        participant_profile_id=ctx["profile"].id,
        pack_id=ctx["pack"].id,
        kind=kind,
        state=SessionState.closed,
        started_at=cand,
    )
    s.add(sed)
    await s.flush()
    return sed


async def _nota(s, ctx, sed, scor, cand, sursa="roleplay"):
    s.add(CompetencyScore(
        user_id=ctx["principal"].user_id, project_id=ctx["project"].id, score=scor, level=2,
        conversation_id=str(sed.id), competency_name=COMP, source_type=sursa, created_at=cand,
    ))
    await s.flush()


@pytest.mark.asyncio
async def test_tipul_dedus_din_rotatie_si_punctele_pe_tablou() -> None:
    async with SessionLocal() as s:
        # cine conduce oameni are rotația: jos, lateral, sus, client
        ctx = await _context_cu_cont(s, "leadership")
        azi = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
        zile = [azi - timedelta(days=d) for d in (3, 2, 1)]
        # trei role-play-uri, pe rând (k = 0, 1, 2) și un quiz între ele
        rp0 = await _sedinta(s, ctx, SessionKind.roleplay, zile[0])
        quiz = await _sedinta(s, ctx, SessionKind.knowledge, zile[0] + timedelta(hours=1))
        rp1 = await _sedinta(s, ctx, SessionKind.roleplay, zile[1])
        rp2 = await _sedinta(s, ctx, SessionKind.roleplay, zile[2])

        tipuri = await sedintele_notelor(s, [str(x.id) for x in (rp0, quiz, rp1, rp2)])
        assert tipuri[str(rp0.id)] == ("roleplay", "jos")
        assert tipuri[str(rp1.id)] == ("roleplay", "lateral")
        assert tipuri[str(rp2.id)] == ("roleplay", "sus")
        assert tipuri[str(quiz.id)] == ("knowledge", None)

        await _nota(s, ctx, rp0, 80, zile[0])                 # 30 + 25 (jos)
        await _nota(s, ctx, quiz, 100, zile[0], "session")    # quiz: NU intră
        await _nota(s, ctx, rp1, 50, zile[1])                 # sub 60: 0, fără bonus
        await _nota(s, ctx, rp2, 70, zile[2])                 # 20 + 25 (sus)

        date = await PracticeDashboardService(s).get_participant_dashboard_data(
            ctx["principal"], ctx["project"].id
        )
        comp = next(c for c in date["competencies"] if c["name"] == COMP)
        assert comp["points"] == 30 + 25 + 20 + 25
        assert comp["interlocutor_types"] == 2
        assert comp["total_roleplays"] == 3
        assert comp["level"] == "APLICARE"
        assert date["points_total"] == 100
        await s.rollback()


@pytest.mark.asyncio
async def test_cine_nu_conduce_are_rotatia_lui() -> None:
    async with SessionLocal() as s:
        ctx = await _context_cu_cont(s, "member")  # rotația: lateral, sus, client
        cand = datetime.now(UTC) - timedelta(days=5)
        sedinte = [await _sedinta(s, ctx, SessionKind.roleplay, cand + timedelta(days=i))
                   for i in range(4)]
        tipuri = await sedintele_notelor(s, [str(x.id) for x in sedinte] + ["nu-e-uuid"])
        assert [tipuri[str(x.id)][1] for x in sedinte] == ["lateral", "sus", "client", "lateral"]
        assert "nu-e-uuid" not in tipuri
        assert str(uuid.uuid4()) not in tipuri
        await s.rollback()
