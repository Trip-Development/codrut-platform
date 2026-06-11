from codrut.modules.forms.definitions import (
    APPROVED_QUESTIONNAIRE_DEFINITIONS,
    get_approved_questionnaire_definition,
)
from codrut.modules.forms.models import QuestionnaireKey


def test_approved_questionnaire_catalog_contains_added_sources() -> None:
    assert {definition.key for definition in APPROVED_QUESTIONNAIRE_DEFINITIONS} == {
        QuestionnaireKey.pcm_base,
        QuestionnaireKey.phase,
        QuestionnaireKey.lencioni,
        QuestionnaireKey.distress_drivers,
        QuestionnaireKey.boss_360,
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
    assert definition.title == "Reziliență și driveri de stres TA"
    assert sets[0]["statements"][0]["label"] == "Rezistența este o resursă valoroasă"
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


def test_pcm_definitions_use_the_six_process_communication_types() -> None:
    base = get_approved_questionnaire_definition(QuestionnaireKey.pcm_base)
    phase = get_approved_questionnaire_definition(QuestionnaireKey.phase)
    base_questions = base.schema["sections"][0]["questions"]

    assert [question["label"] for question in base_questions] == [
        "Care este baza ta PCM?",
        "Care este faza ta PCM?",
    ]
    assert phase.schema["sections"][0]["questions"][0]["label"] == "Care este faza ta PCM?"
    assert {option["value"] for option in base_questions[0]["scale"]} == {
        "harmonizer",
        "thinker",
        "persister",
        "imaginer",
        "rebel",
        "promoter",
    }
    assert {option["value"] for option in base_questions[1]["scale"]} == {
        "harmonizer",
        "thinker",
        "persister",
        "imaginer",
        "rebel",
        "promoter",
    }
    assert {question["type"] for question in base_questions} == {"single_choice"}
    assert phase.schema["sections"][0]["questions"][0]["type"] == "single_choice"


def test_boss_360_definition_is_form_complete_without_scoring_metadata() -> None:
    definition = get_approved_questionnaire_definition(QuestionnaireKey.boss_360)
    questions = definition.schema["sections"][0]["questions"]

    assert definition.title == "Feedback 360 pentru manager"
    assert len(questions) == 8
    assert {question["type"] for question in questions} == {"likert"}
    assert "scoring" not in definition.schema


def test_icare_definition_uses_romanian_copy_without_changing_statement_ids() -> None:
    definition = get_approved_questionnaire_definition(QuestionnaireKey.icare)
    sections = definition.schema["sections"]
    questions = [
        question
        for section in sections
        for question in section["questions"]
    ]
    statements = [
        statement
        for question in questions
        for statement in question["statements"]
    ]

    assert definition.title == "Comportamente de leadership ICARE"
    assert [section["title"] for section in sections] == [
        "Inspirație",
        "Construirea încrederii",
        "Conștientizare",
        "Rezultate",
        "Împuternicire",
    ]
    assert questions[0]["label"] == "Dezvoltarea oamenilor"
    assert questions[-1]["label"] == "Sprijinirea echipei"
    assert [statement["id"] for statement in statements] == [
        f"icare_{number:02d}" for number in range(1, 49)
    ]
    assert len(statements) == 48
