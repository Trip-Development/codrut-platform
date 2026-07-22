from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


class FakeAlembicOp:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []
        self.dropped_constraints: list[tuple[str, str, str | None]] = []
        self.created_indexes: list[tuple[str, str, list[object], bool]] = []

    def execute(self, statement: object) -> None:
        self.executed_sql.append(str(statement))

    def drop_constraint(
        self,
        constraint_name: str,
        table_name: str,
        *,
        type_: str | None = None,
    ) -> None:
        self.dropped_constraints.append((constraint_name, table_name, type_))

    def create_index(
        self,
        index_name: str,
        table_name: str,
        columns: list[object],
        *,
        unique: bool = False,
        **kwargs: object,
    ) -> None:
        self.created_indexes.append((index_name, table_name, columns, unique))


def _load_migration() -> ModuleType:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0035_contact_owner_isolation.py"
    )
    spec = importlib.util.spec_from_file_location(
        "contact_owner_isolation_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load contact owner isolation migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contact_owner_isolation_migration_preserves_and_rescopes_data(monkeypatch) -> None:
    migration = _load_migration()
    fake_op = FakeAlembicOp()
    monkeypatch.setattr(migration, "op", fake_op)

    migration.upgrade()

    joined_sql = "\n".join(fake_op.executed_sql).lower()

    assert migration.down_revision == "0034_invite_session_link"
    assert fake_op.dropped_constraints == [
        ("uq_campaign_recipients_email", "campaign_recipients", "unique")
    ]
    assert "campaign_recipient_owner_clones" in joined_sql
    assert "recipient.owner_id is distinct from campaign.owner_id" in joined_sql
    assert "update campaign_recipient_memberships" in joined_sql
    assert "update email_sends" in joined_sql
    assert "insert into campaign_recipient_events" in joined_sql
    assert "partition by recipient.owner_id, lower(recipient.email)" in joined_sql
    assert "set email = lower(email)" in joined_sql
    assert fake_op.created_indexes[0][0] == ("uq_campaign_recipients_owner_normalized_email")
    assert fake_op.created_indexes[0][3] is True
