"""„Ai o conversație neîncheiată”: drumul de citire — plicul 209.

Andrei, 6 nov: omul care revine alege Continuă sau Începe alta. Drumul întoarce cea mai recentă
conversație deschisă a omului pe proiect, din ultimele 7 zile, în care omul a scris ceva.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.companies.models import (
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.acord import AMPRENTA
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import (
    PracticeConsent,
    PracticeProgramSettings,
    PracticeSession,
    ProgramMode,
    SessionKind,
    SessionState,
)
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context


async def _cere(session, principal, project_id):
    # Importat aici, ca fiecare test să fie roșu pe el, nu toată colectarea.
    from codrut.modules.practice import router

    return await router.get_conversatia_neincheiata(
        project_id=project_id, principal=principal, session=session
    )


def _serviciu(session, settings, redis) -> PracticeSessionService:
    return PracticeSessionService(
        session=session,
        redis=redis,
        generation_provider=LocalGenerationProvider(settings),
        settings=settings,
    )


async def _porneste(service, principal, project_id) -> PracticeSession:
    sesiune, _ = await service.start_session(
        principal=principal, project_id=project_id, kind=SessionKind.roleplay
    )
    return sesiune


async def _vorbeste(service, principal, sesiune, text="Replica omului.") -> None:
    await service.add_participant_turn(principal=principal, session_id=sesiune.id, text=text)


async def _lume():
    """Sesiunea bazei, contextul de test și serviciul, cu tot ce trebuie închis la final."""
    settings = Settings(generation_provider="local")
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return settings, redis


@pytest.mark.asyncio
async def test_b1_conversatia_deschisa_de_azi_vine_cu_replicile_in_ordine() -> None:
    settings, redis = await _lume()
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        service = _serviciu(session, settings, redis)
        sesiune = await _porneste(service, ctx["principal"], ctx["project"].id)
        await _vorbeste(service, ctx["principal"], sesiune, "Prima replică a omului.")
        await _vorbeste(service, ctx["principal"], sesiune, "A doua replică a omului.")

        raspuns = await _cere(session, ctx["principal"], ctx["project"].id)

        assert raspuns is not None
        assert raspuns.session.id == sesiune.id
        assert raspuns.session.state == SessionState.open
        assert raspuns.session.cody_alias == ctx["profile"].cody_alias
        ordine = [t.ordinal for t in raspuns.turns]
        assert ordine == sorted(ordine)
        ale_omului = [t.text for t in raspuns.turns if t.role == "participant"]
        assert ale_omului == ["Prima replică a omului.", "A doua replică a omului."]
        await session.rollback()
    await redis.aclose()


@pytest.mark.asyncio
async def test_b2_conversatia_de_acum_8_zile_nu_mai_vine() -> None:
    settings, redis = await _lume()
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        service = _serviciu(session, settings, redis)
        sesiune = await _porneste(service, ctx["principal"], ctx["project"].id)
        await _vorbeste(service, ctx["principal"], sesiune)

        # marginea: la 6 zile încă vine, la 8 nu
        sesiune.started_at = datetime.now(UTC) - timedelta(days=6)
        await session.flush()
        assert await _cere(session, ctx["principal"], ctx["project"].id) is not None

        sesiune.started_at = datetime.now(UTC) - timedelta(days=8)
        await session.flush()
        assert await _cere(session, ctx["principal"], ctx["project"].id) is None
        await session.rollback()
    await redis.aclose()


@pytest.mark.asyncio
async def test_b3_conversatia_inchisa_nu_vine() -> None:
    settings, redis = await _lume()
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        service = _serviciu(session, settings, redis)
        sesiune = await _porneste(service, ctx["principal"], ctx["project"].id)
        await _vorbeste(service, ctx["principal"], sesiune)

        sesiune.state = SessionState.closed
        await session.flush()

        assert await _cere(session, ctx["principal"], ctx["project"].id) is None
        await session.rollback()
    await redis.aclose()


@pytest.mark.asyncio
async def test_b4_conversatia_altui_participant_nu_vine() -> None:
    settings, redis = await _lume()
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        service = _serviciu(session, settings, redis)

        sufix = uuid.uuid4().hex[:8]
        alt_profil = ParticipantProfile(
            company_id=ctx["company"].id,
            full_name=f"Alt participant {sufix}",
            email=f"alt_{sufix}@example.com",
        )
        session.add(alt_profil)
        await session.flush()
        session.add(ProjectMembership(
            company_id=ctx["company"].id, project_id=ctx["project"].id,
            participant_profile_id=alt_profil.id, active=True,
        ))
        session.add(PracticeConsent(
            participant_profile_id=alt_profil.id, project_id=ctx["project"].id,
            text_hash=AMPRENTA, accepted_at=datetime.now(UTC),
        ))
        await session.flush()
        alt_principal: SessionPrincipal = ctx["principal"].model_copy(
            update={"user_id": uuid.uuid4(), "email": alt_profil.email}
        )

        a_lui = await _porneste(service, alt_principal, ctx["project"].id)
        await _vorbeste(service, alt_principal, a_lui)

        assert await _cere(session, ctx["principal"], ctx["project"].id) is None
        raspuns_lui = await _cere(session, alt_principal, ctx["project"].id)
        assert raspuns_lui is not None and raspuns_lui.session.id == a_lui.id
        await session.rollback()
    await redis.aclose()


@pytest.mark.asyncio
async def test_b5_conversatia_de_pe_alt_proiect_nu_vine() -> None:
    settings, redis = await _lume()
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        service = _serviciu(session, settings, redis)

        alt_proiect = CompanyProject(
            company_id=ctx["company"].id,
            name=f"Alt proiect {uuid.uuid4().hex[:8]}",
            status=CompanyProjectStatus.active,
            project_type="training",
        )
        session.add(alt_proiect)
        await session.flush()
        session.add(PracticeProgramSettings(
            project_id=alt_proiect.id, mode=ProgramMode.training,
            theme_id=ctx["program_settings"].theme_id, active_pack_id=ctx["pack"].id,
            is_enabled=True, max_turns_per_session=10, max_sessions_per_day=5,
            max_chars_per_turn=1200, turn_retention_days=30,
            usd_cap_per_participant=ctx["program_settings"].usd_cap_per_participant,
        ))
        await session.flush()

        sesiune = await _porneste(service, ctx["principal"], ctx["project"].id)
        await _vorbeste(service, ctx["principal"], sesiune)

        assert await _cere(session, ctx["principal"], alt_proiect.id) is None
        assert await _cere(session, ctx["principal"], ctx["project"].id) is not None
        await session.rollback()
    await redis.aclose()


@pytest.mark.asyncio
async def test_b6_din_doua_deschise_vine_cea_mai_recenta() -> None:
    settings, redis = await _lume()
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        service = _serviciu(session, settings, redis)
        veche = await _porneste(service, ctx["principal"], ctx["project"].id)
        await _vorbeste(service, ctx["principal"], veche)
        noua = await _porneste(service, ctx["principal"], ctx["project"].id)
        await _vorbeste(service, ctx["principal"], noua)
        assert noua.id != veche.id

        veche.started_at = datetime.now(UTC) - timedelta(hours=2)
        noua.started_at = datetime.now(UTC) - timedelta(hours=1)
        await session.flush()

        raspuns = await _cere(session, ctx["principal"], ctx["project"].id)
        assert raspuns is not None and raspuns.session.id == noua.id
        await session.rollback()
    await redis.aclose()


@pytest.mark.asyncio
async def test_b7_conversatia_in_care_omul_n_a_scris_nu_vine() -> None:
    settings, redis = await _lume()
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        service = _serviciu(session, settings, redis)
        sesiune, prima = await service.start_session(
            principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        assert sesiune.state == SessionState.open
        assert prima is not None

        assert await _cere(session, ctx["principal"], ctx["project"].id) is None
        await session.rollback()
    await redis.aclose()
