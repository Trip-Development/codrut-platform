"""Migrarea `0074_project_trainers` — plicul 242, §5.4.

Structura se verifică pe un `op` fals (ca la 235/236). Numărătoarea pe o bază reală
(2 traineri × 3 proiecte = 6, întoarcerea, iar 6) se face separat, în poarta M1.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa

CALE = (
    Path(__file__).resolve().parents[1] / "migrations" / "versions"
    / "0074_project_trainers.py"
)


class FakeAlembicOp:
    def __init__(self) -> None:
        self.pasi: list[tuple[str, ...]] = []
        self.tabele: dict[str, list[sa.Column]] = {}
        self.coloane: dict[str, sa.Column] = {}
        self.executii: list = []

    def create_table(self, table_name: str, *args, **kwargs) -> None:
        self.pasi.append(("create_table", table_name))
        self.tabele[table_name] = [a for a in args if isinstance(a, sa.Column)]

    def create_index(self, index_name: str, table_name: str, columns, *args, **kwargs) -> None:
        self.pasi.append(("create_index", index_name, table_name, tuple(columns)))

    def drop_index(self, index_name: str, **kwargs) -> None:
        self.pasi.append(("drop_index", index_name))

    def drop_table(self, table_name: str, **kwargs) -> None:
        self.pasi.append(("drop_table", table_name))

    def add_column(self, table_name: str, column: sa.Column, **kwargs) -> None:
        self.pasi.append(("add_column", table_name, column.name))
        self.coloane[column.name] = column

    def drop_column(self, table_name: str, column_name: str, **kwargs) -> None:
        self.pasi.append(("drop_column", table_name, column_name))

    def execute(self, *args, **kwargs) -> None:
        self.pasi.append(("execute",))
        self.executii.append(args[0] if args else None)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migrare_0074", CALE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revizia_si_parintele() -> None:
    m = _load()
    assert m.revision == "0074_project_trainers"
    assert m.down_revision == "0073_practice_daily_replies"
    assert len(m.revision) <= 32


def test_structura_umplerea_si_intoarcerea(monkeypatch) -> None:
    m = _load()
    op = FakeAlembicOp()
    monkeypatch.setattr(m, "op", op)
    m.upgrade()

    assert "project_trainers" in op.tabele
    coloane = {c.name for c in op.tabele["project_trainers"]}
    assert coloane == {"id", "project_id", "user_id", "created_at", "updated_at"}
    indexuri = {p[3] for p in op.pasi if p[0] == "create_index"}
    assert ("project_id",) in indexuri and ("user_id",) in indexuri

    assert ("add_column", "users", "is_platform_owner") in op.pasi
    col = op.coloane["is_platform_owner"]
    assert col.nullable is False
    assert col.server_default is not None

    assert len(op.executii) == 1
    text = str(op.executii[0])
    assert "WHERE u.role::text = 'trainer'" in text
    assert "CROSS JOIN" in text
    assert "ON CONFLICT (project_id, user_id) DO NOTHING" in text
    assert "is_platform_owner" not in text

    op2 = FakeAlembicOp()
    monkeypatch.setattr(m, "op", op2)
    m.downgrade()
    tipuri = [p[0] for p in op2.pasi if p[0] in ("drop_table", "drop_column")]
    assert tipuri == ["drop_table", "drop_column"]
    assert ("drop_table", "project_trainers") in op2.pasi
    assert ("drop_column", "users", "is_platform_owner") in op2.pasi


def test_migrarea_nu_importa_cod_si_nu_citeste_fisiere() -> None:
    arbore = ast.parse(CALE.read_text(encoding="utf-8"))
    for n in ast.walk(arbore):
        if isinstance(n, ast.ImportFrom):
            assert not (n.module or "").startswith("codrut"), n.module
        if isinstance(n, ast.Import):
            assert not any(a.name.startswith("codrut") for a in n.names)
        if isinstance(n, ast.Name):
            assert n.id not in {"open", "Path"}, n.id
        if isinstance(n, ast.Attribute):
            assert n.attr not in {"read_text", "read_bytes", "load"}, n.attr
