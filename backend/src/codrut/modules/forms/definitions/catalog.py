# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from codrut.modules.forms.models import QuestionnaireKey

DefinitionSchema = dict[str, Any]


@dataclass(frozen=True)
class ApprovedQuestionnaireDefinition:
    key: QuestionnaireKey
    version: int
    title: str
    description: str
    schema: DefinitionSchema


LIKERT_1_TO_3 = [
    {"value": 1, "label": "Rar"},
    {"value": 2, "label": "Uneori"},
    {"value": 3, "label": "De obicei"},
]

DISTRESS_SCORE_0_TO_10 = [
    {"value": value, "label": str(value)}
    for value in range(0, 11)
]


def _statement_question(
    number: int,
    text: str,
    dysfunction: str,
) -> dict[str, Any]:
    return {
        "id": f"lencioni_q{number:02d}",
        "code": f"Q{number}",
        "type": "likert",
        "label": text,
        "required": True,
        "scale": LIKERT_1_TO_3,
        "scoring": {"group": dysfunction},
    }


def _distress_set(number: int, statements: dict[str, tuple[str, str]]) -> dict[str, Any]:
    return {
        "id": f"distress_set_{number:02d}",
        "code": f"SET{number}",
        "type": "statement_score_set",
        "label": f"Set {number}",
        "required": True,
        "instructions": (
            "Acorda fiecarei afirmatii un scor intre 0 si 10. Alege afirmatia cea mai "
            "adevarata pentru tine cu 7-10, cea mai putin adevarata cu 0-3, iar "
            "celelalte intre aceste repere."
        ),
        "scale": DISTRESS_SCORE_0_TO_10,
        "statements": [
            {
                "id": f"distress_set_{number:02d}_{letter}",
                "code": letter,
                "label": text,
                "scoring": {"driver": driver},
            }
            for letter, (text, driver) in statements.items()
        ],
    }


LENCIONI_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.lencioni,
    version=1,
    title="Chestionar de evaluare a echipei",
    description="Evaluare Lencioni pentru cele cinci disfunctii ale unei echipe.",
    schema={
        "schema_version": "questionnaire.v1",
        "source": {
            "type": "pdf",
            "path": "docs/questionnaires/lencioni.pdf",
            "status": "approved",
        },
        "response": {"mode": "team_assessment", "target": "team"},
        "instructions": (
            "Utilizati scala pentru a indica modul in care fiecare declaratie se aplica "
            "echipei. Evaluati sincer si fara sa va ganditi prea mult la raspunsuri."
        ),
        "sections": [
            {
                "id": "team_assessment",
                "title": "Evaluare echipa",
                "questions": [
                    _statement_question(
                        1,
                        "Membrii echipei sunt pasionali si netematori in discutiile lor "
                        "asupra problemelor.",
                        "fear_of_conflict",
                    ),
                    _statement_question(
                        2,
                        "Membrii echipei isi spun reciproc deficientele sau comportamentele "
                        "neproductive.",
                        "avoidance_of_accountability",
                    ),
                    _statement_question(
                        3,
                        "Membrii echipei stiu ce lucreaza colegii lor si cum contribuie la "
                        "binele colectiv al echipei.",
                        "lack_of_commitment",
                    ),
                    _statement_question(
                        4,
                        "Membrii echipei isi cer scuze repede unii altora atunci cand spun "
                        "sau fac ceva necorespunzator sau daunator echipei.",
                        "absence_of_trust",
                    ),
                    _statement_question(
                        5,
                        "Membrii echipei fac de buna voie sacrificii in departamentele sau "
                        "domeniile lor de expertiza, pentru binele echipei.",
                        "inattention_to_results",
                    ),
                    _statement_question(
                        6,
                        "Membrii echipei isi recunosc deschis slabiciunile si greselile.",
                        "absence_of_trust",
                    ),
                    _statement_question(
                        7,
                        "Intalnirile echipei sunt interesante, nu plictisitoare.",
                        "fear_of_conflict",
                    ),
                    _statement_question(
                        8,
                        "Membrii echipei parasesc reuniunile increzatori ca ai lor colegi "
                        "isi asuma cu totul deciziile convenite, chiar daca s-ar afla in "
                        "dezacord initial.",
                        "lack_of_commitment",
                    ),
                    _statement_question(
                        9,
                        "Moralul este afectat in mod semnificativ de esecul atingerii "
                        "obiectivelor echipei.",
                        "inattention_to_results",
                    ),
                    _statement_question(
                        10,
                        "In timpul intalnirilor echipei, problemele cele mai importante si "
                        "dificile sunt puse pe masa pentru a fi rezolvate.",
                        "fear_of_conflict",
                    ),
                    _statement_question(
                        11,
                        "Membrii echipei sunt profund ingrijorati de perspectiva de a-si "
                        "dezamagi colegii.",
                        "avoidance_of_accountability",
                    ),
                    _statement_question(
                        12,
                        "Membrii echipei stiu despre vietile personale ale celorlalti si se "
                        "simt confortabil sa le discute.",
                        "absence_of_trust",
                    ),
                    _statement_question(
                        13,
                        "Membrii echipei incheie discutiile cu hotarari si planuri de actiune "
                        "clare si specifice.",
                        "lack_of_commitment",
                    ),
                    _statement_question(
                        14,
                        "Membrii echipei se provoaca reciproc cu privire la planurile si "
                        "abordarile lor.",
                        "avoidance_of_accountability",
                    ),
                    _statement_question(
                        15,
                        "Membrii echipei nu se grabesc sa obtina recunoastere pentru propria "
                        "munca, dar se grabesc sa recunoasca meritele celorlalti.",
                        "inattention_to_results",
                    ),
                ],
            },
        ],
        "scoring": {
            "method": "sum_by_group",
            "groups": [
                {
                    "id": "absence_of_trust",
                    "label": "Absenta increderii",
                    "question_ids": ["lencioni_q04", "lencioni_q06", "lencioni_q12"],
                },
                {
                    "id": "fear_of_conflict",
                    "label": "Teama de conflict",
                    "question_ids": ["lencioni_q01", "lencioni_q07", "lencioni_q10"],
                },
                {
                    "id": "lack_of_commitment",
                    "label": "Lipsa angajamentului",
                    "question_ids": ["lencioni_q03", "lencioni_q08", "lencioni_q13"],
                },
                {
                    "id": "avoidance_of_accountability",
                    "label": "Evitarea responsabilitatii",
                    "question_ids": ["lencioni_q02", "lencioni_q11", "lencioni_q14"],
                },
                {
                    "id": "inattention_to_results",
                    "label": "Neatentia la rezultate",
                    "question_ids": ["lencioni_q05", "lencioni_q09", "lencioni_q15"],
                },
            ],
            "interpretation": [
                {"min": 8, "max": 9, "label": "Disfunctia probabil nu este o problema."},
                {"min": 6, "max": 7, "label": "Disfunctia poate fi o problema."},
                {"min": 3, "max": 5, "label": "Disfunctia trebuie probabil abordata."},
            ],
        },
    },
)


