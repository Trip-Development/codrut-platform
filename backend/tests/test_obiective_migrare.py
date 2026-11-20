"""Migrarea `0071_practice_objectives` — plicul 230 (L1-P1), testul 8.

Structura se verifică pe un `op` fals, care ține minte ce s-a cerut și în ce ordine. Numărătoarea
pe baza reală (12 / tabel inexistent / 12) se face separat, în poarta M1 a plicului.
"""

from __future__ import annotations

import importlib.util
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType


class FakeAlembicOp:
    def __init__(self) -> None:
        self.pasi: list[tuple[str, ...]] = []
        self.bind = object()

    def create_table(self, table_name: str, *args, **kwargs) -> None:
        self.pasi.append(("create_table", table_name))

    def create_index(self, index_name: str, table_name: str, *args, **kwargs) -> None:
        self.pasi.append(("create_index", index_name, table_name))

    def drop_index(self, index_name: str, **kwargs) -> None:
        self.pasi.append(("drop_index", index_name))

    def drop_table(self, table_name: str, **kwargs) -> None:
        self.pasi.append(("drop_table", table_name))

    def add_column(self, table_name: str, column, **kwargs) -> None:
        self.pasi.append(("add_column", table_name, column.name))

    def drop_column(self, table_name: str, column_name: str, **kwargs) -> None:
        self.pasi.append(("drop_column", table_name, column_name))

    def execute(self, *args, **kwargs) -> None:
        self.pasi.append(("execute",))

    def f(self, name: str) -> str:
        return name

    def get_bind(self) -> object:
        return self.bind

    def get_context(self) -> FakeAlembicOp:
        return self

    def autocommit_block(self) -> object:
        return nullcontext()


def _load_migration() -> ModuleType:
    cale = (
        Path(__file__).resolve().parents[1] / "migrations" / "versions"
        / "0071_practice_objectives.py"
    )
    spec = importlib.util.spec_from_file_location("practice_objectives_migration", cale)
    if spec is None or spec.loader is None:
        raise AssertionError("Migrarea 0071_practice_objectives nu se poate încărca.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migrarea_face_structura_incarca_catalogul_si_se_intoarce_in_ordine(monkeypatch) -> None:
    migration = _load_migration()
    assert migration.revision == "0071_practice_objectives"
    assert migration.down_revision == "0070_practice_consent"

    operation = FakeAlembicOp()
    monkeypatch.setattr(migration, "op", operation)
    incarcari: list[tuple[object, str, int]] = []
    monkeypatch.setattr(
        migration, "incarca_catalog",
        lambda conexiune, date: incarcari.append(
            (conexiune, date["catalog"], len(date["obiective"]))
        ) or len(date["obiective"]),
    )

    migration.upgrade()
    pasi = operation.pasi
    assert ("add_column", "practice_program_settings", "objective_catalog") in pasi
    assert ("create_table", "practice_objectives") in pasi
    assert ("create_table", "practice_objective_choices") in pasi
    indexuri = {p[1] for p in pasi if p[0] == "create_index"}
    assert indexuri == {
        "ix_practice_objectives_catalog",
        "ix_practice_objective_choices_participant_profile_id",
        "ix_practice_objective_choices_project_id",
        "ix_practice_objective_choices_objective_id",
        "uq_practice_objective_choices_current",
    }
    # cele 12 se încarcă în migrare, prin funcția comună, pe conexiunea migrării
    assert incarcari == [(operation.bind, "comunicare-asertiva", 12)]

    operation.pasi.clear()
    migration.downgrade()
    pasi = operation.pasi
    alegeri = pasi.index(("drop_table", "practice_objective_choices"))
    obiective = pasi.index(("drop_table", "practice_objectives"))
    coloana = pasi.index(("drop_column", "practice_program_settings", "objective_catalog"))
    assert alegeri < obiective < coloana
    scoase = {p[1] for p in pasi if p[0] == "drop_index"}
    assert scoase == indexuri
