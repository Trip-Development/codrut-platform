from __future__ import annotations

import hashlib
import hmac
import importlib.util
from pathlib import Path
from types import ModuleType
from uuid import UUID

import pytest

from codrut.core.config import Settings
from codrut.modules.communications.suppression import email_suppression_fingerprint

OWNER_ID = UUID("00000000-0000-4000-8000-000000000111")
SECRET = "migration-test-secret-at-least-thirty-two-characters"  # noqa: S105


def _migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0052_contact_archive.py"
    )


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "contact_archive_migration",
        _migration_path(),
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load contact archive migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contact_archive_migration_fingerprint_matches_runtime_contract() -> None:
    migration = _load_migration()
    message = f"codrut-email-suppression:v1:{OWNER_ID}:ana@example.test".encode()
    expected = hmac.new(SECRET.encode(), message, hashlib.sha256).hexdigest()

    assert (
        migration._fingerprint(
            owner_id=OWNER_ID,
            email=" ANA@Example.Test ",
            secret=SECRET,
        )
        == expected
    )


def test_contact_archive_migration_requires_secret_only_for_existing_suppressions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    monkeypatch.delenv(migration.SUPPRESSION_SECRET_ENV, raising=False)

    assert migration._suppression_secret(0) == ""
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        migration._suppression_secret(1)

    monkeypatch.setenv(migration.SUPPRESSION_SECRET_ENV, SECRET)
    assert migration._suppression_secret(2) == SECRET


@pytest.mark.parametrize("value", ("not-a-number", "29", "3651"))
def test_contact_archive_migration_rejects_invalid_review_window(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    migration = _load_migration()
    monkeypatch.setenv(migration.SUPPRESSION_REVIEW_DAYS_ENV, value)

    with pytest.raises(RuntimeError, match="must be"):
        migration._suppression_review_days()


def test_contact_archive_migration_uses_expand_contract_rollback_shape() -> None:
    normalized = _migration_path().read_text().lower()

    assert 'op.drop_column("email_suppressions", "email")' not in normalized
    assert '"uq_email_suppressions_owner_normalized_email"' not in normalized
    assert (
        'sa.column("email_fingerprint", sa.string(length=64), nullable=true)'
        in normalized
    )
    assert (
        'sa.column("review_after", sa.datetime(timezone=true), nullable=true)'
        in normalized
    )
    assert "uq_email_suppressions_owner_fingerprint" in normalized
    assert "email_fingerprint" in normalized
    assert "review_after" in normalized
    assert "last_reviewed_at" in normalized
    assert "campaign_recipient_archive_window" in normalized
    assert "purge_after >= archived_at" in normalized
    assert "campaign_recipient_events" in normalized
    assert 'ondelete="set null"' in normalized
    assert "where owner_id is null" in normalized
    assert '"email_suppression_reviews"' in normalized
    assert '"campaign_contact_aggregates"' in normalized
    assert '"campaign_contact_tombstones"' in normalized
    assert '"campaign_delivery_tombstones"' in normalized
    assert '"campaign_delivery_event_tombstones"' in normalized
    assert '"provider_message_fingerprint"' in normalized
    assert '"provider_event_fingerprint"' in normalized
    assert '"expires_at"' in normalized
    assert "cannot roll back contact archive expansion" in normalized
    assert (
        'sa.column("owner_id", sa.uuid(), nullable=true)' in normalized
    )
    assert 'op.alter_column("campaign_recipients", "owner_id"' not in normalized


def test_contact_archive_migration_prefers_owned_variant_campaign_before_fallbacks() -> None:
    normalized = _migration_path().read_text().lower()
    variant_update = normalized.index(
        "campaign.id::text = lower(event.variant_key)"
    )
    membership_update = normalized.index(
        "set campaign_id = membership_scope.campaign_id"
    )
    send_update = normalized.index("set campaign_id = latest_send.campaign_id")

    assert variant_update < membership_update < send_update
    assert "event.variant_key::uuid" not in normalized
    assert "campaign.owner_id = event.owner_id" in normalized
    assert "membership_scope.owner_id = event.owner_id" in normalized
    assert "campaign.owner_id = send.owner_id" in normalized
    assert "latest_send.owner_id = event.owner_id" in normalized
    assert normalized.count("where event.campaign_id is null") >= 3


def test_contact_archive_migration_rejects_duplicate_provider_message_ids() -> None:
    normalized = _migration_path().read_text().lower()

    assert "group by provider_message_id" in normalized
    assert "having count(*) > 1" in normalized
    assert "cannot enable replay-safe contact erasure" in normalized
    assert '"uq_email_sends_provider_message_id"' in normalized
    assert '["provider_message_id"]' in normalized
    assert "unique=true" in normalized
    assert 'postgresql_where=sa.text("provider_message_id is not null")' in normalized


def test_delivery_event_receipt_schema_retains_only_protected_fingerprint() -> None:
    normalized = _migration_path().read_text().lower()
    receipt_table = normalized.split(
        'op.create_table(\n        "campaign_delivery_event_tombstones"',
        1,
    )[1].split("op.create_table(", 1)[0]

    assert '"provider_event_fingerprint"' in receipt_table
    assert '"event_type"' not in receipt_table
    assert '"occurred_at"' not in receipt_table
    assert '"created_at"' not in receipt_table
    assert '"updated_at"' not in receipt_table


def test_contact_archive_migration_and_runtime_strip_secret_consistently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    padded_secret = f"  {SECRET}  "
    monkeypatch.setenv(migration.SUPPRESSION_SECRET_ENV, padded_secret)
    runtime_secret = Settings(
        email_suppression_fingerprint_secret=padded_secret
    ).effective_email_suppression_fingerprint_secret

    assert migration._suppression_secret(1) == SECRET
    assert runtime_secret == SECRET
    assert migration._fingerprint(
        owner_id=OWNER_ID,
        email=" ANA@example.test ",
        secret=migration._suppression_secret(1),
    ) == email_suppression_fingerprint(
        owner_id=OWNER_ID,
        email="ana@EXAMPLE.TEST",
        secret=runtime_secret,
    )
