"""Punctele, nivelurile și notele, socotite de mână — banca de probă, stratul 1 (plicul 215).

Valorile așteptate sunt calculate în comentarii, din regulile scrise (`scoring.py`, plicul 165;
`evolution_service.py`, plicul 166 D; `evaluator.md:12`), NU copiate din ce întoarce codul.
Testele `xfail(strict=True)` afirmă purtarea dorită și pică azi: sunt defectele găsite.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.evolution_service import PracticeEvolutionService
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import CompetencyScore, ProjectCompetency, SessionKind
from codrut.modules.practice.scoring import ScoreEntry, compute_competency_evidence, ziua_in_romania
from codrut.modules.practice.service import PracticeSessionService
from test_evolutia_pe_om import COMP, _note, _om
from test_practice_session_flow import create_test_context

ZIUA_0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)  # 12:00 în ora României, departe de miezul nopții


def _e(zi: int, nota: int, tip: str | None = None) -> ScoreEntry:
    return ScoreEntry(score=nota, created_at=ZIUA_0 + timedelta(days=zi),
                      source_type="roleplay", interlocutor=tip)


def _azi(zi: int) -> date:
    return (ZIUA_0 + timedelta(days=zi)).date()


# --- pragurile de puncte -----------------------------------------------------------------

def test_99_de_puncte_e_constientizare_100_e_aplicare() -> None:
    # 100 → 50 de puncte; 99 → 49: total 99. Două note de 100 → 100.
    sub = compute_competency_evidence([_e(0, 100), _e(1, 99)], today=_azi(1))
    la = compute_competency_evidence([_e(0, 100), _e(1, 100)], today=_azi(1))
    assert (sub.points, sub.level) == (99, "CONȘTIENTIZARE")
    assert (la.points, la.level) == (100, "APLICARE")


def _consolidare(ultima: int) -> list[ScoreEntry]:
    # ziua 0: 100 cu „jos” → 50 + 25 (tip nou) = 75; ziua 1: 100 cu „lateral” → 75;
    # zilele 2–5: patru note de 100 fără tip → 200; ziua 6: `ultima` → ultima − 50.
    # Cu ultima = 100: 75 + 75 + 200 + 50 = 400. Cu 99: 399.
    return [_e(0, 100, "jos"), _e(1, 100, "lateral"),
            *[_e(z, 100) for z in range(2, 6)], _e(6, ultima)]


def test_399_cu_doua_tipuri_e_aplicare_400_e_consolidare() -> None:
    sub = compute_competency_evidence(_consolidare(99), today=_azi(6))
    la = compute_competency_evidence(_consolidare(100), today=_azi(6))
    assert (sub.points, sub.interlocutor_types, sub.level) == (399, 2, "APLICARE")
    assert (la.points, la.interlocutor_types, la.level) == (400, 2, "CONSOLIDARE")


def test_400_cu_un_singur_tip_ramane_aplicare() -> None:
    # 75 (jos, tip nou) + șase note de 100 fără tip (300) + o notă de 75 (25) = 400, un tip
    intrari = [_e(0, 100, "jos"), *[_e(z, 100) for z in range(1, 7)], _e(7, 75)]
    d = compute_competency_evidence(intrari, today=_azi(7))
    assert (d.points, d.interlocutor_types, d.level) == (400, 1, "APLICARE")


def _integrare(ultima: int) -> list[ScoreEntry]:
    # trei tipuri în zilele 0–2: 3 × (50 + 25) = 225; zilele 3–17: 15 note de 100 = 750;
    # ziua 18: `ultima` → 75 dă 25 (total 1000), 74 dă 24 (total 999).
    return [_e(0, 100, "jos"), _e(1, 100, "lateral"), _e(2, 100, "sus"),
            *[_e(z, 100) for z in range(3, 18)], _e(18, ultima)]


def test_999_e_consolidare_1000_e_integrare() -> None:
    sub = compute_competency_evidence(_integrare(74), today=_azi(60))
    la = compute_competency_evidence(_integrare(75), today=_azi(60))
    assert (sub.points, sub.interlocutor_types, sub.level) == (999, 3, "CONSOLIDARE")
    assert (la.points, la.interlocutor_types, la.level) == (1000, 3, "INTEGRARE")


def test_55_de_zile_de_la_prima_nota_e_consolidare_56_e_integrare() -> None:
    # aceleași 1000 de puncte și trei tipuri; prima notă e în ziua 0
    assert compute_competency_evidence(_integrare(75), today=_azi(55)).level == "CONSOLIDARE"
    assert compute_competency_evidence(_integrare(75), today=_azi(56)).level == "INTEGRARE"


def test_aceeasi_zi_doua_tipuri_70_jos_si_85_lateral() -> None:
    # ziua numără numai nota cea mai mare: 85 → 35; ambele note ≥ 60, deci două tipuri noi:
    # + 25 + 25. Total 35 + 50 = 85.
    d = compute_competency_evidence([_e(0, 70, "jos"), _e(0, 85, "lateral")], today=_azi(0))
    assert (d.points, d.interlocutor_types, d.best_score_today) == (85, 2, 85)


# --- ziua în ora României, la schimbarea orei (2026) -----------------------------------------

def test_ziua_in_romania_la_trecerea_la_ora_de_vara() -> None:
    # 29 martie 2026, ora 03:00 locală devine 04:00 (EET +2 → EEST +3)
    assert ziua_in_romania(datetime(2026, 3, 28, 21, 30, tzinfo=UTC)) == date(2026, 3, 28)
    assert ziua_in_romania(datetime(2026, 3, 28, 22, 30, tzinfo=UTC)) == date(2026, 3, 29)
    assert ziua_in_romania(datetime(2026, 3, 29, 21, 30, tzinfo=UTC)) == date(2026, 3, 30)
    # două note la o oră distanță, în zile diferite în România → amândouă numără: 50 + 50
    intrari = [ScoreEntry(100, datetime(2026, 3, 28, 21, 30, tzinfo=UTC), "roleplay"),
               ScoreEntry(100, datetime(2026, 3, 28, 22, 30, tzinfo=UTC), "roleplay")]
    assert compute_competency_evidence(intrari, today=date(2026, 3, 29)).points == 100


def test_ziua_in_romania_la_trecerea_la_ora_de_iarna() -> None:
    # 25 octombrie 2026, ora 04:00 locală devine 03:00 (EEST +3 → EET +2)
    assert ziua_in_romania(datetime(2026, 10, 24, 21, 30, tzinfo=UTC)) == date(2026, 10, 25)
    assert ziua_in_romania(datetime(2026, 10, 25, 21, 30, tzinfo=UTC)) == date(2026, 10, 25)
    # 24 de ore UTC distanță, dar aceeași zi în România → numără numai nota mai mare: 100 → 50
    intrari = [ScoreEntry(100, datetime(2026, 10, 24, 21, 30, tzinfo=UTC), "roleplay"),
               ScoreEntry(90, datetime(2026, 10, 25, 21, 30, tzinfo=UTC), "roleplay")]
    assert compute_competency_evidence(intrari, today=date(2026, 10, 25)).points == 50


# --- echipa (evolution_service.py:140-152) -------------------------------------------------

async def _evolutia(note_pe_om: list[list[tuple[int, int]]]) -> dict:
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        s.add(ProjectCompetency(project_id=ctx["project"].id, name=COMP, order_index=0))
        for i, note in enumerate(note_pe_om):
            await _note(s, ctx, await _om(s, ctx, f"Om {i}"), note)
        date_ = await PracticeEvolutionService(s).project_evolution(ctx["project"].id)
        await s.rollback()
    return next(c for c in date_["competencies"] if c["name"] == COMP)


async def test_doi_oameni_cu_10_si_15_puncte() -> None:
    # 60 → 10 puncte; 65 → 15. Media (10 + 15) / 2 = 12,5 și `round(12.5)` = 12 (rotunjire la
    # par, nu în sus). Nivelul = al omului median; la doi, cel de jos (cel cu 10).
    comp = await _evolutia([[(0, 60)], [(0, 65)]])
    assert comp["points"] == 12
    assert comp["level"] == "CONȘTIENTIZARE"
    assert comp["people_count"] == 2


async def test_trei_oameni_cu_30_120_500_de_puncte() -> None:
    # 80 → 30; trei note de 90 → 120; zece note de 100 → 500 (fără tipuri: Aplicare).
    # Media (30 + 120 + 500) / 3 = 216,67 → 217. Omul median are 120 → Aplicare.
    comp = await _evolutia([[(0, 80)], [(z, 90) for z in range(3)],
                            [(z, 100) for z in range(10)]])
    assert comp["points"] == 217
    assert comp["level"] == "APLICARE"
    assert comp["levels_count"]["APLICARE"] == 2
    assert comp["levels_count"]["CONȘTIENTIZARE"] == 1


# --- quiz-ul lângă role-play ---------------------------------------------------------------

async def _quiz_si_roleplay() -> dict:
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        s.add(ProjectCompetency(project_id=ctx["project"].id, name=COMP, order_index=0))
        om = await _om(s, ctx, "Om cu quiz")
        await _note(s, ctx, om, [(0, 60)])  # role-play: 60 → 10 puncte
        s.add(CompetencyScore(user_id=om, project_id=ctx["project"].id, score=100, level=3,
                              conversation_id=f"quiz-{uuid.uuid4().hex[:6]}",
                              competency_name=COMP, source_type="cunostinte",
                              created_at=datetime.now(UTC) - timedelta(days=10)))
        await s.flush()
        date_ = await PracticeEvolutionService(s).project_evolution(ctx["project"].id)
        await s.rollback()
    return {"comp": next(c for c in date_["competencies"] if c["name"] == COMP),
            "saptamani": date_["weekly_average"]}


async def test_azi_quizul_intra_in_media_dar_nu_in_puncte() -> None:
    r = await _quiz_si_roleplay()
    assert r["comp"]["points"] == 10  # numai role-play-ul: 60 − 50
    assert r["comp"]["level"] == "CONȘTIENTIZARE"
    assert r["comp"]["current_average"] == 80.0  # (60 + 100) / 2
    assert [p["average"] for p in r["saptamani"]] == [80.0]


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="BANCA-DEFECT-04: media competenței și media pe săptămâni ale "
                          "echipei amestecă nota de quiz cu notele de role-play "
                          "(evolution_service.py:158 și :167); punctele și nivelul n-o fac.")
async def test_media_competentei_e_numai_din_role_play() -> None:
    r = await _quiz_si_roleplay()
    assert r["comp"]["current_average"] == 60.0
    assert [p["average"] for p in r["saptamani"]] == [60.0]


# --- rezumatul de la închidere (service.py:1527-1539) ---------------------------------------

SINTEZA = (
    "##Concluzie\nAi rămas calm.\n\n##Recomandări\n• Fii mai concret.\n"
    '```json\n{"topic": "Termene", "characters": [], "scores": {"questionsRatio": 4, '
    '"assertiveness": 7.5, "sbiFeedback": 8.25, "conciseness": 3.6}}\n```'
)
REPLICI = (
    "Da, hai.",
    "Înțeleg ce spui. Ce anume te-a deranjat cel mai tare în situația asta, concret?",
    "Raportul a întârziat de trei ori; echipa a trimis cifre greșite clientului.",
    "Aș vrea să stabilim împreună un termen clar pentru următorul raport, joi la prânz.",
)


class FurnizorCuRezumat(LocalGenerationProvider):
    async def generate(self, request):
        rez = await super().generate(request)
        if request.system_instruction == "Ești analizator de discurs.":
            return replace(rez, text=SINTEZA)
        return rez


async def _notele_rezumatului() -> dict[str, tuple[int, int]]:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        cont = User(id=ctx["principal"].user_id, email=ctx["principal"].email,
                    password_hash="x", role=UserRole.participant)  # noqa: S106
        session.add(cont)
        await session.flush()
        ctx["profile"].user_id = cont.id
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis,
                                         generation_provider=FurnizorCuRezumat(settings),
                                         settings=settings)
        sedinta, _ = await service.start_session(
            principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        for r in REPLICI:
            await service.add_participant_turn(principal=ctx["principal"],
                                               session_id=sedinta.id, text=r)
        await service.end_session(principal=ctx["principal"], session_id=sedinta.id)
        note = (await session.execute(select(CompetencyScore).where(
            CompetencyScore.conversation_id == str(sedinta.id),
            CompetencyScore.justification.like("Scor evaluat automat%"),
        ))).scalars().all()
        rezultat = {n.competency_name: (n.score, n.level) for n in note}
        await session.rollback()
        await redis.aclose()
    return rezultat


async def test_azi_rezumatul_pune_nivelul_cu_pragurile_50_si_80() -> None:
    # 4 → 40, 7.5 → 75, 8.25 → `int(round(82.5))` = 82 (rotunjire la par), 3.6 → 36.
    # Pragurile rezumatului: sub 50 → 1, sub 80 → 2, altfel 3.
    assert await _notele_rezumatului() == {
        "Abilități de Coach și Întrebări": (40, 1),
        "Comunicare Asertivă": (75, 2),
        "Feedback Structurat (SBI)": (82, 3),
        "Concizie și Echilibru": (36, 1),
    }


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="BANCA-DEFECT-05: rezumatul de la închidere pune nivelul cu pragurile "
                          "50/80 (service.py:1537-1539), iar evaluatorul cu 36/70 "
                          "(evaluator.md:12): 40, 75 și 36 primesc alt nivel decât la evaluator.")
async def test_rezumatul_pune_nivelul_ca_evaluatorul() -> None:
    # evaluator.md:12 — 1 (0-35), 2 (36-69), 3 (70-100)
    assert await _notele_rezumatului() == {
        "Abilități de Coach și Întrebări": (40, 2),
        "Comunicare Asertivă": (75, 3),
        "Feedback Structurat (SBI)": (82, 3),
        "Concizie și Echilibru": (36, 2),
    }


# --- nota pierdută la 15 secunde (service.py:480-486) ---------------------------------------

async def test_nota_pierduta_la_15_secunde_apare_numai_in_jurnal(caplog) -> None:
    # DE HOTĂRÂT: un numărător pentru notele lipsă; azi nu există nimic în afara jurnalului
    class Lent:
        apeluri = 0

        async def generate(self, cerere):
            Lent.apeluri += 1
            await asyncio.sleep(1.0)

    setari = Settings(generation_provider="local").model_copy(
        update={"vertex_timeout_evaluator_replica_seconds": 0.1})
    service = PracticeSessionService(session=MagicMock(), redis=MagicMock(),
                                     generation_provider=Lent(), settings=setari)
    inceput = time.monotonic()
    with caplog.at_level(logging.WARNING):
        rezultat = await service._evaluatorul(MagicMock(), "sesiune-banca")
    assert rezultat is None
    assert Lent.apeluri == 1
    assert time.monotonic() - inceput < 0.5
    assert [r.getMessage() for r in caplog.records
            if "practice_evaluator_esuat" in r.getMessage()] == [
        "practice_evaluator_esuat sesiune=sesiune-banca incercarea=1 motiv=timp"
    ]
