from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import configure_mappers

from codrut.core.database import Base
from codrut.modules.forms.models import QuestionnaireKey


def test_questionnaire_definition_table_is_registered() -> None:
    assert "questionnaire_definitions" in Base.metadata.tables
    configure_mappers()


def test_questionnaire_keys_cover_current_workflow() -> None:
    assert {key.value for key in QuestionnaireKey} == {
        "pcm_base",
        "phase",
        "lencioni",
        "distress_drivers",
        "boss_360",
    }


def test_questionnaire_definitions_are_versioned_by_key() -> None:
    constraints = Base.metadata.tables["questionnaire_definitions"].constraints
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("key", "version") in unique_columns
