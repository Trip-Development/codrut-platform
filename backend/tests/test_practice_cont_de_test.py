"""Plicul 173 — contul de test al lui Andrei: fara limita pe zi, cu frana lui proprie.

Hotararea lui Andrei (1 oct 2026, `[test-nelimitat]`): contul lui de test trebuie sa poata
porni oricate sedinte. Frana nu dispare, se muta: un plafon lunar PROPRIU de 25 USD, pe toate
proiectele, in loc de punga proiectului.

Si partea care nu se vede, dar conteaza mai mult: testele lui nu au voie sa atinga plafonul
celorlalti. Contul de test nu mai intra nici in numarul de membri dupa care se calculeaza
punga, nici in ce s-a consumat din ea.

Fara retea: furnizorul local / fals peste tot.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.models import User, UserAccountType, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.practice.budget import (
    BudgetExceeded,
    plafonul_programului,
    reserve,
)
from codrut.modules.practice.conturi_test import (
    PLAFON_LUNAR_CONT_TEST_USD,
    e_cont_de_test,
)
from codrut.modules.practice.models import (
    BudgetReservationState,
    CompetencyScore,
    PracticeBudgetReservation,
    PracticeSession,
    SessionKind,
    SessionState,
)
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context
from test_tabloul_pe_proiect import COMPETENTE, FurnizorCuNote

ADRESA_DE_TEST = "andreyvacaru@gmail.com"


# --------------------------------------------------------------------- cine e contul de test


def test_doar_adresa_exacta_e_cont_de_test() -> None:
    """Variantele cu `+` joaca oameni adevarati in probe — nu sunt conturi de test."""
    assert e_cont_de_test(ADRESA_DE_TEST) is True
    assert e_cont_de_test("andreyvacaru+lidera@gmail.com") is False
    assert e_cont_de_test("andreyvacaru+liderc@gmail.com") is False
    assert e_cont_de_test("altcineva@gmail.com") is False
    assert e_cont_de_test(None) is False
    assert e_cont_de_test("") is False


def test_majusculele_si_spatiile_nu_ascund_contul_de_test() -> None:
    assert e_cont_de_test("AndreyVacaru@gmail.com") is True
    assert e_cont_de_test("  ANDREYVACARU@GMAIL.COM  ") is True


# ------------------------------------------------------------------------------- ajutoarele


async def _fa_din_el_contul_de_test(session, ctx, *, cu_cont_legat: bool = False):
    """Rescrie profilul fixturii pe adresa contului de test si intoarce principalul potrivit."""
    ctx["profile"].email = ADRESA_DE_TEST
    if cu_cont_legat:
        # Adresa e fixa si unica in `users`: daca o rulare de dinainte a lasat contul
        # (`start_session` comite la mijloc, nu se poate intoarce), il refolosim.
        cont = (await session.execute(
            select(User).where(User.email == ADRESA_DE_TEST)
        )).scalars().first()
        if cont is None:
            cont = User(
                id=uuid.uuid4(),
                email=ADRESA_DE_TEST,
                password_hash="x",  # noqa: S106
                role=UserRole.participant,
            )
            session.add(cont)
            await session.flush()
        ctx["profile"].user_id = cont.id
        await session.flush()
        ctx["principal"] = ctx["principal"].model_copy(
            update={"email": ADRESA_DE_TEST, "user_id": cont.id}
        )
        return ctx["principal"]
    await session.flush()
    ctx["principal"] = ctx["principal"].model_copy(update={"email": ADRESA_DE_TEST})
    return ctx["principal"]


async def _al_doilea_om(session, ctx, *, adresa: str | None = None):
    """Inca un membru activ in acelasi proiect, cu profil si principal propriu."""
    sufix = uuid.uuid4().hex[:8]
    profil = ParticipantProfile(
        company_id=ctx["company"].id,
        full_name=f"Om obisnuit {sufix}",
        email=adresa or f"om_{sufix}@example.com",
    )
    session.add(profil)
    await session.flush()
    session.add(ProjectMembership(
        company_id=ctx["company"].id,
        project_id=ctx["project"].id,
        participant_profile_id=profil.id,
        active=True,
    ))
    await session.flush()
    from codrut.modules.practice.acord import AMPRENTA
    from codrut.modules.practice.models import PracticeConsent
    session.add(PracticeConsent(
        participant_profile_id=profil.id,
        project_id=ctx["project"].id,
        text_hash=AMPRENTA,
        accepted_at=datetime.now(UTC),
    ))
    await session.flush()
    principal = SessionPrincipal(
        user_id=uuid.uuid4(),
        email=profil.email,
        role=UserRole.participant,
        account_type=UserAccountType.registered,
        access_mode="account",
        consent_current=True,
        terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION,
        session_token=f"test-token-{sufix}",
    )
    return profil, principal


async def _curata_banii_contului_de_test(session) -> None:
    """Sterge rezervarile ramase de la rularile dinainte ale contului de test.

    Frana de 25 $ se numara pe TOATE proiectele si pe toata luna, iar `start_session` comite
    la mijloc (`service.py:629`) — deci `rollback`-ul de la finalul unui test nu sterge ce a
    scris. Fara curatarea asta, al doilea test al zilei ar porni cu punga altuia in spate.
    """
    from sqlalchemy import delete
    await session.execute(
        delete(PracticeBudgetReservation).where(
            PracticeBudgetReservation.session_id.in_(_sedintele_de_test())
        )
    )
    await session.commit()


def _sedintele_de_test():
    from codrut.modules.practice.budget import _sedintele_conturilor_de_test
    return _sedintele_conturilor_de_test()


async def _punga_cheltuita(session, program_settings_id) -> Decimal:
    """Cat s-a consumat din punga proiectului, asa cum o numara `reserve` azi."""
    from sqlalchemy import or_

    from codrut.modules.practice.budget import _cheltuiala, _sedintele_conturilor_de_test
    return (await session.execute(
        select(func.coalesce(func.sum(_cheltuiala()), Decimal("0.0000"))).where(
            PracticeBudgetReservation.program_settings_id == program_settings_id,
            or_(
                PracticeBudgetReservation.session_id.is_(None),
                PracticeBudgetReservation.session_id.not_in(_sedintele_conturilor_de_test()),
            ),
        )
    )).scalar_one()


# ------------------------------------------------------------------------- A · limita pe zi


@pytest.mark.asyncio
async def test_contul_de_test_trece_peste_limita_pe_zi() -> None:
    """Limita 2 pe zi: contul de test porneste si a 3-a sedinta."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session, max_sessions_per_day=2)
        principal = await _fa_din_el_contul_de_test(session, ctx)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)

        for _ in range(3):
            sedinta, _ = await service.start_session(
                principal=principal, project_id=ctx["project"].id, kind=SessionKind.roleplay
            )
            assert sedinta is not None

        pornite = (await session.execute(
            select(func.count(PracticeSession.id)).where(
                PracticeSession.participant_profile_id == ctx["profile"].id
            )
        )).scalar_one()
        assert pornite == 3

        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_un_cont_obisnuit_ramane_cu_limita_pe_zi() -> None:
    """Acelasi proiect, acelasi plafon: omul obisnuit e oprit la a 3-a. Plasa excepției."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session, max_sessions_per_day=2)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)

        for _ in range(2):
            await service.start_session(
                principal=ctx["principal"], project_id=ctx["project"].id,
                kind=SessionKind.roleplay,
            )
        with pytest.raises(DomainError) as exc:
            await service.start_session(
                principal=ctx["principal"], project_id=ctx["project"].id,
                kind=SessionKind.roleplay,
            )
        assert exc.value.code == "practice_daily_limit"

        await redis.aclose()
        await session.rollback()


# ------------------------------------------------------------------------ B · frana de 25 $


@pytest.mark.asyncio
async def test_contul_de_test_trece_peste_punga_proiectului_dar_nu_peste_25() -> None:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        await _curata_banii_contului_de_test(session)
        ctx = await create_test_context(session, usd_cap_per_participant=Decimal("3.00"))
        principal = await _fa_din_el_contul_de_test(session, ctx)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)
        sedinta, _ = await service.start_session(
            principal=principal, project_id=ctx["project"].id, kind=SessionKind.roleplay
        )

        # Peste punga proiectului (3.00), dar sub 25 → merge.
        id_rez = await reserve(
            session=session,
            program_settings_id=ctx["program_settings"].id,
            estimated_usd=Decimal("10.00"),
            cap_usd=Decimal("3.00"),
            session_id=sedinta.id,
        )
        assert id_rez is not None

        # Peste 25 in aceeasi luna → oprit, si se spune pe fata ca e frana contului de test.
        with pytest.raises(BudgetExceeded) as exc:
            await reserve(
                session=session,
                program_settings_id=ctx["program_settings"].id,
                estimated_usd=Decimal("20.00"),
                cap_usd=Decimal("3.00"),
                session_id=sedinta.id,
            )
        assert exc.value.code == "budget_exceeded"
        assert exc.value.details["cont_de_test"] is True
        assert exc.value.details["cap_usd"] == str(PLAFON_LUNAR_CONT_TEST_USD)

        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_rezervarile_din_luna_trecuta_nu_se_numara() -> None:
    """Frana e pe luna calendaristica: ce s-a consumat luna trecuta nu mai apasa."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        await _curata_banii_contului_de_test(session)
        ctx = await create_test_context(session)
        principal = await _fa_din_el_contul_de_test(session, ctx)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)
        sedinta, _ = await service.start_session(
            principal=principal, project_id=ctx["project"].id, kind=SessionKind.roleplay
        )

        acum = datetime.now(UTC)
        luna_trecuta = acum.replace(day=1) - timedelta(days=2)
        veche = PracticeBudgetReservation(
            program_settings_id=ctx["program_settings"].id,
            session_id=sedinta.id,
            reserved_usd=Decimal("24.00"),
            state=BudgetReservationState.settled,
            actual_usd=Decimal("24.00"),
        )
        session.add(veche)
        await session.flush()
        veche.created_at = luna_trecuta
        await session.flush()

        # 24 $ luna trecuta nu apasa pe luna asta: 20 $ acum trebuie sa treaca.
        assert await reserve(
            session=session,
            program_settings_id=ctx["program_settings"].id,
            estimated_usd=Decimal("20.00"),
            cap_usd=Decimal("3.00"),
            session_id=sedinta.id,
        ) is not None

        await redis.aclose()
        await session.rollback()


