"""Pornirea „pe obiectiv” — plicul 244, §4.3.

Serverul ia alegerea curentă a omului (niciun id de obiectiv nu vine din afară), leagă sesiunea de
obiectiv și o ține pe el chiar dacă omul își schimbă alegerea între timp. Trainerul nu are
obiectiv; quizul și strategia nu pornesc pe obiectiv.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from test_practice_router import make_test_client, setup_practice_context

CATALOG = "comunicare-asertiva"


async def _obiectivele(session):
    from codrut.modules.practice.models import PracticeObjective

    return (await session.execute(
        select(PracticeObjective)
        .where(PracticeObjective.catalog == CATALOG, PracticeObjective.is_active.is_(True))
        .order_by(PracticeObjective.order_index)
    )).scalars().all()


async def _context(*, cu_catalog: bool = True) -> dict:
    from codrut.modules.practice.models import PracticeProgramSettings

    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)
        if cu_catalog:
            setari = (await session.execute(
                select(PracticeProgramSettings)
                .where(PracticeProgramSettings.project_id == ctx["project"].id)
            )).scalar_one()
            setari.objective_catalog = CATALOG
            await session.commit()
        ctx["obiective"] = [o.id for o in await _obiectivele(session)]
    return ctx


async def _alege(client, ctx, obiectiv_id) -> None:
    r = await client.post(f"/api/practice/projects/{ctx['project'].id}/obiectiv",
                          json={"objective_id": str(obiectiv_id)})
    assert r.status_code == 200, r.text


async def _porneste(client, ctx, *, kind="roleplay", pe_obiectiv=None):
    corp = {"project_id": str(ctx["project"].id), "kind": kind}
    if pe_obiectiv is not None:
        corp["pe_obiectiv"] = pe_obiectiv
    return await client.post("/api/practice/sessions", json=corp)


async def _sesiunile(ctx):
    from codrut.modules.practice.models import PracticeSession

    async with SessionLocal() as session:
        return (await session.execute(
            select(PracticeSession.id, PracticeSession.objective_id)
            .where(PracticeSession.participant_profile_id == ctx["profile"].id)
            .order_by(PracticeSession.started_at)
        )).all()


def _cod(r) -> str:
    return r.json()["error"]["code"]


@pytest.mark.asyncio
async def test_fara_alegere_obiectiv_neales_si_nicio_sesiune() -> None:
    ctx = await _context()
    async with make_test_client(ctx["participant"]) as client:
        r = await _porneste(client, ctx, pe_obiectiv=True)
    assert r.status_code == 400 and _cod(r) == "obiectiv_neales", r.text
    assert await _sesiunile(ctx) == []


@pytest.mark.asyncio
async def test_proiect_fara_catalog_obiectiv_neales() -> None:
    ctx = await _context(cu_catalog=False)
    async with make_test_client(ctx["participant"]) as client:
        r = await _porneste(client, ctx, pe_obiectiv=True)
    assert r.status_code == 400 and _cod(r) == "obiectiv_neales", r.text
    assert await _sesiunile(ctx) == []


@pytest.mark.asyncio
async def test_cu_alegere_sesiunea_e_legata_de_alegerea_curenta() -> None:
    from codrut.modules.practice.prompts import CODY_PROMPT_VERSION

    ctx = await _context()
    async with make_test_client(ctx["participant"]) as client:
        await _alege(client, ctx, ctx["obiective"][0])
        await _alege(client, ctx, ctx["obiective"][4])
        r = await _porneste(client, ctx, pe_obiectiv=True)
    assert r.status_code == 201, r.text
    assert CODY_PROMPT_VERSION == "v3.15"
    assert r.json()["prompt_version"] == "v3.15"
    assert "objective_id" not in r.json() and "pe_obiectiv" not in r.json()
    assert [o for _, o in await _sesiunile(ctx)] == [ctx["obiective"][4]]


@pytest.mark.asyncio
async def test_quizul_nu_porneste_pe_obiectiv() -> None:
    ctx = await _context()
    async with make_test_client(ctx["participant"]) as client:
        await _alege(client, ctx, ctx["obiective"][0])
        for kind in ("knowledge", "coaching"):
            r = await _porneste(client, ctx, kind=kind, pe_obiectiv=True)
            assert r.status_code == 400 and _cod(r) == "obiectiv_numai_la_joc_de_rol", r.text
    assert await _sesiunile(ctx) == []


@pytest.mark.asyncio
async def test_trainerul_nu_porneste_pe_obiectiv() -> None:
    ctx = await _context()
    async with make_test_client(ctx["trainer"], trainer_direct_entry=True) as client:
        corp = {"project_id": str(ctx["project"].id), "kind": "roleplay"}
        r = await client.post("/api/practice/trainer/sessions", json={**corp, "pe_obiectiv": True})
        assert r.status_code == 400 and _cod(r) == "obiectiv_numai_pentru_participant", r.text
        r = await client.post("/api/practice/trainer/sessions", json={**corp, "pe_obiectiv": False})
        assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_refolosirea_conversatiei_goale() -> None:
    ctx = await _context()
    async with make_test_client(ctx["participant"]) as client:
        await _alege(client, ctx, ctx["obiective"][0])
        obisnuita = (await _porneste(client, ctx)).json()["id"]
        pe_ob_1 = (await _porneste(client, ctx, pe_obiectiv=True)).json()["id"]
        pe_ob_2 = (await _porneste(client, ctx, pe_obiectiv=True)).json()["id"]
        a_doua_obisnuita = (await _porneste(client, ctx, pe_obiectiv=False)).json()["id"]
    assert pe_ob_1 != obisnuita
    assert pe_ob_2 == pe_ob_1
    assert a_doua_obisnuita == obisnuita
    async with make_test_client(ctx["participant"]) as client:
        # conversația goală pe obiectiv + „Începe conversația” → nu se refolosește cea pe obiectiv
        r = await _porneste(client, ctx)
    assert r.json()["id"] != pe_ob_1
    ids = await _sesiunile(ctx)
    assert sum(1 for _, o in ids if o is not None) == 1


@pytest.mark.asyncio
async def test_alegerea_schimbata_dupa_pornire_sesiunea_ramane_pe_obiectivul_vechi() -> None:
    from redis.asyncio import Redis

    from codrut.core.config import Settings
    from codrut.modules.practice.generation_provider import LocalGenerationProvider
    from codrut.modules.practice.models import (
        PracticeObjective,
        PracticeProgramSettings,
        PracticeSession,
        SessionKind,
    )
    from codrut.modules.practice.objective_service import alege
    from codrut.modules.practice.service import PracticeSessionService
    from test_practice_session_flow import create_test_context

    for doua_apeluri in (True, False):
        settings = Settings(generation_provider="local", practice_two_calls=doua_apeluri)
        furnizor = LocalGenerationProvider(settings)
        async with SessionLocal() as s:
            ctx = await create_test_context(s)
            setari = await s.get(PracticeProgramSettings, ctx["program_settings"].id)
            setari.objective_catalog = CATALOG
            await s.flush()
            obiective = await _obiectivele(s)
            vechi, nou = obiective[0], obiective[1]
            await alege(s, ctx["principal"], ctx["project"].id, vechi.id)
            redis = Redis.from_url(settings.redis_url, decode_responses=True)
            svc = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                         settings=settings)
            sed, _ = await svc.start_session(principal=ctx["principal"],
                                             project_id=ctx["project"].id,
                                             kind=SessionKind.roleplay, pe_obiectiv=True)
            await alege(s, ctx["principal"], ctx["project"].id, nou.id)
            n = len(furnizor.recorded_requests)
            for text in ("Da, hai.", "Înțeleg. Azi nu mai pot, ți-l dau luni la prânz."):
                await svc.add_participant_turn(principal=ctx["principal"], session_id=sed.id,
                                               text=text)
            cereri = furnizor.recorded_requests[n:]
            sesiunea = await s.get(PracticeSession, sed.id)
            assert sesiunea.objective_id == vechi.id
            assert isinstance(vechi, PracticeObjective)
            toate = "\n".join(c.system_instruction or "" for c in cereri)
            assert vechi.title in toate and vechi.situation in toate
            assert vechi.success_sign in toate
            assert nou.title not in toate
            await s.rollback()
            await redis.aclose()


@pytest.mark.asyncio
async def test_salutul_nu_se_schimba_pe_obiectiv() -> None:
    from redis.asyncio import Redis

    from codrut.core.config import Settings
    from codrut.modules.practice.generation_provider import LocalGenerationProvider
    from codrut.modules.practice.models import PracticeProgramSettings, SessionKind
    from codrut.modules.practice.objective_service import alege
    from codrut.modules.practice.service import PracticeSessionService
    from test_practice_session_flow import create_test_context

    settings = Settings(generation_provider="local", practice_two_calls=True)
    furnizor = LocalGenerationProvider(settings)
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        setari = await s.get(PracticeProgramSettings, ctx["program_settings"].id)
        setari.objective_catalog = CATALOG
        await s.flush()
        await alege(s, ctx["principal"], ctx["project"].id, (await _obiectivele(s))[0].id)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        svc = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                     settings=settings)
        await svc.start_session(principal=ctx["principal"], project_id=ctx["project"].id,
                                kind=SessionKind.roleplay, pe_obiectiv=True)
        salut = furnizor.recorded_requests[-1].system_instruction
        await s.rollback()
        await redis.aclose()
    assert "AZI SCENA PORNEȘTE" not in salut and "OBIECTIVUL OMULUI" not in salut

