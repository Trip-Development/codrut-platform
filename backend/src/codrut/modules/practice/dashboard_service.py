from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.companies.models import CompanyProject, ParticipantProfile, ProjectMembership
from codrut.modules.identity.models import User
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.models import (
    CompetencyScore,
    InsightMoment,
    ParticipantMemory,
    PracticeCompetency,
    PracticeProgramSettings,
    PracticeSession,
    PracticeTheme,
    SessionSample,
)
from codrut.modules.practice.competency_aliases import CANONICAL_COMPETENCIES, match_comp
from codrut.modules.practice.evaluator import TRAINER_PREFIX
from codrut.modules.practice.scoring import (
    CompetencyEvidence,
    ScoreEntry,
    compute_competency_evidence,
    compute_daily_xp,
    compute_streak,
    evidence_ceiling,
    streak_bonus_pct,
)


class PracticeDashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_participant_dashboard_data(
        self,
        principal: SessionPrincipal,
        project_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Aggregate all participant metrics, competency evidence, moments, and samples for the dashboard."""
        # 1. Resolve participant profile
        #
        # Aceeasi forma ca la plicul 30, pe drumul participantului — plicul 73. Aici ramasese
        # forma veche: dupa cont SAU adresa, fara companie, `scalar_one_or_none`, deci un om cu
        # profil in doua companii dadea MultipleResultsFound si tabloul crapa cu 500.
        #
        # Cand vine un proiect, cautam in compania lui. Cand nu vine, n-avem companie de care sa
        # ne legam: alegem determinist — profilul legat de cont inaintea celui doar cu adresa,
        # iar intre egali cel mai vechi — in loc sa crapam.
        stmt_prof = select(ParticipantProfile).where(
            or_(
                ParticipantProfile.user_id == principal.user_id,
                # plicul 79: dupa adresa, doar profilurile NELEGATE — ca la plicul 75
                and_(
                    ParticipantProfile.user_id.is_(None),
                    ParticipantProfile.email == principal.email,
                ),
            )
        )
        if project_id is not None:
            companie = (await self.session.execute(
                select(CompanyProject.company_id).where(CompanyProject.id == project_id)
            )).scalar_one_or_none()
            if companie is not None:
                stmt_prof = stmt_prof.where(ParticipantProfile.company_id == companie)
        stmt_prof = stmt_prof.order_by(
            ParticipantProfile.user_id.is_(None), ParticipantProfile.created_at
        )
        profile = (await self.session.execute(stmt_prof)).scalars().first()

        # Contul dupa id SAU adresa — plicul 73. N-are companie de care sa se lege; primeste
        # doar ordonare ferma si primul rand: intai contul cu id-ul exact, apoi cel mai vechi.
        stmt_u = (
            select(User)
            .where(
                or_(
                    User.id == principal.user_id,
                    User.email == principal.email,
                )
            )
            .order_by((User.id != principal.user_id), User.created_at)
        )
        user_obj = (await self.session.execute(stmt_u)).scalars().first()

        user_ids = [principal.user_id]
        if profile and profile.user_id and profile.user_id not in user_ids:
            user_ids.append(profile.user_id)
        if user_obj and user_obj.id not in user_ids:
            user_ids.append(user_obj.id)

        # 2. Base XP & Streak
        total_xp = 0
        streak_val = 0
        if profile:
            total_xp = profile.xp or 0
            streak_val = profile.streak or 0
        elif user_obj:
            total_xp = user_obj.xp or 0
            streak_val = user_obj.streak or 0

        # 3. Query all competency scores for this user
        stmt_scores = (
            select(CompetencyScore)
            .where(CompetencyScore.user_id.in_(user_ids))
            .order_by(CompetencyScore.created_at.desc())
        )
        all_scores = list((await self.session.execute(stmt_scores)).scalars().all())

        # Plicul 93: aici era o rezerva „daca omul n-are note, ia ultimele 150 din toata baza",
        # pusa pentru previzualizarea locala. Cine n-are note e fiecare om la prima intrare, deci
        # primul lui tablou era facut din notele altora. Fara note, tabloul ramane gol — ca la
        # momente si mostre, unde aceeasi rezerva a fost scoasa la plicul 29.

        # 4. Activity dates and Streak calculation
        activity_dates = [s.created_at.date() for s in all_scores]
        calculated_streak = compute_streak(activity_dates)
        effective_streak = max(streak_val, calculated_streak)
        bonus_pct = streak_bonus_pct(effective_streak)

        # 5. Today's XP calculation (capped at 100)
        today_date = date.today()
        today_entries = [
            (s.source_type, s.score, s.created_at)
            for s in all_scores
            if s.created_at.date() == today_date
        ]
        xp_today = compute_daily_xp(today_entries)
        if xp_today == 0 and all_scores:
            # For demonstration on archived data, compute XP for the most active recent date
            recent_date = all_scores[0].created_at.date()
            recent_entries = [
                (s.source_type, s.score, s.created_at)
                for s in all_scores
                if s.created_at.date() == recent_date
            ]
            xp_today = compute_daily_xp(recent_entries)

        # 6. Group scores by canonical competency (7 canonical competencies)
        scores_by_comp: dict[str, list[ScoreEntry]] = {c: [] for c in CANONICAL_COMPETENCIES}
        for s in all_scores:
            matched_canonical = match_comp(s.competency_name)
            if not matched_canonical:
                continue
            entry = ScoreEntry(
                score=s.score,
                created_at=s.created_at,
                source_type=s.source_type,
            )
            scores_by_comp[matched_canonical].append(entry)

        competency_results = []
        for name in CANONICAL_COMPETENCIES:
            entries = scores_by_comp[name]
            ev = compute_competency_evidence(entries)
            competency_results.append({
                "name": name,
                "level": ev.level,
                "level_description": ev.level_description,
                "color": ev.color,
                "total_roleplays": ev.total_roleplays,
                "scores_70_count": ev.scores_70_count,
                "days_span_70": ev.days_span_70,
                "distinct_days_70": ev.distinct_days_70,
                "average_score": ev.average_score,
                "why_not_higher": ev.why_not_higher,
            })

        # 7. Insight moments
        #
        # DOUA REGULI, amandoua obligatorii:
        #
        # a) Momentele sunt de DOUA feluri. Cele cu prefixul `[TRAINER]` sunt notele
        #    pentru trainer — numele competentei, scorul, analiza — scrise la persoana
        #    a III-a. Ele NU ajung niciodata pe ecranul participantului. Cele fara
        #    prefix sunt ale lui, scrise pentru el, la persoana a II-a.
        #
        # b) NU exista rezerva „daca omul n-are momente, arata-le pe ale altcuiva".
        #    Pana la plicul 29 exista, ca sa se vada ceva pe datele de arhiva; cu date
        #    adevarate si mai multi participanti, ar fi insemnat ca unul citeste
        #    reflectiile altuia. Ecranul gol e raspunsul corect.
        stmt_moments = (
            select(InsightMoment)
            .where(
                InsightMoment.user_id.in_(user_ids),
                not_(InsightMoment.summary.startswith(TRAINER_PREFIX)),
            )
            .order_by(InsightMoment.created_at.desc())
            .limit(10)
        )
        moments = list((await self.session.execute(stmt_moments)).scalars().all())

        # 8. Session samples (real_weak / real_improved)
        #
        # Fara rezerva de la altcineva, din acelasi motiv ca la momente. Pana la plicul 94
        # intrau aici si mostrele fara stapan (`user_id` gol) — replici adevarate ale unui om,
        # pe tabloul oricui. Pe proba erau zero; le poate scrie doar importul arhivei.
        stmt_samples = (
            select(SessionSample)
            .where(SessionSample.user_id.in_(user_ids))
            .order_by(SessionSample.created_at.desc())
            .limit(10)
        )
        samples = list((await self.session.execute(stmt_samples)).scalars().all())

        return {
            "participant_name": profile.full_name if profile else (principal.email.split("@")[0]),
            "xp_today": xp_today,
            "xp_daily_cap": 100,
            "xp_total": total_xp or sum(e.score for e in all_scores),
            "streak_days": effective_streak,
            "streak_bonus_pct": bonus_pct,
            "evidence_ceiling": evidence_ceiling(30),
            "competencies": competency_results,
            "insight_moments": [
                {
                    "id": str(m.id),
                    "summary": m.summary,
                    "competency_name": m.competency_name,
                    "created_at": m.created_at.isoformat(),
                }
                for m in moments
            ],
            "session_samples": [
                {
                    "id": str(s.id),
                    "real_weak": s.real_weak,
                    "real_improved": s.real_improved,
                    "invented_weak": s.invented_weak,
                    "invented_improved": s.invented_improved,
                    "created_at": s.created_at.isoformat(),
                }
                for s in samples
                if s.real_weak or s.real_improved or s.invented_weak or s.invented_improved
            ],
        }
