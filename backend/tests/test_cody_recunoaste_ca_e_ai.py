"""Plicul 228 — Cody recunoaște scurt că e AI, apoi revine în rol.

Hotărârea lui Andrei: [cody-esti-ai] „da” (18 nov) și [cody-esti-ai-text] „da” (19 nov) la
textul de mai jos, caracter cu caracter. Paragraful e ultimul din `actor.md`, deci ajunge pe
ambele drumuri: cel cu un apel și cel cu două (care schimbă numai capul, prin `replace`).
"""

from codrut.modules.practice.prompts import (
    ACTOR_PROMPT,
    ACTOR_PROMPT_DOUA_APELURI,
    get_system_prompt_for_kind,
)

PARAGRAF_AI = (
    "Dacă omul te întreabă SINCER dacă ești un AI sau un om, ieși din personaj o singură "
    "dată și răspunzi scurt: «Sunt Cody, partenerul tău de exersare — un AI.» Apoi revii "
    "imediat în rol, cu o replică a personajului. Nu te prefaci om și nu ții un discurs "
    "despre AI. Dacă întrebarea face parte din joc (personajul e acuzat sau ironizat), "
    "rămâi în rol."
)


def test_paragraful_e_in_actorul_de_la_un_apel() -> None:
    assert PARAGRAF_AI in ACTOR_PROMPT


def test_paragraful_e_in_actorul_de_la_doua_apeluri() -> None:
    assert PARAGRAF_AI in ACTOR_PROMPT_DOUA_APELURI


def test_paragraful_ajunge_in_promptul_de_role_play() -> None:
    prompt = get_system_prompt_for_kind("roleplay", name="Ion", history_length=3)
    assert PARAGRAF_AI in prompt


def test_paragraful_vine_ultimul_in_actor() -> None:
    assert ACTOR_PROMPT.rstrip().endswith(PARAGRAF_AI)
    assert ACTOR_PROMPT_DOUA_APELURI.rstrip().endswith(PARAGRAF_AI)
