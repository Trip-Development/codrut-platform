from __future__ import annotations

from datetime import date, datetime, timedelta

from codrut.modules.practice.scoring import (
    CompetencyEvidence,
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
    base_date = datetime(2026, 8, 1)

    # 1. No entries or low scores (<50) -> CONȘTIENTIZARE
    low_entries = [
        ScoreEntry(score=40, created_at=base_date, source_type="session"),
        ScoreEntry(score=30, created_at=base_date + timedelta(days=1), source_type="session"),
    ]
    ev = compute_competency_evidence(low_entries)
    assert ev.level == "CONȘTIENTIZARE"
    assert ev.color == "#E24B4A"

    # 2. Quiz scores and test in/out MUST NOT contribute to level
    quiz_entries = [
        ScoreEntry(score=100, created_at=base_date, source_type="cunostinte"),
        ScoreEntry(score=100, created_at=base_date + timedelta(days=5), source_type="quiz"),
        ScoreEntry(score=100, created_at=base_date + timedelta(days=20), source_type="test_in"),
    ]
    ev_quiz = compute_competency_evidence(quiz_entries)
    assert ev_quiz.level == "CONȘTIENTIZARE"
    assert ev_quiz.total_roleplays == 0

    # 3. >= 1 role-play with >= 50% -> APLICARE
    aplicare_entries = [
        ScoreEntry(score=55, created_at=base_date, source_type="session"),
    ]
    ev_app = compute_competency_evidence(aplicare_entries)
    assert ev_app.level == "APLICARE"
    assert ev_app.color == "#BA7517"

    # 4. 10 role-plays in a SINGLE DAY with score >= 70% -> only APLICARE (does not reach Consolidare because distinct days < 2)
    single_day_entries = [
        ScoreEntry(score=85, created_at=base_date + timedelta(hours=i), source_type="session")
        for i in range(10)
    ]
    ev_single_day = compute_competency_evidence(single_day_entries)
    assert ev_single_day.level == "APLICARE"

    # 5. >= 2 role-plays with >= 70% in >= 2 different days -> CONSOLIDARE
    consolidare_entries = [
        ScoreEntry(score=75, created_at=base_date, source_type="session"),
        ScoreEntry(score=80, created_at=base_date + timedelta(days=3), source_type="session"),
    ]
    ev_cons = compute_competency_evidence(consolidare_entries)
    assert ev_cons.level == "CONSOLIDARE"
    assert ev_cons.color == "#1A4A7A"

    # 6. 3 role-plays with >= 70% in only 5 days span (< 14 days) -> CONSOLIDARE (not Integrare yet)
    fast_3_entries = [
        ScoreEntry(score=75, created_at=base_date, source_type="session"),
        ScoreEntry(score=80, created_at=base_date + timedelta(days=2), source_type="session"),
        ScoreEntry(score=90, created_at=base_date + timedelta(days=5), source_type="session"),
    ]
    ev_fast = compute_competency_evidence(fast_3_entries)
    assert ev_fast.level == "CONSOLIDARE"

    # 7. >= 3 role-plays with >= 70% spread across >= 14 days -> INTEGRARE
    integrare_entries = [
        ScoreEntry(score=75, created_at=base_date, source_type="session"),
        ScoreEntry(score=80, created_at=base_date + timedelta(days=7), source_type="session"),
        ScoreEntry(score=90, created_at=base_date + timedelta(days=15), source_type="session"),
    ]
    ev_int = compute_competency_evidence(integrare_entries)
    assert ev_int.level == "INTEGRARE"
    assert ev_int.color == "#639922"
    assert "E reflex automat" in ev_int.level_description
