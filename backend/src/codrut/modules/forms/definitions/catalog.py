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


BOSS_360_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.boss_360,
    version=1,
    title="Feedback 360 pentru manager",
    description="Feedback comportamental pentru manager, din perspectiva proprie, a colegilor și a raportorilor direcți.",
    schema={
        "schema_version": "questionnaire.v1",
        "response": {"mode": "person_feedback", "target": "person"},
        "instructions": (
            "Răspunde pentru persoana indicată în sarcină. Alege frecvența care "
            "descrie cel mai bine comportamentul observat în activitatea curentă."
        ),
        "sections": [
            {
                "id": "manager_feedback",
                "title": "Comportamente manageriale",
                "questions": [
                    _boss360_question(1, "Setează direcții clare și explică rațiunea deciziilor."),
                    _boss360_question(2, "Ascultă activ și verifică înțelegerea înainte de a decide."),
                    _boss360_question(3, "Oferă feedback concret, respectuos și util."),
                    _boss360_question(4, "Delegă responsabilități cu așteptări și criterii clare."),
                    _boss360_question(5, "Își asumă responsabilitatea pentru propriile decizii."),
                    _boss360_question(6, "Încurajează colaborarea între oameni și echipe."),
                    _boss360_question(7, "Gestionează tensiunile fără a evita conversațiile dificile."),
                    _boss360_question(8, "Recunoaște contribuțiile și susține dezvoltarea oamenilor."),
                ],
            }
        ],
    },
)


ICARE_4_POINT_SCALE = [
    {"value": 1, "label": "Rar"},
    {"value": 2, "label": "Uneori"},
    {"value": 3, "label": "Frecvent"},
    {"value": 4, "label": "Întotdeauna"},
]

ICARE_4_POINT_SCALE_EN = [
    {"value": 1, "label": "Rarely"},
    {"value": 2, "label": "Sometimes"},
    {"value": 3, "label": "Frequently"},
    {"value": 4, "label": "Always"},
]

