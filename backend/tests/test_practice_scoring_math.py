from __future__ import annotations

from datetime import date, datetime, timedelta

from codrut.modules.practice.scoring import (
    ScoreEntry,
    compute_competency_evidence,
    compute_daily_xp,
    compute_streak,
    evidence_ceiling,
    mastery_level,
    quiz_xp,
    roleplay_xp,
    streak_bonus_pct,
)


def test_roleplay_xp_formula():
    assert roleplay_xp(0) == 0
    assert roleplay_xp(-10) == 0
    assert roleplay_xp(1) == 1
    assert roleplay_xp(20) == 1
    assert roleplay_xp(21) == 2
    assert roleplay_xp(40) == 2
    assert roleplay_xp(41) == 3
    assert roleplay_xp(60) == 3
    assert roleplay_xp(61) == 4
    assert roleplay_xp(80) == 4
    assert roleplay_xp(81) == 5
    assert roleplay_xp(100) == 5


def test_quiz_xp_formula():
    assert quiz_xp(0) == 0
    assert quiz_xp(-5) == 0
    assert quiz_xp(4) == 0
    assert quiz_xp(5) == 1
    assert quiz_xp(14) == 1
    assert quiz_xp(15) == 2
    assert quiz_xp(94) == 9
    assert quiz_xp(95) == 10
    assert quiz_xp(100) == 10


def test_streak_bonus_percentages():
    assert streak_bonus_pct(0) == 0
    assert streak_bonus_pct(2) == 0
    assert streak_bonus_pct(3) == 5
    assert streak_bonus_pct(6) == 5
    assert streak_bonus_pct(7) == 10
    assert streak_bonus_pct(13) == 10
    assert streak_bonus_pct(14) == 15
    assert streak_bonus_pct(29) == 15
    assert streak_bonus_pct(30) == 20
    assert streak_bonus_pct(50) == 20


def test_evidence_ceiling():
    # project_days: e.g. 30 -> max(500, round(30 * 100 / 12)) = max(500, 250) = 500
    assert evidence_ceiling(30) == 500
    # project_days: 90 -> round(9000/12) = 750 -> 750
    assert evidence_ceiling(90) == 750


def test_mastery_level():
    assert mastery_level(10) == "CONȘTIENTIZARE"
    assert mastery_level(24.9) == "CONȘTIENTIZARE"
    assert mastery_level(25) == "APLICARE"
    assert mastery_level(49.9) == "APLICARE"
    assert mastery_level(50) == "CONSOLIDARE"
    assert mastery_level(74.9) == "CONSOLIDARE"
    assert mastery_level(75) == "INTEGRARE"
    assert mastery_level(100) == "INTEGRARE"


def test_compute_daily_xp_cap_and_exclusions():
    now = datetime.now()
    # 25 roleplays of 100% -> 25 * 5 = 125 XP, but capped at 100 XP
    entries = [("session", 100, now) for _ in range(25)]
    # Plus test_in and test_out which should be completely excluded
    entries.append(("test_in", 100, now))
    entries.append(("test_out", 100, now))

    daily_xp = compute_daily_xp(entries)
    assert daily_xp == 100


def test_compute_streak():
    today = date(2026, 8, 30)
    # Consecutive days: 30, 29, 28, 27
    dates = [date(2026, 8, 30), date(2026, 8, 29), date(2026, 8, 28), date(2026, 8, 27)]
    assert compute_streak(dates, reference_date=today) == 4

    # Broken streak: 30, 29, 27 (missing 28)
    broken_dates = [date(2026, 8, 30), date(2026, 8, 29), date(2026, 8, 27)]
    assert compute_streak(broken_dates, reference_date=today) == 2

    # Inactivity for 3 days: last active 26 Aug
    inactive_dates = [date(2026, 8, 26), date(2026, 8, 25)]
    assert compute_streak(inactive_dates, reference_date=today) == 0


def test_competency_evidence_pedagogy_rules():
    """Plicul 165: regula veche (≥50% → Aplicare, 2×≥70% în 2 zile → Consolidare, 3×≥70% pe 14
    zile → Integrare) a fost înlocuită de punctajul hotărât de Andrei pe 27 septembrie — regulile
    noi, punct cu punct, stau în `test_punctajul_nou.py`. Aici rămâne ce e valabil la ambele:
    quiz-ul și testele IN/OUT nu contează, iar culorile nivelurilor sunt aceleași."""
    base_date = datetime(2026, 8, 1)

    low_entries = [
        ScoreEntry(score=40, created_at=base_date, source_type="session"),
        ScoreEntry(score=30, created_at=base_date + timedelta(days=1), source_type="session"),
    ]
    ev = compute_competency_evidence(low_entries)
    assert ev.level == "CONȘTIENTIZARE"
    assert ev.color == "#E24B4A"

    # Quiz scores and test in/out MUST NOT contribute to level
    quiz_entries = [
        ScoreEntry(score=100, created_at=base_date, source_type="cunostinte"),
        ScoreEntry(score=100, created_at=base_date + timedelta(days=5), source_type="quiz"),
        ScoreEntry(score=100, created_at=base_date + timedelta(days=20), source_type="test_in"),
    ]
    ev_quiz = compute_competency_evidence(quiz_entries)
    assert ev_quiz.level == "CONȘTIENTIZARE"
    assert ev_quiz.total_roleplays == 0
    assert ev_quiz.points == 0

    # culorile și descrierile, pe nivelurile noi
    aplicare = compute_competency_evidence(
        [ScoreEntry(score=100, created_at=base_date + timedelta(days=d), source_type="session")
         for d in range(2)],
        today=(base_date + timedelta(days=1)).date(),
    )
    assert aplicare.level == "APLICARE" and aplicare.color == "#BA7517"
