"""Competențele din afara listei nu mai dispar de pe Tablou — plicul 178 (H4).

Tabloul ia toate notele omului, din toate proiectele, dar le grupa pe lista proiectului DESCHIS:
nota fără loc dispărea, iar totalul depindea de proiect (contul de test: 260 sau 210, raportul 172).
Acum notele evaluatorului care nu sunt pe listă stau la „Alte competențe exersate”, cu aceeași
socoteală, și intră în total. Notele rezumatului de la închidere (4 nume fixe, aplicația veche)
rămân afară, ca de la plicul 143 — hotărârea e a lui Andrei.

Fixture-ul e cel din raportul 172 (fără nume de oameni): două ședințe role-play, pe B și pe A.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.companies.models import CompanyProject, CompanyProjectStatus
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice import competency_aliases
from codrut.modules.practice import service as practice_service
from codrut.modules.practice.competency_aliases import NUMELE_DIN_REZUMAT
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
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context
from test_sesiunea_prea_scurta import FurnizorCuSinteza

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
F1 = list(NUMELE_DIN_REZUMAT.values())
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


async def _note(s, ctx, proiect, conversatie, note, cand, sursa):
    for nume, scor in note.items():
        s.add(CompetencyScore(user_id=ctx["principal"].user_id, project_id=proiect.id, score=scor,
                              level=2, conversation_id=conversatie, competency_name=nume,
                              source_type=sursa, created_at=cand))
    await s.flush()


async def _fixture(s):
    ctx = await create_test_context(s)
    cont = User(email=f"h4-{uuid.uuid4().hex[:6]}@example.com", password_hash="x",  # noqa: S106
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
    await _note(s, ctx, b, str(sed_b.id), NOTE_B, ZI_B, "roleplay")
    await _note(s, ctx, b, str(sed_b.id), REZUMAT_B, ZI_B, "session")
    await _note(s, ctx, a, str(sed_a.id), NOTE_A, ZI_A, "roleplay")
    await _note(s, ctx, a, str(sed_a.id), REZUMAT_A, ZI_A, "session")
    return ctx, {"A": a.id, "B": b.id, "C": c.id, "fara": None}, sed_a, sed_b


async def _vederi(s, ctx, proiecte, fara_sedinta=None):
    serviciu = PracticeDashboardService(s)
    return {
        k: await serviciu.get_participant_dashboard_data(
            ctx["principal"], p, fara_sedinta=fara_sedinta
        )
        for k, p in proiecte.items()
    }


def _puncte_pe_nume(tablou):
    return {c["name"]: c["points"] for c in tablou["competencies"] + tablou["other_competencies"]}


@pytest.mark.asyncio
async def test_aceleasi_note_dau_acelasi_total_pe_orice_proiect() -> None:
    async with SessionLocal() as s:
        ctx, proiecte, _, _ = await _fixture(s)
        vederi = await _vederi(s, ctx, proiecte)
        # azi: 260 pe A și B, 210 pe C (fără listă) și fără proiect
        totaluri = {k: v["points_total"] for k, v in vederi.items()}
        assert totaluri == {"A": 260, "B": 260, "C": 260, "fara": 260}
        await s.rollback()


@pytest.mark.asyncio
async def test_punctele_unei_competente_nu_depind_de_vedere_si_alte_competente() -> None:
    async with SessionLocal() as s:
        ctx, proiecte, _, _ = await _fixture(s)
        vederi = await _vederi(s, ctx, proiecte)
        toate: dict[str, set[int]] = {}
        for v in vederi.values():
            for nume, p in _puncte_pe_nume(v).items():
                toate.setdefault(nume, set()).add(p)
        assert all(len(p) == 1 for p in toate.values()), toate
        alte_c = [(c["name"], c["points"]) for c in vederi["C"]["other_competencies"]]
        assert alte_c == [(REZOLVAREA, 50)]
        assert vederi["A"]["other_competencies"] == []
        assert [c["name"] for c in vederi["A"]["competencies"]] == LISTA      # lista, neatinsă
        await s.rollback()


@pytest.mark.asyncio
async def test_notele_rezumatului_raman_afara_pe_toate_vederile() -> None:
    async with SessionLocal() as s:
        ctx, proiecte, _, _ = await _fixture(s)
        for v in (await _vederi(s, ctx, proiecte)).values():
            assert not set(_puncte_pe_nume(v)) & set(F1)
        await s.rollback()


@pytest.mark.asyncio
async def test_rezumatul_cu_o_cheie_necunoscuta_tot_afara() -> None:
    """Corecția 2: o notă `session` pe o ședință existentă e a rezumatului, oricum s-ar numi."""
    async with SessionLocal() as s:
        ctx, proiecte, sed_a, _ = await _fixture(s)
        a = await s.get(CompanyProject, proiecte["A"])
        await _note(s, ctx, a, str(sed_a.id), {"empathy": 90}, ZI_A, "session")
        vederi = await _vederi(s, ctx, proiecte)
        for v in vederi.values():
            assert "empathy" not in _puncte_pe_nume(v)
            assert v["points_total"] == 260
        await s.rollback()


@pytest.mark.asyncio
async def test_quiz_din_arhiva_nu_apare_la_alte() -> None:
    async with SessionLocal() as s:
        ctx, proiecte, _, _ = await _fixture(s)
        a = await s.get(CompanyProject, proiecte["A"])
        await _note(s, ctx, a, "arhiva-veche", {"Quiz": 100}, ZI_A, "quiz")
        await _note(s, ctx, a, "arhiva-veche", {"Delegare": 70}, ZI_A, "quiz")
        for v in (await _vederi(s, ctx, proiecte)).values():
            assert "Quiz" not in _puncte_pe_nume(v)
            assert "Delegare" not in _puncte_pe_nume(v)
        await s.rollback()


@pytest.mark.asyncio
async def test_doua_scrieri_ale_aceluiasi_nume_un_singur_card() -> None:
    async with SessionLocal() as s:
        ctx, proiecte, _, _ = await _fixture(s)
        b = await s.get(CompanyProject, proiecte["B"])
        sed = await _sedinta(s, ctx, (await s.execute(select(PracticeProgramSettings).where(
            PracticeProgramSettings.project_id == b.id))).scalar_one(), ZI_A + timedelta(days=1))
        await _note(s, ctx, b, str(sed.id), {"rezolvarea  colaborativa a conflictelor": 85},
                    ZI_A + timedelta(days=1), "roleplay")
        alte = (await _vederi(s, ctx, {"C": proiecte["C"]}))["C"]["other_competencies"]
        assert len(alte) == 1
        await s.rollback()


@pytest.mark.asyncio
async def test_plus_n_e_cresterea_pe_orice_proiect_si_pe_orice_nume() -> None:
    async with SessionLocal() as s:
        ctx, proiecte, sed_a, sed_b = await _fixture(s)
        serviciu = PracticeDashboardService(s)
        for sed in (sed_a, sed_b):
            castig = await serviciu.puncte_castigate_in_sedinta(ctx["principal"], sed.id)
            cu = await _vederi(s, ctx, proiecte)
            fara = await _vederi(s, ctx, proiecte, fara_sedinta=sed.id)
            for k in proiecte:
                crestere = cu[k]["points_total"] - fara[k]["points_total"]
                assert sum(c["points"] for c in castig) == crestere, k
                pc, pf = _puncte_pe_nume(cu[k]), _puncte_pe_nume(fara[k])
                for c in castig:
                    assert c["points"] == pc[c["competency"]] - pf.get(c["competency"], 0), (k, c)
        await s.rollback()


@pytest.mark.asyncio
async def test_plus_n_cand_scrierea_noua_e_in_sedinta_scoasa() -> None:
    """Corecția 1: numele afișat la „alte” nu depinde de ședința scoasă."""
    async with SessionLocal() as s:
        ctx, proiecte, _, _ = await _fixture(s)
        c = await s.get(CompanyProject, proiecte["C"])
        setari_c = (await s.execute(select(PracticeProgramSettings).where(
            PracticeProgramSettings.project_id == c.id))).scalar_one()
        cand = ZI_A + timedelta(days=2)
        sed = await _sedinta(s, ctx, setari_c, cand)   # ședința pe C, cu o scriere nouă a numelui
        await _note(s, ctx, c, str(sed.id), {"REZOLVAREA colaborativa a conflictelor!": 90},
                    cand, "roleplay")
        serviciu = PracticeDashboardService(s)
        castig = await serviciu.puncte_castigate_in_sedinta(ctx["principal"], sed.id)
        cu = (await _vederi(s, ctx, {"C": c.id}))["C"]
        fara = (await _vederi(s, ctx, {"C": c.id}, fara_sedinta=sed.id))["C"]
        assert len(cu["other_competencies"]) == 1 and len(fara["other_competencies"]) == 1
        assert cu["other_competencies"][0]["name"] == fara["other_competencies"][0]["name"]
        crestere = cu["points_total"] - fara["points_total"]
        assert sum(x["points"] for x in castig) == crestere == 40 + 25
        await s.rollback()


@pytest.mark.asyncio
async def test_59_in_afara_listei_nu_aduce_nimic() -> None:
    async with SessionLocal() as s:
        ctx, proiecte, _, _ = await _fixture(s)
        b = await s.get(CompanyProject, proiecte["B"])
        setari_b = (await s.execute(select(PracticeProgramSettings).where(
            PracticeProgramSettings.project_id == b.id))).scalar_one()
        cand = ZI_A + timedelta(days=3)
        sed = await _sedinta(s, ctx, setari_b, cand)
        await _note(s, ctx, b, str(sed.id), {"Negociere": 59}, cand, "roleplay")
        serviciu = PracticeDashboardService(s)
        assert await serviciu.puncte_castigate_in_sedinta(ctx["principal"], sed.id) == []
        await s.rollback()


def test_numele_rezumatului_sunt_exact_cele_patru_si_vin_dintr_un_singur_loc() -> None:
    assert NUMELE_DIN_REZUMAT == {
        "questionsRatio": "Abilități de Coach și Întrebări",
        "assertiveness": "Comunicare Asertivă",
        "sbiFeedback": "Feedback Structurat (SBI)",
        "conciseness": "Concizie și Echilibru",
    }
    assert practice_service.NUMELE_DIN_REZUMAT is competency_aliases.NUMELE_DIN_REZUMAT


@pytest.mark.asyncio
async def test_inchiderea_scrie_aceleasi_patru_nume_ca_inainte() -> None:
    settings = Settings(generation_provider="local")
    provider = FurnizorCuSinteza(settings)
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        cont = User(id=ctx["principal"].user_id, email=ctx["principal"].email,
                    password_hash="x", role=UserRole.participant)  # noqa: S106
        s.add(cont)
        await s.flush()
        ctx["profile"].user_id = cont.id
        await s.flush()
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        serviciu = PracticeSessionService(session=s, redis=redis, generation_provider=provider,
                                          settings=settings)
        sedinta, _ = await serviciu.start_session(
            principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay)
        replici = (
            "Da, hai.",
            "Înțeleg ce spui. Ce anume te-a deranjat cel mai tare în situația asta, concret?",
            "Raportul a întârziat de trei ori; echipa a trimis cifre greșite clientului.",
            "Aș vrea să stabilim împreună un termen clar pentru următorul raport, joi la prânz.",
        )
        for r in replici:
            await serviciu.add_participant_turn(
                principal=ctx["principal"], session_id=sedinta.id, text=r)
        await serviciu.end_session(principal=ctx["principal"], session_id=sedinta.id)
        nume = (await s.execute(select(CompetencyScore.competency_name).where(
            CompetencyScore.conversation_id == str(sedinta.id),
            CompetencyScore.source_type == "session"))).scalars().all()
        assert sorted(nume) == sorted(NUMELE_DIN_REZUMAT.values())
        await s.rollback()
        await redis.aclose()
