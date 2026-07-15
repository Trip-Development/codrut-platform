# ruff: noqa: E501

from __future__ import annotations

from copy import deepcopy
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

LIKERT_1_TO_3_EN = [
    {"value": 1, "label": "Rarely"},
    {"value": 2, "label": "Sometimes"},
    {"value": 3, "label": "Usually"},
]

DISTRESS_SCORE_0_TO_10 = [
    {"value": value, "label": str(value)}
    for value in range(0, 11)
]

BOSS_360_SCALE = [
    {"value": 1, "label": "Rar"},
    {"value": 2, "label": "Uneori"},
    {"value": 3, "label": "Des"},
    {"value": 4, "label": "Foarte des"},
    {"value": 5, "label": "Aproape întotdeauna"},
]

PCM_TYPES = [
    {"value": "harmonizer", "label": "Armonizator", "description": "Cald, empatic, orientat către relații și armonie."},
    {"value": "thinker", "label": "Gânditor", "description": "Logic, organizat, atent la structură și date."},
    {"value": "persister", "label": "Perseverent", "description": "Consecvent, valoric, atent la principii și calitate."},
    {"value": "imaginer", "label": "Imaginator", "description": "Reflexiv, calm, orientat către spațiu interior și claritate."},
    {"value": "rebel", "label": "Rebel", "description": "Spontan, creativ, energizat de joc și reacții autentice."},
    {"value": "promoter", "label": "Promotor", "description": "Direct, pragmatic, orientat către acțiune și oportunități."},
]


def _statement_question(
    number: int,
    text: str,
    dysfunction: str,
    *,
    scale: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"lencioni_q{number:02d}",
        "code": f"Q{number}",
        "type": "likert",
        "label": text,
        "required": True,
        "scale": scale or LIKERT_1_TO_3,
        "scoring": {"group": dysfunction},
    }


def _boss360_question(number: int, text: str) -> dict[str, Any]:
    return {
        "id": f"boss_360_q{number:02d}",
        "code": f"360-{number}",
        "type": "likert",
        "label": text,
        "required": True,
        "scale": BOSS_360_SCALE,
    }


def _distress_set(
    number: int,
    statements: dict[str, tuple[str, str]],
    *,
    instructions: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"distress_set_{number:02d}",
        "code": f"SET{number}",
        "type": "statement_score_set",
        "label": f"Set {number}",
        "required": True,
        "instructions": instructions or (
            "Acordă fiecărei afirmații un scor între 0 și 10. Alege afirmația cea mai "
            "adevărată pentru tine cu 7-10, cea mai puțin adevărată cu 0-3, iar "
            "celelalte între aceste repere."
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
    description="Evaluare Lencioni pentru cele cinci disfuncții ale unei echipe.",
    schema={
        "schema_version": "questionnaire.v1",
        "source": {
            "type": "pdf",
            "path": "docs/questionnaires/lencioni.pdf",
            "status": "approved",
        },
        "response": {"mode": "team_assessment", "target": "team"},
        "instructions": (
            "Utilizați scala pentru a indica modul în care fiecare declarație se aplică "
            "echipei. Evaluați sincer și fără să vă gândiți prea mult la răspunsuri."
        ),
        "sections": [
            {
                "id": "team_assessment",
                "title": "Evaluare echipă",
                "questions": [
                    _statement_question(
                        1,
                        "Membrii echipei sunt pasionați și netemători în discuțiile lor "
                        "asupra problemelor.",
                        "fear_of_conflict",
                    ),
                    _statement_question(
                        2,
                        "Membrii echipei își spun reciproc deficiențele sau comportamentele "
                        "neproductive.",
                        "avoidance_of_accountability",
                    ),
                    _statement_question(
                        3,
                        "Membrii echipei știu ce lucrează colegii lor și cum contribuie la "
                        "binele colectiv al echipei.",
                        "lack_of_commitment",
                    ),
                    _statement_question(
                        4,
                        "Membrii echipei își cer scuze repede unii altora atunci când spun "
                        "sau fac ceva necorespunzător sau dăunător echipei.",
                        "absence_of_trust",
                    ),
                    _statement_question(
                        5,
                        "Membrii echipei fac de bună voie sacrificii în departamentele sau "
                        "domeniile lor de expertiză, pentru binele echipei.",
                        "inattention_to_results",
                    ),
                    _statement_question(
                        6,
                        "Membrii echipei își recunosc deschis slăbiciunile și greșelile.",
                        "absence_of_trust",
                    ),
                    _statement_question(
                        7,
                        "Întâlnirile echipei sunt interesante, nu plictisitoare.",
                        "fear_of_conflict",
                    ),
                    _statement_question(
                        8,
                        "Membrii echipei părăsesc reuniunile încrezători că ai lor colegi "
                        "își asumă cu totul deciziile convenite, chiar dacă s-ar afla în "
                        "dezacord inițial.",
                        "lack_of_commitment",
                    ),
                    _statement_question(
                        9,
                        "Moralul este afectat în mod semnificativ de eșecul atingerii "
                        "obiectivelor echipei.",
                        "inattention_to_results",
                    ),
                    _statement_question(
                        10,
                        "În timpul întâlnirilor echipei, problemele cele mai importante și "
                        "dificile sunt puse pe masa pentru a fi rezolvate.",
                        "fear_of_conflict",
                    ),
                    _statement_question(
                        11,
                        "Membrii echipei sunt profund îngrijorați de perspectiva de a-și "
                        "dezamăgi colegii.",
                        "avoidance_of_accountability",
                    ),
                    _statement_question(
                        12,
                        "Membrii echipei știu despre viețile personale ale celorlalți și se "
                        "simt confortabil să le discute.",
                        "absence_of_trust",
                    ),
                    _statement_question(
                        13,
                        "Membrii echipei încheie discuțiile cu hotărâri și planuri de acțiune "
                        "clare și specifice.",
                        "lack_of_commitment",
                    ),
                    _statement_question(
                        14,
                        "Membrii echipei se provoacă reciproc cu privire la planurile și "
                        "abordările lor.",
                        "avoidance_of_accountability",
                    ),
                    _statement_question(
                        15,
                        "Membrii echipei nu se grăbesc să obțină recunoaștere pentru propria "
                        "muncă, dar se grăbesc să recunoască meritele celorlalți.",
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
                    "label": "Absența încrederii",
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
                    "label": "Evitarea responsabilității",
                    "question_ids": ["lencioni_q02", "lencioni_q11", "lencioni_q14"],
                },
                {
                    "id": "inattention_to_results",
                    "label": "Neatenția la rezultate",
                    "question_ids": ["lencioni_q05", "lencioni_q09", "lencioni_q15"],
                },
            ],
            "interpretation": [
                {"min": 8, "max": 9, "label": "Disfuncția probabil nu este o problemă."},
                {"min": 6, "max": 7, "label": "Disfuncția poate fi o problemă."},
                {"min": 3, "max": 5, "label": "Disfuncția trebuie probabil abordată."},
            ],
        },
    },
)


LENCIONI_EN_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.lencioni_en,
    version=1,
    title="Team Assessment Questionnaire",
    description="Lencioni assessment for the five dysfunctions of a team.",
    schema={
        "schema_version": "questionnaire.v1",
        "audience": "team",
        "source": {
            "type": "pdf",
            "path": "docs/questionnaires/lencioni.pdf",
            "status": "approved",
        },
        "response": {"mode": "team_assessment", "target": "team"},
        "instructions": (
            "Use the scale to indicate how each statement applies to the team. "
            "Answer honestly and avoid overthinking your responses."
        ),
        "sections": [
            {
                "id": "team_assessment",
                "title": "Team assessment",
                "questions": [
                    _statement_question(1, "Team members are passionate and unguarded in their discussion of issues.", "fear_of_conflict", scale=LIKERT_1_TO_3_EN),
                    _statement_question(2, "Team members call out one another's deficiencies or unproductive behaviors.", "avoidance_of_accountability", scale=LIKERT_1_TO_3_EN),
                    _statement_question(3, "Team members know what their peers are working on and how they contribute to the collective good of the team.", "lack_of_commitment", scale=LIKERT_1_TO_3_EN),
                    _statement_question(4, "Team members quickly and genuinely apologize to one another when they say or do something inappropriate or damaging to the team.", "absence_of_trust", scale=LIKERT_1_TO_3_EN),
                    _statement_question(5, "Team members willingly make sacrifices in their departments or areas of expertise for the good of the team.", "inattention_to_results", scale=LIKERT_1_TO_3_EN),
                    _statement_question(6, "Team members openly admit their weaknesses and mistakes.", "absence_of_trust", scale=LIKERT_1_TO_3_EN),
                    _statement_question(7, "Team meetings are compelling and not boring.", "fear_of_conflict", scale=LIKERT_1_TO_3_EN),
                    _statement_question(8, "Team members leave meetings confident that their peers are completely committed to the decisions agreed on, even if there was initial disagreement.", "lack_of_commitment", scale=LIKERT_1_TO_3_EN),
                    _statement_question(9, "Morale is significantly affected by the failure to achieve team goals.", "inattention_to_results", scale=LIKERT_1_TO_3_EN),
                    _statement_question(10, "During team meetings, the most important and difficult issues are put on the table to be resolved.", "fear_of_conflict", scale=LIKERT_1_TO_3_EN),
                    _statement_question(11, "Team members are deeply concerned about the prospect of letting down their peers.", "avoidance_of_accountability", scale=LIKERT_1_TO_3_EN),
                    _statement_question(12, "Team members know about one another's personal lives and are comfortable discussing them.", "absence_of_trust", scale=LIKERT_1_TO_3_EN),
                    _statement_question(13, "Team members end discussions with clear and specific resolutions and calls to action.", "lack_of_commitment", scale=LIKERT_1_TO_3_EN),
                    _statement_question(14, "Team members challenge one another about their plans and approaches.", "avoidance_of_accountability", scale=LIKERT_1_TO_3_EN),
                    _statement_question(15, "Team members are slow to seek credit for their own contributions but quick to recognize others.", "inattention_to_results", scale=LIKERT_1_TO_3_EN),
                ],
            },
        ],
        "scoring": {
            "method": "sum_by_group",
            "groups": [
                {
                    "id": "absence_of_trust",
                    "label": "Absence of trust",
                    "question_ids": ["lencioni_q04", "lencioni_q06", "lencioni_q12"],
                },
                {
                    "id": "fear_of_conflict",
                    "label": "Fear of conflict",
                    "question_ids": ["lencioni_q01", "lencioni_q07", "lencioni_q10"],
                },
                {
                    "id": "lack_of_commitment",
                    "label": "Lack of commitment",
                    "question_ids": ["lencioni_q03", "lencioni_q08", "lencioni_q13"],
                },
                {
                    "id": "avoidance_of_accountability",
                    "label": "Avoidance of accountability",
                    "question_ids": ["lencioni_q02", "lencioni_q11", "lencioni_q14"],
                },
                {
                    "id": "inattention_to_results",
                    "label": "Inattention to results",
                    "question_ids": ["lencioni_q05", "lencioni_q09", "lencioni_q15"],
                },
            ],
            "interpretation": [
                {"min": 8, "max": 9, "label": "The dysfunction is probably not a problem."},
                {"min": 6, "max": 7, "label": "The dysfunction could be a problem."},
                {"min": 3, "max": 5, "label": "The dysfunction probably needs to be addressed."},
            ],
        },
    },
)


PCM_BASE_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.pcm_base,
    version=1,
    title="Baza și faza ta PCM",
    description="Alege baza și faza PCM care descriu profilul tău curent.",
    schema={
        "schema_version": "questionnaire.v1",
        "response": {"mode": "profile_onboarding", "target": "self"},
        "instructions": (
            "Alege baza PCM și faza PCM identificate pentru tine. Dacă nu ești sigur, "
            "selectează varianta confirmată în discuția cu trainerul."
        ),
        "sections": [
            {
                "id": "pcm_base",
                "title": "Profil PCM",
                "questions": [
                    {
                        "id": "pcm_base",
                        "code": "PCM-BASE",
                        "type": "single_choice",
                        "label": "Care este baza ta PCM?",
                        "required": True,
                        "scale": PCM_TYPES,
                    },
                    {
                        "id": "pcm_phase",
                        "code": "PCM-PHASE",
                        "type": "single_choice",
                        "label": "Care este faza ta PCM?",
                        "required": True,
                        "scale": PCM_TYPES,
                    },
                ],
            }
        ],
    },
)


