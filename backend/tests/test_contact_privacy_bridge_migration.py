from __future__ import annotations

import hashlib
import hmac
import importlib.util
from pathlib import Path
from types import ModuleType
from uuid import UUID

import pytest

OWNER_ID = UUID("00000000-0000-4000-8000-000000000111")
SECRET = "migration-test-secret-at-least-thirty-two-characters"  # noqa: S105


def _migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0053_contact_privacy_bridge.py"
    )


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "contact_privacy_bridge_migration",
        _migration_path(),
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load contact privacy bridge migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contact_privacy_bridge_fingerprint_matches_runtime_contract() -> None:
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


def test_contact_privacy_bridge_requires_secret_only_for_late_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load_migration()
    monkeypatch.delenv(migration.SUPPRESSION_SECRET_ENV, raising=False)

    assert migration._suppression_secret(0) == ""
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        migration._suppression_secret(1)


def test_contact_privacy_bridge_scrubs_identifiers_and_enforces_contract() -> None:
    normalized = _migration_path().read_text().lower()

    assert "where email_fingerprint is null or review_after is null" in normalized
    assert "where owner_id is null" in normalized
    assert "'suppressed-' || new.email_fingerprint || '@invalid'" in normalized
    assert "'suppressed-' || email_fingerprint || '@invalid'" in normalized
    assert "before insert or update on email_suppressions" in normalized
    assert '"uq_email_suppressions_owner_normalized_email"' in normalized
    assert normalized.count("nullable=false") >= 3
    assert "email_suppressions.email_fingerprint is required" in normalized
