"""Acordul la prima intrare — plicul 139.

Niciun om nu vorbește cu Cody până nu a văzut și a bifat acordul. Serverul ține minte cine, ce
proiect, când și ce text (amprenta lui), și refuză orice ședință fără acord — ecranul ascuns nu e o
ușă închisă. Dacă textul se schimbă, acordul se cere din nou.
"""

from __future__ import annotations

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.practice import acord
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import PracticeConsent, SessionKind
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context

# Textul lui Andrei, refăcut pe 23 septembrie seara — copiat din plicul 139, cuvânt cu cuvânt.
TEXTUL_DIN_PLIC = """Exersează cu Cody

Cody e un asistent de exersare construit de Andrei Văcaru. Funcționează cu un sistem de inteligență artificială (serviciul Google, cu datele păstrate în Uniunea Europeană).

Aici intri sub un cod: [codul omului]. Numele tău nu e trimis sistemului AI.

Ce scrii în conversație e trimis sistemului AI, ca să-ți poată răspunde. Nu scrie nume de colegi, de clienți sau alte date personale.

Conversațiile tale sunt păstrate în aplicație pe durata programului și sunt șterse la finalul acestuia. Până atunci, în aplicație le poate consulta doar trainerul tău. Poți cere oricând ștergerea lor mai devreme.

Compania ta nu vede nimic individual, doar rezultate de grup, fără nume.

Am înțeles și vreau să încep."""  # noqa: E501


def test_textul_e_al_lui_andrei_cuvant_cu_cuvant() -> None:
    assert "\n\n".join((acord.TITLU, *acord.PARAGRAFE, acord.BIFA)) == TEXTUL_DIN_PLIC


async def _fara_acord(session):
    ctx = await create_test_context(session)
    # fixtura comună dă acordul, ca testele vechi să poată exersa; aici îl luăm înapoi
    await session.execute(
        delete(PracticeConsent).where(
            PracticeConsent.participant_profile_id == ctx["profile"].id
        )
    )
    await session.flush()
    settings = Settings(generation_provider="local")
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    service = PracticeSessionService(
        session=session, redis=redis, generation_provider=LocalGenerationProvider(settings),
        settings=settings,
    )
    return ctx, redis, service


async def _porneste(service, ctx):
    return await service.start_session(
        principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
    )


@pytest.mark.asyncio
async def test_fara_acord_serverul_refuza_sedinta() -> None:
    async with SessionLocal() as session:
        ctx, redis, service = await _fara_acord(session)
        with pytest.raises(DomainError) as refuz:
            await _porneste(service, ctx)
        assert refuz.value.code == "acord_lipsa"
        await session.rollback()
        await redis.aclose()


@pytest.mark.asyncio
async def test_dupa_acord_sedinta_porneste_si_acordul_e_tinut_minte() -> None:
    async with SessionLocal() as session:
        ctx, redis, service = await _fara_acord(session)
        stare = await acord.starea_acordului(session, ctx["principal"], ctx["project"].id)
        assert stare["acordat"] is False
        # codul omului intră în text: acolo îl vede prima dată
        assert stare["cod"] and stare["cod"] in stare["paragrafe"][1]
        assert acord.LOC_COD not in " ".join(stare["paragrafe"])

        dupa = await acord.da_acordul(
            session, ctx["principal"], ctx["project"].id, stare["amprenta"]
        )
        assert dupa["acordat"] is True
        (rand,) = (await session.execute(
            select(PracticeConsent).where(
                PracticeConsent.participant_profile_id == ctx["profile"].id
            )
        )).scalars().all()
        assert rand.project_id == ctx["project"].id
        assert rand.text_hash == acord.AMPRENTA
        assert rand.accepted_at is not None

        sedinta, _ = await _porneste(service, ctx)
        assert sedinta is not None
        await session.rollback()
        await redis.aclose()


@pytest.mark.asyncio
async def test_acord_pe_un_text_vechi_e_refuzat() -> None:
    async with SessionLocal() as session:
        ctx, redis, _ = await _fara_acord(session)
        with pytest.raises(DomainError) as refuz:
            await acord.da_acordul(session, ctx["principal"], ctx["project"].id, "alt-text")
        assert refuz.value.code == "acord_text_schimbat"
        await session.rollback()
        await redis.aclose()


@pytest.mark.asyncio
async def test_textul_schimbat_cere_acordul_din_nou(monkeypatch) -> None:
    async with SessionLocal() as session:
        ctx, redis, service = await _fara_acord(session)
        await acord.da_acordul(session, ctx["principal"], ctx["project"].id, acord.AMPRENTA)
        await _porneste(service, ctx)  # merge, cu textul de azi

        monkeypatch.setattr(acord, "AMPRENTA", "amprenta-unui-text-nou")
        stare = await acord.starea_acordului(session, ctx["principal"], ctx["project"].id)
        assert stare["acordat"] is False
        with pytest.raises(DomainError) as refuz:
            await _porneste(service, ctx)
        assert refuz.value.code == "acord_lipsa"
        await session.rollback()
        await redis.aclose()
