"""Migrarea `0076_practice_turn_eval_state` — plicul 247, §6.2.

Structura pe un `op` fals (modelul `test_obiective_migrare.py`); constrângerea, pe baza de test
(adusă la `head`): o valoare în afara celor trei e respinsă, rândurile vechi rămân NULL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from test_obiective_migrare import FakeAlembicOp, _load_migration

NUME = "0076_practice_turn_eval_state"


class OpCuConstrangeri(FakeAlembicOp):
    def create_check_constraint(self, name, table_name, condition, **kwargs) -> None:
        self.pasi.append(("create_check_constraint", name, table_name, str(condition)))

    def drop_constraint(self, name, table_name, type_=None, **kwargs) -> None:
        self.pasi.append(("drop_constraint", name, table_name, type_))


def test_upgrade_si_downgrade(monkeypatch) -> None:
    migrare = _load_migration(NUME)
    assert migrare.revision == NUME and len(NUME) == 29
    assert migrare.down_revision == "0075_practice_session_objective"

    op = OpCuConstrangeri()
    monkeypatch.setattr(migrare, "op", op)
    migrare.upgrade()
    assert op.pasi[0] == ("add_column", "practice_turns", "evaluare_stare")
    assert op.pasi[1][:3] == (
        "create_check_constraint", "ck_practice_turns_evaluare_stare", "practice_turns"
    )
    assert "'vine'" in op.pasi[1][3] and "'gata'" in op.pasi[1][3] and "'lipsa'" in op.pasi[1][3]
    assert not [p for p in op.pasi if p[0] == "execute"]

    op = OpCuConstrangeri()
    monkeypatch.setattr(migrare, "op", op)
    migrare.downgrade()
    assert op.pasi == [
        ("drop_constraint", "ck_practice_turns_evaluare_stare", "practice_turns", "check"),
        ("drop_column", "practice_turns", "evaluare_stare"),
    ]


def test_migrarea_nu_importa_din_aplicatie() -> None:
    cale = Path(__file__).resolve().parents[1] / "migrations" / "versions" / f"{NUME}.py"
    importuri = [r for r in cale.read_text(encoding="utf-8").splitlines()
                 if r.startswith(("import", "from"))]
    assert not [r for r in importuri if "codrut" in r]


@pytest.mark.asyncio
async def test_pe_baza_constrangerea_respinge_alta_valoare() -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select, text
    from sqlalchemy.exc import IntegrityError

    from codrut.core.database import SessionLocal
    from codrut.modules.practice.models import (
        PracticeSession,
        PracticeTurn,
        SessionKind,
        TurnRole,
    )
    from test_practice_session_flow import create_test_context

    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        sed = PracticeSession(program_settings_id=ctx["program_settings"].id,
                              participant_profile_id=ctx["profile"].id, pack_id=ctx["pack"].id,
                              kind=SessionKind.roleplay)
        s.add(sed)
        await s.flush()
        rand = PracticeTurn(session_id=sed.id, ordinal=1, role=TurnRole.actor, text="x",
                            expires_at=datetime.now(UTC) + timedelta(days=1))
        s.add(rand)
        await s.flush()
        assert (await s.execute(
            select(PracticeTurn.evaluare_stare).where(PracticeTurn.id == rand.id)
        )).scalar_one() is None
        for buna in ("vine", "gata", "lipsa"):
            await s.execute(text("UPDATE practice_turns SET evaluare_stare = :v WHERE id = :i"),
                            {"v": buna, "i": rand.id})
        with pytest.raises(IntegrityError):
            await s.execute(text("UPDATE practice_turns SET evaluare_stare = 'altceva' "
                                 "WHERE id = :i"), {"i": rand.id})
        await s.rollback()
