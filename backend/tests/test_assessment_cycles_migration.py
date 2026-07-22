from __future__ import annotations

import importlib.util
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType


class FakeAlembicOp:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []

    def execute(self, statement: object) -> None:
        self.executed_sql.append(str(statement))

    def f(self, name: str) -> str:
        return name

    def get_bind(self) -> object:
        return object()

    def get_context(self) -> FakeAlembicOp:
        return self

    def autocommit_block(self) -> object:
        return nullcontext()

    def __getattr__(self, _name: str) -> object:
        return lambda *args, **kwargs: None


def _load_migration() -> ModuleType:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0045_assessment_cycles.py"
    )
    spec = importlib.util.spec_from_file_location("assessment_cycles_migration", migration_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load assessment cycles migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_assessment_cycles_migration_backfills_legacy_aggregate_publication_keys(
    monkeypatch,
) -> None:
    migration = _load_migration()
    operation = FakeAlembicOp()
    monkeypatch.setattr(migration, "op", operation)
    monkeypatch.setattr(migration.postgresql.ENUM, "create", lambda *args, **kwargs: None)

    migration.upgrade()

    sql = "\n".join(operation.executed_sql).lower()

    assert migration.down_revision == "0044_communications_hardening"
    assert "set assessment_cycle_id = cycle.id" in sql
    assert "cannot migrate legacy aggregate result publications" in sql
    assert "cycle-aware publication_key already exists" in sql
    assert "set publication_key = concat_ws" in sql
    assert "coalesce(publication.assessment_cycle_id::text, 'legacy')" in sql
    assert "where publication.kind = 'aggregate_360'" in sql


def test_assessment_cycles_downgrade_preflights_data_loss_and_restores_legacy_keys(
    monkeypatch,
) -> None:
    migration = _load_migration()
    operation = FakeAlembicOp()
    monkeypatch.setattr(migration, "op", operation)
    monkeypatch.setattr(migration.postgresql.ENUM, "drop", lambda *args, **kwargs: None)

    migration.downgrade()

    sql = "\n".join(operation.executed_sql).lower()

    assert "cannot downgrade 0045_assessment_cycles: multi-profile accounts exist" in sql
    assert "multiple aggregate" in sql
    assert "publications would collapse to one legacy publication_key" in sql
    assert "group by user_id" in sql
    assert "set publication_key = concat_ws" in sql
    assert "coalesce(publication.assessment_cycle_id::text, 'legacy')" in sql
