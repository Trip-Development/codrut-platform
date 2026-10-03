"""Tabloul pe proiect — plicul 184 (hotărârea lui Andrei, 30 sept: „pe proiect”).

„Tabloul adună notele omului DOAR din proiectul curent.” Până acum Tabloul lua toate notele omului,
din toate proiectele. Acum: pe proiectul deschis — numai notele lui; fără proiect deschis — numai
notele care nu țin de niciun proiect. Fiecare proiect pornește de la zero (și bonusul de tip nou
se câștigă din nou).

Fixture-ul e cel din raportul 172 (fără nume de oameni): ședința pe B (25 sept, „jos”), ședința pe A
(26 sept, „lateral”), C fără competențe. Testele nu importă nimic ce nu există pe candidatul 21.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.companies.models import CompanyProject, CompanyProjectStatus
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.models import (
    CompetencyScore,
    PracticeProgramSettings,
    PracticeSession,
    ProgramMode,
    ProjectCompetency,
    SessionKind,
    SessionState,
)
from test_practice_session_flow import create_test_context

LISTA = [
    "Ascultare activă",
    "Exprimarea asertivă a nevoilor și limitelor",
    "Feedback constructiv",
    "Gestionarea propriilor reacții emoționale",
    "Gestionarea reacțiilor celorlalți",
    "Rezolvarea colaborativă a conflictelor",
    "Verificarea înțelegerii și a alinierii",
]
REZOLVAREA = "Rezolvarea colaborativă a conflictelor"
# notele rezumatului de la închidere (F1) — scrise literal, constanta nu există pe 21
F1 = ["Abilități de Coach și Întrebări", "Comunicare Asertivă", "Feedback Structurat (SBI)",
      "Concizie și Echilibru"]
ZI_B = datetime(2026, 9, 25, 9, 49, tzinfo=UTC)
ZI_A = datetime(2026, 9, 26, 18, 37, tzinfo=UTC)
NOTE_B = {"Ascultare activă": 55, "Exprimarea asertivă a nevoilor și limitelor": 50,
          "Feedback constructiv": 65, "Gestionarea reacțiilor celorlalți": 45,
          REZOLVAREA: 52, "Verificarea înțelegerii și a alinierii": 40}
NOTE_A = {"Ascultare activă": 75, "Exprimarea asertivă a nevoilor și limitelor": 90,
          "Gestionarea reacțiilor celorlalți": 80, REZOLVAREA: 75}
REZUMAT_B = dict(zip(F1, (30, 50, 60, 70), strict=True))
REZUMAT_A = dict(zip(F1, (40, 90, 70, 90), strict=True))


async def _proiect(s, ctx, cu_lista: bool):
    p = CompanyProject(company_id=ctx["company"].id, name=f"P {uuid.uuid4().hex[:6]}",
                       status=CompanyProjectStatus.active, project_type="training")
    s.add(p)
    await s.flush()
    setari = PracticeProgramSettings(
        project_id=p.id, mode=ProgramMode.training, theme_id=ctx["program_settings"].theme_id,
        active_pack_id=ctx["pack"].id, is_enabled=True, max_turns_per_session=10,
        max_sessions_per_day=5, max_chars_per_turn=1200, turn_retention_days=30,
        usd_cap_per_participant=ctx["program_settings"].usd_cap_per_participant,
    )
    s.add(setari)
    if cu_lista:
        for i, n in enumerate(LISTA):
            s.add(ProjectCompetency(project_id=p.id, name=n, order_index=i))
    await s.flush()
    return p, setari


async def _sedinta(s, ctx, setari, cand, kind=SessionKind.roleplay):
    sed = PracticeSession(program_settings_id=setari.id, participant_profile_id=ctx["profile"].id,
                          pack_id=ctx["pack"].id, kind=kind, state=SessionState.closed,
                          started_at=cand)
    s.add(sed)
    await s.flush()
    return sed


async def _note(s, ctx, proiect_id, conversatie, note, cand, sursa):
    for nume, scor in note.items():
        s.add(CompetencyScore(user_id=ctx["principal"].user_id, project_id=proiect_id, score=scor,
                              level=2, conversation_id=conversatie, competency_name=nume,
                              source_type=sursa, created_at=cand))
    await s.flush()


async def _fixture(s):
    ctx = await create_test_context(s)
    cont = User(email=f"pe-proiect-{uuid.uuid4().hex[:6]}@example.com", password_hash="x",  # noqa: S106
                role=UserRole.participant)
    s.add(cont)
    await s.flush()
    ctx["profile"].user_id = cont.id
    ctx["profile"].role_group = "leadership"
    ctx["principal"] = ctx["principal"].model_copy(update={"user_id": cont.id, "email": cont.email})
    a, setari_a = await _proiect(s, ctx, cu_lista=True)
    b, setari_b = await _proiect(s, ctx, cu_lista=True)
    c, _ = await _proiect(s, ctx, cu_lista=False)
    sed_b = await _sedinta(s, ctx, setari_b, ZI_B - timedelta(minutes=7))   # rotația: „jos”
    sed_a = await _sedinta(s, ctx, setari_a, ZI_A - timedelta(minutes=2))   # rotația: „lateral”
    await _note(s, ctx, b.id, str(sed_b.id), NOTE_B, ZI_B, "roleplay")
    await _note(s, ctx, b.id, str(sed_b.id), REZUMAT_B, ZI_B, "session")
    await _note(s, ctx, a.id, str(sed_a.id), NOTE_A, ZI_A, "roleplay")
    await _note(s, ctx, a.id, str(sed_a.id), REZUMAT_A, ZI_A, "session")
    proiecte = {"A": a.id, "B": b.id, "C": c.id, "fara": None}
    return ctx, proiecte, {"A": setari_a, "B": setari_b}, sed_a, sed_b


async def _tablou(s, ctx, proiect_id):
    serviciu = PracticeDashboardService(s)
    return await serviciu.get_participant_dashboard_data(ctx["principal"], proiect_id)


def _pe_nume(t):
    return {c["name"]: c["points"] for c in t["competencies"] if c["points"]}


@pytest.mark.asyncio
async def test_tabloul_pe_a_numai_notele_lui_a() -> None:
    async with SessionLocal() as s:
        ctx, p, _, _, _ = await _fixture(s)
        t = await _tablou(s, ctx, p["A"])
        assert t["points_total"] == 220
        assert _pe_nume(t) == {"Ascultare activă": 50,
                               "Exprimarea asertivă a nevoilor și limitelor": 65,
                               "Gestionarea reacțiilor celorlalți": 55, REZOLVAREA: 50}
        assert sum(c["total_roleplays"] for c in t["competencies"]) == 4
        await s.rollback()


@pytest.mark.asyncio
async def test_tabloul_pe_b_numai_notele_lui_b() -> None:
    async with SessionLocal() as s:
        ctx, p, _, _, _ = await _fixture(s)
        t = await _tablou(s, ctx, p["B"])
        assert t["points_total"] == 40
        assert _pe_nume(t) == {"Feedback constructiv": 40}
        assert sum(c["total_roleplays"] for c in t["competencies"]) == 6
        await s.rollback()


@pytest.mark.asyncio
async def test_proiect_fara_note_porneste_de_la_zero() -> None:
    async with SessionLocal() as s:
        ctx, p, _, _, _ = await _fixture(s)
        d, _ = await _proiect(s, ctx, cu_lista=True)
        for proiect in (p["C"], d.id):
            t = await _tablou(s, ctx, proiect)
            assert t["points_total"] == 0, proiect
            assert t["empty_state"] is not None and t["empty_state"]["kind"] == "neexersat", proiect
        await s.rollback()


@pytest.mark.asyncio
async def test_fara_proiect_numai_notele_fara_proiect() -> None:
    async with SessionLocal() as s:
        ctx, p, _, _, _ = await _fixture(s)
        await _note(s, ctx, None, "arhiva-veche", {"Ascultare activă": 90},
                    ZI_A - timedelta(days=5), "roleplay")
        fara = await _tablou(s, ctx, None)
        assert _pe_nume(fara) == {"Ascultare activă": 40}
        assert fara["points_total"] == 40
        for k in ("A", "B", "C"):
            t = await _tablou(s, ctx, p[k])
            assert sum(c["total_roleplays"] for c in t["competencies"]
                       if c["name"] == "Ascultare activă") == {"A": 1, "B": 1, "C": 0}[k], k
        await s.rollback()


@pytest.mark.asyncio
async def test_regula_60_pe_proiect() -> None:
    async with SessionLocal() as s:
        ctx, p, setari, _, _ = await _fixture(s)
        cand = ZI_A + timedelta(days=3)
        sed = await _sedinta(s, ctx, setari["A"], cand)
        await _note(s, ctx, p["A"], str(sed.id), {"Gestionarea propriilor reacții emoționale": 59},
                    cand, "roleplay")
        sed_b = await _sedinta(s, ctx, setari["B"], cand + timedelta(hours=1))
        await _note(s, ctx, p["B"], str(sed_b.id),
                    {"Gestionarea propriilor reacții emoționale": 65},
                    cand + timedelta(hours=1), "roleplay")
        pe_a = _pe_nume(await _tablou(s, ctx, p["A"]))
        pe_b = _pe_nume(await _tablou(s, ctx, p["B"]))
        # pe A: 59 → 0 (iar 65 e pe B); pe B: al 4-lea rol, „client” → 15 + 25
        assert "Gestionarea propriilor reacții emoționale" not in pe_a
        assert pe_b["Gestionarea propriilor reacții emoționale"] == 15 + 25
        await s.rollback()


@pytest.mark.asyncio
async def test_bonusul_de_tip_nou_se_castiga_pe_fiecare_proiect() -> None:
    """Aceeași competență, ACELAȘI tip de interlocutor, ≥ 60 pe A și pe B → bonus pe ambele."""
    async with SessionLocal() as s:
        ctx, p, setari, _, _ = await _fixture(s)
        cand = ZI_A + timedelta(days=4)
        # rotația (leadership): 0 jos (B) · 1 lateral (A) · 2-4 umplutură fără note · 5 lateral (B)
        for h in range(3):
            await _sedinta(s, ctx, setari["B"], cand + timedelta(hours=h))
        sed = await _sedinta(s, ctx, setari["B"], cand + timedelta(hours=3))
        await _note(s, ctx, p["B"], str(sed.id), {"Ascultare activă": 70},
                    cand + timedelta(hours=3), "roleplay")
        # pe A, „Ascultare activă” a luat bonusul „lateral” (75 → 25 + 25); pe B e tot nou
        assert _pe_nume(await _tablou(s, ctx, p["A"]))["Ascultare activă"] == 25 + 25
        assert _pe_nume(await _tablou(s, ctx, p["B"]))["Ascultare activă"] == 20 + 25
        await s.rollback()


@pytest.mark.asyncio
async def test_seria_de_zile_pe_proiect() -> None:
    async with SessionLocal() as s:
        ctx, p, setari, _, _ = await _fixture(s)
        acum = datetime.now(UTC)
        sed = await _sedinta(s, ctx, setari["A"], acum - timedelta(minutes=30))
        await _note(s, ctx, p["A"], str(sed.id), {"Ascultare activă": 70},
                    acum - timedelta(minutes=10), "roleplay")
        assert (await _tablou(s, ctx, p["A"]))["streak_days"] == 1
        assert (await _tablou(s, ctx, p["B"]))["streak_days"] == 0
        await s.rollback()


@pytest.mark.asyncio
async def test_notele_rezumatului_nu_dau_puncte_nicaieri() -> None:
    async with SessionLocal() as s:
        ctx, p, _, _, _ = await _fixture(s)
        for k, proiect in p.items():
            t = await _tablou(s, ctx, proiect)
            nume = {c["name"] for c in t["competencies"]} | {
                c["name"] for c in t.get("other_competencies", [])}
            assert not nume & set(F1), k
        await s.rollback()


@pytest.mark.asyncio
async def test_plus_n_e_cresterea_proiectului_sedintei() -> None:
    if not hasattr(PracticeDashboardService, "puncte_castigate_in_sedinta"):
        pytest.skip("plicul 177 nu e pe ramura asta")
    async with SessionLocal() as s:
        ctx, p, _, _, sed_b = await _fixture(s)
        serviciu = PracticeDashboardService(s)
        castig = await serviciu.puncte_castigate_in_sedinta(ctx["principal"], sed_b.id)
        cu_b = await serviciu.get_participant_dashboard_data(ctx["principal"], p["B"])
        fara_b = await serviciu.get_participant_dashboard_data(ctx["principal"], p["B"],
                                                               fara_sedinta=sed_b.id)
        crestere = cu_b["points_total"] - fara_b["points_total"]
        assert sum(c["points"] for c in castig) == crestere == 40
        for k in ("A", "C", "fara"):
            cu = await serviciu.get_participant_dashboard_data(ctx["principal"], p[k])
            fara = await serviciu.get_participant_dashboard_data(ctx["principal"], p[k],
                                                                 fara_sedinta=sed_b.id)
            assert cu["points_total"] == fara["points_total"], k
        await s.rollback()


@pytest.mark.asyncio
async def test_raspunsul_n_are_alte_competente() -> None:
    async with SessionLocal() as s:
        ctx, p, _, _, _ = await _fixture(s)
        for k, proiect in p.items():
            assert "other_competencies" not in await _tablou(s, ctx, proiect), k
        await s.rollback()
