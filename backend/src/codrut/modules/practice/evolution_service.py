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
from codrut.modules.practice.conturi_test import fara_conturile_de_test
from codrut.modules.practice.interlocutor import intrarile_de_punctaj
from codrut.modules.practice.models import (
    CompetencyScore,
    PracticeProgramSettings,
    PracticeSession,
    SessionState,
)
from codrut.modules.practice.scoring import (
    COMPETENCY_LEVEL_COLORS,
    COMPETENCY_LEVEL_DESCRIPTIONS,
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

        # Contul de test al lui Andrei iese din evolutia ECHIPEI (plicul 173): el porneste
        # sedinte oricand, ca sa incerce aplicatia, iar notele lui ar trage media liderilor
        # in sus sau in jos fara ca nimeni sa fi exersat. Filtrul sta AICI, inainte de
        # `emailuri`/`user_ids`, deci niciuna din notele lui nu ajunge in `scoruri`, nici in
        # numaratori, nici in lista pe om. Tabloul lui propriu (`dashboard_service`) ramane.
        # Aceeasi regula ca in Camera de training — o singura functie (plicul 180).
        randuri, _ = await fara_conturile_de_test(self.session, randuri)

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
        # Fila arata competentele PROIECTULUI, cu numele lor. Gruparea se face si pe
        # numele canonic, si pe numele brut: tema poate purta competente care nu au
        # echivalent canonic (de pilda „Rezolvarea colaborativa a conflictelor"), iar
        # scorurile lor NU au voie sa dispara doar fiindca aliasul nu le cunoaste.
        pe_competenta: dict[str, list[CompetencyScore]] = defaultdict(list)
        for s in scoruri:
            if not s.competency_name:
                continue
            canonic = match_comp(s.competency_name)
            if canonic:
                pe_competenta[canonic].append(s)
            if canonic != s.competency_name:
                pe_competenta[s.competency_name].append(s)

        nume_afisate = competente or sorted(pe_competenta)
        # plicul 165: aceleași reguli de punctaj; aici notele ÎNTREGII echipe, puse la un loc
        intrari_punctaj = await intrarile_de_punctaj(self.session, scoruri)
        evolutie = []
        for nume in nume_afisate:
            canonic = match_comp(nume)
            lst = pe_competenta.get(nume) or (pe_competenta.get(canonic, []) if canonic else [])
            # Plicul 166 D: întâi pe fiecare om, apoi adunat. Până acum regula „o notă pe zi” se
            # aplica echipei puse la un loc. Acum: punctele echipei = media punctelor oamenilor cu
            # cel puțin o notă la competența asta; nivelul echipei = nivelul omului median (ordonați
            # după puncte; la număr par, cel de jos — alegerea prudentă); plus câți oameni sunt pe
            # fiecare nivel. Fila rămâne numai a trainerului (`require_trainer_principal`, router).
            pe_om: dict[uuid.UUID, list] = defaultdict(list)
            for s in lst:
                if s.id in intrari_punctaj:
                    pe_om[s.user_id].append(intrari_punctaj[s.id])
            dovezi = sorted(
                (compute_competency_evidence(intrari) for intrari in pe_om.values()),
                key=lambda d: d.points,
            )
            dovada = (
                dovezi[(len(dovezi) - 1) // 2] if dovezi else compute_competency_evidence([])
            )
            puncte_echipa = round(sum(d.points for d in dovezi) / len(dovezi)) if dovezi else 0
            pe_niveluri = {nivel: 0 for nivel in COMPETENCY_LEVEL_DESCRIPTIONS}
            for d in dovezi:
                pe_niveluri[d.level] += 1
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
                "points": puncte_echipa,
                "people_count": len(dovezi),
                "levels_count": pe_niveluri,
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
                "cody_alias": profil.cody_alias,
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
