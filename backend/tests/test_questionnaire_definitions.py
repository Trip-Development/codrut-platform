from codrut.modules.forms.definitions import (
    APPROVED_QUESTIONNAIRE_DEFINITIONS,
    get_approved_questionnaire_definition,
)
from codrut.modules.forms.models import QuestionnaireKey


def test_approved_questionnaire_catalog_contains_added_sources() -> None:
    assert {definition.key for definition in APPROVED_QUESTIONNAIRE_DEFINITIONS} == {
        QuestionnaireKey.lencioni,
        QuestionnaireKey.distress_drivers,
        QuestionnaireKey.icare,
    }


def test_lencioni_definition_has_all_items_and_scoring_groups() -> None:
    definition = get_approved_questionnaire_definition(QuestionnaireKey.lencioni)
    questions = definition.schema["sections"][0]["questions"]
    groups = definition.schema["scoring"]["groups"]

    assert definition.version == 1
    assert len(questions) == 15
    assert {question["type"] for question in questions} == {"likert"}
    assert {group["id"] for group in groups} == {
        "absence_of_trust",
        "fear_of_conflict",
        "lack_of_commitment",
        "avoidance_of_accountability",
        "inattention_to_results",
    }
    assert all(len(group["question_ids"]) == 3 for group in groups)


def test_distress_drivers_definition_has_sets_and_driver_scoring() -> None:
    definition = get_approved_questionnaire_definition(QuestionnaireKey.distress_drivers)
    sets = definition.schema["sections"][0]["questions"]
    drivers = definition.schema["scoring"]["drivers"]

    assert definition.version == 1
    assert len(sets) == 10
    assert all(question["type"] == "statement_score_set" for question in sets)
    assert all(len(question["statements"]) == 5 for question in sets)
    assert {driver["id"] for driver in drivers} == {
        "be_strong",
        "be_perfect",
        "try_hard",
        "hurry_up",
        "please_people",
    }


def test_distress_driver_statement_mapping_matches_source_table() -> None:
    definition = get_approved_questionnaire_definition(QuestionnaireKey.distress_drivers)
    first_set = definition.schema["sections"][0]["questions"][0]
    driver_by_code = {
        statement["code"]: statement["scoring"]["driver"]
        for statement in first_set["statements"]
    }

    assert driver_by_code == {
        "a": "be_strong",
        "b": "be_perfect",
        "c": "try_hard",
        "d": "hurry_up",
        "e": "please_people",
    }
