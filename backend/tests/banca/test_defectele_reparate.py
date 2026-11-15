"""Cele 5 defecte găsite de banca de probă, reparate — plicul 218.

Valorile așteptate sunt socotite de mână, din regula scrisă în `prompts/evaluator.md:12`:
nivelul 1 = 0–35, nivelul 2 = 36–69, nivelul 3 = 70–100. Rotunjirea scorului ca text e
jumătatea ÎN SUS (hotărârea lui Andrei din plicul 123, `scoring.py::quiz_xp`): 84,5 → 85.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.practice.evaluator import PracticeEvaluator
from codrut.modules.practice.evolution_service import PracticeEvolutionService
from codrut.modules.practice.models import CompetencyScore, InsightMoment, ProjectCompetency
from codrut.modules.practice.scoring import e_nota_de_role_play, nivel_din_scor
from test_evolutia_pe_om import COMP, _note, _om
from test_practice_session_flow import create_test_context

# --- regula nivelului, scrisă o dată ------------------------------------------------------------


@pytest.mark.parametrize(
    ("scor", "nivel"),
    [
        (0, 1), (35, 1),     # 0–35 → 1
        (36, 2), (69, 2),    # 36–69 → 2
        (70, 3), (100, 3),   # 70–100 → 3
        (40, 2), (75, 3),    # rezumatul: 4/10 → 40 → 2 (azi 1); 7,5/10 → 75 → 3 (azi 2)
    ],
)
def test_nivel_din_scor_la_praguri(scor, nivel) -> None:
    assert nivel_din_scor(scor) == nivel


@pytest.mark.parametrize("scor", [-1, 101])
def test_nivel_din_scor_in_afara_0_100_e_eroare(scor) -> None:
    with pytest.raises(ValueError):
        nivel_din_scor(scor)


def test_filtrul_de_role_play() -> None:
    # quiz și testele IN/OUT nu sunt role-play, indiferent de litere mari
    assert e_nota_de_role_play("session") is True
    assert e_nota_de_role_play("roleplay") is True
    assert e_nota_de_role_play("Cunostinte") is False
    assert e_nota_de_role_play("test_out") is False


# --- salvarea notelor profesorului (`_persist`) ------------------------------------------------


class SesiuneFalsa:
    def __init__(self) -> None:
        self.adaugate: list = []

    def add(self, obiect) -> None:
        self.adaugate.append(obiect)

    async def flush(self) -> None:
        return None


async def _salveaza(caz: dict) -> SesiuneFalsa:
    date = {
        "scores": [
            {"competency": "Ascultare activă", "evaluated": True, "score": 72, "level": 3,
             "justification": "x"},
            {"competency": "Comunicare asertivă", "evaluated": True, "justification": "x", **caz},
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


def _celelalte_intacte(s: SesiuneFalsa) -> None:
    note = _notele(s)
    assert note["Ascultare activă"] == (72, 3)
    assert note["Feedback constructiv"] == (40, 2)
    assert sum(1 for o in s.adaugate if isinstance(o, InsightMoment)) == 2


@pytest.mark.parametrize(
    ("scor", "asteptat"),
    [
        ("85.5", (86, 3)),   # 85,5 → 86 (jumătatea în sus) → 70–100 → 3
        ("84.5", (85, 3)),   # 84,5 → 85, nu 84 cum ar da `round()` (la par)
        (150, (100, 3)),     # plafonat la 100 înainte de nivel → 3, fără eroare
    ],
)
async def test_scorul_se_citeste_si_se_plafoneaza(scor, asteptat) -> None:
    s = await _salveaza({"score": scor, "level": 3})
    assert _notele(s)["Comunicare asertivă"] == asteptat
    _celelalte_intacte(s)


@pytest.mark.parametrize(
    "scor", ["8/10", "", "bine", "85,5", "-5", True, float("nan"), float("inf"), None],
)
async def test_un_scor_nevalid_sare_numai_nota_lui(scor, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        s = await _salveaza({"score": scor, "level": 3})
    assert "Comunicare asertivă" not in _notele(s)
    _celelalte_intacte(s)
    mesaje = [r.getMessage() for r in caplog.records if "practice_nota_sarita" in r.getMessage()]
    assert len(mesaje) == 1
    assert mesaje[0].endswith("competenta=Comunicare asertivă motiv=scor_nevalid")


async def test_nivelul_profesorului_care_contrazice_scorul_se_recalculeaza(caplog) -> None:
    # 85 → 70–100 → 3, oricât ar spune profesorul (1)
    with caplog.at_level(logging.INFO):
        s = await _salveaza({"score": 85, "level": 1})
    assert _notele(s)["Comunicare asertivă"] == (85, 3)
    assert any("practice_nivel_recalculat" in r.getMessage() for r in caplog.records)


async def test_o_nota_fara_nivel_ia_nivelul_din_scor() -> None:
    # 64 → 36–69 → 2; înainte se pierdea tăcut
    s = await _salveaza({"score": 64, "level": None})
    assert _notele(s)["Comunicare asertivă"] == (64, 2)
    _celelalte_intacte(s)


# --- același ecran: media, numărul de note, oamenii ---------------------------------------------


async def test_quizul_nu_intra_in_media_numarul_si_tabelul_oamenilor() -> None:
    # role-play 60 + quiz 100 → media 60 (nu 80), o singură notă, iar pe om tot 60 și 1
    async with SessionLocal() as s:
        ctx = await create_test_context(s)
        s.add(ProjectCompetency(project_id=ctx["project"].id, name=COMP, order_index=0))
        om = await _om(s, ctx, "Om cu quiz")
        await _note(s, ctx, om, [(0, 60)])
        s.add(CompetencyScore(user_id=om, project_id=ctx["project"].id, score=100, level=3,
                              conversation_id=f"quiz-{uuid.uuid4().hex[:6]}",
                              competency_name=COMP, source_type="cunostinte",
                              created_at=datetime.now(UTC) - timedelta(days=10)))
        await s.flush()
        date_ = await PracticeEvolutionService(s).project_evolution(ctx["project"].id)
        await s.rollback()
    comp = next(c for c in date_["competencies"] if c["name"] == COMP)
    assert (comp["current_average"], comp["scores_count"]) == (60.0, 1)
    assert [p["scores_count"] for p in date_["weekly_average"]] == [1]
    omul = next(p for p in date_["participants"] if p["user_id"] == om)
    assert (omul["current_average"], omul["scores_count"]) == (60.0, 1)
