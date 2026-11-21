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
        self.randuri: list[dict] = []
        self.executii: list[str] = []

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
        self.executii.append(str(args[0]) if args else "")

    def bulk_insert(self, table, rows, **kwargs) -> None:
        # plicul 235 (230b): rândurile se țin minte, ca testul să le verifice
        self.pasi.append(("bulk_insert", table.name))
        self.randuri.extend(rows)

    def f(self, name: str) -> str:
        return name

    def get_bind(self) -> object:
        return self.bind

    def get_context(self) -> FakeAlembicOp:
        return self

    def autocommit_block(self) -> object:
        return nullcontext()


def _json(cheie: str) -> dict:
    import json

    from codrut.modules.practice import obiective

    return json.loads((obiective.DOSAR / f"{cheie}.json").read_text(encoding="utf-8"))


def _load_migration(nume: str = "0071_practice_objectives") -> ModuleType:
    cale = (
        Path(__file__).resolve().parents[1] / "migrations" / "versions"
        / f"{nume}.py"
    )
    spec = importlib.util.spec_from_file_location(f"migrare_{nume}", cale)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Migrarea {nume} nu se poate încărca.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migrarea_face_structura_incarca_catalogul_si_se_intoarce_in_ordine(monkeypatch) -> None:
    migration = _load_migration()
    assert migration.revision == "0071_practice_objectives"
    assert migration.down_revision == "0070_practice_consent"

    operation = FakeAlembicOp()
    monkeypatch.setattr(migration, "op", operation)

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
    # plicul 235 (230b): cele 12 se încarcă din copia înghețată a migrării, cu `bulk_insert`
    assert pasi[-1] == ("bulk_insert", "practice_objectives")
    date = _json("comunicare-asertiva")
    assert len(operation.randuri) == 12
    assert [r["order_index"] for r in operation.randuri] == list(range(1, 13))
    for rand, o in zip(operation.randuri, date["obiective"], strict=True):
        assert rand["catalog"] == date["catalog"]
        assert rand["catalog_name"] == date["nume"]
        assert (rand["title"], rand["situation"], rand["success_sign"]) == (
            o["titlu"], o["situatie"], o["semn_de_reusita"]
        )
        assert rand["competencies"] == o["competente"]
        assert rand["is_active"] is True

    operation.pasi.clear()
    migration.downgrade()
    pasi = operation.pasi
    alegeri = pasi.index(("drop_table", "practice_objective_choices"))
    obiective = pasi.index(("drop_table", "practice_objectives"))
    coloana = pasi.index(("drop_column", "practice_program_settings", "objective_catalog"))
    assert alegeri < obiective < coloana
    scoase = {p[1] for p in pasi if p[0] == "drop_index"}
    assert scoase == indexuri


def test_migrarea_0072_pune_numai_cele_10_si_se_intoarce_in_ordine(monkeypatch) -> None:
    """Plicul 235: 0072 adaugă rânduri, fără nicio schimbare de structură."""
    migration = _load_migration("0072_practice_objectives_fb")
    assert migration.revision == "0072_practice_objectives_fb"
    assert migration.down_revision == "0071_practice_objectives"

    operation = FakeAlembicOp()
    monkeypatch.setattr(migration, "op", operation)
    migration.upgrade()
    assert operation.pasi == [("bulk_insert", "practice_objectives")]
    date = _json("feedback")
    assert len(operation.randuri) == 10
    assert [r["order_index"] for r in operation.randuri] == list(range(1, 11))
    assert {r["catalog"] for r in operation.randuri} == {"feedback"}
    assert [r["title"] for r in operation.randuri] == [o["titlu"] for o in date["obiective"]]

    operation.pasi.clear()
    migration.downgrade()
    assert operation.pasi == [("execute",), ("execute",), ("execute",)]
    setari, alegeri, obiective = operation.executii
    assert setari.startswith("UPDATE practice_program_settings SET objective_catalog = NULL")
    assert alegeri.startswith("DELETE FROM practice_objective_choices")
    assert obiective.startswith("DELETE FROM practice_objectives")
    assert all("'feedback'" in cerere for cerere in operation.executii)
