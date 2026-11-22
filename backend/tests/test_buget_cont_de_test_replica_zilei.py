"""Replica zilei și contul de test: bugetul îl recunoaște după profil — plicul 250.

Datoria scrisă la CONTROLOR DUPĂ 236 (observația 2): rezervarea replicii zilei n-are ședință,
deci scutirea contului de test (plicul 173), sprijinită pe ședință, nu se aplica, iar pe un
proiect unde singurul membru e contul de test punga era 0 și replica era refuzată.
Acum rezervarea poartă profilul omului; contul de test merge pe frâna lui lunară (25 $), nu pe
punga proiectului, iar pentru oamenii obișnuiți nu se schimbă nimic.

Zero apeluri la modele: profesorul e `ProfesorFals`. Corecția 3: fiecare test care folosește
contul de test îi șterge rezervările la început și la sfârșit.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, or_, select

from codrut.core.database import SessionLocal
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.conturi_test import (
    CONTURI_DE_TEST,
    PLAFON_LUNAR_CONT_TEST_USD,
    e_cont_de_test,
)
from codrut.modules.practice.models import (
    BudgetReservationState,
    PracticeBudgetReservation,
    PracticeDailyReply,
    PracticeSession,
    SessionKind,
)
from test_replica_zilei_profesor import (
    COST_FALS,
    ProfesorFals,
    al_doilea_om,
    proiect_legat,
    trimite,
)

ADRESA = sorted(CONTURI_DE_TEST)[0]


def _profiluri_de_test_ca_in_plafon():
    """Copia subinterogării `profiluri_de_test` din `plafonul_programului` (budget.py, 173)."""
    return (
        select(ParticipantProfile.id)
        .outerjoin(User, User.id == ParticipantProfile.user_id)
        .where(
            or_(
                func.lower(User.email).in_(CONTURI_DE_TEST),
                func.lower(ParticipantProfile.email).in_(CONTURI_DE_TEST),
            )
        )
    )


async def _curata(session) -> None:
    """Rezervările contului de test, pe ambele drumuri (ședință / profil) — corecția 3."""
    from codrut.modules.practice.budget import _sedintele_conturilor_de_test

    conditii = [PracticeBudgetReservation.session_id.in_(_sedintele_conturilor_de_test())]
    if hasattr(PracticeBudgetReservation, "participant_profile_id"):
        conditii.append(
            PracticeBudgetReservation.participant_profile_id.in_(_profiluri_de_test_ca_in_plafon())
        )
    await session.execute(delete(PracticeBudgetReservation).where(or_(*conditii)))
    await session.commit()


async def _contul_de_test(session, ctx) -> None:
    ctx["profile"].email = ADRESA
    await session.flush()
    ctx["principal"] = ctx["principal"].model_copy(update={"email": ADRESA})


async def _rezervarile(session, program_settings_id) -> list[PracticeBudgetReservation]:
    return list((await session.execute(
        select(PracticeBudgetReservation)
        .where(PracticeBudgetReservation.program_settings_id == program_settings_id)
        .order_by(PracticeBudgetReservation.created_at)
    )).scalars().all())


async def _rezervare(session, ctx, usd: Decimal, **unde) -> None:
    session.add(PracticeBudgetReservation(
        program_settings_id=ctx["program_settings"].id, reserved_usd=usd, actual_usd=usd,
        state=BudgetReservationState.settled, **unde,
    ))
    await session.flush()


async def _sedinta(session, ctx, profil_id) -> PracticeSession:
    sed = PracticeSession(program_settings_id=ctx["program_settings"].id,
                          participant_profile_id=profil_id, pack_id=ctx["pack"].id,
                          kind=SessionKind.roleplay)
    session.add(sed)
    await session.flush()
    return sed


async def _replici_zilei(session, profil_id) -> int:
    return (await session.execute(
        select(func.count(PracticeDailyReply.id))
        .where(PracticeDailyReply.participant_profile_id == profil_id)
    )).scalar_one()


# ---- 1. proiectul demo ----


@pytest.mark.asyncio
async def test_1_proiectul_demo_contul_de_test_primeste_replica_zilei() -> None:
    async with SessionLocal() as session:
        await _curata(session)
        try:
            ctx = await proiect_legat(session)
            await _contul_de_test(session, ctx)
            await session.commit()
            profesor = ProfesorFals()
            await trimite(session, ctx, profesor=profesor)
            assert len(profesor.cereri) == 1
            r = (await _rezervarile(session, ctx["program_settings"].id))[-1]
            assert r.session_id is None
            assert r.participant_profile_id == ctx["profile"].id
            assert r.state == BudgetReservationState.settled
            assert r.actual_usd == COST_FALS.quantize(Decimal("0.0001"))
        finally:
            await session.rollback()
            await _curata(session)


# ---- 2. frâna lunară îl oprește ----


@pytest.mark.asyncio
async def test_2_frana_lunara_opreste_replica_zilei() -> None:
    from codrut.modules.practice.budget import BudgetExceeded

    async with SessionLocal() as session:
        await _curata(session)
        try:
            ctx = await proiect_legat(session)
            await _contul_de_test(session, ctx)
            profil_id = ctx["profile"].id
            sed = await _sedinta(session, ctx, profil_id)
            await _rezervare(session, ctx, PLAFON_LUNAR_CONT_TEST_USD - Decimal("0.0001"),
                             session_id=sed.id)
            await session.commit()
            profesor = ProfesorFals()
            with pytest.raises(BudgetExceeded) as e:
                await trimite(session, ctx, profesor=profesor)
            assert e.value.details["cont_de_test"] is True
            assert profesor.cereri == []
            await session.rollback()
            assert await _replici_zilei(session, profil_id) == 0
        finally:
            await session.rollback()
            await _curata(session)


# ---- 3. replica zilei se numără în frâna lunară ----


@pytest.mark.asyncio
async def test_3_replica_zilei_se_numara_in_frana_lunara() -> None:
    from codrut.modules.practice.budget import BudgetExceeded, reserve

    async with SessionLocal() as session:
        await _curata(session)
        try:
            ctx = await proiect_legat(session)
            await _contul_de_test(session, ctx)
            await _rezervare(session, ctx, PLAFON_LUNAR_CONT_TEST_USD - Decimal("0.0001"),
                             participant_profile_id=ctx["profile"].id)
            sed = await _sedinta(session, ctx, ctx["profile"].id)
            with pytest.raises(BudgetExceeded) as e:
                await reserve(session, ctx["program_settings"].id, Decimal("0.01"),
                              Decimal("100"), session_id=sed.id)
            assert e.value.details["cont_de_test"] is True
        finally:
            await session.rollback()
            await _curata(session)


# ---- 4. punga celorlalți nu scade ----


@pytest.mark.asyncio
async def test_4_punga_celorlalti_nu_scade() -> None:
    from codrut.modules.practice.budget import plafonul_programului, reserve

    async with SessionLocal() as session:
        await _curata(session)
        try:
            ctx = await proiect_legat(session)
            await al_doilea_om(session, ctx)
            await _contul_de_test(session, ctx)
            await session.commit()
            await trimite(session, ctx, profesor=ProfesorFals())
            punga = await plafonul_programului(session, ctx["program_settings"])
            assert punga == ctx["program_settings"].usd_cap_per_participant
            # omul obișnuit poate cheltui toată punga: replica de test nu s-a numărat în ea
            await reserve(session, ctx["program_settings"].id, punga, punga, session_id=None)
        finally:
            await session.rollback()
            await _curata(session)


# ---- 5. capcana lui NULL ----


@pytest.mark.asyncio
@pytest.mark.parametrize("cu_sedinta", [False, True])
async def test_5_capcana_lui_null_punga_ramane_numarata(cu_sedinta: bool) -> None:
    from codrut.modules.practice.budget import BudgetExceeded, plafonul_programului, reserve

    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        punga = await plafonul_programului(session, ctx["program_settings"])
        unde = {}
        if cu_sedinta:
            unde["session_id"] = (await _sedinta(session, ctx, ctx["profile"].id)).id
        await _rezervare(session, ctx, punga, **unde)
        with pytest.raises(BudgetExceeded) as e:
            await reserve(session, ctx["program_settings"].id, Decimal("0.01"), punga,
                          session_id=None)
        assert "cont_de_test" not in e.value.details
        await session.rollback()


# ---- 6. nicio ușă pentru conturi reale ----


@pytest.mark.asyncio
async def test_6a_varianta_plus_lidera_e_refuzata() -> None:
    from codrut.modules.practice.budget import BudgetExceeded

    async with SessionLocal() as session:
        ctx = await proiect_legat(session, usd_cap_per_participant=Decimal("0"))
        varianta = ADRESA.replace("@", "+lidera@")
        ctx["profile"].email = varianta
        principal = ctx["principal"].model_copy(update={"email": varianta})
        await session.commit()
        profesor = ProfesorFals()
        with pytest.raises(BudgetExceeded) as e:
            await trimite(session, ctx, profesor=profesor, principal=principal)
        assert "cont_de_test" not in e.value.details and profesor.cereri == []
        await session.rollback()


async def _profil_legat_de_alt_cont(session, ctx):
    """Profil cu adresa contului de test scrisă pe el, dar legat de un cont cu altă adresă."""
    cont = User(id=uuid.uuid4(), email=f"altcineva_{uuid.uuid4().hex[:8]}@example.com",
                password_hash="x", role=UserRole.participant)  # noqa: S106
    session.add(cont)
    await session.flush()
    ctx["profile"].email = ADRESA
    ctx["profile"].user_id = cont.id
    await session.flush()
    return ctx["principal"].model_copy(update={"email": cont.email, "user_id": cont.id})


@pytest.mark.asyncio
async def test_6b_profil_cu_adresa_de_test_legat_de_alt_cont_e_refuzat() -> None:
    from codrut.modules.practice.budget import BudgetExceeded

    async with SessionLocal() as session:
        ctx = await proiect_legat(session, usd_cap_per_participant=Decimal("0"))
        principal = await _profil_legat_de_alt_cont(session, ctx)
        await session.commit()
        profesor = ProfesorFals()
        with pytest.raises(BudgetExceeded) as e:
            await trimite(session, ctx, profesor=profesor, principal=principal)
        assert "cont_de_test" not in e.value.details and profesor.cereri == []
        await session.rollback()


@pytest.mark.asyncio
async def test_6b_pe_punga_mai_mare_ca_zero_intra_in_punga_proiectului() -> None:
    # corecția 6: profilul (b) e om obișnuit — replica lui intră în punga proiectului
    from codrut.modules.practice.budget import BudgetExceeded, plafonul_programului, reserve

    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        # `plafonul_programului` (neatins) nu numără profilul (b): adresa de test e scrisă pe el.
        # Ca punga să fie > 0, mai e un om obișnuit în proiect (diferența din corecția 6).
        await al_doilea_om(session, ctx)
        principal = await _profil_legat_de_alt_cont(session, ctx)
        await session.commit()
        await trimite(session, ctx, profesor=ProfesorFals(), principal=principal)
        r = (await _rezervarile(session, ctx["program_settings"].id))[-1]
        assert r.participant_profile_id == ctx["profile"].id and r.session_id is None
        punga = await plafonul_programului(session, ctx["program_settings"])
        assert punga == ctx["program_settings"].usd_cap_per_participant
        with pytest.raises(BudgetExceeded) as e:
            await reserve(session, ctx["program_settings"].id, punga, punga, session_id=None)
        assert "cont_de_test" not in e.value.details
        await session.rollback()


@pytest.mark.asyncio
async def test_6c_campurile_in_plus_din_cerere_nu_schimba_profilul(monkeypatch) -> None:
    from codrut.modules.practice import router as ruta
    from codrut.modules.practice.models import PracticeProgramSettings
    from test_practice_router import make_test_client, setup_practice_context

    monkeypatch.setattr(ruta, "build_generation_provider", lambda _s: ProfesorFals())
    async with SessionLocal() as session:
        await _curata(session)
    try:
        async with SessionLocal() as session:
            ctx = await setup_practice_context(session)
            test_ctx = await proiect_legat(session)
            await _contul_de_test(session, test_ctx)
            profil_de_test = test_ctx["profile"].id
            setari = (await session.execute(
                select(PracticeProgramSettings)
                .where(PracticeProgramSettings.project_id == ctx["project"].id)
            )).scalar_one()
            setari.objective_catalog = "comunicare-asertiva"
            setari.usd_cap_per_participant = Decimal("0")
            setari_id = setari.id
            await session.commit()
        proiect = ctx["project"].id
        async with make_test_client(ctx["participant"]) as omul:
            stare = (await omul.get(f"/api/practice/projects/{proiect}/replica-zilei")).json()
            r = await omul.post(
                f"/api/practice/projects/{proiect}/replica-zilei",
                json={"situation_id": stare["situatie"]["id"], "replica": "Îți spun deschis.",
                      "participant_profile_id": str(profil_de_test),
                      "session_id": None},
            )
        assert r.status_code != 200
        assert r.json()["error"]["code"] == "budget_exceeded"
        assert "cont_de_test" not in (r.json()["error"].get("details") or {})
        async with SessionLocal() as session:
            rezervari = await _rezervarile(session, setari_id)
            assert all(x.participant_profile_id != profil_de_test for x in rezervari)
    finally:
        async with SessionLocal() as session:
            await _curata(session)


# ---- 7. aceeași regulă ----


@pytest.mark.asyncio
async def test_7_aceeasi_regula_ca_plafonul_programului() -> None:
    from codrut.modules.practice.budget import _profilurile_conturilor_de_test

    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        companie = ctx["company"].id
        cont_test = (await session.execute(
            select(User).where(User.email == ADRESA))).scalars().first()
        if cont_test is None:
            cont_test = User(id=uuid.uuid4(), email=ADRESA, password_hash="x",  # noqa: S106
                             role=UserRole.participant)
            session.add(cont_test)
            await session.flush()

        def profil(email, user_id=None):
            p = ParticipantProfile(company_id=companie, full_name=f"P {uuid.uuid4().hex[:6]}",
                                   email=email, user_id=user_id)
            session.add(p)
            return p

        legat = profil(f"oricare_{uuid.uuid4().hex[:6]}@example.com", cont_test.id)
        nelegat = profil(ADRESA)
        lidera = profil(ADRESA.replace("@", "+lidera@"))
        obisnuit = profil(f"om_{uuid.uuid4().hex[:6]}@example.com")
        await session.flush()
        ctx_b = await proiect_legat(session)  # altă companie: adresa e unică pe companie
        await _profil_legat_de_alt_cont(session, ctx_b)
        b_id = ctx_b["profile"].id
        ale_mele = {legat.id, nelegat.id, lidera.id, obisnuit.id}
        nou = set((await session.execute(_profilurile_conturilor_de_test())).scalars().all())
        vechi = set((await session.execute(_profiluri_de_test_ca_in_plafon())).scalars().all())
        assert nou & ale_mele == vechi & ale_mele == {legat.id, nelegat.id}
        # cazul (b): profil cu adresa de test, legat de alt cont — diferența, scrisă în raport
        assert b_id not in nou
        assert b_id in vechi
        await session.rollback()


# ---- 8. ședințele nu se schimbă ----


@pytest.mark.asyncio
async def test_8_cu_sedinta_profilul_nu_se_citeste() -> None:
    from codrut.modules.practice.budget import BudgetExceeded, plafonul_programului, reserve

    async with SessionLocal() as session:
        await _curata(session)
        try:
            ctx = await proiect_legat(session)
            sed = await _sedinta(session, ctx, ctx["profile"].id)
            test_ctx = await proiect_legat(session)
            await _contul_de_test(session, test_ctx)
            punga = await plafonul_programului(session, ctx["program_settings"])
            await _rezervare(session, ctx, punga)
            with pytest.raises(BudgetExceeded) as e:
                await reserve(session, ctx["program_settings"].id, Decimal("0.01"), punga,
                              session_id=sed.id, participant_profile_id=test_ctx["profile"].id)
            assert "cont_de_test" not in e.value.details
        finally:
            await session.rollback()
            await _curata(session)


# ---- 9. funcția nouă ----


@pytest.mark.asyncio
async def test_9_contul_de_test_al_profilului() -> None:
    from codrut.modules.practice.conturi_test import contul_de_test_al_profilului

    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        companie = ctx["company"].id
        assert await contul_de_test_al_profilului(session, None) is None
        assert await contul_de_test_al_profilului(session, uuid.uuid4()) is None
        lidera = ParticipantProfile(company_id=companie, full_name="L",
                                    email=ADRESA.replace("@", "+lidera@"))
        nelegat = ParticipantProfile(company_id=companie, full_name="N",
                                     email=f"  {ADRESA.upper()} ")
        session.add_all([lidera, nelegat])
        await session.flush()
        assert await contul_de_test_al_profilului(session, lidera.id) is None
        # adresa scrisă pe profil e adusă la forma ei (litere mici, fără spații) de model
        assert e_cont_de_test(await contul_de_test_al_profilului(session, nelegat.id))
        cont_test = (await session.execute(
            select(User).where(User.email == ADRESA))).scalars().first()
        if cont_test is None:
            cont_test = User(id=uuid.uuid4(), email=ADRESA, password_hash="x",  # noqa: S106
                             role=UserRole.participant)
            session.add(cont_test)
            await session.flush()
        legat = ParticipantProfile(company_id=companie, full_name="T",
                                   email="oricare@example.com", user_id=cont_test.id)
        session.add(legat)
        await session.flush()
        assert await contul_de_test_al_profilului(session, legat.id) == ADRESA
        ctx_b = await proiect_legat(session)  # altă companie: adresa e unică pe companie
        await _profil_legat_de_alt_cont(session, ctx_b)
        assert await contul_de_test_al_profilului(session, ctx_b["profile"].id) is None
        await session.rollback()
