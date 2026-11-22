"""Migrarea `0077_reservation_profile` — plicul 250, §5.

Structura pe un `op` fals (modelul `test_obiective_migrare.py`); pe baza de test (adusă la
`head`): coloana există, poate fi goală, are cheie străină și index, iar rândurile vechi rămân
NULL. `downgrade -1` / `upgrade head` pe o bază nouă se fac în `raw/M1-migrare.txt`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from test_obiective_migrare import FakeAlembicOp, _load_migration

NUME = "0077_reservation_profile"
CHEIA = "fk_practice_budget_reservations_participant_profile_id"
INDEXUL = "ix_practice_budget_reservations_participant_profile_id"


class OpCuChei(FakeAlembicOp):
    def create_foreign_key(self, name, source_table, referent_table, local_cols, remote_cols,
                           **kwargs) -> None:
        self.pasi.append(("create_foreign_key", name, source_table, referent_table,
                          tuple(local_cols), tuple(remote_cols), kwargs.get("ondelete")))

    def drop_constraint(self, name, table_name, type_=None, **kwargs) -> None:
        self.pasi.append(("drop_constraint", name, table_name, type_))


def test_upgrade_si_downgrade(monkeypatch) -> None:
    migrare = _load_migration(NUME)
    assert migrare.revision == NUME and len(NUME) == 24
    assert migrare.down_revision == "0076_practice_turn_eval_state"
    assert len(CHEIA) <= 63

    op = OpCuChei()
    monkeypatch.setattr(migrare, "op", op)
    migrare.upgrade()
    assert op.pasi == [
        ("add_column", "practice_budget_reservations", "participant_profile_id"),
        ("create_foreign_key", CHEIA, "practice_budget_reservations", "participant_profiles",
         ("participant_profile_id",), ("id",), "SET NULL"),
        ("create_index", INDEXUL, "practice_budget_reservations"),
    ]

    op = OpCuChei()
    monkeypatch.setattr(migrare, "op", op)
    migrare.downgrade()
    assert op.pasi == [
        ("drop_index", INDEXUL),
        ("drop_constraint", CHEIA, "practice_budget_reservations", "foreignkey"),
        ("drop_column", "practice_budget_reservations", "participant_profile_id"),
    ]


def test_migrarea_nu_importa_din_aplicatie() -> None:
    cale = Path(__file__).resolve().parents[1] / "migrations" / "versions" / f"{NUME}.py"
    importuri = [r for r in cale.read_text(encoding="utf-8").splitlines()
                 if r.startswith(("import", "from"))]
    assert not [r for r in importuri if "codrut" in r]


@pytest.mark.asyncio
async def test_pe_baza_coloana_goala_cu_cheie_si_index() -> None:
    from sqlalchemy import text

    from codrut.core.database import SessionLocal

    async with SessionLocal() as s:
        coloana = (await s.execute(text(
            "SELECT data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'practice_budget_reservations' "
            "AND column_name = 'participant_profile_id'"
        ))).one()
        assert coloana == ("uuid", "YES")
        cheie = (await s.execute(text(
            "SELECT confdeltype::text, confrelid::regclass::text FROM pg_constraint "
            "WHERE conname = :n"), {"n": CHEIA})).one()
        assert cheie == ("n", "participant_profiles")
        index = (await s.execute(text(
            "SELECT count(*) FROM pg_indexes WHERE indexname = :n"), {"n": INDEXUL})).scalar_one()
        assert index == 1
