"""Team competency evolution for a training project - the trainer's tab.

Ported from ``app/admin/projects/[projectId]/page.tsx`` (411 lines) and
``ProjectCharts.tsx`` in the ``codrut-app`` repository: the same blocks, in the
same order, with the same labels.

Test IN and Test OUT arrive in plic 30. Their columns are returned here as
``None`` on purpose rather than omitted, so the screen can keep their place with
the line that says they fill in after the entry test - the plic asks for them to
stay, not to be removed.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select

from codrut.core.errors import DomainError
from codrut.modules.companies.models import (
    CompanyProject,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User
from codrut.modules.practice.competency_aliases import match_comp
from codrut.modules.practice.models import (
    CompetencyScore,
    PracticeSession,
    PracticeProgramSettings,
    SessionState,
)
from codrut.modules.practice.scoring import (
    COMPETENCY_LEVEL_COLORS,
    COMPETENCY_LEVEL_DESCRIPTIONS,
    ScoreEntry,
    compute_competency_evidence,
)
from codrut.modules.practice.setup_service import competency_names_for_project

# Rândul care ține locul coloanelor de test până la plicul 30.
TEST_PENDING_NOTE = "se completează după testul de intrare"


class PracticeEvolutionService:
    def __init__(self, session) -> None:
        self.session = session

    async def project_evolution(self, project_id: uuid.UUID) -> dict:
        project = (await self.session.execute(
            select(CompanyProject).where(CompanyProject.id == project_id)
        )).scalar_one_or_none()
        if project is None:
            raise DomainError(f"Proiectul {project_id} nu a fost găsit.", code="project_not_found")

        competente = await competency_names_for_project(self.session, project_id)

        # Oamenii din proiect, cu contul lor când există.
        randuri = (await self.session.execute(
            select(ParticipantProfile, ProjectMembership)
            .join(
                ProjectMembership,
                ProjectMembership.participant_profile_id == ParticipantProfile.id,
            )
            .where(ProjectMembership.project_id == project_id)
        )).all()

        emailuri = [p.email for p, _ in randuri if p.email]
        utilizatori = (await self.session.execute(
            select(User).where(User.email.in_(emailuri))
        )).scalars().all() if emailuri else []
        user_dupa_email = {u.email.lower(): u for u in utilizatori}

        user_ids = []
        for profil, _ in randuri:
            u = profil.user_id or (
                user_dupa_email[profil.email.lower()].id
                if profil.email and profil.email.lower() in user_dupa_email
                else None
            )
            if u:
                user_ids.append(u)

        scoruri = (await self.session.execute(
            select(CompetencyScore).where(CompetencyScore.user_id.in_(user_ids))
        )).scalars().all() if user_ids else []

        setari = (await self.session.execute(
            select(PracticeProgramSettings)
            .where(PracticeProgramSettings.project_id == project_id)
        )).scalar_one_or_none()
        sesiuni = []
        if setari is not None:
            sesiuni = (await self.session.execute(
                select(PracticeSession)
                .where(PracticeSession.program_settings_id == setari.id)
            )).scalars().all()

        # --- contoarele de sus (ca la rd. 224 din aplicatia veche) ---
        profile_cu_sesiune = {s.participant_profile_id for s in sesiuni}
        activi = len([p for p, _ in randuri if p.id in profile_cu_sesiune])

        # --- evolutia per competenta (rd. 253-254) ---
        pe_competenta: dict[str, list[CompetencyScore]] = defaultdict(list)
        for s in scoruri:
            canonic = match_comp(s.competency_name)
            if canonic:
                pe_competenta[canonic].append(s)

        nume_afisate = competente or sorted(pe_competenta)
        evolutie = []
        for nume in nume_afisate:
            canonic = match_comp(nume) or nume
            lst = pe_competenta.get(canonic, [])
            intrari = [
                ScoreEntry(score=s.score, created_at=s.created_at, source_type=s.source_type)
                for s in lst
            ]
            dovada = compute_competency_evidence(intrari)
            media = round(sum(s.score for s in lst) / len(lst), 1) if lst else None
            evolutie.append({
                "name": nume,
                "test_in_average": None,          # plicul 30
                "current_average": media,         # din sesiunile cu Cody
                "test_out_average": None,         # plicul 30
                "growth": None,                   # diferenta fata de Test IN, plicul 30
                "level": dovada.level,
                "level_description": COMPETENCY_LEVEL_DESCRIPTIONS.get(dovada.level, ""),
                "color": COMPETENCY_LEVEL_COLORS.get(dovada.level, "#888888"),
                "scores_count": len(lst),
            })

        # --- media echipei, saptamana de saptamana (rd. 323-326) ---
        pe_saptamana: dict[date, list[int]] = defaultdict(list)
        for s in scoruri:
            zi = s.created_at.date()
            inceput = zi - timedelta(days=zi.weekday())
            pe_saptamana[inceput].append(s.score)
        serie = [
            {
                "week_start": saptamana.isoformat(),
                "average": round(sum(v) / len(v), 1),
                "scores_count": len(v),
            }
            for saptamana, v in sorted(pe_saptamana.items())
        ]

        # --- tabelul cu oamenii (rd. 340) ---
        scoruri_pe_user: dict[uuid.UUID, list[CompetencyScore]] = defaultdict(list)
        for s in scoruri:
            scoruri_pe_user[s.user_id].append(s)

        oameni = []
        for profil, apartenenta in randuri:
            u = profil.user_id or (
                user_dupa_email[profil.email.lower()].id
                if profil.email and profil.email.lower() in user_dupa_email
                else None
            )
            ale_lui = scoruri_pe_user.get(u, []) if u else []
            sesiuni_lui = [s for s in sesiuni if s.participant_profile_id == profil.id]
            oameni.append({
                "participant_profile_id": profil.id,
                "user_id": u,
                "full_name": profil.full_name,
                "email": profil.email,
                "active": bool(apartenenta.active),
                "test_in_score": None,            # plicul 30
                "test_out_score": None,           # plicul 30
                "current_average": (
                    round(sum(s.score for s in ale_lui) / len(ale_lui), 1) if ale_lui else None
                ),
                "sessions_count": len(sesiuni_lui),
                "closed_sessions_count": len(
                    [s for s in sesiuni_lui if s.state == SessionState.closed]
                ),
                "scores_count": len(ale_lui),
            })
        oameni.sort(key=lambda o: (o["full_name"] or "").lower())

        return {
            "project_id": project_id,
            "project_name": project.name,
            "project_type": project.project_type,
            "participants_total": len(randuri),
            "participants_active": activi,
            "test_in_completed": None,            # plicul 30
            "test_out_enabled": False,            # butonul „Activează Test OUT"
            "test_pending_note": TEST_PENDING_NOTE,
            "competencies": evolutie,
            "weekly_average": serie,
            "participants": oameni,
        }
