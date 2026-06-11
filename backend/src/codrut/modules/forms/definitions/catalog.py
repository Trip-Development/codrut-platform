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


def _boss360_question(number: int, text: str) -> dict[str, Any]:
    return {
        "id": f"boss_360_q{number:02d}",
        "code": f"360-{number}",
        "type": "likert",
        "label": text,
        "required": True,
        "scale": BOSS_360_SCALE,
    }


def _distress_set(number: int, statements: dict[str, tuple[str, str]]) -> dict[str, Any]:
    return {
        "id": f"distress_set_{number:02d}",
        "code": f"SET{number}",
        "type": "statement_score_set",
        "label": f"Set {number}",
        "required": True,
        "instructions": (
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


APPROVED_QUESTIONNAIRE_DEFINITIONS = [
    PCM_BASE_DEFINITION,
    PCM_PHASE_DEFINITION,
    LENCIONI_DEFINITION,
    DISTRESS_DRIVERS_DEFINITION,
    BOSS_360_DEFINITION,
    ICARE_DEFINITION,
]


def get_approved_questionnaire_definition(
    key: str | QuestionnaireKey,
) -> ApprovedQuestionnaireDefinition:
    key_value = key.value if isinstance(key, QuestionnaireKey) else key
    for definition in APPROVED_QUESTIONNAIRE_DEFINITIONS:
        if definition.key == key_value:
            return definition
    msg = f"No approved questionnaire definition for {key_value}"
    raise KeyError(msg)
