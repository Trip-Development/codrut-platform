"""Al doilea catalog de obiective: Feedback — plicul 235, testele 1 și 2.

Cele 10 obiective pentru trainingul de Feedback sunt aprobate de Andrei (panoul, 20 nov 2026,
[m03-feedback]; titlul 5 corectat 15:50). Intră prin migrarea 0072, separat de cele 12 de
comunicare asertivă. Niciun proiect nu se leagă de ele în migrare.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from test_practice_router import make_test_client, setup_practice_context
from test_practice_session_flow import create_test_context

# shasum -a 256 pe SPEC-CODY/FISE/L1-obiective-feedback.json
AMPRENTA_FEEDBACK = "00a8b45f06d2d4f10f911fd2c115eb55c83160ea9561f089be1913e5ea6afd8c"


def _json(cheie: str) -> dict:
    from codrut.modules.practice import obiective

    return json.loads((obiective.DOSAR / f"{cheie}.json").read_text(encoding="utf-8"))


def test_amprenta_feedback_e_fixata() -> None:
    from codrut.modules.practice import obiective

    continut = (obiective.DOSAR / "feedback.json").read_bytes()
    assert hashlib.sha256(continut).hexdigest() == AMPRENTA_FEEDBACK


async def _randurile(session, catalog: str):
    from codrut.modules.practice.models import PracticeObjective

    return (await session.execute(
        select(PracticeObjective)
        .where(PracticeObjective.catalog == catalog, PracticeObjective.is_active.is_(True))
        .order_by(PracticeObjective.order_index)
    )).scalars().all()


def _la_fel(randuri, date: dict) -> None:
    assert [r.order_index for r in randuri] == list(range(1, len(date["obiective"]) + 1))
    for rand, o in zip(randuri, date["obiective"], strict=True):
        assert rand.catalog_name == date["nume"]
        assert rand.title == o["titlu"]
        assert rand.situation == o["situatie"]
        assert rand.success_sign == o["semn_de_reusita"]
        assert rand.competencies == o["competente"]


# ---- 1. catalogul, pe baza migrată ----


@pytest.mark.asyncio
async def test_baza_migrata_are_10_la_feedback_si_tot_12_la_comunicare() -> None:
    async with SessionLocal() as session:
        feedback = await _randurile(session, "feedback")
        assert len(feedback) == 10
        _la_fel(feedback, _json("feedback"))
        comunicare = await _randurile(session, "comunicare-asertiva")
        assert len(comunicare) == 12
        _la_fel(comunicare, _json("comunicare-asertiva"))


@pytest.mark.asyncio
async def test_incarcarea_de_doua_ori_nu_dubleaza_nimic() -> None:
    from codrut.modules.practice.obiective import citeste_catalog, incarca_catalog

    async with SessionLocal() as session:
        for _ in range(2):
            scrise = await session.run_sync(
                lambda s: incarca_catalog(s.connection(), citeste_catalog("feedback"))
            )
            assert scrise == 10
            assert len(await _randurile(session, "feedback")) == 10
            assert len(await _randurile(session, "comunicare-asertiva")) == 12
        await session.rollback()


# ---- 2. separarea cataloagelor ----


async def _id_uri(catalog: str) -> list[uuid.UUID]:
    async with SessionLocal() as session:
        return [r.id for r in await _randurile(session, catalog)]


async def _leaga_prin_setup(ctx, catalog: str) -> None:
    async with SessionLocal() as session:
        from codrut.modules.practice.models import PracticeProgramSettings

        tema = (await session.execute(
            select(PracticeProgramSettings.theme_id)
            .where(PracticeProgramSettings.project_id == ctx["project"].id)
        )).scalar_one()
    async with make_test_client(ctx["trainer"]) as client:
        raspuns = await client.put(
            f"/api/practice/projects/{ctx['project'].id}/setup",
            json={"theme_id": str(tema), "objective_catalog": catalog},
        )
    assert raspuns.status_code == 200, raspuns.text
    assert raspuns.json()["objective_catalog"] == catalog


async def _alegeri_pe_proiect(proiect_id) -> int:
    from codrut.modules.practice.models import PracticeObjectiveChoice

    async with SessionLocal() as session:
        return len((await session.execute(
            select(PracticeObjectiveChoice).where(PracticeObjectiveChoice.project_id == proiect_id)
        )).scalars().all())


@pytest.mark.asyncio
async def test_fiecare_proiect_vede_numai_lista_lui_si_alege_numai_din_ea() -> None:
    async with SessionLocal() as session:
        cu_feedback = await setup_practice_context(session)
    async with SessionLocal() as session:
        cu_comunicare = await setup_practice_context(session)
    await _leaga_prin_setup(cu_feedback, "feedback")
    await _leaga_prin_setup(cu_comunicare, "comunicare-asertiva")
    id_feedback = await _id_uri("feedback")
    id_comunicare = await _id_uri("comunicare-asertiva")

    for ctx, catalog, nume, numar in (
        (cu_feedback, "feedback", "Feedback", 10),
        (cu_comunicare, "comunicare-asertiva", "Comunicare asertivă", 12),
    ):
        async with make_test_client(ctx["participant"]) as client:
            raspuns = await client.get(f"/api/practice/projects/{ctx['project'].id}/obiective")
        assert raspuns.status_code == 200
        corp = raspuns.json()
        assert corp["catalog"] == catalog
        assert corp["catalog_name"] == nume
        assert [o["nr"] for o in corp["obiective"]] == list(range(1, numar + 1))

    # un obiectiv din celălalt catalog: refuzat, nimic scris (în ambele sensuri)
    for ctx, strain in ((cu_comunicare, id_feedback[0]), (cu_feedback, id_comunicare[0])):
        async with make_test_client(ctx["participant"]) as client:
            raspuns = await client.post(
                f"/api/practice/projects/{ctx['project'].id}/obiectiv",
                json={"objective_id": str(strain)},
            )
        assert raspuns.status_code == 400
        assert raspuns.json()["error"]["code"] == "obiectiv_nepermis"
        assert await _alegeri_pe_proiect(ctx["project"].id) == 0


@pytest.mark.asyncio
async def test_un_om_cu_un_proiect_din_fiecare_are_doua_alegeri_separate() -> None:
    from codrut.modules.companies.models import (
        CompanyProject,
        CompanyProjectStatus,
        ProjectMembership,
    )
    from codrut.modules.practice import objective_service as svc
    from codrut.modules.practice.models import PracticeProgramSettings, ProgramMode

    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        ctx["program_settings"].objective_catalog = "comunicare-asertiva"
        alt_proiect = CompanyProject(
            company_id=ctx["company"].id, name="Proiectul de feedback", project_type="training",
            status=CompanyProjectStatus.active,
        )
        session.add(alt_proiect)
        await session.flush()
        session.add(ProjectMembership(
            company_id=ctx["company"].id, project_id=alt_proiect.id,
            participant_profile_id=ctx["profile"].id, active=True,
        ))
        session.add(PracticeProgramSettings(
            project_id=alt_proiect.id, mode=ProgramMode.training, theme_id=ctx["theme"].id,
            active_pack_id=ctx["pack"].id, is_enabled=True, objective_catalog="feedback",
        ))
        await session.flush()
        cine = ctx["principal"]
        comunicare = await _randurile(session, "comunicare-asertiva")
        feedback = await _randurile(session, "feedback")

        await svc.alege(session, cine, ctx["project"].id, comunicare[2].id)
        await svc.alege(session, cine, alt_proiect.id, feedback[4].id)
        with pytest.raises(DomainError) as refuz:
            await svc.alege(session, cine, alt_proiect.id, comunicare[0].id)
        assert refuz.value.code == "obiectiv_nepermis"

        pe_comunicare = await svc.alegerea_mea(session, cine, ctx["project"].id)
        pe_feedback = await svc.alegerea_mea(session, cine, alt_proiect.id)
        assert pe_comunicare["curent"]["obiectiv"]["id"] == comunicare[2].id
        assert pe_feedback["curent"]["obiectiv"]["id"] == feedback[4].id
        assert len(pe_comunicare["istoric"]) == 1 and len(pe_feedback["istoric"]) == 1
        await session.rollback()
