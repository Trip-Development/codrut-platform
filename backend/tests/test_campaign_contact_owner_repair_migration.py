from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from uuid import UUID

import pytest


class FakeAlembicOp:
    def __init__(self) -> None:
        self.bind = object()
        self.dropped_constraints: list[tuple[str, str, str | None]] = []
        self.altered_columns: list[tuple[str, str, bool | None]] = []
        self.created_foreign_keys: list[tuple[str, str, str, str | None]] = []

    def get_bind(self) -> object:
        return self.bind

    def drop_constraint(
        self,
        constraint_name: str,
        table_name: str,
        *,
        type_: str | None = None,
    ) -> None:
        self.dropped_constraints.append((constraint_name, table_name, type_))

    def alter_column(
        self,
        table_name: str,
        column_name: str,
        *,
        nullable: bool | None = None,
        **_kwargs: object,
    ) -> None:
        self.altered_columns.append((table_name, column_name, nullable))

    def create_foreign_key(
        self,
        constraint_name: str,
        source_table: str,
        referent_table: str,
        _local_columns: list[str],
        _remote_columns: list[str],
        *,
        ondelete: str | None = None,
    ) -> None:
        self.created_foreign_keys.append((constraint_name, source_table, referent_table, ondelete))


def _load_migration() -> ModuleType:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0051_contact_owner_repair.py"
    )
    spec = importlib.util.spec_from_file_location(
        "campaign_contact_owner_repair_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load campaign contact owner repair migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_campaign_contact_owner_repair_enforces_non_null_cascading_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    operation = FakeAlembicOp()
    owner_id = UUID("e24ef388-0b16-4645-a9f7-d91bc9ffbeb6")
    ownerless_counts = iter((865, 0))
    validated: list[object] = []
    repaired_campaigns: list[tuple[object, UUID]] = []

    monkeypatch.setattr(migration, "op", operation)
    monkeypatch.setattr(
        migration,
        "_ownerless_count",
        lambda _bind: next(ownerless_counts),
    )
    monkeypatch.setattr(migration, "_ownerless_campaign_count", lambda _bind: 2)
    monkeypatch.setattr(migration, "_resolve_legacy_owner_id", lambda _bind: owner_id)
    monkeypatch.setattr(
        migration,
        "_repair_campaigns",
        lambda bind, resolved_owner_id: repaired_campaigns.append((bind, resolved_owner_id)) or 2,
    )
    monkeypatch.setattr(
        migration,
        "_repair_contacts",
        lambda _bind, _owner_id: (865, 27),
    )
    monkeypatch.setattr(migration, "_repair_suppression_owners", lambda _bind: 2)
    monkeypatch.setattr(migration, "_validate_repair", validated.append)

    migration.upgrade()

    assert migration.revision == "0051_contact_owner_repair"
    assert migration.down_revision == "0050_identity_account_types"
    assert repaired_campaigns == [(operation.bind, owner_id)]
    assert validated == [operation.bind]
    assert operation.dropped_constraints == [
        (
            "fk_campaign_recipients_owner_id_users",
            "campaign_recipients",
            "foreignkey",
        )
    ]
    assert operation.altered_columns == [("campaign_recipients", "owner_id", False)]
    assert operation.created_foreign_keys == [
        (
            "fk_campaign_recipients_owner_id_users",
            "campaign_recipients",
            "users",
            "CASCADE",
        )
    ]


def test_campaign_owner_repair_runs_when_contacts_are_already_owned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    operation = FakeAlembicOp()
    owner_id = UUID("e24ef388-0b16-4645-a9f7-d91bc9ffbeb6")
    ownerless_contact_counts = iter((0, 0))
    repaired_campaigns: list[tuple[object, UUID]] = []

    monkeypatch.setattr(migration, "op", operation)
    monkeypatch.setattr(
        migration,
        "_ownerless_count",
        lambda _bind: next(ownerless_contact_counts),
    )
    monkeypatch.setattr(migration, "_ownerless_campaign_count", lambda _bind: 2)
    monkeypatch.setattr(migration, "_resolve_legacy_owner_id", lambda _bind: owner_id)
    monkeypatch.setattr(
        migration,
        "_repair_campaigns",
        lambda bind, resolved_owner_id: repaired_campaigns.append((bind, resolved_owner_id)) or 2,
    )
    monkeypatch.setattr(
        migration,
        "_repair_contacts",
        lambda *_args: pytest.fail("Contact repair must not run without ownerless contacts"),
    )
    monkeypatch.setattr(migration, "_repair_suppression_owners", lambda _bind: 0)
    monkeypatch.setattr(migration, "_validate_repair", lambda _bind: None)

    migration.upgrade()

    assert repaired_campaigns == [(operation.bind, owner_id)]


def test_campaign_contact_owner_repair_contains_required_history_rewiring() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0051_contact_owner_repair.py"
    ).read_text()
    normalized = source.lower()

    assert "campaign_contact_owner_repair" in normalized
    assert "update campaigns" in normalized
    assert "set owner_id = campaign.owner_id" in normalized
    assert "left join campaign_recipients recipient" in normalized
    assert "insert into campaign_recipient_memberships" in normalized
    assert "delete from campaign_recipient_memberships" in normalized
    assert "update email_sends send" in normalized
    assert "update campaign_recipient_events event" in normalized
    assert "unsubscribed" in normalized
    assert "suppressed" in normalized
    assert "campaign contact ownership repair failed" in normalized


def test_campaign_contact_owner_repair_downgrade_is_blocked() -> None:
    migration = _load_migration()

    with pytest.raises(RuntimeError, match="Cannot safely undo"):
        migration.downgrade()