PCM_PHASE_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.phase,
    version=1,
    title="Faza ta PCM",
    description="Alege faza PCM activă în profilul tău curent.",
    schema={
        "schema_version": "questionnaire.v1",
        "response": {"mode": "profile_onboarding", "target": "self"},
        "instructions": (
            "Alege faza PCM curentă, așa cum a fost stabilită în evaluarea sau "
            "discuția ta de profil."
        ),
        "sections": [
            {
                "id": "pcm_phase",
                "title": "Faza PCM",
                "questions": [
                    {
                        "id": "pcm_phase",
                        "code": "PCM-PHASE",
                        "type": "single_choice",
                        "label": "Care este faza ta PCM?",
                        "required": True,
                        "scale": PCM_TYPES,
                    }
                ],
            }
        ],
    },
)


DISTRESS_DRIVERS_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.distress_drivers,
    version=1,
    title="Reziliență și driveri de stres TA",
    description="Autoevaluare pentru driverii de stres din Analiza Tranzacțională.",
    schema={
        "schema_version": "questionnaire.v1",
        "source": {
            "type": "pdf",
            "path": "docs/questionnaires/distress_drivers.pdf",
            "status": "approved",
        },
        "response": {"mode": "self_assessment", "target": "self"},
        "instructions": (
            "Pentru fiecare set, marchează afirmația cea mai adevărată pentru tine cu "
            "7-10, afirmația cea mai puțin adevărată cu 0-3, iar celelalte între aceste "
            "repere. Gândește-te la relații adulte și la contextul de lucru."
        ),
        "sections": [
            {
                "id": "driver_sets",
                "title": "Driveri TA",
                "questions": [
                    _distress_set(
                        1,
                        {
                            "a": ("Rezistența este o resursă valoroasă", "be_strong"),
                            "b": (
                                "Îmi place să văd oamenii făcând tot ce pot pentru a duce lucrurile la bun sfârșit",
                                "be_perfect",
                            ),
                            "c": (
                                "Având în vedere efortul pe care îl pun în lucruri, ar trebui să reușesc mai mult",
                                "try_hard",
                            ),
                            "d": (
                                "Mă trezesc făcând prea multe lucruri în ultimul moment",
                                "hurry_up",
                            ),
                            "e": (
                                "Per total, mă adaptez mai mult dorințelor altora decât se adaptează ei dorințelor mele",
                                "please_people",
                            ),
                        },
                    ),
                    _distress_set(
                        2,
                        {
                            "a": ("Mă deranjează superficialitatea și neglijența", "be_perfect"),
                            "b": ("Mă interesează să fiu mereu ocupat", "try_hard"),
                            "c": (
                                "Când oamenii spun ceva prea încet, îmi vine să le termin eu propoziția",
                                "hurry_up",
                            ),
                            "d": (
                                "Am destulă imaginație când vine vorba să ghicesc de ce au nevoie oamenii",
                                "please_people",
                            ),
                            "e": (
                                "Când cineva devine emoțional, reacția mea este adesea să fac o glumă",
                                "be_strong",
                            ),
                        },
                    ),
                    _distress_set(
                        3,
                        {
                            "a": (
                                "Chiar și când emoțiile mele sunt intense, în exterior par calm",
                                "be_strong",
                            ),
                            "b": (
                                "Dacă ceva trebuie făcut bine, prefer să îl fac eu",
                                "be_perfect",
                            ),
                            "c": (
                                "Sunt mai interesat să încep și să fac lucruri decât să le finalizez",
                                "try_hard",
                            ),
                            "d": (
                                "Rămân adesea fără timp când vreau să fac multe lucruri",
                                "hurry_up",
                            ),
                            "e": ("Nu îmi place prea mult să cer favoruri oamenilor", "please_people"),
                        },
                    ),
                    _distress_set(
                        4,
                        {
                            "a": (
                                "Nu mă deranjează ca lucrurile să fie grele - găsesc mereu energie",
                                "try_hard",
                            ),
                            "b": (
                                "Mă simt confortabil să las plecarea spre un loc pe ultimul moment",
                                "hurry_up",
                            ),
                            "c": (
                                "Dacă cineva nu mă place, fie încerc mai mult să mă placă, fie mă retrag",
                                "please_people",
                            ),
                            "d": ("Mi se întâmplă rar să mă simt rănit", "be_strong"),
                            "e": (
                                "Dacă este vorba să fac ceva cum trebuie, prefer să îl fac eu",
                                "be_perfect",
                            ),
                        },
                    ),
                    _distress_set(
                        5,
                        {
                            "a": ("Îmi pierd răbdarea cu oamenii lenți", "hurry_up"),
                            "b": (
                                "De obicei prefer să țin cont de dorințele oamenilor înainte de a lua o decizie",
                                "please_people",
                            ),
                            "c": (
                                "Arăt o față calmă, chiar și când sunt enervat sau supărat",
                                "be_strong",
                            ),
                            "d": ("Nu îmi place să caut scuze pentru o muncă făcută superficial", "be_perfect"),
                            "e": (
                                "Este ceva la momentul în care ajung la finalul unui lucru care nu îmi place",
                                "try_hard",
                            ),
                        },
                    ),
                    _distress_set(
                        6,
                        {
                            "a": ("Cred că vorbele ar trebui folosite corect", "be_perfect"),
                            "b": (
                                "Îmi place să explorez mai multe opțiuni înainte să încep",
                                "try_hard",
                            ),
                            "c": (
                                "Mi se potrivește să mă gândesc deja la următorul lucru înainte să îl termin pe primul",
                                "hurry_up",
                            ),
                            "d": ("Când sunt sigur că cineva mă place, mă simt mai bine", "please_people"),
                            "e": (
                                "Duc foarte multe fără ca ceilalți să își dea seama",
                                "be_strong",
                            ),
                        },
                    ),
                    _distress_set(
                        7,
                        {
                            "a": ("Dacă aș avea cu 20% mai mult timp, m-aș putea relaxa mai mult", "hurry_up"),
                            "b": (
                                "Zâmbesc și aprob des din cap când oamenii vorbesc cu mine",
                                "please_people",
                            ),
                            "c": (
                                "Când oamenii se entuziasmează prea tare, prefer să rămân rațional și calm",
                                "be_strong",
                            ),
                            "d": (
                                "Pot face ceva bine și totuși să fiu critic cu mine",
                                "be_perfect",
                            ),
                            "e": (
                                "Sunt atât de multe lucruri de luat în calcul încât poate fi greu să finalizez ceva",
                                "try_hard",
                            ),
                        },
                    ),
                    _distress_set(
                        8,
                        {
                            "a": ("De obicei nu aleg varianta ușoară", "try_hard"),
                            "b": (
                                "Îmi place să am multe lucruri în desfășurare în același timp",
                                "hurry_up",
                            ),
                            "c": ("Îmi place să cred că sunt atent la ceilalți", "please_people"),
                            "d": ("Evit oamenii care sunt prea emoționali", "be_strong"),
                            "e": ("Văd ușor cum poate fi îmbunătățit ceva", "be_perfect"),
                        },
                    ),
                    _distress_set(
                        9,
                        {
                            "a": (
                                "Vorbesc rar despre realizările mele sau despre cât de multe duc",
                                "be_strong",
                            ),
                            "b": (
                                "Îmi este greu să vorbesc despre punctele mele forte și de obicei mă concentrez pe slăbiciuni",
                                "be_perfect",
                            ),
                            "c": (
                                "Îmi plac problemele dificile; mă energizează să găsesc o soluție",
                                "try_hard",
                            ),
                            "d": (
                                "Prefer să mă apuc și să fac lucruri decât să stau să le planific și să vorbesc despre ele",
                                "hurry_up",
                            ),
                            "e": (
                                "În general, mă adaptez mai mult la ceea ce vor ceilalți de la mine",
                                "please_people",
                            ),
                        },
                    ),
                    _distress_set(
                        10,
                        {
                            "a": (
                                "Mă repet adesea pentru că am impresia că nu am fost înțeles",
                                "try_hard",
                            ),
                            "b": ("În general, fac mai multe când sunt sub presiune", "hurry_up"),
                            "c": (
                                "Îmi place să discut lucrurile cu colegii înainte să iau o decizie finală",
                                "please_people",
                            ),
                            "d": (
                                "Mă supăr rar din cauza oamenilor sau situațiilor",
                                "be_strong",
                            ),
                            "e": (
                                "Îmi vine foarte natural să corectez oamenii și greșelile",
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
                {"id": "be_strong", "code": "BS", "label": "Fii puternic"},
                {"id": "be_perfect", "code": "BP", "label": "Fii perfect"},
                {"id": "try_hard", "code": "TH", "label": "Străduiește-te"},
                {"id": "hurry_up", "code": "HU", "label": "Grăbește-te"},
                {"id": "please_people", "code": "PP", "label": "Fă pe plac"},
            ],
            "primary_result": "highest_total",
        },
    },
)


DISTRESS_INSTRUCTIONS_EN = (
    "Score each statement from 0 to 10. Mark the statement that is most true for "
    "you with 7-10, the least true statement with 0-3, and place the others "
    "between those anchors. Think about adult relationships and work context."
)


DISTRESS_DRIVERS_EN_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.distress_drivers_en,
    version=1,
    title="Resilience and TA Distress Drivers",
    description="Self-assessment for Transactional Analysis distress drivers.",
    schema={
        "schema_version": "questionnaire.v1",
        "audience": "leadership",
        "source": {
            "type": "pdf",
            "path": "docs/questionnaires/distress_drivers.pdf",
            "status": "approved",
        },
        "response": {"mode": "self_assessment", "target": "self"},
        "instructions": DISTRESS_INSTRUCTIONS_EN,
        "sections": [
            {
                "id": "driver_sets",
                "title": "TA drivers",
                "questions": [
                    _distress_set(
                        1,
                        {
                            "a": ("Resilience is a valuable resource", "be_strong"),
                            "b": ("I like seeing people do everything they can to get things finished", "be_perfect"),
                            "c": ("Considering the effort I put into things, I should achieve more", "try_hard"),
                            "d": ("I find myself doing too many things at the last minute", "hurry_up"),
                            "e": ("Overall, I adapt more to other people's wishes than they adapt to mine", "please_people"),
                        },
                        instructions=DISTRESS_INSTRUCTIONS_EN,
                    ),
                    _distress_set(
                        2,
                        {
                            "a": ("Superficiality and carelessness bother me", "be_perfect"),
                            "b": ("I am interested in always being busy", "try_hard"),
                            "c": ("When people say something too slowly, I feel like finishing the sentence for them", "hurry_up"),
                            "d": ("I have enough imagination to guess what people need", "please_people"),
                            "e": ("When someone becomes emotional, my reaction is often to make a joke", "be_strong"),
                        },
                        instructions=DISTRESS_INSTRUCTIONS_EN,
                    ),
                    _distress_set(
                        3,
                        {
                            "a": ("Even when my emotions are intense, I appear calm on the outside", "be_strong"),
                            "b": ("If something must be done well, I prefer to do it myself", "be_perfect"),
                            "c": ("I am more interested in starting and doing things than in finishing them", "try_hard"),
                            "d": ("I often run out of time when I want to do many things", "hurry_up"),
                            "e": ("I do not particularly like asking people for favors", "please_people"),
                        },
                        instructions=DISTRESS_INSTRUCTIONS_EN,
                    ),
                    _distress_set(
                        4,
                        {
                            "a": ("I do not mind things being difficult - I always find energy", "try_hard"),
                            "b": ("I feel comfortable leaving for somewhere at the last minute", "hurry_up"),
                            "c": ("If someone does not like me, I either try harder to be liked or withdraw", "please_people"),
                            "d": ("It is rare for me to feel hurt", "be_strong"),
                            "e": ("When something must be done properly, I prefer to do it myself", "be_perfect"),
                        },
                        instructions=DISTRESS_INSTRUCTIONS_EN,
                    ),
                    _distress_set(
                        5,
                        {
                            "a": ("I lose patience with slow people", "hurry_up"),
                            "b": ("I usually prefer to consider people's wishes before making a decision", "please_people"),
                            "c": ("I show a calm face even when I am annoyed or upset", "be_strong"),
                            "d": ("I do not like looking for excuses for work done superficially", "be_perfect"),
                            "e": ("There is something about reaching the end of a task that I do not like", "try_hard"),
                        },
                        instructions=DISTRESS_INSTRUCTIONS_EN,
                    ),
                    _distress_set(
                        6,
                        {
                            "a": ("I believe words should be used correctly", "be_perfect"),
                            "b": ("I like to explore several options before I start", "try_hard"),
                            "c": ("It suits me to already think about the next thing before finishing the first", "hurry_up"),
                            "d": ("When I am sure someone likes me, I feel better", "please_people"),
                            "e": ("I carry a lot without others realizing it", "be_strong"),
                        },
                        instructions=DISTRESS_INSTRUCTIONS_EN,
                    ),
                    _distress_set(
                        7,
                        {
                            "a": ("If I had 20% more time, I could relax more", "hurry_up"),
                            "b": ("I often smile and nod when people speak with me", "please_people"),
                            "c": ("When people get too enthusiastic, I prefer to stay rational and calm", "be_strong"),
                            "d": ("I can do something well and still be critical of myself", "be_perfect"),
                            "e": ("There are so many things to consider that finishing something can be difficult", "try_hard"),
                        },
                        instructions=DISTRESS_INSTRUCTIONS_EN,
                    ),
                    _distress_set(
                        8,
                        {
                            "a": ("I usually do not choose the easy option", "try_hard"),
                            "b": ("I like having many things in progress at the same time", "hurry_up"),
                            "c": ("I like to think I am attentive to others", "please_people"),
                            "d": ("I avoid people who are too emotional", "be_strong"),
                            "e": ("I easily see how something could be improved", "be_perfect"),
                        },
                        instructions=DISTRESS_INSTRUCTIONS_EN,
                    ),
                    _distress_set(
                        9,
                        {
                            "a": ("I rarely talk about my achievements or about how much I carry", "be_strong"),
                            "b": ("It is hard for me to talk about my strengths, and I usually focus on weaknesses", "be_perfect"),
                            "c": ("I like difficult problems; finding a solution gives me energy", "try_hard"),
                            "d": ("I prefer to start and do things rather than sit around planning and talking about them", "hurry_up"),
                            "e": ("In general, I adapt more to what others want from me", "please_people"),
                        },
                        instructions=DISTRESS_INSTRUCTIONS_EN,
                    ),
                    _distress_set(
                        10,
                        {
                            "a": ("I often repeat myself because I feel I have not been understood", "try_hard"),
                            "b": ("In general, I do more when I am under pressure", "hurry_up"),
                            "c": ("I like discussing things with colleagues before making a final decision", "please_people"),
                            "d": ("I rarely get upset because of people or situations", "be_strong"),
                            "e": ("It comes very naturally to me to correct people and mistakes", "be_perfect"),
                        },
                        instructions=DISTRESS_INSTRUCTIONS_EN,
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


ICARE_SOURCE_SECTIONS = [{'id': 'inspiring',
  'title': 'Inspiră (Inspiring)',
  'questions': [{'id': 'icare_01_dezvolta_oamenii',
                 'code': 'ICARE-1',
                 'type': 'statement_score_set',
                 'label': 'Dezvoltă oamenii',
                 'required': True,
                 'instructions': 'Ne asigurăm de dezvoltarea continuă a noastră, a colegilor și a '
                                 'echipelor. Facem asta printr-un angajament personal față de '
                                 'dezvoltare, prin feedback continuu, onest și constructiv. Lăudăm '
                                 'și încurajăm progresul și reușitele.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_01',
                                 'code': 'S1',
                                 'label': 'Oferă feedback constructiv',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu oferă feedback sau îl evită '
                                                           'complet.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Oferă feedback rar, doar când i se '
                                                           'cere.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Oferă feedback destul de des, dar vag, '
                                                           'fără exemple concrete.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Oferă feedback regulat, cu exemple '
                                                           'concrete și pe un ton constructiv.'}]},
                                {'id': 'icare_02',
                                 'code': 'S2',
                                 'label': 'Sprijină planurile de dezvoltare',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu face sesiuni de coaching sau '
                                                           'mentoring prin care să își ajute '
                                                           'colegii să crească.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'A făcut una sau două sesiuni în care a '
                                                           'ghidat un coleg să ia decizii sau să '
                                                           'se dezvolte.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Are conversații despre dezvoltare și '
                                                           'propune resurse sau oportunități '
                                                           'concrete care îi ajută pe oameni să '
                                                           'crească.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Face împreună cu oamenii planuri de '
                                                           'dezvoltare personalizate, alocă timp '
                                                           'pentru mentoring și verifică periodic '
                                                           'progresul.'}]},
                                {'id': 'icare_03',
                                 'code': 'S3',
                                 'label': 'Se implică în propria dezvoltare continuă',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu caută să învețe lucruri noi.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Participă la training-urile '
                                                           'obligatorii, dar nu aplică ce învață.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Caută destul de des să se '
                                                           'îmbunătățească, dar fără un plan '
                                                           'clar.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Caută activ feedback și ocazii de '
                                                           'învățare și aplică ce învață.'}]}]},
                {'id': 'icare_02_conduce_prin_puterea_exemplului',
                 'code': 'ICARE-2',
                 'type': 'statement_score_set',
                 'label': 'Conduce prin puterea exemplului',
                 'required': True,
                 'instructions': 'Oferim constant un exemplu de autenticitate și sinceritate. Ne '
                                 'aliniem faptele cu vorbele.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_04',
                                 'code': 'S1',
                                 'label': 'Acționează conform valorilor declarate',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Spune una și face alta.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Acționează conform valorilor doar când '
                                                           'este observat.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'De cele mai multe ori faptele se '
                                                           'potrivesc cu vorbele, cu unele '
                                                           'excepții.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Vorbele și faptele se potrivesc '
                                                           'constant; există exemple concrete care '
                                                           'arată asta.'}]},
                                {'id': 'icare_05',
                                 'code': 'S2',
                                 'label': 'Respectă angajamentele asumate față de echipă',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Ratează frecvent termene sau '
                                                           'promisiuni față de echipă, fără să '
                                                           'anunțe.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Își respectă angajamentele doar când i '
                                                           'se reamintește sau anunță târziu că nu '
                                                           'a reușit.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Își respectă angajamentele în general, '
                                                           'dar excepțiile le comunică târziu.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Își respectă angajamentele, iar dacă '
                                                           'ceva se schimbă, anunță din timp.'}]},
                                {'id': 'icare_06',
                                 'code': 'S3',
                                 'label': 'Tratează toți membrii echipei cu respect și echitate',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Se poartă vizibil diferit cu oamenii, '
                                                           'în funcție de poziția lor în companie '
                                                           'și de preferințele sale.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Se poartă într-un fel în ședințe și în '
                                                           'alt fel în discuțiile private.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Tratează oamenii echitabil în general, '
                                                           'cu excepții rare.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Tratează toți oamenii cu respect, '
                                                           'indiferent de nivel sau context.'}]}]},
                {'id': 'icare_03_creeaza_un_mediu_care_stimuleaza_implicarea',
                 'code': 'ICARE-3',
                 'type': 'statement_score_set',
                 'label': 'Creează un mediu care stimulează implicarea',
                 'required': True,
                 'instructions': 'Construim împreună un mediu care stimulează implicarea, '
                                 'încurajează asumarea de riscuri și ne eliberează energiile.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_07',
                                 'code': 'S1',
                                 'label': 'Creează spațiu psihologic sigur pentru exprimare',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Critică, ignoră sau ridiculizează '
                                                           'opiniile diferite de ale sale.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Nu descurajează exprimarea, dar nici '
                                                           'nu o încurajează.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Invită oamenii să-și spună părerea, '
                                                           'dar mai ales în cadru formal.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Încurajează constant oamenii să '
                                                           'vorbească deschis și primește bine '
                                                           'opiniile contrare.'}]},
                                {'id': 'icare_08',
                                 'code': 'S2',
                                 'label': 'Delegă cu sens, nu doar cu sarcini',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Dă sarcini fără context; echipa '
                                                           'execută fără să înțeleagă de ce.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Explică pe scurt ce trebuie făcut, dar '
                                                           'nu și de ce.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Oferă deseori context la delegare, dar '
                                                           'nu de fiecare dată.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Delegă explicând scopul, așteptările '
                                                           'și cât de multă autonomie are '
                                                           'persoana.'}]},
                                {'id': 'icare_09',
                                 'code': 'S3',
                                 'label': 'Recunoaște contribuția individuală la succesul echipei',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Succesul e prezentat ca al lui sau al '
                                                           'conducerii; oamenii care au muncit nu '
                                                           'sunt menționați.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Recunoaște contribuțiile individuale '
                                                           'doar la evaluările formale.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Laudă deseori oamenii, dar la modul '
                                                           'general („bravo tuturor”), nu pe '
                                                           'fiecare pentru ce a făcut.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Recunoaște regulat și concret '
                                                           'contribuția fiecăruia la rezultatul '
                                                           'echipei.'}]}]}]},
 {'id': 'create_trust',
  'title': 'Construiește încredere (Create Trust)',
  'questions': [{'id': 'icare_04_promotor_al_colaborarii',
                 'code': 'ICARE-4',
                 'type': 'statement_score_set',
                 'label': 'Promotor al colaborării',
                 'required': True,
                 'instructions': 'Construim încredere prin transparență și prin înțelegerea clară '
                                 'a contextului și motivațiilor celuilalt. Colaborăm activ cu '
                                 'colegii, clienții, furnizorii și partenerii pentru rezultate '
                                 'durabile. Interesul companiei trece înaintea celui individual și '
                                 'al propriei echipe.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_10',
                                 'code': 'S1',
                                 'label': 'Verifică înțelegerea comună după discuții',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Pleacă din discuții fără să verifice '
                                                           'dacă toți au înțeles la fel.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Verifică înțelegerea doar când apar '
                                                           'deja probleme.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Verifică deseori punctele cheie, dar '
                                                           'nu constant.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Se asigură de fiecare dată că toți au '
                                                           'înțeles la fel punctele importante.'}]},
                                {'id': 'icare_11',
                                 'code': 'S2',
                                 'label': 'Împărtășește context și motivații proprii',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu explică niciodată motivele din '
                                                           'spatele deciziilor sau priorităților '
                                                           'sale.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Oferă context doar când este întrebat '
                                                           'direct.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Explică deseori raționamentul '
                                                           'deciziilor, mai ales la cele '
                                                           'importante.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Explică mai mereu din proprie '
                                                           'inițiativă contextul și motivele '
                                                           'deciziilor sale.'}]},
                                {'id': 'icare_12',
                                 'code': 'S3',
                                 'label': 'Prioritizează interesul comun față de cel personal sau '
                                          'al echipei',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Ia decizii doar în beneficiul propriu '
                                                           'sau al echipei sale.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Ține cont de interesul companiei doar '
                                                           'când există presiune din afară.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Pune deseori interesul companiei pe '
                                                           'primul loc, dar nu și în situațiile '
                                                           'dificile.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Alege constant soluțiile bune pentru '
                                                           'companie, chiar dacă sunt mai grele '
                                                           'pentru echipa lui.'}]}]},
                {'id': 'icare_05_ancorat_in_realitate',
                 'code': 'ICARE-5',
                 'type': 'statement_score_set',
                 'label': 'Ancorat în realitate',
                 'required': True,
                 'instructions': 'Construim încredere ascultând activ, împărtășind informații și '
                                 'lucrând împreună pe teren. Recunoaștem faptele cu onestitate și '
                                 'modestie.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_13',
                                 'code': 'S1',
                                 'label': 'Ascultă activ înainte de a răspunde sau decide',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Întrerupe frecvent sau își pregătește '
                                                           'răspunsul în timp ce celălalt '
                                                           'vorbește.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Ascultă până la capăt, dar nu verifică '
                                                           'dacă a înțeles corect.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Reformulează deseori ce a auzit, ca să '
                                                           'verifice că a înțeles.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Ascultă fără să întrerupă, pune '
                                                           'întrebări de clarificare și poate reda '
                                                           'corect punctul de vedere al '
                                                           'celuilalt.'}]},
                                {'id': 'icare_14',
                                 'code': 'S2',
                                 'label': 'Împărtășește informații relevante proactiv',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Ține informațiile pentru el, '
                                                           'intenționat sau din neglijență.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Dă informații doar când este întrebat '
                                                           'direct.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Transmite deseori informațiile utile, '
                                                           'dar nu are un obicei constant.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Transmite din timp informațiile '
                                                           'relevante, astfel încât nimeni să nu '
                                                           'fie luat prin surprindere.'}]},
                                {'id': 'icare_15',
                                 'code': 'S3',
                                 'label': 'Recunoaște faptele neplăcute cu onestitate',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Evită sau minimizează problemele ca să '
                                                           'păstreze aparențele.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Recunoaște problemele doar când nu mai '
                                                           'pot fi evitate.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Vorbește deseori despre problemele '
                                                           'reale, dar cu ezitare.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Numește problemele direct și la timp, '
                                                           'fără să dramatizeze.'}]}]},
                {'id': 'icare_06_aduce_claritate',
                 'code': 'ICARE-6',
                 'type': 'statement_score_set',
                 'label': 'Aduce claritate',
                 'required': True,
                 'instructions': 'Ne ghidăm după scopul, valorile și strategia noastră, care ne '
                                 'ajută să ne înțelegem și să ne aliniem echipele și organizația. '
                                 'Acționăm cu ușurință într-un mediu complex și incert.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_16',
                                 'code': 'S1',
                                 'label': 'Comunică strategia și direcția cu claritate',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu vorbește cu echipa despre strategie '
                                                           'sau direcție.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Transmite informații despre direcție '
                                                           'doar când i se cere de sus.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Explică deseori direcția, dar mesajul '
                                                           'nu e mereu coerent.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Comunică des și clar direcția și o '
                                                           'leagă de munca de zi cu zi a '
                                                           'echipei.'}]},
                                {'id': 'icare_17',
                                 'code': 'S2',
                                 'label': 'Oferă claritate în situații de ambiguitate',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'În situații neclare transmite '
                                                           'nesiguranță sau evită subiectul.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Recunoaște că situația e neclară, dar '
                                                           'nu oferă o direcție de acțiune.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Oferă deseori claritate în situații '
                                                           'ambigue, dar nu de fiecare dată.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Spune clar ce se știe, ce nu se știe '
                                                           'și care sunt pașii următori.'}]},
                                {'id': 'icare_18',
                                 'code': 'S3',
                                 'label': 'Acționează cu claritate în medii complexe și incerte',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'În situații complexe se blochează sau '
                                                           'intră vizibil în panică.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Acționează în incertitudine doar când '
                                                           'nu are altă opțiune.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Se descurcă deseori în situații '
                                                           'complexe, fără disconfort major.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Acționează calm și structurat în '
                                                           'situații complexe și incerte.'}]}]}]},
 {'id': 'awareness',
  'title': 'Conștientizare (Awareness)',
  'questions': [{'id': 'icare_07_modestie',
                 'code': 'ICARE-7',
                 'type': 'statement_score_set',
                 'label': 'Modestie',
                 'required': True,
                 'instructions': 'O înțelegere onestă și vie a propriei persoane ne permite să ne '
                                 'dezvoltăm abilitățile și comportamentele. Cerem regulat feedback '
                                 'cu scopul de a ne îmbunătăți. Putem avea îndoieli, dar apoi '
                                 'decidem și acționăm fără ezitare.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_19',
                                 'code': 'S1',
                                 'label': 'Solicită feedback despre propriul comportament',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu cere niciodată feedback și îl '
                                                           'respinge când îl primește.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Acceptă feedback dacă i se oferă, dar '
                                                           'nu îl caută.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Cere feedback deseori, dar fără '
                                                           'întrebări concrete și fără să revină '
                                                           'asupra lui.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Cere regulat feedback de la colegi și '
                                                           'superiori, cu întrebări concrete, și '
                                                           'schimbă ceva în urma lui.'}]},
                                {'id': 'icare_20',
                                 'code': 'S2',
                                 'label': 'Știe când să ceară ajutor sau să admită că nu știe',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu admite  că nu știe, chiar daca '
                                                           'altii observa asta si ii spun; preferă '
                                                           'să dea răspunsuri greșite.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Își recunoaște lacunele doar când le '
                                                           'observă alții. '},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Recunoaște deseori că nu știe, dar '
                                                           'preferă să se descurce singur.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Cere ajutor din timp atunci când '
                                                           'subiectul îi depășește competența.'}]},
                                {'id': 'icare_21',
                                 'code': 'S3',
                                 'label': 'Integrează perspectivele diferite de a sa în decizii',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Ignoră sau desconsideră părerile care '
                                                           'îl contrazic.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Ascultă părerile diferite, dar rar le '
                                                           'folosește în decizii.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Ține deseori cont de părerile altora, '
                                                           'mai ales când sunt bine argumentate.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Caută activ păreri diferite înainte de '
                                                           'deciziile importante și le '
                                                           'folosește.'}]}]},
                {'id': 'icare_08_inteligenta_emotionala_si_situationala',
                 'code': 'ICARE-8',
                 'type': 'statement_score_set',
                 'label': 'Inteligență emoțională și situațională',
                 'required': True,
                 'instructions': 'Inteligența emoțională și situațională ne permite să înțelegem '
                                 'și să ne adaptăm la oameni și situații diferite. Ne pasă sincer '
                                 'unii de alții.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_22',
                                 'code': 'S1',
                                 'label': 'Recunoaște și gestionează propriile emoții în '
                                          'interacțiuni',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Emoțiile lui afectează vizibil '
                                                           'discuțiile: ton, reacții, decizii.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Se stăpânește la suprafață, dar sub '
                                                           'presiune tensiunea răbufnește.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Își dă seama când e afectat emoțional '
                                                           'și deseori reușește să se calmeze.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Își gestionează bine emoțiile, '
                                                           'inclusiv sub presiune.'}]},
                                {'id': 'icare_23',
                                 'code': 'S2',
                                 'label': 'Arată interes autentic față de oameni ca indivizi',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Discută doar despre sarcini, niciodată '
                                                           'despre oameni.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Se interesează de oameni doar în cadru '
                                                           'formal (evaluări, discuții 1-la-1).'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Se interesează deseori de contextul '
                                                           'personal al colegilor.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Cunoaște oamenii din echipă și ține '
                                                           'cont de situația fiecăruia; oamenii se '
                                                           'simt tratați ca persoane, nu ca '
                                                           'resurse.'}]},
                                {'id': 'icare_24',
                                 'code': 'S3',
                                 'label': 'Adaptează comunicarea la stilul și nevoile '
                                          'interlocutorului',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Comunică la fel cu toată lumea, '
                                                           'indiferent de persoană sau situație.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Își adaptează comunicarea doar când '
                                                           'are timp și nu e sub presiune.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Își adaptează deseori stilul în '
                                                           'funcție de persoană.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Își adaptează constant tonul, ritmul '
                                                           'și mesajul la omul din fața lui.'}]}]},
                {'id': 'icare_09_deschis_catre_lume',
                 'code': 'ICARE-9',
                 'type': 'statement_score_set',
                 'label': 'Deschis către lume',
                 'required': True,
                 'instructions': 'Suntem curioși să înțelegem lumea din jur și căutăm activ repere '
                                 'externe, cu atenție specială la tot ce ține de digital și de '
                                 'noile tehnologii. Încurajăm schimbarea și ne adaptăm la ea.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_25',
                                 'code': 'S1',
                                 'label': 'Caută activ benchmarkuri și tendințe externe',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu urmărește deloc ce se întâmplă în '
                                                           'industrie sau în afara companiei.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Se uită la exemple din exterior doar '
                                                           'când i le aduc alții.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Urmărește deseori tendințele din '
                                                           'exterior, dar fără un obicei '
                                                           'constant.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Urmărește constant tendințele '
                                                           'relevante și le aduce în discuțiile cu '
                                                           'echipa.'}]},
                                {'id': 'icare_26',
                                 'code': 'S2',
                                 'label': 'Îmbrățișează și facilitează schimbarea',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Se opune schimbării și influențează '
                                                           'negativ atitudinea echipei.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Acceptă schimbarea când e impusă, fără '
                                                           'să o susțină.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Acceptă schimbarea fără rezistență și '
                                                           'deseori o susține.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Susține activ schimbarea și ajută '
                                                           'echipa să treacă prin ea.'}]},
                                {'id': 'icare_27',
                                 'code': 'S3',
                                 'label': 'Explorează activ domenii adiacente sau noi tehnologii',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu iese deloc din domeniul lui de '
                                                           'expertiză.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Explorează lucruri noi doar când au '
                                                           'legătură directă cu un proiect '
                                                           'curent.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Explorează deseori subiecte noi din '
                                                           'curiozitate, fără un scop anume.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Explorează constant domenii și '
                                                           'tehnologii noi și aduce idei utile în '
                                                           'echipă.'}]}]}]},
 {'id': 'results',
  'title': 'Rezultate (Results)',
  'questions': [{'id': 'icare_10_ambitios_pentru_companie',
                 'code': 'ICARE-10',
                 'type': 'statement_score_set',
                 'label': 'Ambițios pentru companie',
                 'required': True,
                 'instructions': 'Gândim la scară mare și suntem ambițioși pentru companie. '
                                 'Promovăm activ asumarea de riscuri, inovația și soluțiile '
                                 'îndrăznețe. Încurajăm schimbarea și vrem să fim în frunte. '
                                 'Urmărim rezultate excelente și durabile. Ne facem timp să '
                                 'evaluăm reușitele și să învățăm din eșecuri.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_28',
                                 'code': 'S1',
                                 'label': 'Propune soluții inovatoare și îndrăznețe',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu propune niciodată soluții noi; '
                                                           'merge doar pe metode deja verificate.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Propune soluții noi doar când cele '
                                                           'vechi au eșuat clar.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Propune  idei noi, dar cu reținere și '
                                                           'fără să le susțină până la capăt.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Propune regulat soluții noi, le '
                                                           'argumentează și e dispus să le '
                                                           'testeze.'}]},
                                {'id': 'icare_29',
                                 'code': 'S2',
                                 'label': 'Promovează asumarea responsabilă a riscului',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Descurajează orice asumare de risc, '
                                                           'oricât de mică.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Tolerează riscurile asumate de alții, '
                                                           'dar nu le susține.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Susține deseori asumarea de riscuri, '
                                                           'dacă există o plasă de siguranță.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Încurajează riscurile calculate și '
                                                           'tratează eșecul ca pe o ocazie de '
                                                           'învățare.'}]},
                                {'id': 'icare_30',
                                 'code': 'S3',
                                 'label': 'Urmărește performanța și învață din eșecuri',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu analizează eșecurile și nu învață '
                                                           'nimic din ele.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Analizează eșecurile doar când îl '
                                                           'obligă procesele companiei.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Face deseori retrospective, mai ales '
                                                           'după eșecurile mari.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Face retrospective regulate, cu lecții '
                                                           'clare și acțiuni de îmbunătățire.'}]}]},
                {'id': 'icare_11_grija_egala_pentru_angajati_si_clienti',
                 'code': 'ICARE-11',
                 'type': 'statement_score_set',
                 'label': 'Grijă egală pentru angajați și clienți',
                 'required': True,
                 'instructions': 'Credem cu tărie că satisfacția angajaților este temelia '
                                 'satisfacției și loialității clienților. Avem standarde înalte, '
                                 'bazate pe o bună înțelegere a mediului și a realității echipelor '
                                 'din teren. Suntem atenți la echilibrul muncă–viață al fiecăruia.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_31',
                                 'code': 'S1',
                                 'label': 'Echilibrează presiunile de performanță cu bunăstarea '
                                          'echipei',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Pune presiune de performanță fără să '
                                                           'țină cont de starea echipei.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Se gândește la starea echipei doar '
                                                           'când apare o problemă gravă (ex: '
                                                           'burnout).'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Echilibrează deseori cerințele de '
                                                           'performanță cu nevoile echipei.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Observă din timp semnele de '
                                                           'suprasolicitare și ajustează sarcinile '
                                                           'înainte să apară probleme.'}]},
                                {'id': 'icare_32',
                                 'code': 'S2',
                                 'label': 'Acordă atenție echilibrului muncă-viață al membrilor '
                                          'echipei',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Ignoră complet semnele de dezechilibru '
                                                           'între muncă și viața personală.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Reacționează doar când dezechilibrul '
                                                           'devine evident (absențe, demisii).'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Vorbește deseori despre importanța '
                                                           'echilibrului, dar fără acțiuni '
                                                           'concrete.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Discută regulat cu oamenii despre '
                                                           'echilibru și ajustează sarcinile când '
                                                           'e nevoie.'}]},
                                {'id': 'icare_33',
                                 'code': 'S3',
                                 'label': 'Construiește standarde înalte bazate pe înțelegerea '
                                          'realității',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Impune standarde rupte de realitatea '
                                                           'echipei.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Stabilește standardele după cum i se '
                                                           'pare lui rezonabil, fără să consulte '
                                                           'echipa.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Consultă deseori echipa înainte să '
                                                           'stabilească standardele.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Stabilește standarde ambițioase și '
                                                           'realiste, bazate pe ce poate echipa cu '
                                                           'adevărat.'}]}]},
                {'id': 'icare_12_agilitate_antreprenoriala',
                 'code': 'ICARE-12',
                 'type': 'statement_score_set',
                 'label': 'Agilitate antreprenorială',
                 'required': True,
                 'instructions': 'Lucrăm ca și cum am fi proprietarii companiei. Pentru că '
                                 'interacționăm cu o rețea extinsă în interiorul și în afara '
                                 'companiei, obținem rezultate mai rapide și mai bune, inclusiv '
                                 'prin testare și învățare rapidă.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_34',
                                 'code': 'S1',
                                 'label': 'Testează și învață rapid (test & learn)',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Planifică la nesfârșit și evită '
                                                           'testele rapide.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Testează doar când are mandat clar și '
                                                           'timp suficient.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Testează deseori soluții noi, dar lent '
                                                           'și nestructurat.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Testează rapid, măsoară rezultatele și '
                                                           'ajustează din mers.'}]},
                                {'id': 'icare_35',
                                 'code': 'S2',
                                 'label': 'Livrează rezultate mai rapid prin simplificare și '
                                          'prioritizare',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Menține procese complicate; viteza nu '
                                                           'e o prioritate.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Simplifică doar când vine presiune '
                                                           'puternică din afară.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Găsește deseori ocazii de simplificare '
                                                           'și le rezolvă.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Simplifică în mod constant procesele '
                                                           'și elimină pașii care nu aduc '
                                                           'valoare.'}]},
                                {'id': 'icare_36',
                                 'code': 'S3',
                                 'label': 'Conectează rețeaua externă la oportunități de business',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu folosește deloc rețeaua externă ca '
                                                           'sursă de oportunități.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Găsește oportunități în rețeaua '
                                                           'externă doar întâmplător.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Caută deseori oportunități în rețeaua '
                                                           'externă, când are un obiectiv clar.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Își construiește deliberat rețeaua și '
                                                           'aduce din ea oportunități concrete de '
                                                           'business.'}]}]}]},
 {'id': 'empowerment',
  'title': 'Responsabilizare (Empowerment)',
  'questions': [{'id': 'icare_13_decizii_cat_mai_aproape_de_teren',
                 'code': 'ICARE-13',
                 'type': 'statement_score_set',
                 'label': 'Decizii cât mai aproape de teren',
                 'required': True,
                 'instructions': 'Responsabilizarea reală a fiecăruia dintre noi și a echipelor '
                                 'noastre face parte din felul în care lucrăm. Acționăm autonom, '
                                 'luăm inițiativa și ne asumăm riscuri inteligente. Luăm deciziile '
                                 'cât mai aproape de teren, ne stabilim obiective într-un cadru '
                                 'clar și ne raportăm rezultatele.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_37',
                                 'code': 'S1',
                                 'label': 'Delegă autoritatea decizională la nivelul potrivit',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Toate deciziile trec prin el, '
                                                           'indiferent cât de mici.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Delegă deciziile minore, dar păstrează '
                                                           'controlul asupra majorității.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Delegă deseori deciziile operaționale, '
                                                           'dar le păstrează pe cele importante.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Lasă deciziile la nivelul cel mai '
                                                           'apropiat de realitate, cu reguli clare '
                                                           'despre cine ce decide.'}]},
                                {'id': 'icare_38',
                                 'code': 'S2',
                                 'label': 'Ia inițiativă și acționează fără să aștepte permisiunea',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Așteaptă aprobare pentru orice '
                                                           'acțiune, chiar și pentru cele '
                                                           'mărunte.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Acționează fără aprobare doar în '
                                                           'urgențe clare.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Ia deseori inițiativa, mai ales când '
                                                           'riscul e mic.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Acționează din proprie inițiativă în '
                                                           'aria lui de responsabilitate și '
                                                           'raportează transparent ce a făcut.'}]},
                                {'id': 'icare_39',
                                 'code': 'S3',
                                 'label': 'Setează obiective clare și raportează transparent '
                                          'rezultatele',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Obiectivele sunt vagi sau lipsesc; '
                                                           'rezultatele nu sunt raportate.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Stabilește obiective și raportează '
                                                           'doar când i se cere.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Stabilește obiective clare, dar '
                                                           'raportează mai ales veștile bune.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Stabilește obiective clare și '
                                                           'raportează regulat, inclusiv când '
                                                           'lucrurile merg prost.'}]}]},
                {'id': 'icare_14_cultiva_inteligenta_colectiva',
                 'code': 'ICARE-14',
                 'type': 'statement_score_set',
                 'label': 'Cultivă inteligența colectivă',
                 'required': True,
                 'instructions': 'Încurajăm diversitatea și cultivăm talentele complementare în '
                                 'interiorul echipelor și între ele. Construim un spațiu sigur în '
                                 'care fiecare poate vorbi deschis și este inclus. Putem fi în '
                                 'dezacord într-un mod pozitiv și constructiv, iar odată decizia '
                                 'luată, o susținem chiar dacă diferă de punctul nostru de vedere. '
                                 'Construim soluții împreună, clarificăm procesele de decizie, '
                                 'cerem sfaturi și refuzăm compromisul facil.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_40',
                                 'code': 'S1',
                                 'label': 'Susține decizia finală chiar dacă diferă de propria '
                                          'opinie',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Sabotează sau subminează deciziile cu '
                                                           'care nu e de acord.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Acceptă deciziile, dar își exprimă '
                                                           'dezacordul pe la colțuri.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Susține deseori deciziile, dar fără '
                                                           'convingere vizibilă.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Susține deschis decizia finală chiar '
                                                           'dacă a avut altă părere, și spune asta '
                                                           'explicit.'}]},
                                {'id': 'icare_41',
                                 'code': 'S2',
                                 'label': 'Caută și oferă sfaturi fără a impune soluții',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Impune soluțiile proprii și nu cere '
                                                           'niciodată sfatul altora.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Cere sfaturi, dar le ignoră în decizia '
                                                           'finală.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Cere deseori sfaturi, dar le folosește '
                                                           'doar când îi convin.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Cere sfaturi din surse diverse și se '
                                                           'vede în decizii că ține cont de '
                                                           'ele.'}]},
                                {'id': 'icare_42',
                                 'code': 'S3',
                                 'label': 'Refuză compromisul sistematic în favoarea soluțiilor '
                                          'mai bune',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Merge mereu pe compromis ca să evite '
                                                           'conflictul.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Acceptă compromisul ca soluție '
                                                           'implicită când apare un dezacord.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Caută deseori soluții mai bune decât '
                                                           'compromisul, dar cedează la presiune.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Insistă pe soluția care îndeplinește '
                                                           'criteriile esențiale, nu pe '
                                                           'compromisul care mulțumește pe toți '
                                                           'câte puțin.'}]}]},
                {'id': 'icare_15_ajuta_echipa',
                 'code': 'ICARE-15',
                 'type': 'statement_score_set',
                 'label': 'Ajută echipa',
                 'required': True,
                 'instructions': 'Ne folosim abilitățile și talentele pentru a contribui la '
                                 'rezultatele echipei. Ca să fim agili și să accelerăm progresul, '
                                 'lăsăm decizia să fie luată la nivelul potrivit. Toți contribuim '
                                 'activ la dinamica și dezvoltarea echipei.',
                 'scale': [{'value': 1, 'label': '1'},
                           {'value': 2, 'label': '2'},
                           {'value': 3, 'label': '3'},
                           {'value': 4, 'label': '4'}],
                 'statements': [{'id': 'icare_43',
                                 'code': 'S1',
                                 'label': 'Alimentează dinamica și energia pozitivă a echipei',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Prezența lui scade energia echipei: '
                                                           'negativism, critică, cinism.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Are o contribuție neutră la energia '
                                                           'echipei.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Contribuie deseori la energia '
                                                           'pozitivă, mai ales în momentele bune.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Aduce constant energie pozitivă; '
                                                           'echipa îl vede ca pe un factor de '
                                                           'motivare.'}]},
                                {'id': 'icare_44',
                                 'code': 'S2',
                                 'label': 'Facilitează deblocarea obstacolelor pentru colegii din '
                                          'echipă',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Nu se implică în problemele altora; '
                                                           'fiecare se descurcă singur.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Ajută la deblocare doar când i se cere '
                                                           'direct.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Ajută deseori când observă că cineva e '
                                                           'blocat.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Urmărește activ progresul echipei și '
                                                           'intervine din proprie inițiativă când '
                                                           'apar blocaje.'}]},
                                {'id': 'icare_45',
                                 'code': 'S3',
                                 'label': 'Dezvoltă competențele echipei prin sharing de '
                                          'cunoaștere',
                                 'scale': [{'value': 1,
                                            'label': '1',
                                            'description': 'Ține cunoștințele pentru el; nu le '
                                                           'împarte cu echipa.'},
                                           {'value': 2,
                                            'label': '2',
                                            'description': 'Împărtășește ce știe doar când i se '
                                                           'cere explicit.'},
                                           {'value': 3,
                                            'label': '3',
                                            'description': 'Face deseori sesiuni informale în care '
                                                           'împărtășește ce știe.'},
                                           {'value': 4,
                                            'label': '4',
                                            'description': 'Creează ocazii regulate de învățare '
                                                           '(sesiuni, documentație, mentorat), ca '
                                                           'expertiza lui să fie accesibilă '
                                                           'tuturor.'}]}]}]}]


