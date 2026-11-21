"""Patru întăriri la reparațiile notelor (218) și ale jurnalului (220) — plicul 223.

1. Un scor uriaș (1e30, 10**30, 40 de cifre) sare numai nota lui; restul răspunsului se salvează.
2. Un scor negativ, număr, se sare (nu mai devine 0 tăcut).
3. Rezumatul de la închidere citește notele cu același cititor ca evaluatorul: `True`, NaN, inf,
   uriaș, negativ → nota aceea se sare, restul notelor și memoria se salvează.
4. Jurnalul închiderii scrie numai tipul erorii, nu textul ei.
Plus paza care lipsea (218 O3): nota unei ședințe de coaching nu intră în media competenței.
"""

import logging
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice import evaluator as ev
from codrut.modules.practice.evaluator import PracticeEvaluator
from codrut.modules.practice.evolution_service import PracticeEvolutionService
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import (
    CompetencyScore,
    InsightMoment,
    ParticipantMemory,
    PracticeSession,
    ProjectCompetency,
    SessionKind,
    SessionState,
)
from codrut.modules.practice.service import PracticeSessionService
from test_evolutia_pe_om import COMP, _note, _om
from test_practice_session_flow import create_test_context

MARCAJ = "MARCAJ-PLIC223-text din eroare"

# --- 1 și 2: evaluatorul (`_persist`) ------------------------------------------------------------


class SesiuneFalsa:
    def __init__(self) -> None:
        self.adaugate: list = []

    def add(self, obiect) -> None:
        self.adaugate.append(obiect)

    async def flush(self) -> None:
        return None


async def _salveaza(scor) -> SesiuneFalsa:
    date = {
        "scores": [
            {"competency": "Ascultare activă", "evaluated": True, "score": 72, "level": 3,
             "justification": "x"},
            {"competency": "Comunicare asertivă", "evaluated": True, "score": scor, "level": 3,
             "justification": "x"},
            {"competency": "Feedback constructiv", "evaluated": True, "score": 40, "level": 2,
             "justification": "x"},
        ],
        "insight": "A rămas calm.",
        "recommendations_for_trainer": [
            {"competency": "Feedback constructiv", "score": 40, "analysis": "Prea general.",
             "actions": ["SBI"]},
        ],
    }
    sesiune = SesiuneFalsa()
    evaluator = PracticeEvaluator(sesiune, generation_provider=None, settings=None)
    await evaluator._persist(date=date, session_id=uuid.uuid4(), user_id=uuid.uuid4(),
                             project_id=None, source_type="session")
    return sesiune


def _notele(s: SesiuneFalsa) -> dict[str, tuple[int, int]]:
    return {o.competency_name: (o.score, o.level) for o in s.adaugate
            if isinstance(o, CompetencyScore)}


