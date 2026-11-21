"""„O replică pe zi”: profesorul, nota, o replică pe zi, refuzurile, bugetul — plicul 236 (L2-P1).

Profesorul e ÎNTOTDEAUNA fals (`ProfesorFals`): niciun test nu construiește furnizorul adevărat și
niciun test nu pleacă spre rețea. Ziua „de azi” se dă din test (`acum`), nu din ceasul mașinii.
Ajutoarele de aici (profesorul fals, proiectul legat, al doilea om) le folosesc și celelalte
teste ale plicului.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select

from codrut.contracts.generation import (
    GenerationProviderKey,
    GenerationPurpose,
    GenerationResult,
    TokenUsage,
)
from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.models import UserAccountType, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.practice.models import (
    BudgetReservationState,
    CompetencyScore,
    PracticeBudgetReservation,
    PracticeConsent,
    PracticeSession,
    PracticeTurn,
)
from test_practice_session_flow import create_test_context

CATALOG = "comunicare-asertiva"
COST_FALS = Decimal("0.001234")
# o zi oarecare, la prânz în București
ACUM = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)


class ProfesorFals:
    """Ține minte cererile; întoarce textul cerut de test, cu un cost mic fix."""

    def __init__(
        self,
        text: str = "Bine spus. [🏆 Scor: 7/10]",
        *,
        exceptie: Exception | None = None,
        intarziere: float = 0.0,
    ) -> None:
        self.text = text
        self.exceptie = exceptie
        self.intarziere = intarziere
        self.cereri: list = []

    async def generate(self, request):
        self.cereri.append(request)
        if self.intarziere:
            await asyncio.sleep(self.intarziere)
        if self.exceptie is not None:
            raise self.exceptie
        return GenerationResult(
            text=self.text,
            usage=TokenUsage(prompt_tokens=10, output_tokens=10),
            provider=GenerationProviderKey.local,
            model="profesor-fals",
            region="test",
            finish_reason="STOP",
            estimated_usd=COST_FALS,
        )


def setari(**schimbari) -> Settings:
    baza = Settings(generation_provider="local")
    return baza.model_copy(update=schimbari) if schimbari else baza


async def proiect_legat(session, catalog: str | None = CATALOG, **kw) -> dict:
    ctx = await create_test_context(session, **kw)
    ctx["program_settings"].objective_catalog = catalog
    await session.flush()
    return ctx


async def al_doilea_om(session, ctx) -> tuple[ParticipantProfile, SessionPrincipal]:
    """Încă un om activ în același proiect, cu acordul dat — nume inventat."""
    from codrut.modules.practice.acord import AMPRENTA

    sufix = uuid.uuid4().hex[:8]
    profil = ParticipantProfile(
        company_id=ctx["company"].id, full_name=f"Om Inventat {sufix}",
        email=f"om_{sufix}@example.com",
    )
    session.add(profil)
    await session.flush()
    session.add(ProjectMembership(
        company_id=ctx["company"].id, project_id=ctx["project"].id,
        participant_profile_id=profil.id, active=True,
    ))
    session.add(PracticeConsent(
        participant_profile_id=profil.id, project_id=ctx["project"].id, text_hash=AMPRENTA,
        accepted_at=datetime.now(UTC),
    ))
    await session.flush()
    cine = SessionPrincipal(
        user_id=uuid.uuid4(), email=profil.email, role=UserRole.participant,
        account_type=UserAccountType.registered, access_mode="account", consent_current=True,
        terms_accepted_at=datetime.now(UTC), terms_version=CURRENT_TERMS_VERSION,
        session_token=f"test-token-{sufix}",
    )
    return profil, cine


async def trimite(session, ctx, *, acum=ACUM, profesor=None, text="Îți spun deschis ce cred.",
                  situatie=None, principal=None, settings=None):
    """Trimite replica zilei pe situația zilei (dacă testul nu cere alta)."""
    from codrut.modules.practice import replica_zilei as rz

    principal = principal or ctx["principal"]
    settings = settings or setari()
    if situatie is None:
        stare = await rz.starea_zilei(session, principal, ctx["project"].id, acum=acum)
        situatie = stare["situatie"]["id"]
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        return await rz.trimite_replica(
            session, principal, ctx["project"].id, situatie, text,
            profesor=profesor or ProfesorFals(), settings=settings, redis=redis, acum=acum,
        )
    finally:
        await redis.aclose()


async def replicile(session, profil_id):
    from codrut.modules.practice.models import PracticeDailyReply

    return (await session.execute(
        select(PracticeDailyReply).where(PracticeDailyReply.participant_profile_id == profil_id)
        .order_by(PracticeDailyReply.day)
    )).scalars().all()


async def rezervarile(session, program_settings_id):
    return (await session.execute(
        select(PracticeBudgetReservation)
        .where(PracticeBudgetReservation.program_settings_id == program_settings_id)
    )).scalars().all()


# ---- a. cererea către profesor ----


@pytest.mark.asyncio
async def test_profesorul_e_chemat_o_data_cu_instructiunea_de_azi_si_fara_nume() -> None:
    from codrut.modules.practice import replica_zilei as rz
    from codrut.modules.practice.alias import codul_omului
    from codrut.modules.practice.prompts import get_prompts_pe_meserii
    from codrut.modules.practice.service import SCENA_CELUILALT

    settings = setari()
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        stare = await rz.starea_zilei(session, ctx["principal"], ctx["project"].id, acum=ACUM)
        profesor = ProfesorFals()
        replica = "Înțeleg că e urgent; azi pot doar până la 18."
        await trimite(session, ctx, profesor=profesor, text=replica, settings=settings)

        assert len(profesor.cereri) == 1
        cerere = profesor.cereri[0]
        cod = await codul_omului(session, ctx["profile"])
        _, asteptata = get_prompts_pe_meserii(
            name=cod, history_length=rz.PAS_DE_JOC, memories=None,
            biblioteca_path=settings.biblioteca_path, profil_rol=None,
        )
        assert cerere.system_instruction == asteptata
        assert cerere.purpose == GenerationPurpose.evaluator
        assert cerere.max_output_tokens == settings.vertex_max_output_tokens_evaluator
        assert cerere.temperature == 0.2
        assert cerere.thinking_budget == settings.thinking_budget_evaluator
        assert len(cerere.messages) == 1
        assert cerere.messages[0].role == "user"
        assert cerere.messages[0].text == (
            f"{SCENA_CELUILALT}\n{stare['situatie']['text']}\n\n{replica}"
        )
        nume = ctx["profile"].full_name
        assert nume not in cerere.system_instruction
        assert nume not in cerere.messages[0].text
        assert rz.PAS_DE_JOC == 3


# ---- b. nota o pune codul ----


@pytest.mark.parametrize(
    ("text", "nota"),
    [
        ("Bine. [🏆 Scor: 7/10]", Decimal("7.0")),
        ("Bine. [🏆 Scor: 7,5/10]", Decimal("7.5")),
        ("Întâi [🏆 Scor: 4/10], apoi [🏆 Scor: 8/10]", Decimal("8.0")),
        ("Fără nicio notă.", None),
        ("Prea mult [🏆 Scor: 12/10]", None),
    ],
)
def test_nota_din_textul_profesorului(text, nota) -> None:
    from codrut.modules.practice import replica_zilei as rz

    assert rz.nota_din_text(text) == nota


@pytest.mark.asyncio
async def test_textul_profesorului_se_salveaza_intreg_si_nota_pe_rand() -> None:
    text = "Ai spus clar ce poți.\n\nÎntrebare: ce ai face mâine? [🏆 Scor: 7,5/10]"
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        raspuns = await trimite(session, ctx, profesor=ProfesorFals(text))
        assert raspuns["azi"]["raspuns"] == text
        assert raspuns["azi"]["nota"] == 7.5
        [rand] = await replicile(session, ctx["profile"].id)
        assert rand.teacher_text == text and rand.score == Decimal("7.5")


# ---- c. o singură replică pe zi (ora României) ----


@pytest.mark.asyncio
async def test_a_doua_replica_in_aceeasi_zi_e_refuzata_fara_profesor() -> None:
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        await trimite(session, ctx)
        situatia = (await replicile(session, ctx["profile"].id))[0].situation_id
        profesor = ProfesorFals()
        with pytest.raises(DomainError) as e:
            await trimite(
                session, ctx, acum=ACUM + timedelta(hours=3), profesor=profesor,
                situatie=situatia,
            )
        assert e.value.code == "replica_zilei_facuta"
        assert profesor.cereri == []
        assert len(await replicile(session, ctx["profile"].id)) == 1


@pytest.mark.asyncio
async def test_ziua_se_socoteste_in_ora_romaniei() -> None:
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        # 20 nov 21:30 UTC = 20 nov 23:30 la București; 22:30 UTC = 21 nov 00:30
        await trimite(session, ctx, acum=datetime(2026, 11, 20, 21, 30, tzinfo=UTC))
        await trimite(session, ctx, acum=datetime(2026, 11, 20, 22, 30, tzinfo=UTC))
        zile = [r.day.isoformat() for r in await replicile(session, ctx["profile"].id)]
        assert zile == ["2026-11-20", "2026-11-21"]


# ---- d. situația, replica goală, lungimea ----


@pytest.mark.asyncio
async def test_situatia_alta_replica_goala_si_prea_lunga() -> None:
    async with SessionLocal() as session:
        ctx = await proiect_legat(session, max_chars_per_turn=50)
        await session.commit()
        profesor = ProfesorFals()
        for situatie, text, cod in (
            (uuid.uuid4(), "Ceva.", "situatia_alta"),
            (None, "   \n ", "replica_goala"),
            (None, "x" * 51, "practice_turn_too_long"),
        ):
            with pytest.raises(DomainError) as e:
                await trimite(session, ctx, profesor=profesor, situatie=situatie, text=text)
            assert e.value.code == cod
        assert profesor.cereri == []
        assert await replicile(session, ctx["profile"].id) == []


# ---- e. profesorul cade ----


@pytest.mark.asyncio
async def test_profesorul_cade_nimic_salvat_rezervarea_eliberata_si_se_poate_relua() -> None:
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        with pytest.raises(DomainError) as e:
            await trimite(session, ctx, profesor=ProfesorFals(exceptie=RuntimeError("cade")))
        assert e.value.code == "profesor_indisponibil"
        assert await replicile(session, ctx["profile"].id) == []
        [rez] = await rezervarile(session, ctx["program_settings"].id)
        assert rez.state == BudgetReservationState.released

        await trimite(session, ctx)
        assert len(await replicile(session, ctx["profile"].id)) == 1


# ---- f. profesorul întârzie ----


@pytest.mark.asyncio
async def test_profesorul_intarzie_nimic_salvat_dar_apelul_se_plateste() -> None:
    settings = setari(vertex_timeout_evaluator_replica_seconds=1)
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        with pytest.raises(DomainError) as e:
            await trimite(
                session, ctx, profesor=ProfesorFals(intarziere=2.0), settings=settings
            )
        assert e.value.code == "profesor_indisponibil"
        assert await replicile(session, ctx["profile"].id) == []
        [rez] = await rezervarile(session, ctx["program_settings"].id)
        assert rez.state == BudgetReservationState.settled
        assert rez.actual_usd == rez.reserved_usd


# ---- g. plafonul proiectului ----


@pytest.mark.asyncio
async def test_plafonul_atins_refuza_fara_profesor() -> None:
    from codrut.modules.practice.budget import BudgetExceeded

    async with SessionLocal() as session:
        ctx = await proiect_legat(session, usd_cap_per_participant=Decimal("0"))
        await session.commit()
        profesor = ProfesorFals()
        with pytest.raises(BudgetExceeded):
            await trimite(session, ctx, profesor=profesor)
        assert profesor.cereri == []
        assert await replicile(session, ctx["profile"].id) == []


# ---- h. rândul salvat ----


@pytest.mark.asyncio
async def test_randul_salvat_si_nimic_altceva() -> None:
    from codrut.modules.practice.prompts import CODY_PROMPT_VERSION

    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()

        async def numara():
            return [
                (await session.execute(select(func.count()).select_from(m))).scalar_one()
                for m in (CompetencyScore, PracticeSession, PracticeTurn)
            ]

        inainte = await numara()
        await trimite(session, ctx, acum=datetime(2026, 11, 20, 22, 30, tzinfo=UTC))
        [rand] = await replicile(session, ctx["profile"].id)
        assert rand.cost_usd == COST_FALS
        assert rand.prompt_version == CODY_PROMPT_VERSION
        assert rand.day.isoformat() == "2026-11-21"
        assert rand.expires_at == datetime(2026, 11, 20, 22, 30, tzinfo=UTC) + timedelta(
            days=ctx["program_settings"].turn_retention_days
        )
        assert await numara() == inainte


# ---- i. contul de test singur pe proiect (corecția 3 a controlorului) ----


@pytest.mark.asyncio
async def test_proiect_numai_cu_contul_de_test_e_refuzat_de_buget() -> None:
    """Comportament de azi, documentat: rezervarea replicii zilei n-are sesiune, deci nu
    recunoaște contul de test (scutirea plicului 173 se sprijină pe sesiune), iar punga
    proiectului fără conturile de test e 0. DATORIE înainte de L2-P2/L2-P3: rezervarea replicii
    zilei recunoaște contul de test după profil (atinge `budget.py`, plic separat)."""
    from codrut.modules.practice.budget import BudgetExceeded
    from codrut.modules.practice.conturi_test import CONTURI_DE_TEST

    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        adresa = sorted(CONTURI_DE_TEST)[0]
        ctx["profile"].email = adresa
        await session.flush()
        principal = ctx["principal"].model_copy(update={"email": adresa})
        await session.commit()
        profesor = ProfesorFals()
        with pytest.raises(BudgetExceeded):
            await trimite(session, ctx, profesor=profesor, principal=principal)
        assert profesor.cereri == []