def _icare_grade_sections() -> list[dict[str, Any]]:
    return deepcopy(ICARE_SOURCE_SECTIONS)


def _boss_360_schema_from_icare(*, english: bool = False) -> DefinitionSchema:
    schema: DefinitionSchema = {
        "schema_version": "questionnaire.v1",
        "audience": "participant",
        "source": {
            "type": "xlsx",
            "path": "docs/questionnaires/icare_360.xlsx",
            "status": "approved",
            "calculation_sheet": "Agregare 360",
        },
        "response": {"mode": "person_feedback", "target": "person"},
        "instructions": (
            "Răspunde pentru persoana indicată în sarcină. Evaluează comportamentele "
            "iCARE observabile din perspectiva ta: autoevaluare, coleg manager sau raportor direct. "
            "Notele sunt de la 1 la 4, cu descrieri specifice pentru fiecare comportament. "
            "Secțiunea N/A este ignorată în această versiune."
        ),
        "sections": _icare_grade_sections(),
        "scoring": {
            "method": "average_statement_scores_by_section",
            "scale_min": 1,
            "scale_max": 4,
            "score_unit": "percent",
            "primary_result": "lowest_dimension",
            "source_sheet": "Agregare 360",
        },
    }
    if english:
        schema["instructions"] = (
            "Answer for the person named in the assignment. The Romanian iCARE source "
            "wording is the approved current questionnaire."
        )
    return schema


