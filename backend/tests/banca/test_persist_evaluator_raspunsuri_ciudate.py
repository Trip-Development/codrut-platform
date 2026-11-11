"""Ce salvează `PracticeEvaluator._persist` când profesorul răspunde ciudat — plicul 215, B.

Fără bază și fără furnizor: `_persist(date=…)` se cheamă direct, cu o sesiune falsă care ține ce
i se dă. Fiecare caz stă lângă două note bune, un `insight` și o recomandare pentru trainer.

Testele marcate `xfail(strict=True)` afirmă purtarea DORITĂ și pică azi — sunt defectele găsite.
Lângă fiecare, un test verde fixează purtarea de azi. Nimic nu se repară în plicul ăsta.
"""

import uuid

import pytest

from codrut.modules.practice.evaluator import PracticeEvaluator
from codrut.modules.practice.models import CompetencyScore, InsightMoment


class SesiuneFalsa:
    def __init__(self) -> None:
        self.adaugate: list = []

    def add(self, obiect) -> None:
        self.adaugate.append(obiect)

    async def flush(self) -> None:
        return None


def _date(caz: dict) -> dict:
    return {
        "scores": [
            {"competency": "Ascultare activă", "evaluated": True, "score": 72, "level": 3,
             "justification": "A reluat cuvintele colegului."},
            caz,
            {"competency": "Feedback constructiv", "evaluated": True, "score": 40, "level": 2,
             "justification": "Feedback vag."},
        ],
        "insight": "A rămas calm când colegul a ridicat tonul.",
        "recommendations_for_trainer": [
            {"competency": "Feedback constructiv", "score": 40, "analysis": "Prea general.",
             "actions": ["Exercițiu SBI"]},
        ],
    }


async def _salveaza(caz: dict) -> SesiuneFalsa:
    sesiune = SesiuneFalsa()
    evaluator = PracticeEvaluator(sesiune, generation_provider=None, settings=None)
    await evaluator._persist(date=_date(caz), session_id=uuid.uuid4(), user_id=uuid.uuid4(),
                             project_id=None, source_type="session")
    return sesiune


def _note(s: SesiuneFalsa) -> dict[str, tuple[int, int]]:
    return {o.competency_name: (o.score, o.level) for o in s.adaugate
            if isinstance(o, CompetencyScore)}


def _momente(s: SesiuneFalsa) -> int:
    return sum(1 for o in s.adaugate if isinstance(o, InsightMoment))


def _ciudat(**campuri) -> dict:
    return {"competency": "Comunicare asertivă", "evaluated": True, "justification": "x",
            **campuri}


# --- scor cu zecimale și scor ca fracție: ValueError la `int()` (evaluator.py:305) -----------

@pytest.mark.parametrize("scor", ["85.5", "8/10"])
async def test_azi_scorul_ca_text_opreste_salvarea_intregului_raspuns(scor) -> None:
    with pytest.raises(ValueError):
        await _salveaza(_ciudat(score=scor, level=3))


@pytest.mark.xfail(strict=True, raises=ValueError,
                   reason="BANCA-DEFECT-01: un scor scris ca text („85.5”, „8/10”) oprește "
                          "salvarea întregului răspuns: se pierd notele bune de după el, "
                          "insight-ul și recomandarea pentru trainer.")
@pytest.mark.parametrize("scor", ["85.5", "8/10"])
async def test_un_scor_ciudat_nu_pierde_restul_raspunsului(scor) -> None:
    s = await _salveaza(_ciudat(score=scor, level=3))
    note = _note(s)
    assert note["Ascultare activă"] == (72, 3)
    assert note["Feedback constructiv"] == (40, 2)
    assert _momente(s) == 2  # insight-ul și recomandarea pentru trainer


# --- scor pe scara 0–10 ----------------------------------------------------------------------

async def test_azi_un_scor_pe_scara_de_10_se_salveaza_ca_atare() -> None:
    # DE HOTĂRÂT: aplicația nu are de unde ști că 8 înseamnă 8/10; azi se salvează 8 din 100
    note = _note(await _salveaza(_ciudat(score=8, level=3)))
    assert note["Comunicare asertivă"] == (8, 3)


# --- competență cerută de nimeni ---------------------------------------------------------------

async def test_azi_o_competenta_inventata_se_salveaza() -> None:
    # DE HOTĂRÂT: `_persist` nu primește lista competențelor cerute, deci nu are ce compara
    s = await _salveaza({"competency": "Telepatie managerială", "evaluated": True,
                         "score": 90, "level": 3, "justification": "x"})
    assert _note(s)["Telepatie managerială"] == (90, 3)


# --- nume fără diacritice ----------------------------------------------------------------------

async def test_azi_un_nume_fara_diacritice_se_salveaza_cum_a_venit() -> None:
    # DE HOTĂRÂT: numele brut („Comunicare asertiva”) ajunge altundeva decât cel al proiectului
    s = await _salveaza({"competency": "Comunicare asertiva", "evaluated": True,
                         "score": 66, "level": 2, "justification": "x"})
    assert _note(s)["Comunicare asertiva"] == (66, 2)


# --- nivelul nu se potrivește cu scorul (pragurile din evaluator.md:12) ------------------------

async def test_azi_nivelul_vine_de_la_profesor_chiar_daca_contrazice_scorul() -> None:
    note = _note(await _salveaza(_ciudat(score=85, level=1)))
    assert note["Comunicare asertivă"] == (85, 1)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="BANCA-DEFECT-02: nivelul se ia de la profesor chiar când contrazice "
                          "scorul; după evaluator.md:12, 85 înseamnă nivelul 3, nu 1.")
async def test_nivelul_urmeaza_pragurile_din_evaluator_md() -> None:
    note = _note(await _salveaza(_ciudat(score=85, level=1)))
    assert note["Comunicare asertivă"] == (85, 3)


# --- nivel lipsă cu scor valid -----------------------------------------------------------------

async def test_azi_o_nota_fara_nivel_se_sare_tacut() -> None:
    note = _note(await _salveaza(_ciudat(score=64, level=None)))
    assert "Comunicare asertivă" not in note
    assert len(note) == 2


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="BANCA-DEFECT-03: o notă cu scor valid și nivel lipsă se pierde "
                          "tăcut (evaluator.py:299); nivelul se poate socoti din scor.")
async def test_o_nota_fara_nivel_se_salveaza_cu_nivelul_din_scor() -> None:
    note = _note(await _salveaza(_ciudat(score=64, level=None)))
    assert note.get("Comunicare asertivă") == (64, 2)
