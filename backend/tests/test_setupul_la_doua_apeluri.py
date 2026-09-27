"""Setup-ul nu mai scrie replica participantului — plicul 164, partea A.

Andrei, pe live, de două ori: după setup, în locul replicii personajului, venea replica LUI
(„— Tudor, te-am auzit spunând…"). Pe probă, înainte de plic: 3 din 20 de porniri cu replica
participantului, 3 cu persoanele amestecate.

Reparația e numai text, numai pe drumul cu două apeluri: un rând în capul actorului și regula
setup-ului, spusă ultima, lângă numele personajului. `actor.md` și drumul cu un apel nu se ating.
"""

from __future__ import annotations

from codrut.modules.practice.prompts import (
    ACTOR_PROMPT,
    ACTOR_PROMPT_DOUA_APELURI,
    _numele_personajului,
    get_prompts_pe_meserii,
    get_system_prompt_for_kind,
)

ROL = {"conduce_oameni": True, "nr_roleplay_anterioare": 6}
INTERDICTIA = "nu scrii niciodată ce spune participantul"


def test_la_pornire_regula_sta_ultima_langa_numele_personajului() -> None:
    actor, evaluator = get_prompts_pe_meserii(name="Fox 34", history_length=2, profil_rol=ROL)
    nume = _numele_personajului(6, "Fox")
    coada = actor[actor.index(f"PERSONAJUL SE NUMEȘTE {nume}"):]
    assert "CUM ARATĂ SETUP-UL" in coada
    assert actor.rstrip().endswith("el răspunde singur, după tine.")
    assert f"eticheta „{nume}:”" in coada
    assert "persoana a II-a" in coada
    assert "CUM ARATĂ SETUP-UL" not in evaluator


def test_dupa_pornire_regula_setupului_nu_mai_apare_dar_interdictia_ramane() -> None:
    actor, _ = get_prompts_pe_meserii(name="Fox 34", history_length=3, profil_rol=ROL)
    assert "CUM ARATĂ SETUP-UL" not in actor
    assert INTERDICTIA in actor  # din capul actorului, la fiecare replică


def test_drumul_cu_un_apel_nu_primeste_nimic() -> None:
    for pas in (2, 3):
        prompt = get_system_prompt_for_kind("roleplay", name="Fox 34", history_length=pas,
                                            profil_rol=ROL)
        assert "CUM ARATĂ SETUP-UL" not in prompt
        assert INTERDICTIA not in prompt
    assert INTERDICTIA not in ACTOR_PROMPT
    assert INTERDICTIA in ACTOR_PROMPT_DOUA_APELURI
