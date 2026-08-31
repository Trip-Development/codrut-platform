"""The training room - everything the trainer's project screen shows.

Ported from ``app/admin/projects/[projectId]/page.tsx`` (411 lines) in the
``codrut-app`` repository, read whole before writing this. The sections, their
order and their texts are the old application's; only the clothing is new.

How the old app tells the three kinds of score apart, kept exactly:

    Test IN     conversation_id == "TEST_IN_01"
    Test OUT    conversation_id == "TEST_OUT_01"
    quiz        source_type == "cunostinte"
    practice    everything else

And how it counts people:

    activ       activity in the last 7 days
    recurent    3 or more distinct sessions
    inactiv     total - activ
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from codrut.core.errors import DomainError
from codrut.modules.companies.models import (
    CompanyProject,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User
from codrut.modules.practice.models import (
    CompetencyScore,
    PracticeProgramSettings,
    PracticeSession,
    PracticeTheme,
    SessionState,
)
from codrut.modules.practice.setup_service import competency_names_for_project

TEST_IN_ID = "TEST_IN_01"
TEST_OUT_ID = "TEST_OUT_01"
QUIZ_SOURCE = "cunostinte"

ZILE_ACTIV = 7
SESIUNI_RECURENT = 3


def _medie(valori: list[int]) -> int:
    return round(sum(valori) / len(valori)) if valori else 0


class PracticeRoomService:
    """Camera de training: ce vede trainerul pe ecranul proiectului."""

    def __init__(self, session) -> None:
        self.session = session

    async def project_room(self, project_id: uuid.UUID) -> dict:
        project = (await self.session.execute(
            select(CompanyProject).where(CompanyProject.id == project_id)
        )).scalar_one_or_none()
        if project is None:
            raise DomainError(f"Proiectul {project_id} nu a fost găsit.", code="project_not_found")

        competente = await competency_names_for_project(self.session, project_id)

        setari = (await self.session.execute(
            select(PracticeProgramSettings)
            .where(PracticeProgramSettings.project_id == project_id)
        )).scalar_one_or_none()

        tema_nume = None
        if setari is not None:
            tema = (await self.session.execute(
                select(PracticeTheme).where(PracticeTheme.id == setari.theme_id)
            )).scalar_one_or_none()
            tema_nume = tema.name if tema else None

        # ---- oamenii din proiect, cu contul lor cand exista ----
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

        def contul(profil: ParticipantProfile) -> uuid.UUID | None:
            if profil.user_id:
                return profil.user_id
            if profil.email and profil.email.lower() in user_dupa_email:
                return user_dupa_email[profil.email.lower()].id
            return None

        user_ids = [u for u in (contul(p) for p, _ in randuri) if u]

        scoruri = (await self.session.execute(
            select(CompetencyScore).where(CompetencyScore.project_id == project_id)
        )).scalars().all()

        sesiuni = []
        if setari is not None:
            sesiuni = (await self.session.execute(
                select(PracticeSession)
                .where(PracticeSession.program_settings_id == setari.id)
            )).scalars().all()

        # ---- cele patru feluri de scor, ca in aplicatia veche ----
        test_in = [s for s in scoruri if s.conversation_id == TEST_IN_ID]
        test_out = [s for s in scoruri if s.conversation_id == TEST_OUT_ID]
        de_sesiune = [
            s for s in scoruri
            if s.conversation_id not in (TEST_IN_ID, TEST_OUT_ID)
        ]
        quiz = [s for s in scoruri if s.source_type == QUIZ_SOURCE]
        practica = [
            s for s in de_sesiune if s.source_type != QUIZ_SOURCE
        ]

        acum = datetime.now(UTC)
        acum_o_saptamana = acum - timedelta(days=ZILE_ACTIV)

        ultima_activitate: dict[uuid.UUID, datetime] = {}
        sesiuni_pe_om: dict[uuid.UUID, set[str]] = defaultdict(set)
        for s in de_sesiune:
            if s.user_id not in ultima_activitate or s.created_at > ultima_activitate[s.user_id]:
                ultima_activitate[s.user_id] = s.created_at
            sesiuni_pe_om[s.user_id].add(s.conversation_id)

        cu_test_in = {s.user_id for s in test_in}
        cu_test_out = {s.user_id for s in test_out}

        total = len(randuri)
        activi = 0
        recurenti = 0
        for profil, _ in randuri:
            u = contul(profil)
            ultima = ultima_activitate.get(u) if u else None
            if ultima and ultima >= acum_o_saptamana:
                activi += 1
            if u and len(sesiuni_pe_om.get(u, set())) >= SESIUNI_RECURENT:
                recurenti += 1

        # ---- Evolutie per competenta: IN vs acum vs OUT ----
        comparatie = []
        for nume in competente:
            ale_in = [s.score for s in test_in if s.competency_name == nume]
            ale_acum = [s.score for s in practica if s.competency_name == nume]
            ale_out = [s.score for s in test_out if s.competency_name == nume]
            comparatie.append({
                "name": nume,
                "test_in": _medie(ale_in),
                "acum": _medie(ale_acum),
                "test_out": _medie(ale_out) if ale_out else None,
                "has_test_in": bool(ale_in),
                "has_data": bool(ale_in or ale_acum or ale_out),
            })

        # ---- Ritm de crestere: delta fata de Test IN ----
        ritm = sorted(
            [
                {**c, "delta": c["acum"] - c["test_in"]}
                for c in comparatie
                if c["test_in"] > 0 or c["acum"] > 0
            ],
            key=lambda c: c["delta"],
            reverse=True,
        )

        # ---- Ce nu a fost inteles bine: din quizuri ----
        quiz_pe_comp: dict[str, list[int]] = defaultdict(list)
        for s in quiz:
            if s.competency_name:
                quiz_pe_comp[s.competency_name].append(s.score)
        puncte_slabe = sorted(
            ({"name": n, "average": _medie(v)} for n, v in quiz_pe_comp.items()),
            key=lambda x: x["average"],
        )

        # ---- Evolutie scor mediu saptamanal (doar practica) ----
        pe_saptamana: dict[date, list[int]] = defaultdict(list)
        for s in practica:
            zi = s.created_at.date()
            pe_saptamana[zi - timedelta(days=zi.weekday())].append(s.score)
        serie = [
            {"week_start": w.isoformat(), "average": _medie(v), "scores_count": len(v)}
            for w, v in sorted(pe_saptamana.items())
        ]

        # ---- Tabelul participantilor ----
        oameni = []
        for profil, apartenenta in randuri:
            u = contul(profil)
            ale_lui = [s for s in practica if s.user_id == u] if u else []
            ultima = ultima_activitate.get(u) if u else None
            oameni.append({
                "participant_profile_id": profil.id,
                "user_id": u,
                "full_name": profil.full_name,
                "email": profil.email,
                "has_account": u is not None,
                "average_score": _medie([s.score for s in ale_lui]),
                "sessions_count": len(sesiuni_pe_om.get(u, set())) if u else 0,
                "last_activity": ultima.isoformat() if ultima else None,
                "inactive": not (ultima and ultima >= acum_o_saptamana),
                "has_test_in": u in cu_test_in if u else False,
                "has_test_out": u in cu_test_out if u else False,
                "active_membership": bool(apartenenta.active),
            })
        oameni.sort(key=lambda o: (o["full_name"] or "").lower())

        toate_valide = [s.score for s in scoruri]

        return {
            "project_id": project_id,
            "project_name": project.name,
            "project_type": project.project_type,
            "theme_name": tema_nume,
            "practice_configured": setari is not None,
            "starts_at": project.starts_at.isoformat() if project.starts_at else None,
            "due_at": project.due_at.isoformat() if project.due_at else None,
            "timeline_percent": self._procent_timeline(project, acum),
            # cele patru contoare de sus
            "participants_total": total,
            "average_score": _medie(toate_valide),
            "sessions_total": len({s.conversation_id for s in de_sesiune}),
            "inactive_count": total - activi,
            # participare & engagement
            "test_in_completed": len(cu_test_in),
            "test_out_completed": len(cu_test_out),
            "active_count": activi,
            "recurrent_count": recurenti,
            "test_out_active": False,
            "competencies": comparatie,
            "growth_ranking": ritm,
            "quiz_weak_spots": puncte_slabe,
            "weekly_average": serie,
            "participants": oameni,
        }

    @staticmethod
    def _procent_timeline(project: CompanyProject, acum: datetime) -> float | None:
        if not project.starts_at or not project.due_at:
            return None
        total = (project.due_at - project.starts_at).total_seconds()
        if total <= 0:
            return None
        trecut = (acum - project.starts_at).total_seconds()
        return round(min(max(trecut / total * 100, 0), 100), 1)


class PracticeInvitationsService:
    """Invitatiile in forma de training.

    Mecanismul de invitatie si de facut cont exista si e bun
    (`create_company_invitation`, `/invite/verify`, `/invite/exchange`) — nu se
    construieste altul. Aici doar se aduna starea, in forma cerută:

        invitat · a intrat · a facut testul de intrare
    """

    def __init__(self, session) -> None:
        self.session = session

    async def statuses(self, project_id: uuid.UUID) -> list[dict]:
        from codrut.modules.identity.models import AssignmentInvite

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

        profil_ids = [p.id for p, _ in randuri]
        invitatii = (await self.session.execute(
            select(AssignmentInvite).where(
                AssignmentInvite.respondent_profile_id.in_(profil_ids),
                AssignmentInvite.project_id == project_id,
            )
        )).scalars().all() if profil_ids else []
        invitatie_dupa_profil = {i.respondent_profile_id: i for i in invitatii}

        cu_test_in = {
            s.user_id for s in (await self.session.execute(
                select(CompetencyScore).where(
                    CompetencyScore.project_id == project_id,
                    CompetencyScore.conversation_id == TEST_IN_ID,
                )
            )).scalars().all()
        }

        out = []
        for profil, _ in randuri:
            cont = profil.user_id
            if cont is None and profil.email:
                u = user_dupa_email.get(profil.email.lower())
                cont = u.id if u else None
            inv = invitatie_dupa_profil.get(profil.id)
            out.append({
                "participant_profile_id": profil.id,
                "full_name": profil.full_name,
                "email": profil.email,
                "invited": inv is not None,
                "invited_at": inv.created_at.isoformat() if inv and inv.created_at else None,
                "has_account": cont is not None,
                "has_test_in": cont in cu_test_in if cont else False,
            })
        out.sort(key=lambda o: (o["full_name"] or "").lower())
        return out