@pytest.mark.parametrize(
    "scor", [1e28, 1e30, 10**30, "1" * 40, -5, -5.0],
    ids=["1e28", "1e30", "10la30", "40-de-cifre", "minus5", "minus5.0"],
)
async def test_scorul_urias_sau_negativ_sare_numai_nota_lui(scor, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        s = await _salveaza(scor)
    note = _notele(s)
    assert "Comunicare asertivă" not in note
    assert note["Ascultare activă"] == (72, 3)
    assert note["Feedback constructiv"] == (40, 2)
    assert sum(1 for o in s.adaugate if isinstance(o, InsightMoment)) == 2
    sarite = [r.getMessage() for r in caplog.records if "practice_nota_sarita" in r.getMessage()]
    assert len(sarite) == 1
    assert sarite[0].endswith("competenta=Comunicare asertivă motiv=scor_nevalid")


@pytest.mark.parametrize(
    ("valoare", "asteptat"),
    [(True, None), (float("nan"), None), (float("inf"), None), (-1, None), ("-5", None),
     (10**30, None), ("8/10", None), (None, None), ("8.5", "8.5"), (7, "7"), (8.25, "8.25"),
     (0, "0"), (10**20, "100000000000000000000")],
)
def test_cititorul_comun(valoare, asteptat) -> None:
    rez = ev._numarul_citit(valoare)
    assert (None if rez is None else str(rez)) == asteptat


# --- 3 și 4: rezumatul de la închidere -----------------------------------------------------------

REPLICI = (
    "Da, hai.",
    "Înțeleg ce spui. Ce anume te-a deranjat cel mai tare în situația asta, concret?",
    "Raportul a întârziat de trei ori; echipa a trimis cifre greșite clientului.",
    "Aș vrea să stabilim împreună un termen clar pentru următorul raport, joi la prânz.",
)


def _sinteza(note_json: str) -> str:
    return (
        "##Concluzie\nAi rămas calm.\n\n##Recomandări\n• Fii mai concret.\n"
        '```json\n{"topic": "Termene", "characters": [], "scores": ' + note_json + "}\n```"
    )


async def _inchide(sinteza: str, ce_mai_face=None) -> dict:
    settings = Settings(generation_provider="local")

    class FurnizorCuRezumat(LocalGenerationProvider):
        async def generate(self, request):
            rez = await super().generate(request)
            if request.system_instruction == "Ești analizator de discurs.":
                return replace(rez, text=sinteza)
            return rez

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
        if ce_mai_face is None:
            await service.end_session(principal=ctx["principal"], session_id=sedinta.id)
        else:
            with ce_mai_face():
                await service.end_session(principal=ctx["principal"], session_id=sedinta.id)
        note = (await session.execute(select(CompetencyScore).where(
            CompetencyScore.conversation_id == str(sedinta.id),
            CompetencyScore.justification.like("Scor evaluat automat%"),
        ))).scalars().all()
        memorii = (await session.execute(select(ParticipantMemory).where(
            ParticipantMemory.session_id == str(sedinta.id)))).scalars().all()
        rezultat = {
            "note": {n.competency_name: (n.score, n.level) for n in note},
            "memorii": [(m.relevance_score, dict(m.evolution_signals or {})) for m in memorii],
        }
        await session.rollback()
        await redis.aclose()
    return rezultat


async def test_rezumatul_sare_numai_notele_ciudate(caplog) -> None:
    # True, NaN, 11 (pe scara 10), 7 și 5. Azi: True → 10, NaN rupe tot ce urmează (și memoria).
    sinteza = _sinteza('{"questionsRatio": true, "assertiveness": NaN, "sbiFeedback": 11, '
                       '"conciseness": 7, "empatie": 5}')
    with caplog.at_level(logging.WARNING):
        r = await _inchide(sinteza)
    # 11 → 110 → plafonat la 100 → 3 (218 §7.2); 7 → 70 → 3; 5 → 50 → 2
    assert r["note"] == {
        "Feedback Structurat (SBI)": (100, 3),
        "Concizie și Echilibru": (70, 3),
        "empatie": (50, 2),
    }
    # memoria se salvează, cu media numai din notele valide: (11 + 7 + 5) / 3 × 10 = 76,67 → 77
    assert len(r["memorii"]) == 1
    relevanta, semnale = r["memorii"][0]
    assert relevanta == 77
    assert semnale == {"sbiFeedback": 11, "conciseness": 7, "empatie": 5}
    sarite = [m for m in caplog.messages if "practice_nota_sarita" in m]
    assert len(sarite) == 2
    assert all(m.endswith("motiv=scor_nevalid") for m in sarite)
    assert "Failed to parse evaluation JSON" not in caplog.text


@pytest.mark.parametrize("ciudat", ["Infinity", "-3", "1e30"])
async def test_rezumatul_cu_inf_negativ_urias_nu_pierde_restul(ciudat) -> None:
    r = await _inchide(_sinteza(f'{{"questionsRatio": {ciudat}, "conciseness": 7}}'))
    assert r["note"] == {"Concizie și Echilibru": (70, 3)}
    assert len(r["memorii"]) == 1


async def test_rezumatul_citeste_8_5_ca_text_si_pastreaza_rotunjirea() -> None:
    # hotărât de arhitect (223 §6.1): textul „8.5” devine notă; 8.25 → 82 ca azi
    r = await _inchide(_sinteza('{"questionsRatio": "8.5", "sbiFeedback": 8.25}'))
    assert r["note"] == {"Abilități de Coach și Întrebări": (85, 3),
                         "Feedback Structurat (SBI)": (82, 3)}


async def test_jurnalul_inchiderii_scrie_numai_tipul_erorii(caplog) -> None:
    sinteza = _sinteza('{"questionsRatio": 4, "assertiveness": 7.5}')

    def pica():
        # `end_session` importă `InsightMoment` local, din `models`, la fiecare chemare
        return patch("codrut.modules.practice.models.InsightMoment",
                     side_effect=Exception(MARCAJ))

    with caplog.at_level(logging.WARNING):
        await _inchide(sinteza, ce_mai_face=pica)
    assert "Failed to parse evaluation JSON in end_session" in caplog.text
    assert "MARCAJ" not in caplog.text


# --- 218 O3: filtrul pe ședință ---------------------------------------------------------------


async def test_nota_unei_sedinte_de_coaching_nu_intra_in_media() -> None:
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        s.add(ProjectCompetency(project_id=ctx["project"].id, name=COMP, order_index=0))
        om = await _om(s, ctx, "Om cu coaching")
        await _note(s, ctx, om, [(0, 60)])  # role-play (arhivă): 60
        coaching = PracticeSession(
            program_settings_id=ctx["program_settings"].id,
            participant_profile_id=ctx["profile"].id, pack_id=ctx["pack"].id,
            kind=SessionKind.coaching, state=SessionState.closed,
            started_at=datetime.now(UTC) - timedelta(days=9))
        s.add(coaching)
        await s.flush()
        # rezumatul scrie „session” la orice fel de ședință: numai legătura cu ședința o scoate
        s.add(CompetencyScore(user_id=om, project_id=ctx["project"].id, score=100, level=3,
                              conversation_id=str(coaching.id), competency_name=COMP,
                              source_type="session",
                              created_at=datetime.now(UTC) - timedelta(days=9)))
        await s.flush()
        date_ = await PracticeEvolutionService(s).project_evolution(ctx["project"].id)
        await s.rollback()
    comp = next(c for c in date_["competencies"] if c["name"] == COMP)
    assert comp["current_average"] == 60.0
    assert comp["points"] == 10
    assert [p["average"] for p in date_["weekly_average"]] == [60.0]
