"""Migrarea `0073_practice_daily_replies` — plicul 236 (L2-P1), testul 7.

Structura se verifică pe un `op` fals, care ține minte ce s-a cerut și în ce ordine (ca la 235).
Numărătoarea pe baza reală (36 / tabele inexistente / 36) se face separat, în poarta M1.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa

CALE = (
    Path(__file__).resolve().parents[1] / "migrations" / "versions"
    / "0073_practice_daily_replies.py"
)
JSON = (
    Path(__file__).resolve().parents[1] / "src" / "codrut" / "modules" / "practice"
    / "obiective" / "situatii-comunicare-asertiva.json"
)


class FakeAlembicOp:
    def __init__(self) -> None:
        self.pasi: list[tuple[str, ...]] = []
        self.tabele: dict[str, list[sa.Column]] = {}
        self.executii: list = []
        self.randuri: list[dict] = []

    def create_table(self, table_name: str, *args, **kwargs) -> None:
        self.pasi.append(("create_table", table_name))
        self.tabele[table_name] = [a for a in args if isinstance(a, sa.Column)]

    def create_index(self, index_name: str, table_name: str, *args, **kwargs) -> None:
        self.pasi.append(("create_index", index_name, table_name))

    def drop_index(self, index_name: str, **kwargs) -> None:
        self.pasi.append(("drop_index", index_name))

    def drop_table(self, table_name: str, **kwargs) -> None:
        self.pasi.append(("drop_table", table_name))

    def execute(self, *args, **kwargs) -> None:
        self.pasi.append(("execute",))
        self.executii.append(args[0] if args else None)

    def bulk_insert(self, table, rows, **kwargs) -> None:
        self.pasi.append(("bulk_insert", table.name))
        self.randuri.extend(rows)

    def get_context(self) -> FakeAlembicOp:
        return self

    def autocommit_block(self) -> object:
        return nullcontext()


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migrare_0073", CALE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revizia_si_parintele() -> None:
    m = _load()
    assert m.revision == "0073_practice_daily_replies"
    assert m.down_revision == "0072_practice_objectives_fb"


def test_structura_datele_si_intoarcerea(monkeypatch) -> None:
    m = _load()
    op = FakeAlembicOp()
    monkeypatch.setattr(m, "op", op)
    m.upgrade()
    pasi = op.pasi
    assert pasi.index(("create_table", "practice_daily_situations")) < pasi.index(
        ("create_table", "practice_daily_replies")
    )
    indexuri = {p[1] for p in pasi if p[0] == "create_index"}
    assert indexuri == {
        "ix_practice_daily_situations_objective_id",
        "ix_practice_daily_replies_participant_profile_id",
        "ix_practice_daily_replies_project_id",
        "ix_practice_daily_replies_situation_id",
    }
    # datele: 36 de inserări, apoi verificarea finală
    inserari = [e for e in op.executii if "INSERT INTO practice_daily_situations" in str(e)]
    assert len(inserari) == 36
    assert "trebuiau 36" in str(op.executii[-1])
    assert pasi[-1] == ("execute",)
    date = json.loads(JSON.read_text(encoding="utf-8"))
    parametri = [
        {k: e.compile().params[k] for k in ("nr", "ordine", "text", "catalog")} for e in inserari
    ]
    assert parametri == [
        {"nr": s["obiectiv_nr"], "ordine": s["ordine"], "text": s["text"],
         "catalog": "comunicare-asertiva"}
        for s in date["situatii"]
    ]

    # tabelele: coloanele de text și niciun nume/adresă
    def text_cols(tabel: str) -> set[str]:
        return {
            c.name for c in op.tabele[tabel] if isinstance(c.type, (sa.Text, sa.String))
        }

    assert text_cols("practice_daily_situations") == {"text"}
    assert text_cols("practice_daily_replies") == {"reply_text", "teacher_text", "prompt_version"}
    for tabel in op.tabele.values():
        for c in tabel:
            assert "name" not in c.name and "email" not in c.name, c.name

    op.pasi.clear()
    m.downgrade()
    pasi = op.pasi
    assert pasi.index(("drop_table", "practice_daily_replies")) < pasi.index(
        ("drop_table", "practice_daily_situations")
    )
    assert {p[1] for p in pasi if p[0] == "drop_index"} == indexuri


def test_constanta_situatii_e_json_ul_din_pachet() -> None:
    m = _load()
    date = json.loads(JSON.read_text(encoding="utf-8"))
    assert m.CATALOG == date["catalog"]
    assert list(m.SITUATII) == date["situatii"]


def test_migrarea_nu_importa_din_codrut_si_nu_citeste_fisiere() -> None:
    arbore = ast.parse(CALE.read_text(encoding="utf-8"))
    for nod in ast.walk(arbore):
        if isinstance(nod, ast.ImportFrom):
            assert not (nod.module or "").startswith("codrut"), nod.module
        if isinstance(nod, ast.Import):
            for alias in nod.names:
                assert not alias.name.startswith("codrut"), alias.name
        if isinstance(nod, ast.Name):
            assert nod.id not in {"open", "Path"}, nod.id
        if isinstance(nod, ast.Attribute):
            assert nod.attr not in {"read_text", "read_bytes", "load"}, nod.attr
