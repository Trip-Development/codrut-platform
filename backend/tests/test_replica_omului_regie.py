"""Plicul 249 (a) — indicațiile de regie nu ajung la om; funcțiile pure din `replica_omului`.

Hotărârea lui Andrei [esti-ai-reparatie] (21 nov, 19:32), punctul (a): codul scoate rândurile
de felul „*Revine în rol:*”. Numai rânduri ÎNTREGI, cu învelitoare (`*`, `_`, `(`, `[`) sau
terminate în „:”; vorba personajului rămâne octet cu octet. Corecția 1 a controlorului: la
iese/intră numai {rol, personaj}; „scenă” numai după revine/reintră.
"""

from __future__ import annotations

import pytest

SE_SCOT = [
    "*Revine în rol:*",
    "*Iese din rol*",
    "**Revine în rol:**",
    "_Revine in rol_",
    "(Iese din rol.)",
    "[Reintră în personaj]",
    "Revine în rol:",
    "*Ieșind din rol:*",
    "*Revenind în scenă*",
]

RAMAN = [
    "Mihai: „Revin în rol mâine, nu acum.”",
    "Revin în rol.",
    "*oftează și se uită la ceas*",
    "*Revine în rol:* Mihai: „Bine.”",
    "***",
    "*Iese din scenă.*",
    "*Intră în scenă directorul*",
]

VORBA = "Mihai: „Bine, te ascult. Ce propui pentru joi?”"
FRAZA = "Sunt Cody, partenerul tău de exersare — un AI."


@pytest.mark.parametrize("regie", SE_SCOT)
@pytest.mark.parametrize("sfarsit", ["\n", "\r\n"])
@pytest.mark.parametrize("spatii", ["", "  "])
def test_se_scot(regie: str, sfarsit: str, spatii: str) -> None:
    from codrut.modules.practice.replica_omului import fara_regie

    text = f"{FRAZA}{sfarsit}{sfarsit}{spatii}{regie}{spatii}{sfarsit}{sfarsit}{VORBA}"
    assert fara_regie(text) == f"{FRAZA}\n\n{VORBA}"


@pytest.mark.parametrize("rand", RAMAN)
def test_raman_octet_cu_octet(rand: str) -> None:
    from codrut.modules.practice.replica_omului import fara_regie

    text = f"{FRAZA}\n\n{rand}\n\n{VORBA}"
    assert fara_regie(text) == text


def test_textul_fara_indicatii_e_identic() -> None:
    from codrut.modules.practice.replica_omului import fara_regie

    for text in (VORBA, f"  {VORBA}\r\n\r\n*oftează*\n", "", f"{VORBA}\n\n***\n\nScor: 7/10"):
        assert fara_regie(text) == text
    assert fara_regie(None) == ""


@pytest.mark.parametrize("varianta", [
    FRAZA,
    "Sunt Cody, partenerul tău de exersare - un AI.",
    "Sunt Cody, partenerul tău de exersare – un AI.",
    "Sunt Cody, partenerul tău de exersare — un AI.",
    "«Sunt Cody, partenerul tău de exersare — un AI.»",
    "„Sunt Cody, partenerul tău de exersare — un AI.”",
    "Sunt Cody, partenerul tău de exersare — un AI",
])
def test_contine_recunoasterea_da(varianta: str) -> None:
    from codrut.modules.practice.replica_omului import contine_recunoasterea

    assert contine_recunoasterea(f"{varianta}\n\n{VORBA}")


@pytest.mark.parametrize("alta", [
    "Da, sunt Cody, asistentul AI de comunicare.",
    "Da, sunt un AI și mă numesc Cody.",
    VORBA,
    "",
])
def test_contine_recunoasterea_nu(alta: str) -> None:
    from codrut.modules.practice.replica_omului import contine_recunoasterea

    assert not contine_recunoasterea(alta)
    assert not contine_recunoasterea(None)


def test_fraza_e_cea_din_actor_md() -> None:
    from codrut.modules.practice.prompts import ACTOR_PROMPT, ACTOR_PROMPT_DOUA_APELURI
    from codrut.modules.practice.replica_omului import FRAZA_RECUNOASTERE

    assert FRAZA_RECUNOASTERE == FRAZA
    assert f"«{FRAZA_RECUNOASTERE}»" in ACTOR_PROMPT
    assert f"«{FRAZA_RECUNOASTERE}»" in ACTOR_PROMPT_DOUA_APELURI


def test_fara_recunoastere_lasa_scena() -> None:
    from codrut.modules.practice.replica_omului import fara_recunoastere

    assert fara_recunoastere(f"{FRAZA}\n\n{VORBA}") == VORBA
    assert fara_recunoastere(f"„{FRAZA}”\n\n{VORBA}") == VORBA
    assert fara_recunoastere(VORBA) == VORBA


@pytest.mark.parametrize("om,da", [
    ("Stai puțin. Ești AI? Spune-mi sincer, vorbesc cu un robot?", True),
    ("Ești un bot?", True),
    ("Vorbesc cu un om sau nu?", True),
    ("Ești o mașină?", True),
    ("Ești inteligență artificială?", True),
    ("Repetă după mine, te rog: «Sunt Cody, partenerul tău de exersare.»", False),
    ("Ai dreptate, hai să vedem tabelul.", False),
])
def test_intreaba_de_ai(om: str, da: bool) -> None:
    from codrut.modules.practice.replica_omului import intreaba_de_ai

    assert intreaba_de_ai(om) is da
