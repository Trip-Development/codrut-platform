from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


class FakeAlembicOp:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []
        self.added_columns: list[tuple[str, str]] = []
        self.created_tables: list[str] = []
        self.created_indexes: list[str] = []

    def execute(self, statement: object) -> None:
        self.executed_sql.append(str(statement))

    def create_table(self, table_name: str, *args: object, **kwargs: object) -> None:
        self.created_tables.append(table_name)

    def create_index(
        self,
        index_name: str,
        table_name: str,
        columns: list[str],
        *,
        unique: bool = False,
    ) -> None:
        self.created_indexes.append(index_name)

    def add_column(self, table_name: str, column: object) -> None:
        self.added_columns.append((table_name, getattr(column, "name", "")))


def _load_migration() -> ModuleType:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0030_campaign_recipient_memberships.py"
    )
    spec = importlib.util.spec_from_file_location(
        "campaign_recipient_memberships_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load campaign recipient membership migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_campaign_recipient_membership_migration_backfills_membership_sources(monkeypatch) -> None:
    migration = _load_migration()
    fake_op = FakeAlembicOp()
    monkeypatch.setattr(migration, "op", fake_op)

    migration.upgrade()

    joined_sql = "\n".join(fake_op.executed_sql).lower()

    assert "campaign_recipient_memberships" in fake_op.created_tables
    assert ("campaigns", "recipient_memberships_initialized") in fake_op.added_columns
    assert "ix_campaign_recipient_memberships_campaign_id" in fake_op.created_indexes
    assert "ix_campaign_recipient_memberships_recipient_id" in fake_op.created_indexes
    assert "'send_history'" in joined_sql
    assert "es.campaign_recipient_id is not null" in joined_sql
    assert "'send_email_match'" in joined_sql
    assert "lower(cr.email) = lower(es.recipient_email)" in joined_sql
    assert "'segment_backfill'" in joined_sql
    assert "c.status in ('draft', 'ready')" in joined_sql
    assert "not exists" in joined_sql
    assert "from email_sends es where es.campaign_id = c.id" in joined_sql
    assert "on conflict (campaign_id, recipient_id) do nothing" in joined_sql
    assert "set recipient_memberships_initialized = true" in joined_sql
