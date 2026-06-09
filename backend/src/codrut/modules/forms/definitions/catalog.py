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


ICARE_4_POINT_SCALE = [
    {"value": 1, "label": "Rar"},
    {"value": 2, "label": "Uneori"},
    {"value": 3, "label": "Frecvent"},
    {"value": 4, "label": "Întotdeauna"},
]

ICARE_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.icare,
    version=1,
    title="ICARE leadership behaviors",
    description=(
        "Evaluare comportamentală pe atributele ICARE. Versiune provizorie cu scală în 4 trepte, "
        "pregătită pentru ajustarea scalei finale."
    ),
    schema={
        "schema_version": "questionnaire.v1",
        "audience": "leadership",
        "source": {
            "type": "xlsx",
            "path": "docs/questionnaires/ICARE_scala.xlsx",
            "status": "provisional",
        },
        "instructions": (
            "Alege frecvența care descrie cel mai bine comportamentul observat. "
            "Scala curentă are 4 opțiuni și poate fi modificată fără rescrierea itemilor."
        ),
        "scoring": {
            "scale_status": "provisional_4_point",
            "source_columns_used": ["2; Rar / 25%", "3; Uneori / 50%", "4; Frecvent / 75%", "5; Întotdeauna / 100%"],
            "source_column_excluded_for_now": "1; Niciodată / 0%",
        },
        "sections": [
            {
                "id": "inspiring",
                "title": "Inspiring",
                "questions": [
                    {
                        "id": "icare_inspiring_developing_people",
                        "code": "ICARE-1.1",
                        "type": "statement_score_set",
                        "label": "Developing people",
                        "required": True,
                        "instructions": "Dezvoltare continuă prin feedback constructiv, încurajare și follow-up.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_01", "code": "S1", "label": "Oferă feedback constructiv"},
                            {"id": "icare_02", "code": "S2", "label": "Sprijină planurile de dezvoltare"},
                            {"id": "icare_03", "code": "S3", "label": "Se implică în propria dezvoltare continuă"},
                        ],
                    },
                    {
                        "id": "icare_inspiring_leading_by_example",
                        "code": "ICARE-1.2",
                        "type": "statement_score_set",
                        "label": "Leading by example",
                        "required": True,
                        "instructions": "Aliniere între valori, angajamente și comportamentul zilnic.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_04", "code": "S1", "label": "Acționează conform valorilor declarate"},
                            {"id": "icare_05", "code": "S2", "label": "Respectă angajamentele asumate față de echipă"},
                            {"id": "icare_06", "code": "S3", "label": "Tratează toți membrii echipei cu respect și echitate"},
                        ],
                    },
                    {
                        "id": "icare_inspiring_engagement_environment",
                        "code": "ICARE-1.3",
                        "type": "statement_score_set",
                        "label": "Creating an environment that drives engagement",
                        "required": True,
                        "instructions": "Mediu sigur, energizant și orientat către contribuția fiecărui membru.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_07", "code": "S1", "label": "Creează spațiu psihologic sigur pentru exprimare"},
                            {"id": "icare_08", "code": "S2", "label": "Delegă cu sens, nu doar cu sarcini"},
                            {"id": "icare_09", "code": "S3", "label": "Recunoaște contribuția individuală la succesul echipei"},
                        ],
                    },
                ],
            },
            {
                "id": "create_trust",
                "title": "Create Trust",
                "questions": [
                    {
                        "id": "icare_trust_collaboration",
                        "code": "ICARE-2.1",
                        "type": "statement_score_set",
                        "label": "Advocate of collaboration",
                        "required": True,
                        "instructions": "Transparență, colaborare și prioritizarea interesului comun.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_10", "code": "S1", "label": "Verifică înțelegerea comună după discuții"},
                            {"id": "icare_11", "code": "S2", "label": "Împărtășește context și motivații proprii"},
                            {"id": "icare_12", "code": "S3", "label": "Prioritizează interesul comun față de cel personal sau al echipei"},
                        ],
                    },
                    {
                        "id": "icare_trust_inspired",
                        "code": "ICARE-2.2",
                        "type": "statement_score_set",
                        "label": "Inspired",
                        "required": True,
                        "instructions": "Sens, ambiție și angajament construite împreună cu echipa.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_13", "code": "S1", "label": "Conectează munca echipei la un scop mai larg"},
                            {"id": "icare_14", "code": "S2", "label": "Co-construiește ambiții îndrăznețe cu echipa"},
                            {"id": "icare_15", "code": "S3", "label": "Inspiră prin propriul nivel de angajament"},
                        ],
                    },
                    {
                        "id": "icare_trust_reality",
                        "code": "ICARE-2.3",
                        "type": "statement_score_set",
                        "label": "Anchored in reality",
                        "required": True,
                        "instructions": "Ascultare activă, informații relevante și realism onest.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_16", "code": "S1", "label": "Ascultă activ înainte de a răspunde sau decide"},
                            {"id": "icare_17", "code": "S2", "label": "Împărtășește informații relevante proactiv"},
                            {"id": "icare_18", "code": "S3", "label": "Recunoaște faptele neplăcute cu onestitate"},
                        ],
                    },
                    {
                        "id": "icare_trust_illuminating",
                        "code": "ICARE-2.4",
                        "type": "statement_score_set",
                        "label": "Illuminating",
                        "required": True,
                        "instructions": "Claritate strategică în contexte complexe și incerte.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_19", "code": "S1", "label": "Comunică strategia și direcția cu claritate"},
                            {"id": "icare_20", "code": "S2", "label": "Oferă claritate în situații de ambiguitate"},
                            {"id": "icare_21", "code": "S3", "label": "Acționează cu claritate în medii complexe și incerte"},
                        ],
                    },
                ],
            },
            {
                "id": "awareness",
                "title": "Awareness",
                "questions": [
                    {
                        "id": "icare_awareness_humility",
                        "code": "ICARE-3.1",
                        "type": "statement_score_set",
                        "label": "Humility",
                        "required": True,
                        "instructions": "Feedback, limite personale și integrarea perspectivelor diferite.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_22", "code": "S1", "label": "Solicită feedback despre propriul comportament"},
                            {"id": "icare_23", "code": "S2", "label": "Știe când să ceară ajutor sau să admită că nu știe"},
                            {"id": "icare_24", "code": "S3", "label": "Integrează perspectivele diferite de a sa în decizii"},
                        ],
                    },
                    {
                        "id": "icare_awareness_emotional_intelligence",
                        "code": "ICARE-3.2",
                        "type": "statement_score_set",
                        "label": "Emotional and situational intelligence",
                        "required": True,
                        "instructions": "Autoreglare, interes autentic și adaptarea comunicării.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_25", "code": "S1", "label": "Recunoaște și gestionează propriile emoții în interacțiuni"},
                            {"id": "icare_26", "code": "S2", "label": "Arată interes autentic față de oameni ca indivizi"},
                            {"id": "icare_27", "code": "S3", "label": "Adaptează comunicarea la stilul și nevoile interlocutorului"},
                        ],
                    },
                    {
                        "id": "icare_awareness_open_world",
                        "code": "ICARE-3.3",
                        "type": "statement_score_set",
                        "label": "Open to the world",
                        "required": True,
                        "instructions": "Curiozitate, benchmarkuri externe și facilitarea schimbării.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_28", "code": "S1", "label": "Caută activ benchmarkuri și tendințe externe"},
                            {"id": "icare_29", "code": "S2", "label": "Îmbrățișează și facilitează schimbarea"},
                            {"id": "icare_30", "code": "S3", "label": "Explorează activ domenii adiacente sau noi tehnologii"},
                        ],
                    },
                ],
            },
            {
                "id": "results",
                "title": "Results",
                "questions": [
                    {
                        "id": "icare_results_ambitious",
                        "code": "ICARE-4.1",
                        "type": "statement_score_set",
                        "label": "Openly ambitious for the company",
                        "required": True,
                        "instructions": "Inovație, asumarea riscului și învățare din performanță.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_31", "code": "S1", "label": "Propune soluții inovatoare și îndrăznețe"},
                            {"id": "icare_32", "code": "S2", "label": "Promovează asumarea responsabilă a riscului"},
                            {"id": "icare_33", "code": "S3", "label": "Urmărește performanța și învață din eșecuri"},
                        ],
                    },
                    {
                        "id": "icare_results_caring",
                        "code": "ICARE-4.2",
                        "type": "statement_score_set",
                        "label": "Caring equally for employees and customers",
                        "required": True,
                        "instructions": "Echilibru între performanță, bunăstarea echipei și standarde realiste.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_34", "code": "S1", "label": "Echilibrează presiunile de performanță cu bunăstarea echipei"},
                            {"id": "icare_35", "code": "S2", "label": "Acordă atenție echilibrului muncă-viață al membrilor echipei"},
                            {"id": "icare_36", "code": "S3", "label": "Construiește standarde înalte bazate pe înțelegerea realității"},
                        ],
                    },
                    {
                        "id": "icare_results_agility",
                        "code": "ICARE-4.3",
                        "type": "statement_score_set",
                        "label": "Entrepreneurial agility",
                        "required": True,
                        "instructions": "Testare rapidă, simplificare și conectarea rețelei externe la oportunități.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_37", "code": "S1", "label": "Testează și învață rapid (test & learn)"},
                            {"id": "icare_38", "code": "S2", "label": "Livrează rezultate mai rapid prin simplificare și prioritizare"},
                            {"id": "icare_39", "code": "S3", "label": "Conectează rețeaua externă la oportunități de business"},
                        ],
                    },
                ],
            },
            {
                "id": "empowerment",
                "title": "Empowerment",
                "questions": [
                    {
                        "id": "icare_empowerment_decision_making",
                        "code": "ICARE-5.1",
                        "type": "statement_score_set",
                        "label": "On-the-ground decision-making",
                        "required": True,
                        "instructions": "Autonomie, inițiativă și raportare transparentă.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_40", "code": "S1", "label": "Delegă autoritatea decizională la nivelul potrivit"},
                            {"id": "icare_41", "code": "S2", "label": "Ia inițiativă și acționează fără să aștepte permisiunea"},
                            {"id": "icare_42", "code": "S3", "label": "Setează obiective clare și raportează transparent rezultatele"},
                        ],
                    },
                    {
                        "id": "icare_empowerment_collective_intelligence",
                        "code": "ICARE-5.2",
                        "type": "statement_score_set",
                        "label": "Cultivating collective intelligence",
                        "required": True,
                        "instructions": "Diversity, co-construcție, decizii asumate și refuzul compromisului facil.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_43", "code": "S1", "label": "Susține decizia finală chiar dacă diferă de propria opinie"},
                            {"id": "icare_44", "code": "S2", "label": "Caută și oferă sfaturi fără a impune soluții"},
                            {"id": "icare_45", "code": "S3", "label": "Refuză compromisul sistematic în favoarea soluțiilor mai bune"},
                        ],
                    },
                    {
                        "id": "icare_empowerment_helping_team",
                        "code": "ICARE-5.3",
                        "type": "statement_score_set",
                        "label": "Helping the team",
                        "required": True,
                        "instructions": "Contribuție la dinamica echipei, deblocare și sharing de cunoaștere.",
                        "scale": ICARE_4_POINT_SCALE,
                        "statements": [
                            {"id": "icare_46", "code": "S1", "label": "Alimentează dinamica și energia pozitivă a echipei"},
                            {"id": "icare_47", "code": "S2", "label": "Facilitează deblocarea obstacolelor pentru colegii din echipă"},
                            {"id": "icare_48", "code": "S3", "label": "Dezvoltă competențele echipei prin sharing de cunoaștere"},
                        ],
                    },
                ],
            },
        ],
    },
)


APPROVED_QUESTIONNAIRE_DEFINITIONS = [
    LENCIONI_DEFINITION,
    DISTRESS_DRIVERS_DEFINITION,
    ICARE_DEFINITION,
]


def get_approved_questionnaire_definition(
    key: QuestionnaireKey,
) -> ApprovedQuestionnaireDefinition:
    for definition in APPROVED_QUESTIONNAIRE_DEFINITIONS:
        if definition.key == key:
            return definition
    msg = f"No approved questionnaire definition for {key.value}"
    raise KeyError(msg)