ICARE_DEFINITION = ApprovedQuestionnaireDefinition(
    key=QuestionnaireKey.icare,
    version=1,
    title="Comportamente de leadership ICARE",
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
                "title": "Inspirație",
                "questions": [
                    {
                        "id": "icare_inspiring_developing_people",
                        "code": "ICARE-1.1",
                        "type": "statement_score_set",
                        "label": "Dezvoltarea oamenilor",
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
                        "label": "Conducere prin exemplu",
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
                        "label": "Crearea unui mediu care stimulează implicarea",
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
                "title": "Construirea încrederii",
                "questions": [
                    {
                        "id": "icare_trust_collaboration",
                        "code": "ICARE-2.1",
                        "type": "statement_score_set",
                        "label": "Promotor al colaborării",
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
                        "label": "Inspirație împărtășită",
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
                        "label": "Ancorare în realitate",
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
                        "label": "Clarificare",
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
                "title": "Conștientizare",
                "questions": [
                    {
                        "id": "icare_awareness_humility",
                        "code": "ICARE-3.1",
                        "type": "statement_score_set",
                        "label": "Modestie",
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
                        "label": "Inteligență emoțională și situațională",
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
                        "label": "Deschidere către lume",
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
                "title": "Rezultate",
                "questions": [
                    {
                        "id": "icare_results_ambitious",
                        "code": "ICARE-4.1",
                        "type": "statement_score_set",
                        "label": "Ambiție asumată pentru companie",
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
                        "label": "Grijă egală pentru angajați și clienți",
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
                        "label": "Agilitate antreprenorială",
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
                "title": "Împuternicire",
                "questions": [
                    {
                        "id": "icare_empowerment_decision_making",
                        "code": "ICARE-5.1",
                        "type": "statement_score_set",
                        "label": "Decizie aproape de teren",
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
                        "label": "Cultivarea inteligenței colective",
                        "required": True,
                        "instructions": "Diversitate, co-construcție, decizii asumate și refuzul compromisului facil.",
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
                        "label": "Sprijinirea echipei",
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


ICARE_SECTION_TITLES_EN = {
    "inspiring": "Inspiring",
    "create_trust": "Building Trust",
    "awareness": "Awareness",
    "results": "Results",
    "empowerment": "Empowerment",
}

ICARE_QUESTION_COPY_EN = {
    "icare_inspiring_developing_people": (
        "Developing people",
        "Continuous development through constructive feedback, encouragement, and follow-up.",
    ),
    "icare_inspiring_leading_by_example": (
        "Leading by example",
        "Alignment between values, commitments, and daily behavior.",
    ),
    "icare_inspiring_engagement_environment": (
        "Creating an engaging environment",
        "A safe, energizing environment oriented around each person's contribution.",
    ),
    "icare_trust_collaboration": (
        "Promoting collaboration",
        "Transparency, collaboration, and prioritizing the shared interest.",
    ),
    "icare_trust_inspired": (
        "Shared inspiration",
        "Meaning, ambition, and commitment built together with the team.",
    ),
    "icare_trust_reality": (
        "Grounding in reality",
        "Active listening, relevant information, and honest realism.",
    ),
    "icare_trust_illuminating": (
        "Clarifying",
        "Strategic clarity in complex and uncertain contexts.",
    ),
    "icare_awareness_humility": (
        "Humility",
        "Feedback, personal limits, and integrating perspectives different from one's own.",
    ),
    "icare_awareness_emotional_intelligence": (
        "Emotional intelligence",
        "Self-regulation, genuine interest in people, and adaptive communication.",
    ),
    "icare_awareness_open_world": (
        "Openness to the world",
        "External benchmarks, change, adjacent domains, and new technologies.",
    ),
    "icare_results_ambitious": (
        "Ambition owned for the company",
        "Innovation, responsible risk-taking, and learning from performance.",
    ),
    "icare_results_caring": (
        "Equal care for employees and customers",
        "Balance between performance, team wellbeing, and realistic standards.",
    ),
    "icare_results_agility": (
        "Entrepreneurial agility",
        "Rapid testing, simplification, and connecting the external network to opportunities.",
    ),
    "icare_empowerment_decision_making": (
        "Decision-making close to the field",
        "Autonomy, initiative, and transparent reporting.",
    ),
    "icare_empowerment_collective_intelligence": (
        "Cultivating collective intelligence",
        "Diversity, co-construction, committed decisions, and refusing easy compromise.",
    ),
    "icare_empowerment_helping_team": (
        "Supporting the team",
        "Contribution to team dynamics, unblocking others, and knowledge sharing.",
    ),
}

ICARE_STATEMENT_LABELS_EN = {
    "icare_01": "Gives constructive feedback",
    "icare_02": "Supports development plans",
    "icare_03": "Invests in their own continuous development",
    "icare_04": "Acts in line with stated values",
    "icare_05": "Honors commitments made to the team",
    "icare_06": "Treats all team members with respect and fairness",
    "icare_07": "Creates psychologically safe space for speaking up",
    "icare_08": "Delegates with meaning, not just tasks",
    "icare_09": "Recognizes individual contribution to team success",
    "icare_10": "Checks shared understanding after discussions",
    "icare_11": "Shares their own context and motivations",
    "icare_12": "Prioritizes the shared interest over personal or local-team interest",
    "icare_13": "Connects the team's work to a broader purpose",
    "icare_14": "Co-creates bold ambitions with the team",
    "icare_15": "Inspires through their own level of commitment",
    "icare_16": "Listens actively before responding or deciding",
    "icare_17": "Proactively shares relevant information",
    "icare_18": "Acknowledges uncomfortable facts honestly",
    "icare_19": "Communicates strategy and direction clearly",
    "icare_20": "Provides clarity in ambiguous situations",
    "icare_21": "Acts with clarity in complex and uncertain environments",
    "icare_22": "Asks for feedback about their own behavior",
    "icare_23": "Knows when to ask for help or admit they do not know",
    "icare_24": "Integrates perspectives different from their own into decisions",
    "icare_25": "Recognizes and manages their own emotions in interactions",
    "icare_26": "Shows genuine interest in people as individuals",
    "icare_27": "Adapts communication to the other person's style and needs",
    "icare_28": "Actively looks for external benchmarks and trends",
    "icare_29": "Embraces and facilitates change",
    "icare_30": "Actively explores adjacent domains or new technologies",
    "icare_31": "Proposes innovative and bold solutions",
    "icare_32": "Promotes responsible risk-taking",
    "icare_33": "Tracks performance and learns from failure",
    "icare_34": "Balances performance pressure with team wellbeing",
    "icare_35": "Pays attention to team members' work-life balance",
    "icare_36": "Builds high standards grounded in reality",
    "icare_37": "Tests and learns quickly",
    "icare_38": "Delivers results faster through simplification and prioritization",
    "icare_39": "Connects the external network to business opportunities",
    "icare_40": "Delegates decision authority to the right level",
    "icare_41": "Takes initiative and acts without waiting for permission",
    "icare_42": "Sets clear objectives and reports results transparently",
    "icare_43": "Supports the final decision even when it differs from their own opinion",
    "icare_44": "Seeks and offers advice without imposing solutions",
    "icare_45": "Rejects systematic compromise in favor of better solutions",
    "icare_46": "Feeds the team's positive dynamics and energy",
    "icare_47": "Helps unblock obstacles for colleagues in the team",
    "icare_48": "Develops team capability through knowledge sharing",
}


def _boss_360_schema_from_icare(*, english: bool = False) -> DefinitionSchema:
    schema = deepcopy(ICARE_DEFINITION.schema)
    schema["audience"] = "participant"
    schema["response"] = {"mode": "person_feedback", "target": "person"}
    schema["instructions"] = (
        "Răspunde pentru persoana indicată în sarcină. Evaluează comportamentele "
        "iCARE observabile din perspectiva ta: autoevaluare, coleg sau raportor direct."
    )
    schema.pop("scoring", None)
    if source := schema.get("source"):
        source["status"] = "approved"

    if not english:
        return schema

    schema["instructions"] = (
        "Answer for the person named in the assignment. Evaluate observable iCARE "
        "behaviors from your perspective: self-review, peer review, or direct-report feedback."
    )
    for section in schema["sections"]:
        section["title"] = ICARE_SECTION_TITLES_EN.get(section["id"], section["title"])
        for question in section["questions"]:
            label, instructions = ICARE_QUESTION_COPY_EN[question["id"]]
            question["label"] = label
            question["instructions"] = instructions
            question["scale"] = ICARE_4_POINT_SCALE_EN
            for statement in question.get("statements", []):
                statement["label"] = ICARE_STATEMENT_LABELS_EN[statement["id"]]
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
    description=(
        "iCARE behavioral feedback for a manager from self, manager peers, "
        "and direct reports."
    ),
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
}


APPROVED_QUESTIONNAIRE_DEFINITIONS = [
    PCM_BASE_DEFINITION,
    PCM_PHASE_DEFINITION,
    LENCIONI_DEFINITION,
    LENCIONI_EN_DEFINITION,
    DISTRESS_DRIVERS_DEFINITION,
    DISTRESS_DRIVERS_EN_DEFINITION,
    BOSS_360_DEFINITION,
    BOSS_360_EN_DEFINITION,
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
