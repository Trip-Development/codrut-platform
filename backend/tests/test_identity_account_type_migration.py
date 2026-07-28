from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


class FakeAlembicOp:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []
        self.added_columns: list[tuple[str, object]] = []
        self.created_checks: list[tuple[str, str, str]] = []
        self.dropped_columns: list[tuple[str, str]] = []

    def execute(self, statement: object) -> None:
        self.executed_sql.append(str(statement))

    def add_column(self, table_name: str, column: object) -> None:
        self.added_columns.append((table_name, column))

    def create_check_constraint(
        self,
        name: str,
        table_name: str,
        condition: str,
    ) -> None:
        self.created_checks.append((name, table_name, condition))

    def drop_column(self, table_name: str, column_name: str) -> None:
        self.dropped_columns.append((table_name, column_name))

    def drop_constraint(self, *args: object, **kwargs: object) -> None:
        return None

    def get_bind(self) -> object:
        return object()

    def f(self, name: str) -> str:
        return name


def _load_migration() -> ModuleType:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0050_identity_account_types.py"
    )
    spec = importlib.util.spec_from_file_location(
        "identity_account_type_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load identity account type migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_identity_account_type_migration_backfills_shadow_accounts(monkeypatch) -> None:
    migration = _load_migration()
    operation = FakeAlembicOp()
    monkeypatch.setattr(migration, "op", operation)
    monkeypatch.setattr(migration.account_type, "create", lambda *args, **kwargs: None)

    migration.upgrade()

    assert migration.down_revision == "0049_user_avatar_palettes"
    assert len(operation.added_columns) == 1
    table_name, column = operation.added_columns[0]
    assert table_name == "users"
    assert column.name == "account_type"
    assert column.nullable is False
    assert str(column.server_default.arg) == "registered"
    assert "password_hash = 'shadow_account_no_password'" in "\n".join(
        operation.executed_sql
    )
    assert operation.created_checks[-1][2] == (
        "action in "
        "('link_matching_email', 'unlink', 'invite_claim', 'registration_claim')"
    )


def test_identity_account_type_downgrade_restores_legacy_constraint(monkeypatch) -> None:
    migration = _load_migration()
    operation = FakeAlembicOp()
    monkeypatch.setattr(migration, "op", operation)
    monkeypatch.setattr(migration.account_type, "drop", lambda *args, **kwargs: None)

    migration.downgrade()

    assert operation.created_checks[-1][2] == (
        "action in ('link_matching_email', 'unlink')"
    )
    assert operation.dropped_columns == [("users", "account_type")]
