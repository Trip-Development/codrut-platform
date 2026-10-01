"""Evoluția echipei: întâi pe om, apoi adunat — plicul 166, partea D.

Până acum regula „o notă pe zi” se aplica notelor echipei puse la un loc. Acum: punctele
echipei = media punctelor oamenilor cu cel puțin o notă; nivelul echipei = nivelul omului median
(ordonați după puncte; la număr par, cel de jos); câți oameni sunt pe fiecare nivel. Fila rămâne
numai a trainerului.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.evolution_service import PracticeEvolutionService
from codrut.modules.practice.models import CompetencyScore, ProjectCompetency
from codrut.modules.practice.router import get_project_evolution
from test_practice_session_flow import create_test_context

COMP = "Feedback asertiv"


async def _om(s, ctx, nume):
    cont = User(email=f"evo-{uuid.uuid4().hex[:6]}@example.com", password_hash="x",  # noqa: S106
                role=UserRole.participant)
    s.add(cont)
    await s.flush()
    profil = ParticipantProfile(company_id=ctx["company"].id, full_name=nume,
                                email=cont.email, user_id=cont.id)
    s.add(profil)
    await s.flush()
    s.add(ProjectMembership(company_id=ctx["company"].id, project_id=ctx["project"].id,
                            participant_profile_id=profil.id, active=True))
    await s.flush()
    return cont.id


async def _note(s, ctx, user_id, note):
    start = datetime.now(UTC) - timedelta(days=10)
    for zi, scor in note:
        # fără ședință legată (ca arhiva): intră în punctaj, fără tip de interlocutor
        s.add(CompetencyScore(user_id=user_id, project_id=ctx["project"].id, score=scor, level=2,
                              conversation_id=f"arhiva-{uuid.uuid4().hex[:6]}",
                              competency_name=COMP, source_type="roleplay",
                              created_at=start + timedelta(days=zi)))
    await s.flush()


@pytest.mark.asyncio
async def test_punctele_echipei_media_oamenilor_nivelul_omul_median() -> None:
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        s.add(ProjectCompetency(project_id=ctx["project"].id, name=COMP, order_index=0))
        a = await _om(s, ctx, "Om A")
        b = await _om(s, ctx, "Om B")
        await _om(s, ctx, "Om C, fără note")
        await _note(s, ctx, a, [(0, 80)])                    # 30 de puncte → Conștientizare
        await _note(s, ctx, b, [(0, 90), (1, 90), (2, 90)])  # 120 → Aplicare
        date = await PracticeEvolutionService(s).project_evolution(ctx["project"].id)
        comp = next(c for c in date["competencies"] if c["name"] == COMP)
        assert comp["points"] == 75                           # media (30 + 120) / 2
        assert comp["people_count"] == 2                      # omul fără note nu intră
        assert comp["level"] == "CONȘTIENTIZARE"               # omul median, la doi: cel de jos
        assert comp["levels_count"] == {"INTEGRARE": 0, "CONSOLIDARE": 0, "APLICARE": 1,
                                        "CONȘTIENTIZARE": 1}
        await s.rollback()


@pytest.mark.asyncio
async def test_la_trei_oameni_nivelul_e_al_celui_din_mijloc() -> None:
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        s.add(ProjectCompetency(project_id=ctx["project"].id, name=COMP, order_index=0))
        oameni = [await _om(s, ctx, f"Om {i}") for i in range(3)]
        await _note(s, ctx, oameni[0], [(0, 60)])                           # 10
        await _note(s, ctx, oameni[1], [(z, 100) for z in range(3)])       # 150 → Aplicare
        await _note(s, ctx, oameni[2], [(z, 100) for z in range(5)])       # 250 → Aplicare
        date = await PracticeEvolutionService(s).project_evolution(ctx["project"].id)
        comp = next(c for c in date["competencies"] if c["name"] == COMP)
        assert comp["level"] == "APLICARE"
        assert comp["points"] == round((10 + 150 + 250) / 3)
        await s.rollback()


@pytest.mark.asyncio
async def test_contul_de_test_nu_intra_in_evolutia_echipei() -> None:
    """Plicul 173: contul de test al lui Andrei nu are ce cauta in media liderilor.

    El porneste sedinte oricand, ca sa incerce aplicatia. Daca notele lui ar intra in
    evolutia echipei, fiecare incercare ar misca media unor oameni care n-au exersat.
    Masurat pe aceeasi echipa, cu si fara el: aceleasi cifre, pana la ultima.
    """
    from codrut.modules.practice.conturi_test import CONTURI_DE_TEST

    async def _cifrele(cu_contul_de_test: bool):
        async with SessionLocal() as s:
            ctx = await create_test_context(s)
            s.add(ProjectCompetency(project_id=ctx["project"].id, name=COMP, order_index=0))
            a = await _om(s, ctx, "Om A")
            b = await _om(s, ctx, "Om B")
            await _note(s, ctx, a, [(0, 80)])                    # 30 de puncte
            await _note(s, ctx, b, [(0, 90), (1, 90), (2, 90)])  # 120 de puncte
            if cu_contul_de_test:
                # acelasi om, dar pe adresa contului de test, cu note foarte diferite
                adresa = next(iter(CONTURI_DE_TEST))
                t = await _om(s, ctx, "Contul de test")
                profil = (await s.execute(
                    select(ParticipantProfile).where(ParticipantProfile.user_id == t)
                )).scalars().one()
                # Adresa e unica in `users`: daca o rulare dinainte a lasat contul, il legam
                # pe el (`start_session` comite la mijloc, deci nu se poate intoarce).
                existent = (await s.execute(
                    select(User).where(User.email == adresa)
                )).scalars().first()
                if existent is not None:
                    t = existent.id
                    profil.user_id = existent.id
                else:
                    (await s.get(User, t)).email = adresa
                profil.email = adresa
                await s.flush()
                await _note(s, ctx, t, [(z, 100) for z in range(6)])  # 300 de puncte
            date = await PracticeEvolutionService(s).project_evolution(ctx["project"].id)
            comp = next(c for c in date["competencies"] if c["name"] == COMP)
            rezultat = (comp["points"], comp["people_count"], comp["level"],
                        dict(comp["levels_count"]), date["participants_total"],
                        date["participants_active"])
            await s.rollback()
            return rezultat

    fara = await _cifrele(cu_contul_de_test=False)
    cu = await _cifrele(cu_contul_de_test=True)
    assert cu == fara, f"contul de test a miscat evolutia echipei: {fara} -> {cu}"
    assert fara[0] == 75, "plasa: media celor doi oameni adevarati e tot (30 + 120) / 2"


@pytest.mark.asyncio
async def test_fila_ramane_numai_a_trainerului() -> None:
    """Regula de confidențialitate existentă pe datele astea: numai trainerul le vede (router)."""
    async with SessionLocal() as s:
        ctx = await create_test_context(s)  # principalul lui e un participant
        with pytest.raises(HTTPException) as e:
            await get_project_evolution(ctx["project"].id, ctx["principal"], s)
        assert e.value.status_code == 403
        await s.rollback()
