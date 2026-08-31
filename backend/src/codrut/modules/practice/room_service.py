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

import logging
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from codrut.core.config import get_settings
from codrut.core.errors import DomainError
from codrut.modules.communications.task_links import build_task_url
from codrut.modules.companies.models import (
    CompanyProject,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User
from codrut.modules.practice.models import (
    CompetencyScore,
    PracticeProgramSettings,
    PracticeTheme,
)
from codrut.modules.practice.setup_service import competency_names_for_project

TEST_IN_ID = "TEST_IN_01"
TEST_OUT_ID = "TEST_OUT_01"
QUIZ_SOURCE = "cunostinte"

logger = logging.getLogger(__name__)

ZILE_ACTIV = 7
# Cat tine linkul de invitatie la training. Programul dureaza saptamani, nu ore.
ZILE_INVITATIE = 90
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

        scoruri = (await self.session.execute(
            select(CompetencyScore).where(CompetencyScore.project_id == project_id)
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

    Ce s-a crezut la plicul 30 si s-a dovedit gresit la 31: ca ruta obisnuita de
    invitatii (`POST /companies/{id}/participants/invitations`) merge si fara
    ciclu de evaluare. Nu merge. Acea ruta cere ca omul sa aiba deja o asignare
    de chestionar activa; altfel il sare tacut, cu `no_assignments`, si nu scrie
    nimic — nici invitatie, nici email. Un proiect de training nu are chestionare,
    deci nu are nici asignari, deci nu putea trimite niciodata nimic.

    Aici e calea proprie a trainingului: se face invitatia direct, fara asignare
    (`allow_without_assignments`, deschisa doar pentru `project_type` = training),
    se refoloseste acelasi token si acelasi drum de intrare
    (`/invite/verify`, `/invite/exchange`) si se incearca emailul. Linkul se
    intoarce mereu, chiar daca emailul nu pleaca: drumul trebuie sa se poata
    parcurge si fara posta.

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
                "invite_url": (
                    build_task_url(inv.token, get_settings())
                    if inv is not None and inv.status == "active"
                    else None
                ),
                "has_account": cont is not None,
                "has_test_in": cont in cu_test_in if cont else False,
            })
        out.sort(key=lambda o: (o["full_name"] or "").lower())
        return out

    async def send(
        self,
        project_id: uuid.UUID,
        participant_profile_ids: list[uuid.UUID],
        *,
        trainer_user_id: uuid.UUID,
    ) -> list[dict]:
        """Face invitatiile si incearca emailul. Intoarce un rand pentru fiecare om.

        Linkul se intoarce chiar si cand emailul nu pleaca. Asta e regula:
        emailul poate sa cada din motive care nu tin de noi (cheie, plafon,
        furnizor), dar drumul participantului trebuie sa se poata parcurge —
        trainerul copiaza linkul si il da cum vrea.
        """
        from codrut.modules.communications.email_provider import build_email_provider
        from codrut.modules.communications.service import TransactionalEmailService
        from codrut.modules.identity.service import IdentityService

        if not participant_profile_ids:
            return []

        proiect = (await self.session.execute(
            select(CompanyProject).where(CompanyProject.id == project_id)
        )).scalars().first()
        if proiect is None:
            raise DomainError("Proiectul nu exista.", code="project_not_found")
        if (proiect.project_type or "") != "training":
            raise DomainError(
                "Calea asta e doar pentru proiectele de training.",
                code="not_a_training_project",
            )

        ceruti = set(participant_profile_ids)
        randuri = (await self.session.execute(
            select(ParticipantProfile)
            .join(
                ProjectMembership,
                ProjectMembership.participant_profile_id == ParticipantProfile.id,
            )
            .where(
                ProjectMembership.project_id == project_id,
                ParticipantProfile.id.in_(ceruti),
            )
        )).scalars().all()
        gasiti = {p.id: p for p in randuri}

        setari = get_settings()
        identitate = IdentityService(self.session)
        posta = TransactionalEmailService(
            build_email_provider(setari),
            self.session,
            owner_id=trainer_user_id,
        )
        expira = datetime.now(UTC) + timedelta(days=ZILE_INVITATIE)

        out: list[dict] = []
        for profil_id in participant_profile_ids:
            profil = gasiti.get(profil_id)
            if profil is None:
                out.append(_rand_invitatie(
                    profil_id, None, None, None, False,
                    "Omul nu e inscris in acest proiect.",
                ))
                continue
            if not profil.email:
                out.append(_rand_invitatie(
                    profil_id, profil.full_name, None, None, False,
                    "Omul nu are email.",
                ))
                continue

            try:
                async with self.session.begin_nested():
                    invitatie = await identitate.create_invite(
                        company_id=profil.company_id,
                        respondent_profile_id=profil.id,
                        assignment_ids=None,
                        project_id=project_id,
                        expires_at=expira,
                        allow_without_assignments=True,
                    )
                link = build_task_url(invitatie.token, setari)
            except DomainError as exc:
                out.append(_rand_invitatie(
                    profil_id, profil.full_name, profil.email, None, False,
                    f"Invitatia nu s-a putut face: {exc.code}.",
                ))
                continue
            except Exception:
                logger.exception(
                    "Invitatia de training nu s-a putut face.",
                    extra={"participant_profile_id": str(profil_id)},
                )
                out.append(_rand_invitatie(
                    profil_id, profil.full_name, profil.email, None, False,
                    "Invitatia nu s-a putut face.",
                ))
                continue

            # Linkul exista de acum. Emailul e o incercare separata: daca pica,
            # randul ramane bun si omul primeste linkul copiat de trainer.
            la_coada, motiv = await self._incearca_emailul(
                posta,
                profil=profil,
                proiect=proiect,
                link=link,
                invitatie_id=invitatie.id,
            )
            out.append(_rand_invitatie(
                profil_id, profil.full_name, profil.email, link, la_coada, motiv,
            ))

        return out

    async def _incearca_emailul(
        self,
        posta,
        *,
        profil,
        proiect,
        link: str,
        invitatie_id: uuid.UUID,
    ) -> tuple[bool, str | None]:
        """Pune emailul la coada. Nu arunca: intoarce de ce n-a mers.

        Atentie la ce inseamna „da": emailul a intrat in coada, NU ca a ajuns la
        om. Plecarea propriu-zisa se intampla mai tarziu, in `EmailOutboxProcessor`,
        si poate esua acolo — de exemplu cu o cheie Brevo invalida. De aceea
        campul se cheama `email_queued`, nu `email_sent`.
        """
        from codrut.contracts.emails import EmailAddress, EmailMessage

        nume = (profil.full_name or "").split(" ")[0] or "Salut"
        subiect = f"Ai fost invitat la {proiect.name}"
        mesaj = EmailMessage(
            to=EmailAddress(profil.email),
            subject=subiect,
            html_body=(
                f"<p>{nume},</p>"
                f"<p>Ai fost invitat la programul <strong>{proiect.name}</strong>.</p>"
                f'<p><a href="{link}">Intra aici ca sa incepi</a></p>'
                "<p>Linkul e doar al tau. Nu il da mai departe.</p>"
            ),
            text_body=(
                f"{nume},\n\n"
                f"Ai fost invitat la programul {proiect.name}.\n\n"
                f"Intra aici ca sa incepi: {link}\n\n"
                "Linkul e doar al tau. Nu il da mai departe."
            ),
        )
        try:
            await posta.enqueue_transactional_message(
                mesaj,
                template_key="training_invitation",
                template_version=1,
                idempotency_key=f"training-invite:{invitatie_id}",
                delivery_kind="training_invitation",
            )
            return True, None
        except DomainError as exc:
            if exc.code == "daily_send_cap_reached":
                return False, (
                    "Emailul nu a intrat la coada: s-a atins plafonul zilnic de "
                    "trimiteri. Linkul de mai jos merge oricum."
                )
            return False, f"Emailul nu a intrat la coada ({exc.code}). Linkul merge oricum."
        except Exception:
            logger.exception(
                "Emailul de invitatie la training nu s-a putut pune la coada.",
                extra={"invitation_id": str(invitatie_id)},
            )
            return False, "Emailul nu a intrat la coada. Linkul de mai jos merge oricum."


def _rand_invitatie(
    profil_id: uuid.UUID,
    nume: str | None,
    email: str | None,
    link: str | None,
    email_la_coada: bool,
    motiv: str | None = None,
) -> dict:
    return {
        "participant_profile_id": profil_id,
        "full_name": nume,
        "email": email,
        "invite_url": link,
        "email_queued": email_la_coada,
        "error": motiv,
    }
