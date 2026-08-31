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

from sqlalchemy import func, select

from codrut.core.config import get_settings
from codrut.core.errors import DomainError
from codrut.modules.companies.models import (
    CompanyProject,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import (
    SHADOW_ACCOUNT_PASSWORD_HASH,
    User,
    UserAccountType,
    UserRole,
)
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
# Cat tine linkul prin care omul isi pune parola. Cel de resetare obisnuita tine o
# ora, pentru ca omul tocmai l-a cerut. Aici linkul il primeste de la trainer si
# poate sa-l deschida peste cateva zile, deci o ora ar fi o capcana.
ZILE_LINK_PAROLA = 14
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
    """Invitatiile la training. Sunt invitatii la CONT, nu la un chestionar.

    Aici e deosebirea care a costat un plic intreg ca sa fie inteleasa.

    La coaching exista doua feluri de oameni: liderul, care are cont, si colegii
    lui, care primesc o legatura trecatoare catre un chestionar si dispar. De
    aceea invitatia de acolo e legata de asignari — legatura ESTE sarcina. Fara
    sarcina n-are ce trimite, si asa trebuie sa ramana.

    La training nu exista doua feluri. Toti exerseaza cu Cody, toti dau testul de
    intrare si pe cel de iesire, toti au tablou de competente si o memorie care se
    aduna saptamani la rand. Nu primesc niciun chestionar de completat: trebuie
    doar sa intre in cont, unde gasesc pasii urmatori. Deci toti au nevoie de cont
    adevarat, cu parola.

    Drumul, facut numai din piese care exista deja:

        bifezi oamenii → li se face contul → email cu link de pus parola
        → isi pun parola → cont permanent → intra la testul de intrare

    Nu se creeaza asignari false. Nu se slabeste verificarea de la coaching. Nu se
    face un al doilea mecanism de email: linkul pleaca prin acelasi `email_sends`.
    """

    def __init__(self, session) -> None:
        self.session = session

    async def statuses(self, project_id: uuid.UUID) -> list[dict]:
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
            select(User).where(func.lower(User.email).in_([e.lower() for e in emailuri]))
        )).scalars().all() if emailuri else []
        user_dupa_email = {u.email.lower(): u for u in utilizatori}

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
            u = user_dupa_email.get((profil.email or "").lower())
            if u is None and profil.user_id:
                u = next((x for x in utilizatori if x.id == profil.user_id), None)
            # „Invitat" = i s-a facut contul. „A intrat" = si-a pus parola lui.
            si_a_pus_parola = bool(
                u is not None
                and u.account_type == UserAccountType.registered
                and u.password_hash != SHADOW_ACCOUNT_PASSWORD_HASH
            )
            out.append({
                "participant_profile_id": profil.id,
                "full_name": profil.full_name,
                "email": profil.email,
                "invited": u is not None,
                "invited_at": u.created_at.isoformat() if u is not None and u.created_at else None,
                "has_account": si_a_pus_parola,
                "has_test_in": (u.id in cu_test_in) if u is not None else False,
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
        """Face conturile si trimite fiecaruia linkul de pus parola.

        Linkul se intoarce chiar si cand emailul nu pleaca: emailul poate cadea
        din motive care nu tin de noi (cheie, plafon, furnizor), dar trainerul
        trebuie sa poata da linkul mai departe cum vrea.
        """
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
        gasiti = {
            p.id: p
            for p in (await self.session.execute(
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
        }

        setari = get_settings()

        out: list[dict] = []
        for profil_id in participant_profile_ids:
            profil = gasiti.get(profil_id)
            if profil is None:
                out.append(_rand(profil_id, None, None, None, False,
                                 "Omul nu e inscris in acest proiect."))
                continue
            if not profil.email:
                out.append(_rand(profil_id, profil.full_name, None, None, False,
                                 "Omul nu are email."))
                continue

            try:
                async with self.session.begin_nested():
                    utilizator = await self._contul_lui(profil)
                    link = await self._link_de_parola(utilizator, setari)
            except DomainError as exc:
                out.append(_rand(profil_id, profil.full_name, profil.email, None, False,
                                 f"Contul nu s-a putut pregati: {exc.code}."))
                continue
            except Exception:
                logger.exception(
                    "Contul de training nu s-a putut pregati.",
                    extra={"participant_profile_id": str(profil_id)},
                )
                out.append(_rand(profil_id, profil.full_name, profil.email, None, False,
                                 "Contul nu s-a putut pregati."))
                continue

            la_coada, motiv = await self._trimite_emailul(
                profil=profil,
                proiect=proiect,
                link=link,
                utilizator=utilizator,
                trainer_user_id=trainer_user_id,
            )
            out.append(_rand(profil_id, profil.full_name, profil.email, link, la_coada, motiv))

        return out

    async def _contul_lui(self, profil) -> User:
        """Contul permanent al omului. Il face daca nu exista, si nu-l atinge daca exista.

        Contul se naste `registered`, nu `guest`: la training omul trebuie sa ajunga
        in zona participantului, iar aceea refuza din constructie oaspetii si
        sesiunile de link. Parola ramane cea de santier pana si-o pune el.
        """
        utilizator = (await self.session.execute(
            select(User).where(User.email == profil.email.lower())
        )).scalar_one_or_none()
        if utilizator is None:
            utilizator = User(
                id=uuid.uuid4(),
                email=profil.email.lower(),
                password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
                role=UserRole.participant,
                account_type=UserAccountType.registered,
            )
            self.session.add(utilizator)
            await self.session.flush()
        elif utilizator.account_type == UserAccountType.guest:
            # Un cont de oaspete ramas de la un link vechi nu poate intra in zona
            # participantului. La training e nevoie de cont adevarat.
            utilizator.account_type = UserAccountType.registered
        if profil.user_id is None:
            profil.user_id = utilizator.id
        return utilizator

    async def _link_de_parola(self, utilizator: User, setari) -> str:
        """Un link prin care omul isi pune parola. Acelasi mecanism ca la resetare.

        Nu se pastreaza nicaieri in clar: in baza sta doar amprenta lui. De aceea
        linkul se poate arata o singura data, la trimitere; „Trimite din nou" face
        unul proaspat si il stinge pe cel vechi.
        """
        import hashlib

        from codrut.core.security import new_session_token
        from codrut.modules.identity.models import PasswordResetToken

        brut = new_session_token()
        acum = datetime.now(UTC)
        # Linkurile vechi ale omului se sting, ca la orice cerere de parola noua.
        vechi = (await self.session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == utilizator.id,
                PasswordResetToken.used_at.is_(None),
            )
        )).scalars().all()
        for jeton in vechi:
            jeton.used_at = acum
        self.session.add(
            PasswordResetToken(
                id=uuid.uuid4(),
                user_id=utilizator.id,
                # Aceeasi amprenta ca la resetarea obisnuita, ca sa mearga pe
                # aceeasi ruta de confirmare.
                token_hash=hashlib.sha256(brut.encode()).hexdigest(),
                expires_at=acum + timedelta(days=ZILE_LINK_PAROLA),
            )
        )
        await self.session.flush()
        return f"{setari.public_app_url.rstrip('/')}/update-password?token={brut}"

    async def _trimite_emailul(
        self,
        *,
        profil,
        proiect,
        link: str,
        utilizator: User,
        trainer_user_id: uuid.UUID,
    ) -> tuple[bool, str | None]:
        """Pune emailul in aceeasi coada ca toate celelalte. Nu arunca.

        Atentie la ce inseamna „da": emailul a intrat in coada, NU ca a ajuns la
        om. Plecarea propriu-zisa se face mai tarziu, in `EmailOutboxProcessor`, si
        poate esua acolo — de pilda cu o cheie invalida la furnizor.
        """
        from codrut.contracts.emails import EmailAddress, EmailMessage
        from codrut.core.config import get_settings
        from codrut.modules.communications.email_provider import build_email_provider
        from codrut.modules.communications.service import TransactionalEmailService

        nume = (profil.full_name or "").split(" ")[0] or "Salut"
        mesaj = EmailMessage(
            to=EmailAddress(profil.email),
            subject=f"Invitatie la {proiect.name} — pune-ti parola",
            html_body=(
                f"<p>{nume},</p>"
                f"<p>Ai fost invitat la programul <strong>{proiect.name}</strong>.</p>"
                f'<p><a href="{link}">Pune-ti parola si intra in cont</a></p>'
                f"<p>Linkul e doar al tau si tine {ZILE_LINK_PAROLA} de zile. "
                "Dupa ce intri, gasesti acolo pasii urmatori.</p>"
            ),
            text_body=(
                f"{nume},\n\n"
                f"Ai fost invitat la programul {proiect.name}.\n\n"
                f"Pune-ti parola si intra in cont: {link}\n\n"
                f"Linkul e doar al tau si tine {ZILE_LINK_PAROLA} de zile. "
                "Dupa ce intri, gasesti acolo pasii urmatori."
            ),
        )
        try:
            await TransactionalEmailService(
                build_email_provider(get_settings()),
                self.session,
                owner_id=trainer_user_id,
            ).enqueue_transactional_message(
                mesaj,
                template_key="training_account_invitation",
                template_version=1,
                idempotency_key=f"training-cont:{utilizator.id}:{profil.id}",
                delivery_kind="training_account_invitation",
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
                extra={"participant_profile_id": str(profil.id)},
            )
            return False, "Emailul nu a intrat la coada. Linkul de mai jos merge oricum."


def _rand(
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
