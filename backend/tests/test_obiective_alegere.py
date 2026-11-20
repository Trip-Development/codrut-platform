"""Alegerea obiectivului de aplicare — plicul 230 (L1-P1), testele 3, 4, 5 și 9.

Omul își alege un obiectiv din lista training-ului său; aplicația ține minte alegerea curentă și
istoricul la schimbare. Rutele sunt numai ale omului, pentru el însuși.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from codrut.api.dependencies import db_session
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.main import create_app
from codrut.modules.companies.models import (
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import UserAccountType, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.practice.models import PracticeProgramSettings, ProgramMode
from test_practice_router import make_test_client, setup_practice_context
from test_practice_session_flow import create_test_context

CATALOG = "comunicare-asertiva"


async def _obiectivele(session, catalog: str = CATALOG):
    from codrut.modules.practice.models import PracticeObjective

    return (await session.execute(
        select(PracticeObjective)
        .where(PracticeObjective.catalog == catalog, PracticeObjective.is_active.is_(True))
        .order_by(PracticeObjective.order_index)
    )).scalars().all()


async def _alegerile(session, profil_id, proiect_id):
    from codrut.modules.practice.models import PracticeObjectiveChoice

    return (await session.execute(
        select(PracticeObjectiveChoice).where(
            PracticeObjectiveChoice.participant_profile_id == profil_id,
            PracticeObjectiveChoice.project_id == proiect_id,
        ).order_by(PracticeObjectiveChoice.chosen_at)
    )).scalars().all()


async def _legat(session):
    ctx = await create_test_context(session)
    ctx["program_settings"].objective_catalog = CATALOG
    await session.flush()
    return ctx


def _principal(email: str) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=uuid.uuid4(), email=email, role=UserRole.participant,
        account_type=UserAccountType.registered, access_mode="account", consent_current=True,
        terms_accepted_at=datetime.now(UTC), terms_version=CURRENT_TERMS_VERSION,
        session_token=f"test-token-{uuid.uuid4().hex[:8]}",
    )


# ---- 3. lista obiectivelor, pe rute ----


async def _leaga_in_baza(project_id, catalog: str | None) -> None:
    async with SessionLocal() as session:
        setari = (await session.execute(
            select(PracticeProgramSettings).where(PracticeProgramSettings.project_id == project_id)
        )).scalar_one()
        setari.objective_catalog = catalog
        await session.commit()


@pytest.mark.asyncio
async def test_lista_pe_proiect_legat_are_cele_12() -> None:
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)
    await _leaga_in_baza(ctx["project"].id, CATALOG)

    async with make_test_client(ctx["participant"]) as client:
        raspuns = await client.get(f"/api/practice/projects/{ctx['project'].id}/obiective")
    assert raspuns.status_code == 200
    corp = raspuns.json()
    assert corp["catalog"] == CATALOG
    assert corp["catalog_name"] == "Comunicare asertivă"
    assert [o["nr"] for o in corp["obiective"]] == list(range(1, 13))
    assert set(corp["obiective"][0]) == {
        "id", "nr", "titlu", "situatie", "competente", "semn_de_reusita",
    }


@pytest.mark.asyncio
async def test_lista_pe_proiect_nelegat_e_goala() -> None:
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)

    async with make_test_client(ctx["participant"]) as client:
        raspuns = await client.get(f"/api/practice/projects/{ctx['project'].id}/obiective")
    assert raspuns.status_code == 200
    assert raspuns.json() == {"catalog": None, "catalog_name": None, "obiective": []}


@pytest.mark.asyncio
async def test_un_om_fara_profil_in_firma_si_trainerul_sunt_refuzati() -> None:
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)
    await _leaga_in_baza(ctx["project"].id, CATALOG)
    proiect = ctx["project"].id

    # un om fără profil în firma proiectului; un cont de trainer fără profil de participant
    for cine in ("other_participant", "trainer"):
        async with make_test_client(ctx[cine]) as client:
            for metoda, cale, corp in (
                ("GET", "obiective", None),
                ("GET", "obiectiv", None),
                ("POST", "obiectiv", {"objective_id": str(uuid.uuid4())}),
            ):
                raspuns = await client.request(
                    metoda, f"/api/practice/projects/{proiect}/{cale}", json=corp
                )
                assert raspuns.status_code == 400, (cine, metoda, cale)
                assert raspuns.json()["error"]["code"] == "participant_not_found", (cine, cale)


@pytest.mark.asyncio
async def test_fara_sesiune_401() -> None:
    app = create_app()

    async def fara_baza():
        yield None

    app.dependency_overrides[db_session] = fara_baza
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for metoda, cale in (("GET", "obiective"), ("GET", "obiectiv"), ("POST", "obiectiv")):
            raspuns = await client.request(
                metoda, f"/api/practice/projects/{uuid.uuid4()}/{cale}",
                json={"objective_id": str(uuid.uuid4())} if metoda == "POST" else None,
            )
            assert raspuns.status_code == 401, (metoda, cale)
            assert raspuns.json()["error"]["code"] == "http_401"


# ---- 4. alegerea și istoricul ----


@pytest.mark.asyncio
async def test_alegerea_schimbarea_si_istoricul() -> None:
    from codrut.modules.practice import objective_service as svc

    async with SessionLocal() as session:
        ctx = await _legat(session)
        cine, proiect = ctx["principal"], ctx["project"].id
        obiective = await _obiectivele(session)

        gol = await svc.alegerea_mea(session, cine, proiect)
        assert gol == {"curent": None, "prima_alegere_la": None, "istoric": []}

        prima = await svc.alege(session, cine, proiect, obiective[0].id)
        assert prima["curent"]["obiectiv"]["id"] == obiective[0].id
        assert prima["curent"]["obiectiv"]["nr"] == 1
        citita = await svc.alegerea_mea(session, cine, proiect)
        assert citita["curent"]["obiectiv"]["id"] == obiective[0].id
        assert citita["prima_alegere_la"] == citita["curent"]["aleasa_la"]

        # același obiectiv încă o dată: nimic nou
        await svc.alege(session, cine, proiect, obiective[0].id)
        assert len(await _alegerile(session, ctx["profile"].id, proiect)) == 1

        a_doua = await svc.alege(session, cine, proiect, obiective[3].id)
        assert a_doua["curent"]["obiectiv"]["id"] == obiective[3].id
        randuri = await _alegerile(session, ctx["profile"].id, proiect)
        assert len(randuri) == 2
        assert randuri[0].objective_id == obiective[0].id and randuri[0].replaced_at is not None
        assert randuri[1].objective_id == obiective[3].id and randuri[1].replaced_at is None
        istoric = a_doua["istoric"]
        assert [i["obiectiv_id"] for i in istoric] == [obiective[0].id, obiective[3].id]
        assert istoric[0]["inlocuita_la"] is not None and istoric[1]["inlocuita_la"] is None
        assert istoric[0]["titlu"] == obiective[0].title
        assert a_doua["prima_alegere_la"] == randuri[0].chosen_at
        await session.rollback()


@pytest.mark.asyncio
async def test_obiectiv_din_alt_catalog_inactiv_sau_proiect_nelegat_e_refuzat() -> None:
    from codrut.modules.practice import objective_service as svc
    from codrut.modules.practice.models import PracticeObjective

    async with SessionLocal() as session:
        ctx = await _legat(session)
        cine, proiect = ctx["principal"], ctx["project"].id
        strain = PracticeObjective(
            catalog=f"alt-catalog-{uuid.uuid4().hex[:6]}", catalog_name="Alt training",
            order_index=1, title="Un obiectiv de test.", situation="",
            success_sign="trece testul.", competencies=["Feedback constructiv"],
        )
        session.add(strain)
        obiective = await _obiectivele(session)
        inactiv = obiective[5]
        inactiv.is_active = False
        await session.flush()

        for obiectiv_id in (strain.id, inactiv.id, uuid.uuid4()):
            with pytest.raises(DomainError) as refuz:
                await svc.alege(session, cine, proiect, obiectiv_id)
            assert refuz.value.code == "obiectiv_nepermis"
        assert await _alegerile(session, ctx["profile"].id, proiect) == []

        ctx["program_settings"].objective_catalog = None
        await session.flush()
        with pytest.raises(DomainError) as refuz:
            await svc.alege(session, cine, proiect, obiective[0].id)
        assert refuz.value.code == "obiective_lipsa"
        assert await _alegerile(session, ctx["profile"].id, proiect) == []
        await session.rollback()


# ---- 5. fiecare om, alegerea lui ----


@pytest.mark.asyncio
async def test_doi_oameni_si_doua_proiecte_au_alegeri_separate() -> None:
    from codrut.modules.practice import objective_service as svc

    async with SessionLocal() as session:
        ctx = await _legat(session)
        proiect = ctx["project"]
        obiective = await _obiectivele(session)

        al_doilea = ParticipantProfile(
            company_id=ctx["company"].id, full_name="Participant Doi",
            email=f"doi_{uuid.uuid4().hex[:8]}@example.com",
        )
        session.add(al_doilea)
        await session.flush()
        session.add(ProjectMembership(
            company_id=ctx["company"].id, project_id=proiect.id,
            participant_profile_id=al_doilea.id, active=True,
        ))
        alt_proiect = CompanyProject(
            company_id=ctx["company"].id, name="Al doilea proiect", project_type="training",
            status=CompanyProjectStatus.active,
        )
        session.add(alt_proiect)
        await session.flush()
        session.add(PracticeProgramSettings(
            project_id=alt_proiect.id, mode=ProgramMode.training, theme_id=ctx["theme"].id,
            active_pack_id=ctx["pack"].id, is_enabled=True, objective_catalog=CATALOG,
        ))
        await session.flush()
        unu, doi = ctx["principal"], _principal(al_doilea.email)

        await svc.alege(session, unu, proiect.id, obiective[0].id)
        await svc.alege(session, doi, proiect.id, obiective[1].id)
        await svc.alege(session, unu, alt_proiect.id, obiective[2].id)

        assert (await svc.alegerea_mea(session, unu, proiect.id))["curent"]["obiectiv"]["nr"] == 1
        assert (await svc.alegerea_mea(session, doi, proiect.id))["curent"]["obiectiv"]["nr"] == 2
        pe_altul = await svc.alegerea_mea(session, unu, alt_proiect.id)
        assert pe_altul["curent"]["obiectiv"]["nr"] == 3
        assert len(pe_altul["istoric"]) == 1
        assert len((await svc.alegerea_mea(session, doi, proiect.id))["istoric"]) == 1
        await session.rollback()


# ---- 9. configurarea proiectului ----


@pytest.mark.asyncio
async def test_configurarea_leaga_catalogul_numai_cand_e_cerut() -> None:
    from codrut.modules.practice.schemas import PracticeSetupRequest
    from codrut.modules.practice.setup_service import PracticeSetupService

    assert PracticeSetupRequest(theme_id=uuid.uuid4()).objective_catalog is None
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        proiect, tema = ctx["project"].id, ctx["theme"].id
        serviciu = PracticeSetupService(session)

        fara = await serviciu.configure(project_id=proiect, theme_id=tema, competency_names=None)
        assert fara["objective_catalog"] is None

        cu = await serviciu.configure(
            project_id=proiect, theme_id=tema, competency_names=None, objective_catalog=CATALOG
        )
        assert cu["objective_catalog"] == CATALOG
        # fără câmp: legătura rămâne neatinsă
        din_nou = await serviciu.configure(project_id=proiect, theme_id=tema, competency_names=None)
        assert din_nou["objective_catalog"] == CATALOG
        assert (await serviciu.get_setup(proiect))["objective_catalog"] == CATALOG

        with pytest.raises(DomainError) as refuz:
            await serviciu.configure(
                project_id=proiect, theme_id=tema, competency_names=None,
                objective_catalog="nu-exista",
            )
        assert refuz.value.code == "objective_catalog_not_found"
        setari = ctx["program_settings"]
        await session.refresh(setari)
        assert setari.objective_catalog == CATALOG
        await session.rollback()

