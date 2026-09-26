"""Drumul cu UN SINGUR apel nu se atinge — plicul 119, partea B.

`ACTOR_PROMPT` e folosit și de drumul care merge azi, cel pe care se sprijină tot. Plicul 119
schimbă primele două rânduri ale actorului **numai** pentru despărțire; dacă schimbarea ar
atinge și varianta veche, plicul a eșuat, oricât de bune ar fi celelalte cifre.

Lacătul e pe amprenta fișierului, nu pe promptul compus: promptul compus conține materialul din
BIBLIOTECĂ, care se schimbă legitim (plicurile 105 și 107), iar o amprentă pe el ar suna alarma
la fiecare frază pe care o scrie Andrei.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from codrut.modules.practice.prompts import (
    ACTOR_PROMPT,
    ACTOR_PROMPT_DOUA_APELURI,
    get_system_prompt_for_kind,
)

# `actor.md`, așa cum era înainte de comiterea plicului 119 (măsurat pe `573bb7a`).
AMPRENTA_ACTOR_MD = "bb4fe933dd47553abb088c87aa184a5cfd235427a0c2dd81569f47692812a38b"

CAP_VECHI = "Ești simultan actor și Cody-ca-profesor."
CAP_NOU = "NU ești Cody-ca-profesor"


def test_actor_md_nu_s_a_atins() -> None:
    """Fișierul de pe disc, caracter cu caracter."""
    cale = Path(__file__).resolve().parents[1] / "src/codrut/modules/practice/prompts/actor.md"
    amprenta = hashlib.sha256(cale.read_bytes()).hexdigest()
    assert amprenta == AMPRENTA_ACTOR_MD, (
        "actor.md s-a schimbat. E folosit de drumul cu UN SINGUR apel, cel care merge azi — "
        "plicul 119 avea voie să schimbe numai varianta de la două apeluri."
    )


def test_promptul_de_la_un_apel_are_capul_vechi() -> None:
    prompt = get_system_prompt_for_kind("roleplay", name="Ion", history_length=3)
    assert CAP_VECHI in prompt
    assert CAP_NOU not in prompt
    assert ACTOR_PROMPT in prompt


def test_varianta_de_la_doua_apeluri_difera_numai_la_cap() -> None:
    """Restul, după primele două rânduri, e identic — nimic altceva n-a fost atins."""
    assert CAP_NOU in ACTOR_PROMPT_DOUA_APELURI
    assert CAP_VECHI not in ACTOR_PROMPT_DOUA_APELURI

    coada_veche = ACTOR_PROMPT.split("\n\n", 1)[1]
    coada_noua = ACTOR_PROMPT_DOUA_APELURI.split("\n\n", 1)[1]
    assert coada_veche == coada_noua
