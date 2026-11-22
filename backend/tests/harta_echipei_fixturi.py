"""Fixtura comună pentru harta echipei — plicul 240 (nu e test).

Un proiect de training cu `n` oameni inventați (cont, profil, alias, apartenență activă),
7 competențe cu nume inventate, catalogul de obiective „comunicare-asertiva” (deja în baza
migrată) și un trainer alocat pe proiect (după 242: `User` + `ProjectTrainer`).
Ajutoare pentru ședințe (cu replica omului sau fără), note pe zile și alegeri de obiectiv.
Numele și adresele sunt numai inventate (după 187).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
    ProjectTrainer,
)
from codrut.modules.identity.models import User, UserAccountType, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.practice.models import (
    CompetencyScore,
    KnowledgePackState,
    PracticeKnowledgePack,
    PracticeObjective,
    PracticeObjectiveChoice,
    PracticeProgramSettings,
    PracticeSession,
    PracticeTheme,
    PracticeTurn,
    ProgramMode,
    ProjectCompetency,
    SessionKind,
    SessionState,
    TurnRole,
)

CATALOG = "comunicare-asertiva"
COMPETENTE = [f"Competența inventată {litera}" for litera in "ABCDEFG"]
PAROLA_DE_TEST = "hash-de-test-nu-e-parola"  # noqa: S105


def principal(user_id: uuid.UUID, email: str, role: UserRole = UserRole.trainer):
    return SessionPrincipal(
        user_id=user_id,
        email=email,
        role=role,
        account_type=UserAccountType.registered,
        access_mode="account",
        consent_current=True,
        terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION,
        session_token=f"tok-{uuid.uuid4().hex[:8]}",
    )


async def adauga_om(session, ctx: dict, *, email: str | None = None, nume: str | None = None):
    """Un om inventat în proiectul fixturii; întoarce dicționarul omului."""
    marca = uuid.uuid4().hex[:8]
    adresa = email or f"om-{marca}@example.com"
    cont = User(email=f"cont-{marca}@example.com" if email else adresa,
                password_hash=PAROLA_DE_TEST, role=UserRole.participant)
    session.add(cont)
    await session.flush()
    profil = ParticipantProfile(
        company_id=ctx["company"].id,
        full_name=nume or f"Om Inventat {marca}",
        email=adresa,
        user_id=cont.id,
        cody_alias=f"al-{marca}",
    )
    session.add(profil)
    await session.flush()
    membru = ProjectMembership(
        company_id=ctx["company"].id, project_id=ctx["project"].id,
        participant_profile_id=profil.id, active=True,
    )
    session.add(membru)
    await session.flush()
    om = {
        "profil_id": profil.id, "user_id": cont.id, "email": adresa, "cont_email": cont.email,
        "nume": profil.full_name, "alias": profil.cody_alias, "membru_id": membru.id,
    }
    ctx["oameni"].append(om)
    return om


async def setari_noi(session, company_id, *, catalog: str | None = CATALOG):
    """Un proiect de training nou în firmă, cu temă, pachet și setări."""
    marca = uuid.uuid4().hex[:8]
    proiect = CompanyProject(
        company_id=company_id, name=f"Proiect inventat {marca}",
        project_type="training", status=CompanyProjectStatus.active,
    )
    session.add(proiect)
    await session.flush()
    tema = PracticeTheme(slug=f"harta-{marca}", name="Tema inventată")
    session.add(tema)
    await session.flush()
    pachet = PracticeKnowledgePack(
        theme_id=tema.id, version=1, state=KnowledgePackState.approved,
        checksum=f"chk-{marca}", manifest={}, content_uri=f"gs://test-bucket/pack-{marca}",
        word_count=500,
    )
    session.add(pachet)
    await session.flush()
    setari = PracticeProgramSettings(
        project_id=proiect.id, mode=ProgramMode.training, theme_id=tema.id,
        active_pack_id=pachet.id, is_enabled=True, max_turns_per_session=10,
        max_sessions_per_day=5, max_chars_per_turn=1200,
        usd_cap_per_participant=Decimal("3.00"), objective_catalog=catalog,
    )
    session.add(setari)
    await session.flush()
    return proiect, pachet, setari


async def proiect_cu_oameni(session, n: int, *, catalog: str | None = CATALOG) -> dict:
    """Firma, proiectul, 7 competențe, `n` oameni și trainerul alocat. Comite."""
    marca = uuid.uuid4().hex[:8]
    firma = Company(name=f"Firma inventată {marca}")
    session.add(firma)
    await session.flush()
    proiect, pachet, setari = await setari_noi(session, firma.id, catalog=catalog)
    for i, nume in enumerate(COMPETENTE):
        session.add(ProjectCompetency(project_id=proiect.id, name=nume, order_index=i))
    trainer = User(email=f"trainer-{marca}@example.com", password_hash=PAROLA_DE_TEST,
                   role=UserRole.trainer)
    session.add(trainer)
    await session.flush()
    session.add(ProjectTrainer(project_id=proiect.id, user_id=trainer.id))
    await session.flush()
    ctx = {
        "company": firma, "project": proiect, "pack": pachet, "settings": setari,
        "trainer_user": trainer, "trainer": principal(trainer.id, trainer.email),
        "oameni": [],
    }
    for _ in range(n):
        await adauga_om(session, ctx)
    await session.commit()
    return ctx


async def sedinta(
    session, ctx: dict, om: dict, start: datetime, *,
    kind: SessionKind = SessionKind.roleplay,
    replici_minute: tuple[float, ...] = (0.0, 1.0),
    cu_omul: bool = True,
    setari=None,
    pachet=None,
) -> uuid.UUID:
    """O ședință; replicile la `start + minute`.

    Prima e a omului dacă `cu_omul`, restul ale actorului."""
    s = PracticeSession(
        program_settings_id=(setari or ctx["settings"]).id,
        participant_profile_id=om["profil_id"],
        pack_id=(pachet or ctx["pack"]).id,
        kind=kind, state=SessionState.open, started_at=start, turn_count=len(replici_minute),
    )
    session.add(s)
    await session.flush()
    for i, minute in enumerate(replici_minute):
        rol = TurnRole.participant if (cu_omul and i == 0) else TurnRole.actor
        session.add(PracticeTurn(
            session_id=s.id, ordinal=i + 1, role=rol, text="replică inventată",
            created_at=start + timedelta(minutes=minute),
            expires_at=start + timedelta(days=90),
        ))
    await session.flush()
    return s.id


async def nota(
    session, ctx: dict, om: dict, conversation_id, competenta: str, scor: int,
    moment: datetime, *, source_type: str = "roleplay",
) -> None:
    session.add(CompetencyScore(
        user_id=om["user_id"], project_id=ctx["project"].id, score=scor, level=2,
        conversation_id=str(conversation_id), competency_name=competenta,
        source_type=source_type, created_at=moment,
    ))
    await session.flush()


async def alege(session, ctx: dict, om: dict, nr: int, *, inlocuita: bool = False) -> None:
    obiectiv = (await session.execute(
        select(PracticeObjective).where(
            PracticeObjective.catalog == CATALOG, PracticeObjective.order_index == nr,
        )
    )).scalar_one()
    acum = datetime.now(UTC)
    session.add(PracticeObjectiveChoice(
        participant_profile_id=om["profil_id"], project_id=ctx["project"].id,
        objective_id=obiectiv.id, chosen_at=acum - timedelta(days=2 if inlocuita else 1),
        replaced_at=acum - timedelta(days=1) if inlocuita else None,
    ))
    await session.flush()
