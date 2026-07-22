from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPTS = REPOSITORY_ROOT / "infra" / "backup"
SYSTEMD_UNITS = BACKUP_SCRIPTS / "systemd"
BASH = shutil.which("bash")
assert BASH is not None


def _environment(**overrides: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "RESTIC_REPOSITORY": "s3:https://fsn1.example.invalid/codrut/backups",
            "RESTIC_PASSWORD": "test-repository-password",  # noqa: S105
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",  # noqa: S105
            "POSTGRES_HOST": "db",
            "POSTGRES_DB": "codrut",
            "POSTGRES_USER": "codrut",
            "POSTGRES_PASSWORD": "test-database-password",  # noqa: S105
            "RESTORE_POSTGRES_HOST": "backup-restore-db",
            "RESTORE_POSTGRES_DB": "codrut_restore",
            "RESTORE_POSTGRES_USER": "codrut_restore",
            "RESTORE_ROOT": "/restore",
            "RESTORE_REHEARSAL_ID": "test-rehearsal",
        }
    )
    environment.update(overrides)
    return environment


def _run(
    script: str, *arguments: str, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed executable and repository-owned scripts
        [BASH, str(BACKUP_SCRIPTS / script), *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment or _environment(),
        check=False,
        capture_output=True,
        text=True,
    )


def test_backup_plan_describes_dump_assets_and_retention_without_printing_secrets() -> None:
    environment = _environment()

    result = _run("backup.sh", "--plan", environment=environment)

    assert result.returncode == 0, result.stderr
    assert "pg_dump" in result.stderr
    assert "campaign-assets" in result.stderr
    assert "Alembic head" in result.stderr
    assert "SHA-256" in result.stderr
    assert "14 daily, 8 weekly, and 6 monthly" in result.stderr
    assert environment["RESTIC_PASSWORD"] not in result.stderr
    assert environment["AWS_SECRET_ACCESS_KEY"] not in result.stderr
    assert environment["POSTGRES_PASSWORD"] not in result.stderr


def test_backup_preflight_reports_missing_repository() -> None:
    environment = _environment()
    environment.pop("RESTIC_REPOSITORY")

    result = _run("backup.sh", "--plan", environment=environment)

    assert result.returncode == 1
    assert "RESTIC_REPOSITORY is required" in result.stderr


def test_s3_preflight_requires_object_storage_credentials() -> None:
    environment = _environment()
    environment.pop("AWS_SECRET_ACCESS_KEY")

    result = _run("check.sh", "--plan", environment=environment)

    assert result.returncode == 1
    assert "AWS_SECRET_ACCESS_KEY is required" in result.stderr


def test_preflight_accepts_a_mounted_restic_password_file(tmp_path: Path) -> None:
    password_file = tmp_path / "restic-password"
    password_file.write_text("file-only-test-value\n")
    environment = _environment(RESTIC_PASSWORD="", RESTIC_PASSWORD_FILE=str(password_file))

    result = _run("check.sh", "--plan", environment=environment)

    assert result.returncode == 0, result.stderr
    assert "file-only-test-value" not in result.stderr


def test_retention_plan_uses_locked_controlled_pilot_policy() -> None:
    result = _run("retention.sh", "--plan")

    assert result.returncode == 0, result.stderr
    assert "--keep-daily\n14" in result.stderr
    assert "--keep-weekly\n8" in result.stderr
    assert "--keep-monthly\n6" in result.stderr
    assert "--prune" in result.stderr


def test_restore_rehearsal_refuses_live_postgres_host() -> None:
    environment = _environment(RESTORE_POSTGRES_HOST="db")

    result = _run("restore-rehearsal.sh", "--plan", environment=environment)

    assert result.returncode == 1
    assert "target PostgreSQL host must differ from the live source host" in result.stderr


def test_restore_rehearsal_plan_uses_new_isolated_targets() -> None:
    result = _run("restore-rehearsal.sh", "--plan")

    assert result.returncode == 0, result.stderr
    assert "/restore/test-rehearsal" in result.stderr
    assert "backup-restore-db" in result.stderr
    assert "foreign-key integrity" in result.stderr
    assert "campaign asset SHA-256" in result.stderr
    assert "never write to 'db/codrut'" in result.stderr


def test_restore_rehearsal_requires_manifest_integrity_evidence() -> None:
    script = (BACKUP_SCRIPTS / "restore-rehearsal.sh").read_text()

    assert "codrut-controlled-pilot-v2" in script
    assert "SELECT version_num FROM alembic_version" in script
    assert "NOT convalidated" in script
    assert "sha256sum --check --strict" in script
    for table_name in (
        "users",
        "companies",
        "participant_profiles",
        "questionnaire_assignments",
        "campaigns",
        "email_sends",
    ):
        assert table_name in script


def test_backup_and_restore_scripts_have_valid_bash_syntax() -> None:
    for script_name in ("backup.sh", "restore-rehearsal.sh"):
        result = subprocess.run(  # noqa: S603 - fixed shell and repository-owned script
            [BASH, "-n", str(BACKUP_SCRIPTS / script_name)],
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


def test_systemd_backup_units_are_deployable_and_non_overlapping() -> None:
    backup_service = (SYSTEMD_UNITS / "codrut-backup.service").read_text()
    backup_timer = (SYSTEMD_UNITS / "codrut-backup.timer").read_text()
    check_service = (SYSTEMD_UNITS / "codrut-backup-check.service").read_text()
    check_timer = (SYSTEMD_UNITS / "codrut-backup-check.timer").read_text()

    assert "EnvironmentFile=/etc/codrut/backup.env" in backup_service
    assert "/usr/bin/flock --nonblock /run/lock/codrut-backup.lock" in backup_service
    assert "backup backup" in backup_service
    assert "/usr/bin/flock --nonblock /run/lock/codrut-backup.lock" in check_service
    assert "backup check" in check_service
    assert "Persistent=true" in backup_timer
    assert "OnCalendar=*-*-* 02:15:00" in backup_timer
    assert "Persistent=true" in check_timer
    assert "OnCalendar=Sun *-*-* 04:15:00" in check_timer


def test_entrypoint_rejects_unknown_commands() -> None:
    result = _run("entrypoint.sh", "destroy-everything")

    assert result.returncode == 2
    assert "Unknown backup command" in result.stderr