BOSS_360_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.boss_360,
    version=1,
    title="Feedback 360 iCARE pentru manager",
    description=(
        "Feedback comportamental iCARE pentru manager, din perspectivă proprie, "
        "de colegi manageri și de raportori direcți."
    ),
    schema=_boss_360_schema_from_icare(),
)


BOSS_360_EN_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.boss_360_en,
    version=1,
    title="iCARE 360 Feedback for Manager",
    description="Compatibility alias; new projects use the Romanian source-backed iCARE/360 definition.",
    schema=_boss_360_schema_from_icare(english=True),
)


ICARE_LEGACY_ALIAS_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.icare,
    version=1,
    title="Feedback 360 iCARE pentru manager",
    description="Alias vechi pentru chestionarul canonic Feedback 360 iCARE.",
    schema=_boss_360_schema_from_icare(),
)


LEGACY_QUESTIONNAIRE_ALIAS_DEFINITIONS = {
    QuestionnaireKey.icare.value: ICARE_LEGACY_ALIAS_DEFINITION,
    QuestionnaireKey.phase.value: PCM_PHASE_DEFINITION,
    QuestionnaireKey.lencioni_en.value: LENCIONI_EN_DEFINITION,
    QuestionnaireKey.distress_drivers_en.value: DISTRESS_DRIVERS_EN_DEFINITION,
    QuestionnaireKey.boss_360_en.value: BOSS_360_EN_DEFINITION,
}


APPROVED_QUESTIONNAIRE_DEFINITIONS = [
    PCM_BASE_DEFINITION,
    LENCIONI_DEFINITION,
    DISTRESS_DRIVERS_DEFINITION,
    BOSS_360_DEFINITION,
]


def get_approved_questionnaire_definition(
    key: str | QuestionnaireKey,
) -> ApprovedQuestionnaireDefinition:
    key_value = key.value if isinstance(key, QuestionnaireKey) else key
    for definition in APPROVED_QUESTIONNAIRE_DEFINITIONS:
        if definition.key == key_value:
            return definition
    if key_value in LEGACY_QUESTIONNAIRE_ALIAS_DEFINITIONS:
        return LEGACY_QUESTIONNAIRE_ALIAS_DEFINITIONS[key_value]
    msg = f"No approved questionnaire definition for {key_value}"
    raise KeyError(msg)
