"""Migrarea `0075_practice_session_objective` — plicul 244, testul 6.

Structura se verifică pe un `op` fals (modelul `test_obiective_migrare.py`); dus-întors pe baza
reală se face în poarta M1 a plicului.
"""

from __future__ import annotations

from pathlib import Path

from test_obiective_migrare import FakeAlembicOp, _load_migration

NUME = "0075_practice_session_objective"


def test_upgrade_adauga_coloana_si_indexul_downgrade_le_scoate_in_ordine(monkeypatch) -> None:
    migrare = _load_migration(NUME)
    assert migrare.revision == NUME
    assert migrare.down_revision == "0074_project_trainers"
    assert len(migrare.revision) <= 32

    op = FakeAlembicOp()
    monkeypatch.setattr(migrare, "op", op)
    migrare.upgrade()
    assert op.pasi == [
        ("add_column", "practice_sessions", "objective_id"),
        ("create_index", "ix_practice_sessions_objective_id", "practice_sessions"),
    ]

    op = FakeAlembicOp()
    monkeypatch.setattr(migrare, "op", op)
    migrare.downgrade()
    assert op.pasi == [
        ("drop_index", "ix_practice_sessions_objective_id"),
        ("drop_column", "practice_sessions", "objective_id"),
    ]


def test_migrarea_nu_importa_din_aplicatie() -> None:
    cale = Path(__file__).resolve().parents[1] / "migrations" / "versions" / f"{NUME}.py"
    text = cale.read_text(encoding="utf-8")
    assert "codrut" not in "\n".join(
        r for r in text.splitlines() if r.startswith(("import", "from"))
    )
    assert 'ondelete="RESTRICT"' in text
    assert "practice_objectives.id" in text
