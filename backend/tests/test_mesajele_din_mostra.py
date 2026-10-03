"""Mesajele din mostră — plicul 177 (texte propuse; Andrei le vede pe probă, `[culori-texte-noi]`).

(a) Tabloul primește nota de azi pe competență (`best_score_today`): cea mai mare notă role-play a
    zilei, în ora României — aceeași notă care dă punctele.
(b) Închiderea întoarce punctele câștigate în ședință (`points_earned`): Tabloul cu notele
    ședinței minus Tabloul fără ele, pe proiectul ședinței — prin construcție, cât crește Tabloul.
Nicio migrare; socoteala punctelor nu se schimbă.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice import router as practice_router
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.models import (
    CompetencyScore,
    PracticeSession,
    ProjectCompetency,
    SessionKind,
    SessionState,
)
from codrut.modules.practice.schemas import PracticeSessionEndRequest
from codrut.modules.practice.scoring import (
    ZONA_ROMANIEI,
    ScoreEntry,
    compute_competency_evidence,
    puncte_pentru_nota,
)
from test_practice_session_flow import create_test_context

AZI = date(2026, 10, 1)


def _intrare(nota, zi, ora=10, sursa="roleplay", tip=None):
    moment = datetime(zi.year, zi.month, zi.day, ora, 0, tzinfo=ZONA_ROMANIEI).astimezone(UTC)
    return ScoreEntry(score=nota, created_at=moment, source_type=sursa, interlocutor=tip)


# ---- (a) nota de azi ------------------------------------------------------------------------

def _nota_azi(intrari):
    return compute_competency_evidence(intrari, AZI).best_score_today


def test_nota_de_azi_e_cea_mai_mare_nota_role_play_a_zilei() -> None:
    ieri = AZI - timedelta(days=1)
    assert _nota_azi([_intrare(55, AZI), _intrare(48, AZI, 14)]) == 55
    assert _nota_azi([_intrare(70, ieri), _intrare(52, AZI)]) == 52
    assert _nota_azi([_intrare(70, ieri)]) is None
    assert _nota_azi([]) is None
    # quiz-ul nu intră, ca la puncte
    assert _nota_azi([_intrare(90, AZI, sursa="quiz"), _intrare(55, AZI)]) == 55


def test_nota_de_azi_pe_ziua_romaniei() -> None:
    # 23:30 ora României pe 30 sept = 20:30 UTC: e „ieri”, nu azi
    tarziu_ieri = _intrare(57, AZI - timedelta(days=1), ora=23)
    assert compute_competency_evidence([tarziu_ieri], AZI).best_score_today is None
    # 00:30 ora României pe 1 oct = 21:30 UTC pe 30 sept: e „azi”
    devreme_azi = _intrare(57, AZI, ora=0)
    assert devreme_azi.created_at.date() == AZI - timedelta(days=1)
    assert compute_competency_evidence([devreme_azi], AZI).best_score_today == 57


def test_nota_de_azi_nu_schimba_punctele() -> None:
    intrari = [_intrare(80, AZI - timedelta(days=2), tip="jos"), _intrare(55, AZI)]
    ev = compute_competency_evidence(intrari, AZI)
    assert (ev.points, ev.points_today, ev.best_score_today) == (30 + 25, 0, 55)


def test_regula_lui_60_scrisa_explicit() -> None:
    assert puncte_pentru_nota(59) == 0
    assert puncte_pentru_nota(60) == 10


# ---- (b) punctele câștigate în ședință -------------------------------------------------------

COMP = "Feedback asertiv"
ALTA = "Delegare"


async def _context(s, grup="leadership"):
    ctx = await create_test_context(s)
    cont = User(email=f"mostra-{uuid.uuid4().hex[:6]}@example.com", password_hash="x",  # noqa: S106
                role=UserRole.participant)
    s.add(cont)
    await s.flush()
    ctx["profile"].user_id = cont.id
    ctx["profile"].role_group = grup
    ctx["principal"] = ctx["principal"].model_copy(update={"user_id": cont.id, "email": cont.email})
    s.add(ProjectCompetency(project_id=ctx["project"].id, name=COMP, order_index=0))
    s.add(ProjectCompetency(project_id=ctx["project"].id, name=ALTA, order_index=1))
    await s.flush()
    return ctx


async def _sedinta(s, ctx, cand, kind=SessionKind.roleplay):
    sed = PracticeSession(
        program_settings_id=ctx["program_settings"].id,
        participant_profile_id=ctx["profile"].id,
        pack_id=ctx["pack"].id,
        kind=kind,
        state=SessionState.closed,
        started_at=cand,
    )
    s.add(sed)
    await s.flush()
    return sed


async def _nota(s, ctx, sed, scor, cand, comp=COMP):
    s.add(CompetencyScore(
        user_id=ctx["principal"].user_id, project_id=ctx["project"].id, score=scor, level=2,
        conversation_id=str(sed.id), competency_name=comp, source_type="roleplay", created_at=cand,
    ))
    await s.flush()


def _azi(ore_in_urma: float) -> datetime:
    """Un moment de azi (ora României), cu `ore_in_urma` ore înainte de acum, dar tot azi."""
    acum = datetime.now(ZONA_ROMANIEI)
    inceput = acum.replace(hour=0, minute=1, second=0, microsecond=0)
    return max(inceput, acum - timedelta(hours=ore_in_urma)).astimezone(UTC)


async def _castig_si_crestere(s, ctx, sed):
    serviciu = PracticeDashboardService(s)
    castig = await serviciu.puncte_castigate_in_sedinta(ctx["principal"], sed.id)
    dupa = await serviciu.get_participant_dashboard_data(ctx["principal"], ctx["project"].id)
    inainte = await serviciu.get_participant_dashboard_data(
        ctx["principal"], ctx["project"].id, fara_sedinta=sed.id
    )
    crestere = dupa["points_total"] - inainte["points_total"]
    assert sum(c["points"] for c in castig) == crestere, "+N = exact creșterea Tabloului"
    return castig


@pytest.mark.asyncio
async def test_prima_sedinta_cu_60_si_primul_tip_reusit() -> None:
    async with SessionLocal() as s:
        ctx = await _context(s)
        sed = await _sedinta(s, ctx, _azi(1))          # primul role-play: tipul „jos”
        await _nota(s, ctx, sed, 60, _azi(1))
        assert await _castig_si_crestere(s, ctx, sed) == [{"competency": COMP, "points": 10 + 25}]
        await s.rollback()


@pytest.mark.asyncio
async def test_tip_deja_reusit_aduce_numai_nota_minus_50() -> None:
    async with SessionLocal() as s:
        ctx = await _context(s, grup="member")          # rotația: lateral, sus, client, lateral
        ieri = datetime.now(UTC) - timedelta(days=4)
        for i in range(3):                              # lateral, sus, client — reușite deja
            vechi = await _sedinta(s, ctx, ieri + timedelta(days=i - 3))
            await _nota(s, ctx, vechi, 80, ieri + timedelta(days=i - 3))
        sed = await _sedinta(s, ctx, _azi(1))           # al patrulea: din nou „lateral”
        await _nota(s, ctx, sed, 60, _azi(1))
        assert await _castig_si_crestere(s, ctx, sed) == [{"competency": COMP, "points": 10}]
        await s.rollback()


@pytest.mark.asyncio
async def test_59_nu_aduce_nimic() -> None:
    async with SessionLocal() as s:
        ctx = await _context(s)
        sed = await _sedinta(s, ctx, _azi(1))
        await _nota(s, ctx, sed, 59, _azi(1))
        assert await _castig_si_crestere(s, ctx, sed) == []
        await s.rollback()


@pytest.mark.asyncio
async def test_a_doua_sedinta_a_zilei_aduce_numai_diferenta_peste_nota_mai_mare() -> None:
    async with SessionLocal() as s:
        ctx = await _context(s, grup="member")
        prima = await _sedinta(s, ctx, _azi(3))         # „lateral”, 70 → 20 + 25
        await _nota(s, ctx, prima, 70, _azi(3))
        slaba = await _sedinta(s, ctx, _azi(2))         # „sus”, 65 după 70: maximul rămâne 70
        await _nota(s, ctx, slaba, 65, _azi(2))
        # „sus” e un tip nou reușit (65 ≥ 60): +25, fără puncte din notă
        assert await _castig_si_crestere(s, ctx, slaba) == [{"competency": COMP, "points": 25}]
        mai_buna = await _sedinta(s, ctx, _azi(1))      # „client”, 75 după 70: +5, +25 tip nou
        await _nota(s, ctx, mai_buna, 75, _azi(1))
        castig = await _castig_si_crestere(s, ctx, mai_buna)
        assert castig == [{"competency": COMP, "points": 5 + 25}]
        await s.rollback()


@pytest.mark.asyncio
async def test_a_doua_sedinta_mai_slaba_fara_tip_nou_nu_aduce_nimic() -> None:
    async with SessionLocal() as s:
        ctx = await _context(s, grup="member")
        acum = datetime.now(UTC)
        vechi = [await _sedinta(s, ctx, acum - timedelta(days=9 - i)) for i in range(3)]
        for i, v in enumerate(vechi):                   # lateral, sus, client — toate reușite
            await _nota(s, ctx, v, 80, datetime.now(UTC) - timedelta(days=9 - i))
        prima = await _sedinta(s, ctx, _azi(2))         # lateral din nou, 70
        await _nota(s, ctx, prima, 70, _azi(2))
        a_doua = await _sedinta(s, ctx, _azi(1))        # sus din nou, 65 după 70
        await _nota(s, ctx, a_doua, 65, _azi(1))
        assert await _castig_si_crestere(s, ctx, a_doua) == []
        await s.rollback()


@pytest.mark.asyncio
async def test_doua_competente_numai_cea_cu_puncte() -> None:
    async with SessionLocal() as s:
        ctx = await _context(s)
        sed = await _sedinta(s, ctx, _azi(1))
        await _nota(s, ctx, sed, 62, _azi(1), COMP)
        await _nota(s, ctx, sed, 55, _azi(1), ALTA)
        assert await _castig_si_crestere(s, ctx, sed) == [{"competency": COMP, "points": 12 + 25}]
        await s.rollback()


@pytest.mark.asyncio
async def test_sedinta_fara_note_si_sedinta_care_nu_e_role_play() -> None:
    async with SessionLocal() as s:
        ctx = await _context(s)
        scurta = await _sedinta(s, ctx, _azi(2))        # prea scurtă: nicio notă
        assert await _castig_si_crestere(s, ctx, scurta) == []
        quiz = await _sedinta(s, ctx, _azi(1), kind=SessionKind.knowledge)
        await _nota(s, ctx, quiz, 90, _azi(1))
        assert await _castig_si_crestere(s, ctx, quiz) == []
        await s.rollback()


@pytest.mark.asyncio
async def test_competenta_din_afara_proiectului_nu_apare() -> None:
    async with SessionLocal() as s:
        ctx = await _context(s)
        sed = await _sedinta(s, ctx, _azi(1))
        await _nota(s, ctx, sed, 90, _azi(1), "Negociere")  # nu e a proiectului — ca pe Tablou
        # plicul 178: pe Tablou apare la „Alte competențe exersate”, deci și în „+N”
        castig = await _castig_si_crestere(s, ctx, sed)
        assert castig == [{"competency": "Negociere", "points": 40 + 25}]
        await s.rollback()


@pytest.mark.asyncio
async def test_tabloul_trimite_nota_de_azi() -> None:
    async with SessionLocal() as s:
        ctx = await _context(s)
        sed = await _sedinta(s, ctx, _azi(1))
        await _nota(s, ctx, sed, 55, _azi(1))
        date_ = await PracticeDashboardService(s).get_participant_dashboard_data(
            ctx["principal"], ctx["project"].id
        )
        pe_nume = {c["name"]: c for c in date_["competencies"]}
        assert pe_nume[COMP]["best_score_today"] == 55
        assert pe_nume[ALTA]["best_score_today"] is None
        await s.rollback()


# ---- ruta de închidere ------------------------------------------------------------------------

class _ServiciuInchidere:
    def __init__(self, session):
        self.session = session

    async def end_session(self, principal, session_id, outcome_kind, note):
        sed = await self.session.get(PracticeSession, session_id)
        sed.state = SessionState.closed
        sed.ended_at = datetime.now(UTC)
        return sed, "Sinteza."


@pytest.mark.asyncio
async def test_ruta_de_inchidere_intoarce_punctele(monkeypatch) -> None:
    async with SessionLocal() as s:
        ctx = await _context(s)
        sed = await _sedinta(s, ctx, _azi(1))
        await _nota(s, ctx, sed, 70, _azi(1))
        monkeypatch.setattr(practice_router, "PracticeSessionService", _ServiciuInchidere)
        monkeypatch.setattr(s, "commit", s.flush)
        raspuns = await practice_router.end_practice_session(
            sed.id, PracticeSessionEndRequest(), ctx["principal"], s
        )
        assert raspuns.summary == "Sinteza."
        castig = [p.model_dump() for p in raspuns.points_earned]
        assert castig == [{"competency": COMP, "points": 20 + 25}]
        assert "points_earned" in raspuns.model_dump()
        await s.rollback()


@pytest.mark.asyncio
async def test_inchiderea_nu_pica_din_cauza_anuntului(monkeypatch) -> None:
    async with SessionLocal() as s:
        ctx = await _context(s)
        sed = await _sedinta(s, ctx, _azi(1))

        async def _arunca(self, principal, session_id):
            raise RuntimeError("anunțul a picat")

        monkeypatch.setattr(practice_router, "PracticeSessionService", _ServiciuInchidere)
        monkeypatch.setattr(PracticeDashboardService, "puncte_castigate_in_sedinta", _arunca)
        monkeypatch.setattr(s, "commit", s.flush)
        raspuns = await practice_router.end_practice_session(
            sed.id, PracticeSessionEndRequest(), ctx["principal"], s
        )
        assert raspuns.session.state == SessionState.closed
        assert raspuns.points_earned == []
        await s.rollback()
