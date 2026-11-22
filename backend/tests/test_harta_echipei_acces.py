"""Harta echipei — cine are voie s-o vadă (plicul 240, §6, cu ajustarea după 242).

Paza e cea din 242: trainerul alocat proiectului sau proprietarul platformei. Trainerul
nealocat (chiar `owner` în firmă) și trainerul altui proiect primesc 403; participantul 403;
fără sesiune 401; proiect inexistent 404. Ruta numai citește.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from codrut.api.dependencies import db_session
from codrut.core.database import SessionLocal
from codrut.main import create_app
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ProjectTrainer,
)
from codrut.modules.identity.models import User, UserRole
from harta_echipei_fixturi import (
    COMPETENTE,
    PAROLA_DE_TEST,
    alege,
    nota,
    principal,
    proiect_cu_oameni,
    sedinta,
)
from test_practice_router import make_test_client


def _cale(project_id) -> str:
    return f"/api/practice/projects/{project_id}/harta-echipei"


async def _get(cine, project_id):
    async with make_test_client(cine) as client:
        return await client.get(_cale(project_id))


async def _cont(session, marca: str, rol: str, *, proprietar: bool = False) -> User:
    u = User(email=f"{rol}-{marca}@example.com", password_hash=PAROLA_DE_TEST,
             role=UserRole.trainer)
    if proprietar:
        u.is_platform_owner = True
    session.add(u)
    await session.flush()
    return u


@pytest.mark.asyncio
async def test_fara_sesiune_401() -> None:
    app = create_app()

    async def fara_baza():
        yield None

    app.dependency_overrides[db_session] = fara_baza
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(_cale(uuid.uuid4()))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "http_401"


@pytest.mark.asyncio
async def test_participantul_403() -> None:
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 1)
    om = ctx["oameni"][0]
    r = await _get(principal(om["user_id"], om["cont_email"], UserRole.participant),
                   ctx["project"].id)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_trainer_nealocat_chiar_owner_in_firma_si_trainerul_altui_proiect_403() -> None:
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 1)
        marca = uuid.uuid4().hex[:8]
        nealocat = await _cont(s, marca, "nealocat")
        s.add(CompanyMembership(company_id=ctx["company"].id, user_id=nealocat.id,
                                role=CompanyMembershipRole.owner))
        strain = await _cont(s, marca, "strain")
        alta = Company(name=f"Alta firma {marca}")
        s.add(alta)
        await s.flush()
        alt_proiect = CompanyProject(company_id=alta.id, name=f"Alt proiect {marca}",
                                     project_type="training",
                                     status=CompanyProjectStatus.active)
        s.add(alt_proiect)
        await s.flush()
        s.add(ProjectTrainer(project_id=alt_proiect.id, user_id=strain.id))
        await s.commit()
        conturi = [(nealocat.id, nealocat.email), (strain.id, strain.email)]
    for user_id, email in conturi:
        r = await _get(principal(user_id, email), ctx["project"].id)
        assert r.status_code == 403, (email, r.text)
        assert r.json()["error"]["code"] == "not_project_trainer"


@pytest.mark.asyncio
async def test_trainerul_alocat_si_proprietarul_nealocat_200() -> None:
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 1)
        proprietar = await _cont(s, uuid.uuid4().hex[:8], "proprietar", proprietar=True)
        await s.commit()
        p = principal(proprietar.id, proprietar.email)
    r = await _get(ctx["trainer"], ctx["project"].id)
    assert r.status_code == 200, r.text
    assert r.json()["project_id"] == str(ctx["project"].id)
    r = await _get(p, ctx["project"].id)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_proiect_inexistent_404() -> None:
    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 0)
    r = await _get(ctx["trainer"], uuid.uuid4())
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "project_not_found"


@pytest.mark.asyncio
async def test_ruta_nu_scrie_nimic() -> None:
    from codrut.modules.practice.models import (
        CompetencyScore,
        PracticeBudgetReservation,
        PracticeObjectiveChoice,
        PracticeSession,
        PracticeTurn,
    )

    tabele = (PracticeSession, PracticeTurn, CompetencyScore, PracticeObjectiveChoice,
              PracticeBudgetReservation)

    async def _numere():
        async with SessionLocal() as s:
            return [(await s.execute(select(func.count()).select_from(t))).scalar_one()
                    for t in tabele]

    async with SessionLocal() as s:
        ctx = await proiect_cu_oameni(s, 5)
        start = datetime.now(UTC) - timedelta(days=3)
        for om in ctx["oameni"]:
            sid = await sedinta(s, ctx, om, start)
            await nota(s, ctx, om, sid, COMPETENTE[0], 60, start)
            await alege(s, ctx, om, 3)
        await s.commit()
    inainte = await _numere()
    r = await _get(ctx["trainer"], ctx["project"].id)
    assert r.status_code == 200, r.text
    assert await _numere() == inainte
