"""Competența țintă a scenariului — plicul 165, partea C.

La pornirea role-play-ului (numai pe drumul cu două apeluri), aplicația alege competența proiectului
cu cele mai puține note role-play ale omului — la egalitate, ordinea trainerului — și o spune în
regula setup-ului. Evaluatorul de la închidere notează în continuare toate competențele văzute.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis

from codrut.contracts.generation import GenerationPurpose
from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import (
    CompetencyScore,
    PracticeSession,
    ProjectCompetency,
    SessionKind,
    SessionState,
)
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context

COMPETENTE = ["Ascultare activă", "Feedback asertiv", "Limite sănătoase"]


async def _pregatire(s, note_pe_competenta):
    ctx = await create_test_context(s)
    cont = User(email=f"tinta-{uuid.uuid4().hex[:6]}@example.com", password_hash="x",  # noqa: S106
                role=UserRole.participant)
    s.add(cont)
    await s.flush()
    ctx["profile"].user_id = cont.id
    for i, nume in enumerate(COMPETENTE):
        s.add(ProjectCompetency(project_id=ctx["project"].id, name=nume, order_index=i))
    trecut = datetime.now(UTC) - timedelta(days=10)
    for i, (nume, cate) in enumerate(note_pe_competenta.items()):
        for j in range(cate):
            sed = PracticeSession(program_settings_id=ctx["program_settings"].id,
                                  participant_profile_id=ctx["profile"].id, pack_id=ctx["pack"].id,
                                  kind=SessionKind.roleplay, state=SessionState.closed,
                                  started_at=trecut + timedelta(hours=i * 10 + j))
            s.add(sed)
            await s.flush()
            s.add(CompetencyScore(user_id=cont.id, project_id=ctx["project"].id, score=80, level=2,
                                  conversation_id=str(sed.id), competency_name=nume,
                                  source_type="roleplay", created_at=trecut))
    await s.flush()
    ctx["principal"] = ctx["principal"].model_copy(update={"user_id": cont.id, "email": cont.email})
    return ctx


async def _pornirea(note_pe_competenta, doua_apeluri=True):
    settings = Settings(generation_provider="local", practice_two_calls=doua_apeluri)
    furnizor = LocalGenerationProvider(settings)
    async with SessionLocal() as s:
        ctx = await _pregatire(s, note_pe_competenta)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        svc = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                     settings=settings)
        sed, _ = await svc.start_session(principal=ctx["principal"], project_id=ctx["project"].id,
                                         kind=SessionKind.roleplay)
        n = len(furnizor.recorded_requests)
        await svc.add_participant_turn(principal=ctx["principal"], session_id=sed.id,
                                       text="Da, hai.")
        cereri = furnizor.recorded_requests[n:]
        await s.rollback()
        await redis.aclose()
    return cereri


@pytest.mark.asyncio
async def test_tinta_e_competenta_cu_cele_mai_putine_note() -> None:
    cereri = await _pornirea({"Ascultare activă": 2, "Feedback asertiv": 0, "Limite sănătoase": 1})
    assert [c.purpose for c in cereri] == [GenerationPurpose.actor]
    prompt = cereri[0].system_instruction
    assert "Scenariul pune la încercare mai ales competența „Feedback asertiv”" in prompt
    assert "În „Obiectivul tău” se vede limpede competența asta" in prompt
    # stă lângă regula setup-ului, la capătul promptului
    assert prompt.index("CUM ARATĂ SETUP-UL") < prompt.index("mai ales competența")


@pytest.mark.asyncio
async def test_la_egalitate_ordinea_trainerului() -> None:
    cereri = await _pornirea({"Ascultare activă": 1, "Feedback asertiv": 1, "Limite sănătoase": 1})
    assert "mai ales competența „Ascultare activă”" in cereri[0].system_instruction


@pytest.mark.asyncio
async def test_la_un_singur_apel_nu_se_schimba_nimic() -> None:
    cereri = await _pornirea({"Ascultare activă": 2}, doua_apeluri=False)
    assert all("mai ales competența" not in (c.system_instruction or "") for c in cereri)
