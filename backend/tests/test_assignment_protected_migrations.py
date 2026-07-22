from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock


def _load_migration(file_name: str) -> ModuleType:
    migration_path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / file_name
    spec = importlib.util.spec_from_file_location(file_name.removesuffix(".py"), migration_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load migration {file_name}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_op() -> Mock:
    operation = Mock()
    operation.f.side_effect = lambda name: name
    return operation


def test_protected_content_migration_pins_only_unambiguous_definitions(monkeypatch) -> None:
    migration = _load_migration("0037_protected_content_boundary.py")
    operation = _fake_op()
    monkeypatch.setattr(migration, "op", operation)

    migration.upgrade()

    sql = "\n".join(str(call.args[0]) for call in operation.execute.call_args_list).lower()
    assignment_column = next(
        call.args[1]
        for call in operation.add_column.call_args_list
        if call.args[0] == "questionnaire_assignments"
    )

    assert assignment_column.name == "questionnaire_definition_id"
    assert assignment_column.nullable is True
    assert "definition.version = response.questionnaire_version" in sql
    assert "having count(*) = 1" in sql
    assert "cannot safely pin % legacy questionnaire assignments" in sql
    assert "create trigger trg_pin_questionnaire_assignment_definition" in sql
    assert "no unique active definition" in sql
    operation.alter_column.assert_called_once()
    alter_call = operation.alter_column.call_args
    assert alter_call.args == ("questionnaire_assignments", "questionnaire_definition_id")
    assert isinstance(alter_call.kwargs["existing_type"], migration.sa.Uuid)
    assert alter_call.kwargs["nullable"] is False


def test_assignment_round_migration_uses_per_row_default_without_timestamp_grouping(
    monkeypatch,
) -> None:
    migration = _load_migration("0041_assignment_rounds.py")
    operation = _fake_op()
    monkeypatch.setattr(migration, "op", operation)

    migration.upgrade()

    assignment_column = operation.add_column.call_args.args[1]
    assert assignment_column.name == "assignment_round_id"
    assert assignment_column.nullable is False
    assert "gen_random_uuid" in str(assignment_column.server_default.arg)
    operation.alter_column.assert_not_called()
    operation.execute.assert_not_called()
