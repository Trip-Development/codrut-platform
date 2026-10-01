from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

COMPETENCY_LEVEL_DESCRIPTIONS = {
    "INTEGRARE": "E reflex automat — apare și sub stres, fără efort conștient.",
    "CONSOLIDARE": "Îl aplici consistent în majoritatea situațiilor.",
    "APLICARE": "Îl aplici uneori; sub presiune încă mai scapi.",
    "CONȘTIENTIZARE": "Cunoști principiul, dar nu-l aplici încă consistent.",
}

COMPETENCY_LEVEL_COLORS = {
    "INTEGRARE": "#639922",
    "CONSOLIDARE": "#1A4A7A",
    "APLICARE": "#BA7517",
    "CONȘTIENTIZARE": "#E24B4A",
}


def roleplay_xp(score: int | float) -> int:
    """Scor role-play -> puncte XP.

    0 dacă <= 0; altfel min(5, ceil(scor / 20)), minim 1.
    """
    if score <= 0:
        return 0
    calculated = math.ceil(score / 20.0)
    return min(5, max(1, calculated))


def quiz_xp(percent: int | float) -> int:
    """Procent quiz -> puncte XP.

    0 dacă <= 0; altfel cel mult 10, cu jumătatea rotunjită ÎN SUS: 8,5 -> 9.

    Hotărârea lui Andrei, 20 septembrie (plicul 123). Până atunci se folosea `round()`, care în
    Python rotunjește BANCAR: `round(8.5)` dă 8, dar `round(1.5)` dă 2. Deci nu era nici măcar
    „în jos" — era inconsecvent, iar doi oameni cu jumătăți diferite primeau tratamente diferite,
    fără nicio regulă pe care s-o poată înțelege.

    E atingibil, nu teoretic: un scor de 8,5 la o competență devine 85%, iar acolo cele două
    rotunjiri diferă cu un punct.
    """
    if percent <= 0:
        return 0
    calculated = int(Decimal(str(percent / 10.0)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return min(10, max(0, calculated))


def streak_bonus_pct(streak_days: int) -> int:
    """Bonus procentual streak zile consecutive.

    3-6 zile: +5%
    7-13 zile: +10%
    14-29 zile: +15%
    30+ zile: +20%
    < 3 zile: 0%
    """
    if streak_days >= 30:
        return 20
    if streak_days >= 14:
        return 15
    if streak_days >= 7:
        return 10
    if streak_days >= 3:
        return 5
    return 0


def evidence_ceiling(project_days: int) -> int:
    """Pragul de dovezi raportat la durata proiectului.

    max(500, round(zile_proiect * 100 / 12))
    """
    return max(500, round((project_days * 100) / 12.0))


def mastery_level(score: int | float) -> str:
    """Nivel Bloom bazat pe scor procentual 0-100.

    < 25: Conștientizare
    25-50: Aplicare
    50-75: Consolidare
    >= 75: Integrare
    """
    if score < 25:
        return "CONȘTIENTIZARE"
    if score < 50:
        return "APLICARE"
    if score < 75:
        return "CONSOLIDARE"
    return "INTEGRARE"


@dataclass(frozen=True)
class ScoreEntry:
    score: int
    created_at: datetime
    source_type: str = "session"  # "session", "roleplay", "cunostinte", "test_in", "test_out"
    # tipul interlocutorului din ședință („jos", „lateral", „sus", „client"), dedus în
    # `interlocutor.sedintele_notelor` — plicul 165. Gol pentru notele fără ședință (arhiva).
    interlocutor: str | None = None


@dataclass(frozen=True)
class CompetencyEvidence:
    level: str
    level_description: str
    color: str
    total_roleplays: int
    scores_70_count: int
    days_span_70: int
    distinct_days_70: int
    average_score: float
    why_not_higher: str
    # punctajul nou — plicul 165
    points: int = 0
    points_today: int = 0
    interlocutor_types: int = 0
    # plicul 177: cea mai mare notă role-play de azi (ora României) — aceeași care dă punctele
    best_score_today: int | None = None


def compute_daily_xp(entries: Sequence[tuple[str, int | float, datetime]]) -> int:
    """Calculează XP pe o zi, plafonat la 100 XP/zi.

    Testele IN și OUT sunt excluse complet.
    Fiecare intrare este (source_type, score/percent, datetime).
    """
    total = 0
    for source_type, score_val, _ in entries:
        norm_source = source_type.lower()
        if norm_source in ("test_in", "test_out", "test-in", "test-out"):
            continue
        if norm_source in ("cunostinte", "quiz", "knowledge"):
            total += quiz_xp(score_val)
        else:
            total += roleplay_xp(score_val)

    return min(100, total)


def compute_streak(activity_dates: Sequence[date], reference_date: date | None = None) -> int:
    """Calculează numărul de zile consecutive cu activitate până la reference_date (implicit azi)."""  # noqa: E501
    if not activity_dates:
        return 0

    ref = reference_date or date.today()
    sorted_unique_dates = sorted(set(activity_dates), reverse=True)

    # Dacă ultima activitate nu este azi sau ieri, streak-ul este întrerupt
    if sorted_unique_dates[0] < ref and (ref - sorted_unique_dates[0]).days > 1:
        return 0

    # Punct de pornire
    current_check = sorted_unique_dates[0]
    streak = 1

    for d in sorted_unique_dates[1:]:
        if (current_check - d).days == 1:
            streak += 1
            current_check = d
        else:
            break

    return streak


# ---- Punctajul nou — plicul 165, hotărârea lui Andrei din 27 septembrie ----
#
# Nota din conversație („[🏆 Scor: 8/10]") rămâne cum e. Punctele și nivelurile le calculează
# aplicația, din notele pe competență (`CompetencyScore`, 0–100, date la închidere), fără niciun
# apel la vreun model:
#   1. contează numai role-play-urile;
#   2. o zi (în ora României) = cel mult o notă numărată pe competență: cea mai mare;
#   3. nota numărată sub 60 → 0 puncte; de la 60: nota − 50;
#   4. +25 în prima zi în care competența trece de 60 cu un tip nou de interlocutor, o dată pe tip;
#   5. punctele nu scad; fără plafon de sus.
ZONA_ROMANIEI = ZoneInfo("Europe/Bucharest")
NOTA_MINIMA = 60
BONUS_TIP_NOU = 25
PRAG_APLICARE = 100
PRAG_CONSOLIDARE = 400
PRAG_INTEGRARE = 1000
TIPURI_CONSOLIDARE = 2
TIPURI_INTEGRARE = 3
ZILE_INTEGRARE = 56
_NU_ROLEPLAY = ("cunostinte", "quiz", "knowledge", "test_in", "test_out", "test-in", "test-out")


def ziua_in_romania(moment: datetime) -> date:
    """Ziua calendaristică a unei note, în ora României (o notă fără fus e socotită UTC)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(ZONA_ROMANIEI).date()


def puncte_pentru_nota(nota: int | float) -> int:
    """Nota numărată a unei zile → puncte: sub 60 nimic, altfel nota − 50 (60→10 … 100→50)."""
    return 0 if nota < NOTA_MINIMA else int(nota) - 50


def _in_lipsa(parti: list[str]) -> str:
    if len(parti) <= 1:
        return "".join(parti)
    return ", ".join(parti[:-1]) + " și " + parti[-1]


def compute_competency_evidence(
    entries: Sequence[ScoreEntry],
    today: date | None = None,
) -> CompetencyEvidence:
    """Nivelul unei competențe, pe puncte — plicul 165.

    CONȘTIENTIZARE  sub 100 de puncte
    APLICARE        ≥ 100 puncte
    CONSOLIDARE     ≥ 400 puncte și ≥ 2 tipuri de interlocutor cu notă ≥ 60
    INTEGRARE       ≥ 1.000 puncte, ≥ 3 tipuri și ≥ 56 de zile de la prima notă a competenței

    Quiz-ul și testele IN/OUT nu contribuie. `today` e ziua în ora României (implicit azi).
    """
    azi = today or datetime.now(ZONA_ROMANIEI).date()
    valid_roleplays = [e for e in entries if e.source_type.lower() not in _NU_ROLEPLAY]

    # 2 · pe zi, cea mai mare notă; 4 · tipurile noi reușite în ziua aceea
    pe_zi: dict[date, list[ScoreEntry]] = {}
    for e in valid_roleplays:
        pe_zi.setdefault(ziua_in_romania(e.created_at), []).append(e)
    puncte = 0
    puncte_azi = 0
    nota_azi: int | None = None
    tipuri_reusite: set[str] = set()
    for zi in sorted(pe_zi):
        ale_zilei = pe_zi[zi]
        castig = puncte_pentru_nota(max(e.score for e in ale_zilei))
        for tip in sorted({e.interlocutor for e in ale_zilei
                           if e.interlocutor and e.score >= NOTA_MINIMA}):
            if tip not in tipuri_reusite:
                tipuri_reusite.add(tip)
                castig += BONUS_TIP_NOU
        puncte += castig
        if zi == azi:
            puncte_azi = castig
            nota_azi = int(max(e.score for e in ale_zilei))

    tipuri = len(tipuri_reusite)
    prima_zi = min(pe_zi) if pe_zi else None
    zile_de_la_prima = (azi - prima_zi).days if prima_zi else 0

    integrare = (
        puncte >= PRAG_INTEGRARE
        and tipuri >= TIPURI_INTEGRARE
        and zile_de_la_prima >= ZILE_INTEGRARE
    )
    if integrare:
        level = "INTEGRARE"
        why_not_higher = (
            "Nivel maxim atins. Punctele cresc în continuare cu fiecare simulare reușită."
        )
    elif puncte >= PRAG_CONSOLIDARE and tipuri >= TIPURI_CONSOLIDARE:
        level = "CONSOLIDARE"
        parti = []
        if puncte < PRAG_INTEGRARE:
            parti.append(f"{PRAG_INTEGRARE - puncte} puncte")
        if tipuri < TIPURI_INTEGRARE:
            parti.append(f"reușite cu cel puțin 3 tipuri de interlocutor (ai {tipuri})")
        if zile_de_la_prima < ZILE_INTEGRARE:
            ramase = ZILE_INTEGRARE - zile_de_la_prima
            parti.append(f"8 săptămâni de la prima simulare (mai sunt {ramase} zile)")
        why_not_higher = f"Pentru Integrare: îți mai trebuie {_in_lipsa(parti)}."
    elif puncte >= PRAG_APLICARE:
        level = "APLICARE"
        parti = []
        if puncte < PRAG_CONSOLIDARE:
            parti.append(f"{PRAG_CONSOLIDARE - puncte} puncte")
        if tipuri < TIPURI_CONSOLIDARE:
            parti.append(f"reușite cu cel puțin 2 tipuri de interlocutor (ai {tipuri})")
        why_not_higher = f"Pentru Consolidare: îți mai trebuie {_in_lipsa(parti)}."
    else:
        level = "CONȘTIENTIZARE"
        why_not_higher = (
            f"Pentru Aplicare: îți mai trebuie {PRAG_APLICARE - puncte} puncte. Primești puncte la "
            "simulările în care nota ta la această competență e de cel puțin 60%."
        )

    # câmpurile de dinainte rămân în răspuns, socotite ca înainte (nu se mai afișează)
    scores_70 = [e for e in valid_roleplays if e.score >= 70]
    days_span_70 = 0
    if len(scores_70) >= 2:
        sorted_dates_70 = sorted(e.created_at for e in scores_70)
        days_span_70 = (sorted_dates_70[-1].date() - sorted_dates_70[0].date()).days
    avg_score = (
        round(sum(e.score for e in valid_roleplays) / len(valid_roleplays), 1)
        if valid_roleplays else 0.0
    )
    return CompetencyEvidence(
        level=level,
        level_description=COMPETENCY_LEVEL_DESCRIPTIONS[level],
        color=COMPETENCY_LEVEL_COLORS[level],
        total_roleplays=len(valid_roleplays),
        scores_70_count=len(scores_70),
        days_span_70=days_span_70,
        distinct_days_70=len({e.created_at.date() for e in scores_70}),
        average_score=avg_score,
        why_not_higher=why_not_higher,
        points=puncte,
        points_today=puncte_azi,
        interlocutor_types=tipuri,
        best_score_today=nota_azi,
    )
