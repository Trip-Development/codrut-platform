"""Contul de test iese și din Camera de training — plicul 180 (a doua opinie pe fișa lui).

Plicul 173 l-a scos din fila Evoluție; Camera de training îl număra încă (oameni, medie, serie,
tabel), iar notele ei se iau pe PROIECT, nu pe oameni. Pe live trainerul vedea 20 de oameni
într-un ecran și 21 în celălalt. Acum, pe orice proiect, Camera arată aceleași cifre cu sau fără
contul de test.

Testele importă numai serviciile (corecția 1 a controlorului): roșul trebuie să fie pe cifre.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.conturi_test import CONTURI_DE_TEST
from codrut.modules.practice.evolution_service import PracticeEvolutionService
from codrut.modules.practice.models import CompetencyScore, ProjectCompetency
from codrut.modules.practice.room_service import (
    QUIZ_SOURCE,
    TEST_IN_ID,
    TEST_OUT_ID,
    PracticeRoomService,
)
from test_practice_session_flow import create_test_context

COMP = "Feedback asertiv"
ADRESA_TEST = next(iter(CONTURI_DE_TEST))
CHEI = (
    "participants_total", "average_score", "sessions_total", "inactive_count",
    "test_in_completed", "test_out_completed", "active_count", "recurrent_count",
    "competencies", "growth_ranking", "quiz_weak_spots", "weekly_average",
)


async def _om(s, ctx, nume, adresa=None, membru=True):
    """Un om cu cont; adresa dată (contul de test, `+lidera`) se leagă de contul existent."""
    adresa = adresa or f"camera-{uuid.uuid4().hex[:6]}@example.com"
    cont = (await s.execute(select(User).where(User.email == adresa))).scalars().first()
    if cont is None:
        cont = User(email=adresa, password_hash="x", role=UserRole.participant)  # noqa: S106
        s.add(cont)
        await s.flush()
    profil = ParticipantProfile(company_id=ctx["company"].id, full_name=nume,
                                email=adresa, user_id=cont.id)
    s.add(profil)
    await s.flush()
    if membru:
        s.add(ProjectMembership(company_id=ctx["company"].id, project_id=ctx["project"].id,
                                participant_profile_id=profil.id, active=True))
        await s.flush()
    return cont.id


async def _note(s, ctx, user_id, note):
    """`note` = [(conversatie, sursa, scor, cand)]; toate pe proiectul contextului."""
    for conversatie, sursa, scor, cand in note:
        s.add(CompetencyScore(user_id=user_id, project_id=ctx["project"].id, score=scor, level=2,
                              conversation_id=conversatie, competency_name=COMP,
                              source_type=sursa, created_at=cand))
    await s.flush()


def _cifrele(camera):
    rezultat = {k: camera[k] for k in CHEI}
    # profilul pus de contextul de test are un sufix aleator în nume („Participant 1a2b…”)
    rezultat["oameni"] = sorted(
        "Participant" if p["full_name"].startswith("Participant ") else p["full_name"]
        for p in camera["participants"]
    )
    return rezultat


async def _camera(cu_contul_de_test: bool, membru: bool = True, adresa: str = ADRESA_TEST):
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        s.add(ProjectCompetency(project_id=ctx["project"].id, name=COMP, order_index=0))
        acum = datetime.now(UTC)
        ieri = acum - timedelta(days=1)
        a = await _om(s, ctx, "Om A")
        b = await _om(s, ctx, "Om B")
        await _note(s, ctx, a, [(TEST_IN_ID, "test_in", 40, ieri - timedelta(days=2)),
                                ("sedinta-a1", "roleplay", 60, ieri)])
        await _note(s, ctx, b, [("sedinta-b1", "roleplay", 50, ieri),
                                ("quiz-b1", QUIZ_SOURCE, 45, ieri)])
        if cu_contul_de_test:
            # corecția 2: la ≥ 14 zile de notele celorlalți, ca să cadă în altă săptămână a seriei
            departe = acum - timedelta(days=20)
            t = await _om(s, ctx, "Contul de test", adresa=adresa, membru=membru)
            await _note(s, ctx, t, [(TEST_IN_ID, "test_in", 100, departe),
                                    (TEST_OUT_ID, "test_out", 100, departe),
                                    ("quiz-t1", QUIZ_SOURCE, 100, departe),
                                    ("sedinta-t1", "roleplay", 100, departe),
                                    ("sedinta-t2", "roleplay", 100, departe),
                                    ("sedinta-t3", "roleplay", 100, departe)])
        camera = await PracticeRoomService(s).project_room(ctx["project"].id)
        evolutie = await PracticeEvolutionService(s).project_evolution(ctx["project"].id)
        await s.rollback()
        return camera, evolutie


@pytest.mark.asyncio
async def test_camera_are_aceleasi_cifre_cu_si_fara_contul_de_test() -> None:
    fara, _ = await _camera(cu_contul_de_test=False)
    cu, _ = await _camera(cu_contul_de_test=True)
    assert _cifrele(cu) == _cifrele(fara), (
        f"contul de test a mișcat Camera: {_cifrele(fara)} -> {_cifrele(cu)}"
    )
    # plasa: cei doi oameni adevărați + profilul pe care îl pune contextul de test
    assert fara["participants_total"] == 3
    assert "Contul de test" not in [p["full_name"] for p in cu["participants"]]


@pytest.mark.asyncio
async def test_notele_contului_de_test_pe_proiect_fara_sa_fie_membru_nu_intra() -> None:
    """Ca după o ședință „ca trainer”: note cu `project_id` al proiectului, fără apartenență."""
    fara, _ = await _camera(cu_contul_de_test=False)
    cu, _ = await _camera(cu_contul_de_test=True, membru=False)
    for cheie in ("average_score", "sessions_total", "weekly_average", "test_in_completed",
                  "test_out_completed", "quiz_weak_spots", "competencies"):
        assert cu[cheie] == fara[cheie], (cheie, fara[cheie], cu[cheie])


@pytest.mark.asyncio
async def test_plasa_lidera_nu_e_cont_de_test_si_intra_in_cifre() -> None:
    fara, _ = await _camera(cu_contul_de_test=False)
    cu, _ = await _camera(cu_contul_de_test=True, adresa="andreyvacaru+lidera@gmail.com")
    assert cu["participants_total"] == fara["participants_total"] + 1
    assert cu["average_score"] != fara["average_score"]


@pytest.mark.asyncio
async def test_acelasi_numar_de_oameni_in_camera_si_in_evolutie() -> None:
    camera, evolutie = await _camera(cu_contul_de_test=True)
    assert camera["participants_total"] == evolutie["participants_total"], (
        camera["participants_total"], evolutie["participants_total"]
    )