DISTRESS_DRIVERS_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.distress_drivers,
    version=1,
    title="Resilience and Transactional Analysis Drivers",
    description="Self-assessment pentru driverii de stres din Transactional Analysis.",
    schema={
        "schema_version": "questionnaire.v1",
        "source": {
            "type": "pdf",
            "path": "docs/questionnaires/distress_drivers.pdf",
            "status": "approved",
        },
        "response": {"mode": "self_assessment", "target": "self"},
        "instructions": (
            "Pentru fiecare set, marcheaza afirmatia cea mai adevarata pentru tine cu "
            "7-10, afirmatia cea mai putin adevarata cu 0-3, iar celelalte intre aceste "
            "repere. Gandeste-te la relatii adulte si la contextul de lucru."
        ),
        "sections": [
            {
                "id": "driver_sets",
                "title": "TA drivers",
                "questions": [
                    _distress_set(
                        1,
                        {
                            "a": ("Endurance is a valuable asset", "be_strong"),
                            "b": (
                                "I like to see people doing their best to get things done",
                                "be_perfect",
                            ),
                            "c": (
                                "Considering all the effort I put into things I should get more done",
                                "try_hard",
                            ),
                            "d": (
                                "I find myself doing too many things at the last minute",
                                "hurry_up",
                            ),
                            "e": (
                                "On balance, I adapt more to other people's wishes than they do to mine",
                                "please_people",
                            ),
                        },
                    ),
                    _distress_set(
                        2,
                        {
                            "a": ("Casualness and carelessness bother me", "be_perfect"),
                            "b": ("It is keeping busy that interests me", "try_hard"),
                            "c": (
                                "When people are slow about saying something, I want to finish their sentence",
                                "hurry_up",
                            ),
                            "d": (
                                "I have a fair amount of imagination when it comes to guessing what people need",
                                "please_people",
                            ),
                            "e": (
                                "When someone gets emotional, my reaction is often to make a joke of it",
                                "be_strong",
                            ),
                        },
                    ),
                    _distress_set(
                        3,
                        {
                            "a": (
                                "Even when my feelings run high, I show a calm exterior",
                                "be_strong",
                            ),
                            "b": (
                                "If something needs to be done well, I would rather do it myself",
                                "be_perfect",
                            ),
                            "c": (
                                "I'm more interested in doing things than finishing them",
                                "try_hard",
                            ),
                            "d": (
                                "I often run out of time when I want to get lots of things done",
                                "hurry_up",
                            ),
                            "e": ("I don't really like asking people for favours", "please_people"),
                        },
                    ),
                    _distress_set(
                        4,
                        {
                            "a": (
                                "I don't mind things being hard - I can always find the energy",
                                "try_hard",
                            ),
                            "b": (
                                "I am comfortable leaving it to the last minute to get to a place",
                                "hurry_up",
                            ),
                            "c": (
                                "If someone doesn't like me, I either try harder to get them to like me or walk away",
                                "please_people",
                            ),
                            "d": ("It's rare for me to feel hurt", "be_strong"),
                            "e": (
                                "If it's a question of doing something properly, I'd rather do it myself",
                                "be_perfect",
                            ),
                        },
                    ),
                    _distress_set(
                        5,
                        {
                            "a": ("I get impatient with slow people", "hurry_up"),
                            "b": (
                                "Normally I prefer to take people's wishes into account before reaching a decision",
                                "please_people",
                            ),
                            "c": (
                                "I show a calm face, even when I am annoyed or upset",
                                "be_strong",
                            ),
                            "d": ("I don't like to make excuses for shoddy work", "be_perfect"),
                            "e": (
                                "There's something about coming to the end of something that I don't like",
                                "try_hard",
                            ),
                        },
                    ),
                    _distress_set(
                        6,
                        {
                            "a": ("I believe words should be used correctly", "be_perfect"),
                            "b": (
                                "I like to explore a variety of options before getting started",
                                "try_hard",
                            ),
                            "c": (
                                "It's quite like me to be already thinking of the next thing before I've finished the first",
                                "hurry_up",
                            ),
                            "d": ("When I'm sure someone likes me, I feel better", "please_people"),
                            "e": (
                                "I put up with a great deal without anyone realising it",
                                "be_strong",
                            ),
                        },
                    ),
                    _distress_set(
                        7,
                        {
                            "a": ("If I had 20% more time I could relax more", "hurry_up"),
                            "b": (
                                "I often smile and nod when people talk to me",
                                "please_people",
                            ),
                            "c": (
                                "When people get overly excited, I prefer to stay rational and cool",
                                "be_strong",
                            ),
                            "d": (
                                "I can do something well and still be critical of myself",
                                "be_perfect",
                            ),
                            "e": (
                                "There are so many things to consider it can be hard to finalise something",
                                "try_hard",
                            ),
                        },
                    ),
                    _distress_set(
                        8,
                        {
                            "a": ("I don't usually go for the easy option", "try_hard"),
                            "b": (
                                "I like to have a lot of things on the go at any one time",
                                "hurry_up",
                            ),
                            "c": ("I like to think I am considerate", "please_people"),
                            "d": ("I avoid people who are overly emotional", "be_strong"),
                            "e": ("I can see easily how something can be improved", "be_perfect"),
                        },
                    ),
                    _distress_set(
                        9,
                        {
                            "a": (
                                "I rarely talk about my achievements or how much I have to put up with",
                                "be_strong",
                            ),
                            "b": (
                                "I find it difficult to talk about my strengths and usually focus on my weaknesses",
                                "be_perfect",
                            ),
                            "c": (
                                "I enjoy difficult problems; I feel energised to find a solution",
                                "try_hard",
                            ),
                            "d": (
                                "I'd rather get on and do things than sit planning and talking about them",
                                "hurry_up",
                            ),
                            "e": (
                                "Generally, I fit in more with what other people want from me",
                                "please_people",
                            ),
                        },
                    ),
                    _distress_set(
                        10,
                        {
                            "a": (
                                "I often repeat myself because I think I've not been understood",
                                "try_hard",
                            ),
                            "b": ("Generally, I get more done when up against it", "hurry_up"),
                            "c": (
                                "I like to discuss things with colleagues before I make a final decision",
                                "please_people",
                            ),
                            "d": (
                                "I rarely get upset by people or situations",
                                "be_strong",
                            ),
                            "e": (
                                "Correcting people and mistakes comes very naturally to me",
                                "be_perfect",
                            ),
                        },
                    ),
                ],
            },
        ],
        "scoring": {
            "method": "sum_statement_scores_by_driver",
            "drivers": [
                {"id": "be_strong", "code": "BS", "label": "Be Strong"},
                {"id": "be_perfect", "code": "BP", "label": "Be Perfect"},
                {"id": "try_hard", "code": "TH", "label": "Try Hard"},
                {"id": "hurry_up", "code": "HU", "label": "Hurry Up"},
                {"id": "please_people", "code": "PP", "label": "Please People"},
            ],
            "primary_result": "highest_total",
        },
    },
)


APPROVED_QUESTIONNAIRE_DEFINITIONS = [
    LENCIONI_DEFINITION,
    DISTRESS_DRIVERS_DEFINITION,
]


def get_approved_questionnaire_definition(
    key: QuestionnaireKey,
) -> ApprovedQuestionnaireDefinition:
    for definition in APPROVED_QUESTIONNAIRE_DEFINITIONS:
        if definition.key == key:
            return definition
    msg = f"No approved questionnaire definition for {key.value}"
    raise KeyError(msg)
