from __future__ import annotations

import importlib.util
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType


class FakeAlembicOp:
    def __init__(self) -> None:
        self.created_tables: list[str] = []
        self.created_indices: list[str] = []
        self.dropped_indices: list[str] = []
        self.dropped_tables: list[str] = []

    def create_table(self, table_name: str, *args, **kwargs) -> None:
        self.created_tables.append(table_name)

    def create_index(self, index_name: str, table_name: str, *args, **kwargs) -> None:
        self.created_indices.append(index_name)

    def drop_index(self, index_name: str, **kwargs) -> None:
        self.dropped_indices.append(index_name)

    def drop_table(self, table_name: str, **kwargs) -> None:
        self.dropped_tables.append(table_name)

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
        / "0059_participant_view_audits.py"
    )
    spec = importlib.util.spec_from_file_location(
        "participant_view_audits_migration", migration_path
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load participant_view_audits migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_participant_view_audits_migration_upgrade_and_downgrade(monkeypatch) -> None:
    migration = _load_migration()
    operation = FakeAlembicOp()
    monkeypatch.setattr(migration, "op", operation)

    # 1. Upgrade
    migration.upgrade()
    assert "participant_view_audits" in operation.created_tables
    assert "ix_participant_view_audits_company_id" in operation.created_indices
    assert "ix_participant_view_audits_trainer_user_id" in operation.created_indices
    assert "ix_participant_view_audits_participant_profile_id" in operation.created_indices
    assert "ix_participant_view_audits_created_at" in operation.created_indices

    # 2. Downgrade
    migration.downgrade()
    assert "ix_participant_view_audits_created_at" in operation.dropped_indices
    assert "ix_participant_view_audits_participant_profile_id" in operation.dropped_indices
    assert "ix_participant_view_audits_trainer_user_id" in operation.dropped_indices
    assert "ix_participant_view_audits_company_id" in operation.dropped_indices
    assert "participant_view_audits" in operation.dropped_tables
