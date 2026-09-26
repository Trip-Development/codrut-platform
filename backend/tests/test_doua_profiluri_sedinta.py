"""Omul cu două profiluri (două firme) poate vorbi cu Cody pe al doilea — plicul 158.

Văzut în browser pe 26 septembrie, pe gmail-ul lui Andrei (2 profiluri): ședința pornea (201), dar
„Da, hai" dădea `session_not_found` („Nu am putut trimite mesajul"), la fel și închiderea.

Cauza: `start_session` găsește profilul după PROIECT, dar replica, istoricul și închiderea
îl luau cu `_resolve_participant_profile`, care alege CEL MAI VECHI profil legat. Pentru
o ședință a celui de-al doilea profil, comparația pica.

Paza care rămâne: ședința altui om e refuzată la fel ca azi.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import SessionKind, SessionState
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context


async def _cont_cu_doua_profiluri(s):
    """Un cont; profilul vechi în firma 1, profilul nou în firma 2, amândouă legate."""
    vechi = await create_test_context(s)
    nou = await create_test_context(s)
    cont = User(id=uuid.uuid4(), email=f"doua-{uuid.uuid4().hex[:6]}@example.com",
                password_hash="x", role=UserRole.participant)  # noqa: S106
    s.add(cont)
    await s.flush()
    vechi["profile"].user_id = cont.id
    nou["profile"].user_id = cont.id
    # în aceeași tranzacție `now()` e același; profilul din firma 1 e făcut, dinadins, mai vechi
    vechi["profile"].created_at = datetime.now(UTC) - timedelta(days=30)
    await s.flush()
    principal = nou["principal"].model_copy(update={"user_id": cont.id, "email": cont.email})
    return vechi, nou, principal


def _serviciu(s, redis, settings):
    return PracticeSessionService(session=s, redis=redis,
                                  generation_provider=LocalGenerationProvider(settings),
                                  settings=settings)


@pytest.mark.asyncio
async def test_al_doilea_profil_trimite_vede_istoricul_si_inchide() -> None:
    settings = Settings(generation_provider="local")
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    async with SessionLocal() as s:
        _vechi, nou, principal = await _cont_cu_doua_profiluri(s)
        svc = _serviciu(s, redis, settings)
        sed, _ = await svc.start_session(principal=principal, project_id=nou["project"].id,
                                         kind=SessionKind.roleplay)
        sid = sed.id
        assert sed.participant_profile_id == nou["profile"].id

        replica = await svc.add_participant_turn(principal=principal, session_id=sid,
                                                 text="Da, hai.")
        assert replica is not None
        _, istoric = await svc.get_session_history(principal=principal, session_id=sid)
        assert len(istoric) >= 3
        inchisa, _ = await svc.end_session(principal=principal, session_id=sid)
        assert inchisa.state == SessionState.closed
        await s.rollback()
    await redis.aclose()


@pytest.mark.asyncio
async def test_sedinta_altui_om_ramane_refuzata() -> None:
    settings = Settings(generation_provider="local")
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    async with SessionLocal() as s:
        _vechi, nou, principal = await _cont_cu_doua_profiluri(s)
        strain = await create_test_context(s)  # alt om, alt cont
        svc = _serviciu(s, redis, settings)
        sed, _ = await svc.start_session(principal=principal, project_id=nou["project"].id,
                                         kind=SessionKind.roleplay)
        sid = sed.id
        for pas in (
            lambda: svc.add_participant_turn(principal=strain["principal"], session_id=sid,
                                             text="Da, hai."),
            lambda: svc.get_session_history(principal=strain["principal"], session_id=sid),
            lambda: svc.end_session(principal=strain["principal"], session_id=sid),
        ):
            with pytest.raises(DomainError) as e:
                await pas()
            assert e.value.code == "session_not_found"
        await s.rollback()
    await redis.aclose()
