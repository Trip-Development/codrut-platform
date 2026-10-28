"""Plicul 200 — Cody nu mai iese din rol; „reacțiile emoționale” nu se mai notează în role-play.

Proba din 19 oct: un narator l-a întrebat pe om ce simte, „— Cody” a apărut lipit de replica
personajului, iar „Gestionarea propriilor reacții emoționale” a primit notă într-un role-play,
deși rubrica spune că se evaluează doar dacă există dialog de coaching.
"""

import uuid

from codrut.modules.practice.evaluator import PracticeEvaluator
from codrut.modules.practice.models import CompetencyScore
from codrut.modules.practice.prompts import (
    ACTOR_PROMPT,
    ACTOR_PROMPT_DOUA_APELURI,
    EVALUARE_PROMPT,
)

FRAZA_ACTOR = (
    "Cât joci personajul nu ieși din rol: fără narator care vorbește cu omul, fără "
    "întrebări despre ce simte, fără semnătura «— Cody». Tot ce ține de exercițiu se "
    "spune în evaluare."
)
FRAZA_EVALUARE = (
    "Dacă închei cu o întrebare, ea îl duce înapoi în scenă: «Cum îi răspunzi acum "
    "lui <personaj>?». Nu întrebi ce ar răspunde personajul și nici cum vrea să "
    "continue exercițiul."
)


class _SesiuneDeProba:
    def __init__(self) -> None:
        self.adaugate: list[object] = []

    def add(self, obiect: object) -> None:
        self.adaugate.append(obiect)

    async def flush(self) -> None:
        return None


def _nota(competenta: str) -> dict:
    return {"competency": competenta, "evaluated": True, "score": 70, "level": 2}


async def _salvate(source_type: str) -> list[str]:
    sesiune = _SesiuneDeProba()
    evaluator = PracticeEvaluator(sesiune, None, None)
    await evaluator._persist(
        date={
            "scores": [
                _nota("Gestionarea propriilor reacții emoționale"),
                _nota("gestionarea propriilor reactii emotionale"),
                _nota("GESTIONAREA PROPRIILOR REACȚII EMOȚIONALE"),
                _nota("Feedback constructiv"),
            ]
        },
        session_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        project_id=None,
        source_type=source_type,
    )
    return [o.competency_name for o in sesiune.adaugate if isinstance(o, CompetencyScore)]


def test_actorul_primeste_fraza_pe_ambele_drumuri() -> None:
    assert FRAZA_ACTOR in ACTOR_PROMPT
    assert FRAZA_ACTOR in ACTOR_PROMPT_DOUA_APELURI


def test_evaluarea_primeste_fraza() -> None:
    assert FRAZA_EVALUARE in EVALUARE_PROMPT


async def test_in_role_play_emotiile_nu_se_salveaza() -> None:
    assert await _salvate("roleplay") == ["Feedback constructiv"]


async def test_in_coaching_emotiile_se_salveaza_ca_azi() -> None:
    assert len(await _salvate("coaching")) == 4
