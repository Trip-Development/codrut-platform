"""Salutul e numai „Salut.", iar strategia întreabă de situație — plicul 128, părțile A și C.

**A.** Andrei, 22 septembrie, după prima lui probă pe server: *„Când încep conversația, îmi spune:
Salut user. Refă să spună doar salut."* Numele venea din profil, iar pe contul lui de probă
profilul se cheamă „user 1" — deci Cody îi zicea „Salut, user." Până azi formula cerea
`Salut, {prenume}.` plus o vorbă din `SALUTURI`, la toate trei modurile.

**C.** Tot atunci, Andrei a schimbat hotărârea lui din 31 august: la strategie, după salut nu se
mai întreabă „Cum îți merge ziua până acum?", ci direct de situația pe care vrea s-o pregătească.
Trei formulări, pe rând, cuvânt cu cuvânt ale lui.
"""

from __future__ import annotations

import pytest

from codrut.modules.practice.prompts import (
    INTREBARI_DE_STRATEGIE,
    get_prompts_pe_meserii,
    get_system_prompt_for_kind,
)

MODURI = ("roleplay", "knowledge", "coaching")


def _profil(nr_sesiuni: int) -> dict:
    return {
        "conduce_oameni": True,
        "functie": None,
        "nr_roleplay_anterioare": 0,
        "nr_sesiuni_anterioare": nr_sesiuni,
    }


# --------------------------------------------------------------------------- A · salutul


@pytest.mark.parametrize("mod", MODURI)
@pytest.mark.parametrize("nr_sesiuni", [0, 1, 2, 3, 6, 7])
def test_salutul_e_numai_salut(mod: str, nr_sesiuni: int) -> None:
    """La toate trei modurile, oricâte ședințe ar avea omul în urmă: `Salut.` și atât."""
    prompt = get_system_prompt_for_kind(
        mod, name="Ion Popescu", history_length=0, profil_rol=_profil(nr_sesiuni)
    )
    assert "copiate ca atare: Salut. " in prompt or "copiate ca atare: Salut." in prompt
    assert "Salut, Ion" not in prompt
    assert "Salut, Ion Popescu" not in prompt


@pytest.mark.parametrize("mod", MODURI)
def test_numele_nu_mai_intra_in_salut(mod: str) -> None:
    """Numele profilului nu mai are voie în formula de salut, oricum ar arăta."""
    prompt = get_system_prompt_for_kind(
        mod, name="user 1", history_length=0, profil_rol=_profil(0)
    )
    # numai randul SALUTULUI, pana la urmatoarea regula — regula numelui de la plicul 76 vine
    # mai jos si ACOLO numele are voie sa fie, ca fapt. Aici, nu.
    de_la = prompt.index("- SALUTUL:")
    salut = prompt[de_la : prompt.index("\n- ", de_la + 5)]
    assert "user" not in salut.lower().replace("salutul", "")


def test_salutul_e_la_fel_si_pe_drumul_cu_doua_apeluri() -> None:
    """Plicul cere „pe ambele drumuri" — actorul de la două apeluri primește aceeași regulă."""
    prompt_actor, _prompt_evaluator = get_prompts_pe_meserii(
        name="Ion Popescu", history_length=0, profil_rol=_profil(0)
    )
    assert "Salut." in prompt_actor
    assert "Salut, Ion" not in prompt_actor


# ----------------------------------------------------------------- C · întrebarea de strategie


def test_cele_trei_intrebari_sunt_cuvant_cu_cuvant_ale_lui_andrei() -> None:
    assert INTREBARI_DE_STRATEGIE == (
        "Pentru ce situație vrei să facem o strategie azi?",
        "Ce situație ai pe masă, pentru care vrei să pregătim o strategie?",
        "Spune-mi situația pe care vrei s-o pregătim împreună.",
    )


@pytest.mark.parametrize(
    ("nr_sesiuni", "asteptat"),
    [(0, 0), (1, 1), (2, 2), (3, 0), (4, 1), (5, 2)],
)
def test_intrebarea_de_strategie_se_roteste(nr_sesiuni: int, asteptat: int) -> None:
    prompt = get_system_prompt_for_kind(
        "coaching", name="Ion", history_length=0, profil_rol=_profil(nr_sesiuni)
    )
    assert INTREBARI_DE_STRATEGIE[asteptat] in prompt
    for alta in range(3):
        if alta != asteptat:
            assert INTREBARI_DE_STRATEGIE[alta] not in prompt


def test_intrebarea_veche_a_disparut_de_la_strategie() -> None:
    """Din REGULA PRIMULUI MESAJ. În `cody-v1.md` rămâne, dar acolo e un exemplu INTERZIS."""
    prompt = get_system_prompt_for_kind(
        "coaching", name="Ion", history_length=0, profil_rol=_profil(0)
    )
    de_la = prompt.index("- REGULA PRIMULUI MESAJ:")
    regula = prompt[de_la : prompt.index("\n- ", de_la + 5)]
    assert "Cum îți merge ziua până acum?" not in regula
    assert INTREBARI_DE_STRATEGIE[0] in regula


@pytest.mark.parametrize("mod", ("roleplay", "knowledge"))
def test_intrebarile_de_strategie_nu_s_in_celelalte_moduri(mod: str) -> None:
    prompt = get_system_prompt_for_kind(
        mod, name="Ion", history_length=0, profil_rol=_profil(0)
    )
    for intrebare in INTREBARI_DE_STRATEGIE:
        assert intrebare not in prompt
