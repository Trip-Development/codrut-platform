"""„O replică pe zi”: cine are voie — plicul 236 (L2-P1), testul 5.

Aceleași reguli ca la pornirea unei ședințe; rutele sunt numai ale omului, pentru el însuși.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from codrut.api.dependencies import db_session
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.main import create_app
from codrut.modules.practice.models import PracticeConsent, PracticeProgramSettings
from test_practice_router import make_test_client, setup_practice_context
from test_replica_zilei_profesor import ACUM, ProfesorFals, proiect_legat, trimite

CAI = (("GET", None), ("POST", {"situation_id": str(uuid.uuid4()), "replica": "Ceva."}))


@pytest.mark.asyncio
async def test_fara_sesiune_401() -> None:
    app = create_app()

    async def fara_baza():
        yield None

    app.dependency_overrides[db_session] = fara_baza
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for metoda, corp in CAI:
            r = await client.request(
                metoda, f"/api/practice/projects/{uuid.uuid4()}/replica-zilei", json=corp
            )
            assert r.status_code == 401, metoda


@pytest.mark.asyncio
async def test_om_fara_profil_si_trainerul_sunt_refuzati() -> None:
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)
    async with SessionLocal() as session:
        setari = (await session.execute(
            select(PracticeProgramSettings)
            .where(PracticeProgramSettings.project_id == ctx["project"].id)
        )).scalar_one()
        setari.objective_catalog = "comunicare-asertiva"
        await session.commit()
    for cine in ("other_participant", "trainer"):
        async with make_test_client(ctx[cine]) as client:
            for metoda, corp in CAI:
                r = await client.request(
                    metoda, f"/api/practice/projects/{ctx['project'].id}/replica-zilei",
                    json=corp,
                )
                assert r.status_code == 400, (cine, metoda)
                assert r.json()["error"]["code"] == "participant_not_found", (cine, metoda)


async def _refuzul(session, ctx) -> list[str]:
    from codrut.modules.practice import replica_zilei as rz

    coduri = []
    with pytest.raises(DomainError) as e:
        await rz.starea_zilei(session, ctx["principal"], ctx["project"].id, acum=ACUM)
    coduri.append(e.value.code)
    profesor = ProfesorFals()
    with pytest.raises(DomainError) as e:
        await trimite(session, ctx, profesor=profesor, situatie=uuid.uuid4())
    coduri.append(e.value.code)
    assert profesor.cereri == []
    return coduri


@pytest.mark.asyncio
async def test_membru_inactiv_cody_oprit_si_fara_acord() -> None:
    async with SessionLocal() as session:
        ctx = await proiect_legat(session, membership_active=False)
        await session.commit()
        assert await _refuzul(session, ctx) == ["not_project_member"] * 2

        ctx = await proiect_legat(session, is_enabled=False)
        await session.commit()
        assert await _refuzul(session, ctx) == ["practice_not_enabled"] * 2

        ctx = await proiect_legat(session)
        await session.execute(delete(PracticeConsent).where(
            PracticeConsent.participant_profile_id == ctx["profile"].id
        ))
        await session.commit()
        assert await _refuzul(session, ctx) == ["acord_lipsa"] * 2
