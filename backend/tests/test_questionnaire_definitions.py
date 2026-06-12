from codrut.modules.forms.definitions import (
    APPROVED_QUESTIONNAIRE_DEFINITIONS,
    get_approved_questionnaire_definition,
)
from codrut.modules.forms.models import QuestionnaireKey


def test_approved_questionnaire_catalog_contains_added_sources() -> None:
    assert {definition.key for definition in APPROVED_QUESTIONNAIRE_DEFINITIONS} == {
        QuestionnaireKey.pcm_base,
        QuestionnaireKey.lencioni,
        QuestionnaireKey.lencioni_en,
        QuestionnaireKey.distress_drivers,
        QuestionnaireKey.distress_drivers_en,
        QuestionnaireKey.boss_360,
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


def test_lencioni_english_definition_keeps_scoring_contract() -> None:
    definition = get_approved_questionnaire_definition(QuestionnaireKey.lencioni_en)
    questions = definition.schema["sections"][0]["questions"]

    assert definition.title == "Team Assessment Questionnaire"
    assert len(questions) == 15
    assert (
        questions[0]["label"]
        == "Team members are passionate and unguarded in their discussion of issues."
    )
    assert definition.schema["scoring"]["groups"][0]["question_ids"] == [
        "lencioni_q04",
        "lencioni_q06",
        "lencioni_q12",
    ]


def test_distress_drivers_english_definition_keeps_driver_scoring_contract() -> None:
    definition = get_approved_questionnaire_definition(QuestionnaireKey.distress_drivers_en)
    first_set = definition.schema["sections"][0]["questions"][0]

    assert definition.title == "Resilience and TA Distress Drivers"
    assert len(definition.schema["sections"][0]["questions"]) == 10
    assert first_set["statements"][0]["label"] == "Resilience is a valuable resource"
    assert first_set["statements"][0]["scoring"]["driver"] == "be_strong"


def test_boss_360_definition_is_icare_form_complete_with_section_scoring() -> None:
    definition = get_approved_questionnaire_definition(QuestionnaireKey.boss_360)
    questions = definition.schema["sections"][0]["questions"]
    statements = [
        statement
        for section in definition.schema["sections"]
        for question in section["questions"]
        for statement in question["statements"]
    ]

    assert definition.title == "Feedback 360 iCARE pentru manager"
    assert len(questions) == 3
    assert len(statements) == 48
    question_types = {
        question["type"]
        for section in definition.schema["sections"]
        for question in section["questions"]
    }
    assert question_types == {"statement_score_set"}
    assert definition.schema["scoring"] == {
        "method": "average_statement_scores_by_section",
        "scale_min": 1,
        "scale_max": 4,
        "score_min": 0,
        "score_unit": "percent",
        "primary_result": "lowest_dimension",
    }


def test_boss_360_english_definition_uses_english_icare_copy() -> None:
    definition = get_approved_questionnaire_definition(QuestionnaireKey.boss_360_en)
    first_question = definition.schema["sections"][0]["questions"][0]

    assert definition.title == "iCARE 360 Feedback for Manager"
    assert definition.schema["sections"][0]["title"] == "Inspiring"
    assert first_question["label"] == "Developing people"
    assert first_question["statements"][0]["label"] == "Gives constructive feedback"


def test_legacy_icare_key_resolves_to_360_alias_without_listing_separately() -> None:
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

    assert definition.title == "Feedback 360 iCARE pentru manager"
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
