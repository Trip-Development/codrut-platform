"""Plicul 95: Sandwich iese de peste tot — regula ajunge la toate trei modurile.

Hotararea lui Andrei, 19 septembrie: „Sandwich iese de peste tot." La referinta din aceeasi zi,
quizul l-a pomenit de 8 ori, o data ca „Metoda Sandwich functioneaza…". Regula sta in
reguli-generale.md, care intra in prompt la fiecare replica, in toate trei modurile — aceeasi
cale ca numele omului la plicul 76. ADKAR si OILS NU se pomenesc in prompt, in niciun fel.
"""

import re

import pytest

from codrut.modules.practice.prompts import get_system_prompt_for_kind

REGULA = (
    "METODA SANDWICH NU SE MAI PREDĂ. Nu construi întrebări despre ea, nu o recomanda și nu o "
    "pomeni ca metodă bună, oricât de des ar apărea în material."
)


@pytest.mark.parametrize("mod", ["roleplay", "knowledge", "coaching"])
@pytest.mark.parametrize("istoric", [0, 2, 4])
def test_regula_ajunge_in_fiecare_mod_la_fiecare_replica(mod: str, istoric: int) -> None:
    prompt = get_system_prompt_for_kind(
        mod, name="Ion Popescu", history_length=istoric,
        quiz_competency="mix" if mod == "knowledge" else None,
    )

    assert REGULA in prompt


def test_regula_nu_numeste_adkar_sau_oils() -> None:
    assert not re.search(r"ADKAR|OILS", REGULA, re.IGNORECASE)
