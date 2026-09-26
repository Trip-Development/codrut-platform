"""Pagina omului - al doilea ecran al camerei de training.

Portat din ``app/admin/projects/[projectId]/participant/[userId]/page.tsx``
(462 rd.) plus ``TrainerNotes.tsx`` (149 rd.), din ``codrut-app``.

Doua sectiuni mari, cu intelesuri diferite, exact ca in vechi:

    Cunostinte teoretice  - Test IN vs Test OUT, ce STIE omul
    Practica aplicata     - evidence acumulat din sesiuni, ce FACE omul

Notele trainerului se scriu si se citesc de aici; `trainer_notes` exista deja.
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
from codrut.modules.practice.evaluator import TRAINER_PREFIX
from codrut.modules.practice.models import (
    CompetencyScore,
    InsightMoment,
    PracticeProgramSettings,
    PracticeSession,
    SessionSample,
    TrainerNote,
)
from codrut.modules.practice.room_service import (
    QUIZ_SOURCE,
    TEST_IN_ID,
    TEST_OUT_ID,
    _medie,
)
from codrut.modules.practice.scoring import ScoreEntry, compute_competency_evidence
from codrut.modules.practice.setup_service import competency_names_for_project


class PracticePersonService:
    def __init__(self, session) -> None:
        self.session = session

    async def _profil_si_cont(
        self, project_id: uuid.UUID, profile_id: uuid.UUID
    ) -> tuple[ParticipantProfile, uuid.UUID | None]:
        profil = (await self.session.execute(
            select(ParticipantProfile).where(ParticipantProfile.id == profile_id)
        )).scalar_one_or_none()
        if profil is None:
            raise DomainError("Participantul nu a fost găsit.", code="participant_not_found")

        apartenenta = (await self.session.execute(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.participant_profile_id == profile_id,
            )
        )).scalar_one_or_none()
        if apartenenta is None:
            raise DomainError(
                "Participantul nu e în acest proiect.",
                code="participant_not_in_project",
            )

        cont = profil.user_id
        if cont is None and profil.email:
            u = (await self.session.execute(
                select(User).where(User.email == profil.email.lower())
            )).scalar_one_or_none()
            cont = u.id if u else None
        return profil, cont

    async def person(self, project_id: uuid.UUID, profile_id: uuid.UUID) -> dict:
        project = (await self.session.execute(
            select(CompanyProject).where(CompanyProject.id == project_id)
        )).scalar_one_or_none()
        if project is None:
            raise DomainError(f"Proiectul {project_id} nu a fost găsit.", code="project_not_found")

        profil, cont = await self._profil_si_cont(project_id, profile_id)
        competente = await competency_names_for_project(self.session, project_id)

        scoruri = []
        momente = []
        mostre = []
        note = []
        if cont is not None:
            scoruri = (await self.session.execute(
                select(CompetencyScore).where(
                    CompetencyScore.user_id == cont,
                    CompetencyScore.project_id == project_id,
                )
            )).scalars().all()
            momente = (await self.session.execute(
                select(InsightMoment)
                .where(InsightMoment.user_id == cont)
                .order_by(InsightMoment.created_at.desc())
                .limit(20)
            )).scalars().all()
            mostre = (await self.session.execute(
                select(SessionSample)
                .where(SessionSample.user_id == cont)
                .order_by(SessionSample.created_at.desc())
                .limit(10)
            )).scalars().all()
            note = (await self.session.execute(
                select(TrainerNote)
                .where(
                    TrainerNote.participant_id == cont,
                    TrainerNote.project_id == project_id,
                )
                .order_by(TrainerNote.created_at.desc())
            )).scalars().all()

        test_in = [s for s in scoruri if s.conversation_id == TEST_IN_ID]
        test_out = [s for s in scoruri if s.conversation_id == TEST_OUT_ID]
        practica = [
            s for s in scoruri
            if s.conversation_id not in (TEST_IN_ID, TEST_OUT_ID)
            and s.source_type != QUIZ_SOURCE
        ]
        quiz = [s for s in scoruri if s.source_type == QUIZ_SOURCE]

        sesiuni = 0
        if cont is not None:
            setari = (await self.session.execute(
                select(PracticeProgramSettings)
                .where(PracticeProgramSettings.project_id == project_id)
            )).scalar_one_or_none()
            if setari is not None:
                sesiuni = len((await self.session.execute(
                    select(PracticeSession).where(
                        PracticeSession.program_settings_id == setari.id,
                        PracticeSession.participant_profile_id == profile_id,
                    )
                )).scalars().all())

        # ---- Cunostinte teoretice: IN vs OUT, pe competenta ----
        teorie = []
        for nume in competente:
            ale_in = [s.score for s in test_in if s.competency_name == nume]
            ale_out = [s.score for s in test_out if s.competency_name == nume]
            teorie.append({
                "name": nume,
                "test_in": _medie(ale_in) if ale_in else None,
                "test_out": _medie(ale_out) if ale_out else None,
                "delta": (_medie(ale_out) - _medie(ale_in)) if (ale_in and ale_out) else None,
            })

        # ---- Practica aplicata: evidence acumulat ----
        pe_competenta: dict[str, list[CompetencyScore]] = defaultdict(list)
        for s in practica:
            if s.competency_name:
                pe_competenta[s.competency_name].append(s)

        evidence = []
        for nume in competente:
            lst = pe_competenta.get(nume, [])
            dovada = compute_competency_evidence([
                ScoreEntry(score=s.score, created_at=s.created_at, source_type=s.source_type)
                for s in lst
            ])
            evidence.append({
                "name": nume,
                "level": dovada.level,
                "level_description": dovada.level_description,
                "color": dovada.color,
                "average_score": round(dovada.average_score, 1),
                "sessions_count": len({s.conversation_id for s in lst}),
                "scores_count": len(lst),
                "why_not_higher": dovada.why_not_higher,
            })

        # Top progres pe practica: dupa media acumulata
        top = sorted(
            [e for e in evidence if e["scores_count"] > 0],
            key=lambda e: e["average_score"],
            reverse=True,
        )

        # ---- Evolutie scor mediu, per saptamana, doar practica ----
        pe_saptamana: dict[date, list[int]] = defaultdict(list)
        for s in practica:
            zi = s.created_at.date()
            pe_saptamana[zi - timedelta(days=zi.weekday())].append(s.score)
        serie = [
            {"week_start": w.isoformat(), "average": _medie(v), "scores_count": len(v)}
            for w, v in sorted(pe_saptamana.items())
        ]

        # ---- Ce nu a fost inteles bine, din quizuri ----
        quiz_pe_comp: dict[str, list[int]] = defaultdict(list)
        for s in quiz:
            if s.competency_name:
                quiz_pe_comp[s.competency_name].append(s.score)
        puncte_slabe = sorted(
            ({"name": n, "average": _medie(v)} for n, v in quiz_pe_comp.items()),
            key=lambda x: x["average"],
        )

        # ---- Momentele: ale lui, si separat notele pentru trainer ----
        ale_lui = [m for m in momente if not (m.summary or "").startswith(TRAINER_PREFIX)]
        pentru_trainer = [m for m in momente if (m.summary or "").startswith(TRAINER_PREFIX)]

        durata_zile = None
        if project.starts_at and project.due_at:
            durata_zile = max(0, (project.due_at - project.starts_at).days)

        return {
            "project_id": project_id,
            "project_name": project.name,
            "participant_profile_id": profil.id,
            "user_id": cont,
            "full_name": profil.full_name,
            "email": profil.email,
            "has_account": cont is not None,
            "duration_days": durata_zile,
            # cele patru cifre de sus
            "test_in_average": _medie([s.score for s in test_in]) if test_in else None,
            "progress_average": _medie([s.score for s in practica]) if practica else 0,
            "test_out_average": _medie([s.score for s in test_out]) if test_out else None,
            "sessions_count": sesiuni,
            "theory": teorie,
            "evidence": evidence,
            "top_progress": top,
            "weekly_average": serie,
            "quiz_weak_spots": puncte_slabe,
            "insight_moments": [
                {"id": m.id, "summary": m.summary, "created_at": m.created_at.isoformat()}
                for m in ale_lui
            ],
            "trainer_recommendations": [
                {"id": m.id, "summary": m.summary, "created_at": m.created_at.isoformat()}
                for m in pentru_trainer
            ],
            "session_samples": [
                {
                    "id": s.id,
                    "real_weak": s.real_weak,
                    "real_improved": s.real_improved,
                    "invented_weak": s.invented_weak,
                    "invented_improved": s.invented_improved,
                    "created_at": s.created_at.isoformat(),
                }
                for s in mostre
            ],
            "trainer_notes": [
                {"id": n.id, "note": n.note, "created_at": n.created_at.isoformat()}
                for n in note
            ],
        }

    async def add_note(
        self,
        project_id: uuid.UUID,
        profile_id: uuid.UUID,
        trainer_id: uuid.UUID,
        text: str,
    ) -> dict:
        _, cont = await self._profil_si_cont(project_id, profile_id)
        if cont is None:
            raise DomainError(
                "Participantul nu are încă un cont, deci nu i se pot atașa note.",
                code="participant_without_account",
            )
        nota = TrainerNote(
            id=uuid.uuid4(),
            trainer_id=trainer_id,
            participant_id=cont,
            project_id=project_id,
            note=text.strip(),
        )
        self.session.add(nota)
        await self.session.flush()
        return {
            "id": nota.id,
            "note": nota.note,
            "created_at": nota.created_at.isoformat() if nota.created_at else "",
        }
