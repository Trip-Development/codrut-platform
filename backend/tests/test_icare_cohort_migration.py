import importlib.util
from pathlib import Path
from types import ModuleType


class RecordingBind:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: object) -> None:
        self.statements.append(str(statement))


def _load_migration() -> ModuleType:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0057_icare_assignment_cohorts.py"
    )
    spec = importlib.util.spec_from_file_location("icare_cohort_migration", migration_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load iCARE cohort migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_icare_cohort_backfill_uses_only_immutable_cycle_evidence() -> None:
    migration = _load_migration()
    bind = RecordingBind()

    migration._backfill_self(bind)
    migration._backfill_leadership_peers(bind)
    migration._backfill_direct_team(bind)

    statements = "\n".join(bind.statements).casefold()
    assert migration.revision == "0057_icare_assignment_cohorts"
    assert migration.down_revision == "0056_email_send_sandbox_scope"
    assert statements.count("icare_cohort is null") == 3
    assert "assessment_cycle_team_memberships" in statements
    assert "project_memberships" not in statements
    assert "team_memberships" not in statements.replace(
        "assessment_cycle_team_memberships",
        "",
    )


def test_icare_cohort_backfill_leaves_ambiguous_external_rows_nullable() -> None:
    migration = _load_migration()
    bind = RecordingBind()

    migration._backfill_self(bind)
    migration._backfill_leadership_peers(bind)
    migration._backfill_direct_team(bind)

    statements = "\n".join(bind.statements).casefold()
    assert "set icare_cohort = 'self'" in statements
    assert "set icare_cohort = 'leadership_peers'" in statements
    assert "set icare_cohort = 'direct_team'" in statements
    assert "else" not in statements
