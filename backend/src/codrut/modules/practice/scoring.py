from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence

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

    0 dacă <= 0; altfel min(10, round(percent / 10)).
    """
    if percent <= 0:
        return 0
    calculated = round(percent / 10.0)
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
    """Calculează numărul de zile consecutive cu activitate până la reference_date (implicit azi)."""
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


def compute_competency_evidence(entries: Sequence[ScoreEntry]) -> CompetencyEvidence:
    """Calculează nivelul de competență conform pedagogiei:

    INTEGRARE       >=3 role-play-uri cu scor >=70%, întinse pe >=14 zile (între primul și ultimul >=70%)
    CONSOLIDARE     >=2 role-play-uri cu scor >=70%, în >=2 zile diferite
    APLICARE        >=1 role-play cu scor >=50%
    CONȘTIENTIZARE  competența apare în sesiuni, dar fără dovezile de sus

    Quiz-ul (source_type='cunostinte') NU contribuie la nivel. Test IN/OUT idem.
    """
    valid_roleplays = [
        e for e in entries
        if e.source_type.lower() not in ("cunostinte", "quiz", "knowledge", "test_in", "test_out", "test-in", "test-out")
    ]

    if not valid_roleplays:
        return CompetencyEvidence(
            level="CONȘTIENTIZARE",
            level_description=COMPETENCY_LEVEL_DESCRIPTIONS["CONȘTIENTIZARE"],
            color=COMPETENCY_LEVEL_COLORS["CONȘTIENTIZARE"],
            total_roleplays=0,
            scores_70_count=0,
            days_span_70=0,
            distinct_days_70=0,
            average_score=0.0,
            why_not_higher="Exersează primul role-play pentru a debloca nivelul Aplicare (scor ≥50%).",
        )

    avg_score = round(sum(e.score for e in valid_roleplays) / len(valid_roleplays), 1)

    scores_70 = [e for e in valid_roleplays if e.score >= 70]
    scores_50 = [e for e in valid_roleplays if e.score >= 50]

    distinct_days_70 = len(set(e.created_at.date() for e in scores_70))
    days_span_70 = 0
    if len(scores_70) >= 2:
        sorted_dates_70 = sorted(e.created_at for e in scores_70)
        days_span_70 = (sorted_dates_70[-1].date() - sorted_dates_70[0].date()).days

    # Verificare condiții în ordine descrescătoare de mastery
    if len(scores_70) >= 3 and days_span_70 >= 14:
        level = "INTEGRARE"
        why_not_higher = "Nivel maxim atins: reflex automat integrat în practică și testat în timp."
    elif len(scores_70) >= 2 and distinct_days_70 >= 2:
        level = "CONSOLIDARE"
        if len(scores_70) < 3:
            why_not_higher = "Pentru Integrare: ai nevoie de cel puțin 3 simulări cu scor ≥70% întinse pe minim 14 zile."
        else:
            days_needed = 14 - days_span_70
            why_not_higher = f"Pentru Integrare: ai cele 3 scoruri ≥70%, dar intervalul actual este de {days_span_70} zile (necesar ≥14 zile, mai sunt ~{days_needed} zile de consistență)."
    elif len(scores_50) >= 1:
        level = "APLICARE"
        why_not_higher = "Pentru Consolidare: ai nevoie de minim 2 simulări cu scor ≥70% în cel puțin 2 zile diferite."
    else:
        level = "CONȘTIENTIZARE"
        why_not_higher = "Pentru Aplicare: ai nevoie de cel puțin o simulare cu scor ≥50%."

    return CompetencyEvidence(
        level=level,
        level_description=COMPETENCY_LEVEL_DESCRIPTIONS[level],
        color=COMPETENCY_LEVEL_COLORS[level],
        total_roleplays=len(valid_roleplays),
        scores_70_count=len(scores_70),
        days_span_70=days_span_70,
        distinct_days_70=distinct_days_70,
        average_score=avg_score,
        why_not_higher=why_not_higher,
    )
