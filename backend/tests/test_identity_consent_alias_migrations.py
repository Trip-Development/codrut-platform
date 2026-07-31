from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def _load_migration(filename: str, module_name: str) -> ModuleType:
    path = MIGRATIONS_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load migration {filename}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_submission_migration_preserves_consent_audit_events() -> None:
    path = MIGRATIONS_DIR / "0054_identity_consent_submission.py"
    normalized = path.read_text().lower()

    assert "delete from consent_acceptances" not in normalized
    assert "uq_consent_acceptances_user_version" not in normalized
    assert "uq_consent_acceptances_user_session_version" not in normalized
    assert "submission_processing_jobs" in normalized


def test_alias_migration_generates_stable_unique_backfill_values() -> None:
    migration = _load_migration(
        "0055_participant_aliases.py",
        "participant_alias_migration",
    )

    first = migration._replacement_alias(
        "10000000-0000-4000-8000-000000000001",
        0,
    )
    repeated = migration._replacement_alias(
        "10000000-0000-4000-8000-000000000001",
        0,
    )
    second = migration._replacement_alias(
        "10000000-0000-4000-8000-000000000002",
        0,
    )

    assert first == repeated
    assert first != second
    assert len(first) <= 80


def test_alias_migration_keeps_collision_unaware_rollback_image_safe() -> None:
    path = MIGRATIONS_DIR / "0055_participant_aliases.py"
    normalized = path.read_text().lower()

    trigger_position = normalized.index("create trigger trg_participant_profiles_unique_alias")
    constraint_position = normalized.index(
        'op.create_unique_constraint(\n        "uq_participant_profiles_anonymous_name"'
    )

    assert "before insert or update of anonymous_name" in normalized
    assert "pg_advisory_xact_lock" in normalized
    assert "hashtextextended(new.anonymous_name, 0)" in normalized
    assert "existing.id is distinct from new.id" in normalized
    assert trigger_position < constraint_position
    assert "drop trigger if exists" in normalized
    assert "drop function if exists" in normalized