# ------------------------------------------------- C · punga celorlalti nu creste si nu scade


@pytest.mark.asyncio
async def test_punga_proiectului_nu_numara_contul_de_test() -> None:
    """2 membri activi (1 de test + 1 obisnuit), plafon 3.00 → punga = 3.00, nu 6.00."""
    async with SessionLocal() as session:
        ctx = await create_test_context(session, usd_cap_per_participant=Decimal("3.00"))
        await _fa_din_el_contul_de_test(session, ctx)
        await _al_doilea_om(session, ctx)

        activi = (await session.execute(
            select(func.count(ProjectMembership.id)).where(
                ProjectMembership.project_id == ctx["project"].id,
                ProjectMembership.active.is_(True),
            )
        )).scalar_one()
        assert activi == 2, "amandoi sunt membri activi"

        punga = await plafonul_programului(session, ctx["program_settings"])
        assert punga == Decimal("3.00"), "contul de test nu intra in socoteala"

        await session.rollback()


@pytest.mark.asyncio
async def test_consumul_contului_de_test_nu_scade_punga_celorlalti() -> None:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        await _curata_banii_contului_de_test(session)
        ctx = await create_test_context(
            session, usd_cap_per_participant=Decimal("3.00"), max_sessions_per_day=50,
        )
        principal_test = await _fa_din_el_contul_de_test(session, ctx)
        _, principal_om = await _al_doilea_om(session, ctx)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)

        sedinta_test, _ = await service.start_session(
            principal=principal_test, project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        inainte = await _punga_cheltuita(session, ctx["program_settings"].id)
        await reserve(
            session=session, program_settings_id=ctx["program_settings"].id,
            estimated_usd=Decimal("9.00"), cap_usd=Decimal("3.00"), session_id=sedinta_test.id,
        )
        dupa = await _punga_cheltuita(session, ctx["program_settings"].id)
        assert dupa == inainte, "cei 9 $ ai contului de test nu intra in punga proiectului"

        # Omul obisnuit isi gaseste punga intreaga.
        sedinta_om, _ = await service.start_session(
            principal=principal_om, project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        assert await reserve(
            session=session, program_settings_id=ctx["program_settings"].id,
            estimated_usd=Decimal("2.00"),
            cap_usd=await plafonul_programului(session, ctx["program_settings"]),
            session_id=sedinta_om.id,
        ) is not None

        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_omul_obisnuit_e_oprit_de_punga_lui() -> None:
    """Excepția nu slabeste plafonul nimanui: peste punga, omul obisnuit e oprit."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session, usd_cap_per_participant=Decimal("3.00"))
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)
        sedinta, _ = await service.start_session(
            principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        with pytest.raises(BudgetExceeded) as exc:
            await reserve(
                session=session, program_settings_id=ctx["program_settings"].id,
                estimated_usd=Decimal("99.00"), cap_usd=Decimal("3.00"),
                session_id=sedinta.id,
            )
        assert "cont_de_test" not in exc.value.details

        await redis.aclose()
        await session.rollback()


# ------------------------------------------------------------------------ D · drumul intreg


@pytest.mark.asyncio
async def test_cap_coada_peste_limita_pe_zi_pana_la_note() -> None:
    """Drumul omului, intreg: a 3-a sedinta peste limita → 10 replici → „Incheie" → note.

    Si ce nu trebuie sa se intample: punga proiectului ramane neatinsa, iar rezervarile
    sedintei se deconteaza toate.
    """
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        await _curata_banii_contului_de_test(session)
        ctx = await create_test_context(
            session, max_sessions_per_day=2, max_turns_per_session=14,
        )
        principal = await _fa_din_el_contul_de_test(session, ctx, cu_cont_legat=True)
        from codrut.modules.practice.models import ProjectCompetency
        for i, nume in enumerate(COMPETENTE):
            session.add(ProjectCompetency(project_id=ctx["project"].id, name=nume, order_index=i))
        await session.flush()

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis,
            generation_provider=FurnizorCuNote(settings), settings=settings,
        )

        # cele doua sedinte de azi, cat tine limita
        for _ in range(2):
            await service.start_session(
                principal=principal, project_id=ctx["project"].id, kind=SessionKind.roleplay
            )

        punga_inainte = await _punga_cheltuita(session, ctx["program_settings"].id)

        # a 3-a: peste limita, dar contul de test o porneste
        sedinta, _ = await service.start_session(
            principal=principal, project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        assert sedinta is not None

        for i in range(10):
            await service.add_participant_turn(
                principal=principal, session_id=sedinta.id,
                text=f"Replica {i} a omului, destul de lunga ca sa treaca pragul de semne.",
            )
        await service.end_session(principal=principal, session_id=sedinta.id)

        note = (await session.execute(
            select(func.count(CompetencyScore.id)).where(
                CompetencyScore.conversation_id == str(sedinta.id)
            )
        )).scalar_one()
        assert note > 0, "sedinta incheiata cu butonul a primit note"

        ramase = (await session.execute(
            select(func.count(PracticeBudgetReservation.id)).where(
                PracticeBudgetReservation.session_id == sedinta.id,
                PracticeBudgetReservation.state == BudgetReservationState.reserved,
            )
        )).scalar_one()
        assert ramase == 0, "nicio rezervare nu ramane atarnata"

        punga_dupa = await _punga_cheltuita(session, ctx["program_settings"].id)
        assert punga_dupa == punga_inainte, "punga proiectului n-a fost atinsa deloc"

        await redis.aclose()
        await session.rollback()


# --------------------------------------------------------------- E · frana de 25 $ atinsa


@pytest.mark.asyncio
async def test_la_25_dolari_atinsi_replica_omului_e_refuzata() -> None:
    """Ce vede omul: sedinta se deschide goala, iar primul lui mesaj primeste refuzul."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        await _curata_banii_contului_de_test(session)
        ctx = await create_test_context(session)
        principal = await _fa_din_el_contul_de_test(session, ctx)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)

        # o sedinta veche a contului de test, cu frana deja atinsa
        veche, _ = await service.start_session(
            principal=principal, project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        session.add(PracticeBudgetReservation(
            program_settings_id=ctx["program_settings"].id,
            session_id=veche.id,
            reserved_usd=PLAFON_LUNAR_CONT_TEST_USD,
            state=BudgetReservationState.settled,
            actual_usd=PLAFON_LUNAR_CONT_TEST_USD,
        ))
        await session.flush()

        sedinta, _ = await service.start_session(
            principal=principal, project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        # `_prima_replica` prinde refuzul si intoarce None: sedinta ramane deschisa, FARA salut.
        assert sedinta.state == SessionState.open

        with pytest.raises(BudgetExceeded) as exc:
            await service.add_participant_turn(
                principal=principal, session_id=sedinta.id, text="Buna ziua, incepem?",
            )
        assert exc.value.details["cont_de_test"] is True

        await redis.aclose()
        await session.rollback()


# ---------------------------------------------------------- F · sedintele „ca trainer"


@pytest.mark.asyncio
async def test_sedinta_ca_trainer_a_contului_de_test_se_numara_pe_frana_lui() -> None:
    """Corectia (d) a controlorului: si sedintele „ca trainer" apasa pe cei 25 $, nu pe punga."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        await _curata_banii_contului_de_test(session)
        ctx = await create_test_context(session)
        principal = await _fa_din_el_contul_de_test(session, ctx, cu_cont_legat=True)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)

        sedinta, _ = await service.start_session(
            principal=principal, project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        punga_inainte = await _punga_cheltuita(session, ctx["program_settings"].id)
        await reserve(
            session=session, program_settings_id=ctx["program_settings"].id,
            estimated_usd=Decimal("5.00"), cap_usd=Decimal("3.00"), session_id=sedinta.id,
        )
        assert await _punga_cheltuita(session, ctx["program_settings"].id) == punga_inainte

        # si frana lui a crescut
        with pytest.raises(BudgetExceeded):
            await reserve(
                session=session, program_settings_id=ctx["program_settings"].id,
                estimated_usd=Decimal("21.00"), cap_usd=Decimal("3.00"),
                session_id=sedinta.id,
            )

        await redis.aclose()
        await session.rollback()
