"""Notele de la finalul ședinței dau puncte — plicul 192 (Andrei, 14 oct: „da” pe tabel).

La „Încheie”, rezumatul scrie 4 note (`source_type="session"`) sub nume din aplicația veche, care nu
sunt pe lista proiectului: până la 192, Tabloul le pierdea la potrivire, deci nu dădeau puncte.
Acum, pe proiectele cu lista temei, trei dintre ele se potrivesc cu competența programului:
„Comunicare Asertivă” → „Exprimarea asertivă a nevoilor și limitelor”, „Feedback Structurat (SBI)”
→ „Feedback constructiv”, „Abilități de Coach și Întrebări” → „Verificarea înțelegerii și a
alinierii”. „Concizie și Echilibru” nu se potrivește și nu dă puncte. Nu se numără de două ori: pe
zi, pe competență, contează numai nota cea mai bună (regula 165).

Notele se scriu exact ca `service.py` (numele de mai jos sunt copiate din `score_name_map`, care e
local în funcție). Valorile așteptate se calculează din `puncte_pentru_nota` și `BONUS_TIP_NOU`.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.dashboard_service import PracticeDashboardService, _cheie
from codrut.modules.practice.models import ProjectCompetency
from codrut.modules.practice.scoring import BONUS_TIP_NOU, puncte_pentru_nota
from test_practice_session_flow import create_test_context
from test_tabloul_numai_pe_proiect import LISTA, ZI_A, _note, _proiect, _sedinta

# exact ca în service.py (score_name_map, la închidere)
COACH = "Abilități de Coach și Întrebări"
ASERTIVA = "Comunicare Asertivă"
SBI = "Feedback Structurat (SBI)"
CONCIZIE = "Concizie și Echilibru"

EXPRIMAREA = "Exprimarea asertivă a nevoilor și limitelor"
FEEDBACK = "Feedback constructiv"
VERIFICAREA = "Verificarea înțelegerii și a alinierii"


async def _om(s):
    ctx = await create_test_context(s)
    cont = User(email=f"note-final-{uuid.uuid4().hex[:6]}@example.com", password_hash="x",  # noqa: S106
                role=UserRole.participant)
    s.add(cont)
    await s.flush()
    ctx["profile"].user_id = cont.id
    ctx["profile"].role_group = "leadership"
    ctx["principal"] = ctx["principal"].model_copy(update={"user_id": cont.id, "email": cont.email})
    return ctx


async def _tablou(s, ctx, proiect_id):
    serviciu = PracticeDashboardService(s)
    return await serviciu.get_participant_dashboard_data(ctx["principal"], proiect_id)


def _puncte(t):
    return {c["name"]: c["points"] for c in t["competencies"] if c["points"]}


def test_cheile_numelor_scrise_de_service() -> None:
    assert [_cheie(n) for n in (COACH, ASERTIVA, SBI, CONCIZIE)] == [
        "abilitati de coach si intrebari", "comunicare asertiva", "feedback structurat sbi",
        "concizie si echilibru",
    ]


@pytest.mark.asyncio
async def test_notele_de_final_dau_puncte_pe_competenta_programului() -> None:
    async with SessionLocal() as s:
        ctx = await _om(s)
        p, setari = await _proiect(s, ctx, cu_lista=True)
        sed = await _sedinta(s, ctx, setari, ZI_A)
        # rezumatul dă note pe 10, iar service.py scrie int(round(v * 10)): 8 / 7 / 9 / 7,5
        await _note(s, ctx, p.id, str(sed.id), {COACH: 80, ASERTIVA: 70, SBI: 90, CONCIZIE: 75},
                    ZI_A, "session")
        t = await _tablou(s, ctx, p.id)
        asteptat = {
            VERIFICAREA: puncte_pentru_nota(80) + BONUS_TIP_NOU,
            EXPRIMAREA: puncte_pentru_nota(70) + BONUS_TIP_NOU,
            FEEDBACK: puncte_pentru_nota(90) + BONUS_TIP_NOU,
        }
        assert _puncte(t) == asteptat
        assert t["points_total"] == sum(asteptat.values())
        assert [c["name"] for c in t["competencies"]] == LISTA
        assert CONCIZIE not in {c["name"] for c in t["competencies"]}
        await s.rollback()


@pytest.mark.asyncio
async def test_aceeasi_zi_conteaza_numai_nota_cea_mai_buna() -> None:
    """Nota din ședință 85 + nota de final 90, aceeași competență → 40 + bonus, nu 35 + 40."""
    async with SessionLocal() as s:
        ctx = await _om(s)
        p, setari = await _proiect(s, ctx, cu_lista=True)
        sed = await _sedinta(s, ctx, setari, ZI_A)
        await _note(s, ctx, p.id, str(sed.id), {FEEDBACK: 85}, ZI_A, "roleplay")
        await _note(s, ctx, p.id, str(sed.id), {SBI: 90}, ZI_A + timedelta(minutes=1), "session")
        t = await _tablou(s, ctx, p.id)
        assert _puncte(t)[FEEDBACK] == puncte_pentru_nota(90) + BONUS_TIP_NOU
        adunate = puncte_pentru_nota(85) + puncte_pentru_nota(90) + BONUS_TIP_NOU
        assert _puncte(t)[FEEDBACK] != adunate
        await s.rollback()


@pytest.mark.asyncio
async def test_proiect_fara_competenta_tinta_nota_nu_da_puncte() -> None:
    async with SessionLocal() as s:
        ctx = await _om(s)
        p, setari = await _proiect(s, ctx, cu_lista=False)
        lista = [n for n in LISTA if n != FEEDBACK]
        for i, n in enumerate(lista):
            s.add(ProjectCompetency(project_id=p.id, name=n, order_index=i))
        await s.flush()
        sed = await _sedinta(s, ctx, setari, ZI_A)
        await _note(s, ctx, p.id, str(sed.id), {SBI: 90}, ZI_A, "session")
        t = await _tablou(s, ctx, p.id)
        assert t["points_total"] == 0
        assert [c["name"] for c in t["competencies"]] == lista
        await s.rollback()


@pytest.mark.asyncio
async def test_fara_proiect_tabloul_ramane_cel_de_azi() -> None:
    async with SessionLocal() as s:
        ctx = await _om(s)
        await _note(s, ctx, None, "arhiva-veche", {COACH: 80, ASERTIVA: 70, SBI: 90, CONCIZIE: 75},
                    ZI_A, "session")
        t = await _tablou(s, ctx, None)
        assert t["points_total"] == 0
        assert not {c["name"] for c in t["competencies"]} & {COACH, ASERTIVA, SBI, CONCIZIE}
        await s.rollback()
