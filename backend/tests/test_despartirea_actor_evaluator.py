"""Despărțirea actor/evaluator — plicul 112, decizia de arhitectură 7.

Ce se apără aici:

1. **ordinea e a instalației, nu a modelului.** Actorul nu primește regulile de evaluare, deci
   n-are cum să evalueze; evaluatorul nu primește `actor.md`, deci n-are personaj. Până acum
   ordinea era o rugăminte în prompt, iar la plicurile 87, 88 și 91 s-a văzut ce valorează:
   fără regulă 3 înainte / 6 după, iar cu regula de ordine singură personajul a dispărut la 3 pași.
2. **poarta 9**, instrumentul nou: pică pe un evaluator care joacă, trece pe unul curat.
   Un instrument de măsură se verifică întâi pe un caz în care TREBUIE să pice.
3. **comutatorul e stins implicit**: fără el, purtarea e cea de azi.
"""

from __future__ import annotations

import os

from codrut.core.config import Settings
from codrut.modules.practice.prompts import (
    ACTOR_PROMPT,
    ACTOR_PROMPT_DOUA_APELURI,
    EVALUARE_PROMPT,
    get_core_material,
    get_prompts_pe_meserii,
    get_system_prompt_for_kind,
)
from codrut.tools.probe_automate import evaluatorul_joaca

BIBLIOTECA = os.environ.get("BIBLIOTECA_PATH", "")


def _cele_doua() -> tuple[str, str]:
    return get_prompts_pe_meserii(name="Ion", history_length=3, biblioteca_path=BIBLIOTECA)


def test_comutatorul_e_stins_implicit() -> None:
    assert Settings(vertex_actor_model="m", vertex_evaluator_model="m").practice_two_calls is False


def test_actorul_nu_primeste_regulile_de_evaluare() -> None:
    """Ordinea, prin construcție: cine n-are regulile de evaluare nu poate evalua.

    De la plicul 119 actorul primește, la două apeluri, varianta căreia i s-a scos rândul
    „ești simultan actor și Cody-ca-profesor". Restul e neschimbat, iar `ACTOR_PROMPT` —
    cel de la un singur apel — rămâne neatins, apărat de lacătul lui.
    """
    actor, _ = _cele_doua()
    assert ACTOR_PROMPT_DOUA_APELURI[:200] in actor
    assert "NU ești Cody-ca-profesor" in actor
    assert EVALUARE_PROMPT[:200] not in actor
    assert "PUNCTAJUL E OBLIGATORIU" not in actor


def test_evaluatorul_nu_primeste_personajul() -> None:
    _, evaluator = _cele_doua()
    assert EVALUARE_PROMPT[:200] in evaluator
    assert ACTOR_PROMPT[:200] not in evaluator


def test_numele_omului_ajunge_la_amandoi() -> None:
    """Poarta 5 se cere de la amândouă ieșirile, deci numele trebuie să fie în amândouă."""
    actor, evaluator = _cele_doua()
    assert "Ion" in actor
    assert "Ion" in evaluator


def test_materialul_nu_se_trimite_de_doua_ori() -> None:
    """Fiecare felie merge la cel mult o meserie: nimic dublu în afară de regulile generale.

    Până la plicul 135 cele două felii adunate dădeau tot materialul. De atunci PROFIL-ANDREI,
    FILOZOFIE și FILOZOFIE-CONVERSATII nu pleacă nicăieri la role-play cu două apeluri (vezi
    `test_vocea_la_cody.py`), deci suma e mai mică decât tot — dinadins.
    """
    m_actor, _ = get_core_material(BIBLIOTECA, felie="actor")
    m_eval, _ = get_core_material(BIBLIOTECA, felie="evaluator")
    tot, _ = get_core_material(BIBLIOTECA)
    if not tot:
        return  # fără bibliotecă pe disc nu se poate măsura; restul testelor rămân valabile
    assert "TEORIA-TEMEI" not in m_actor
    assert "PROFIL-ANDREI" not in m_eval
    assert "PROFIL-ANDREI" not in m_actor
    assert len(m_actor) + len(m_eval) < len(tot)


def test_promptul_cu_un_apel_ramane_ce_era() -> None:
    """Comutatorul stins nu schimbă nimic: promptul de azi le conține pe amândouă."""
    vechi = get_system_prompt_for_kind("roleplay", name="Ion", history_length=3,
                                       biblioteca_path=BIBLIOTECA)
    assert ACTOR_PROMPT[:200] in vechi
    assert EVALUARE_PROMPT[:200] in vechi


# ---------------------------------------------------------------- poarta 9, lacătul ei

JOACA = (
    "[🏆 Scor: 4/10] Ai ales să te aperi.\n\n"
    'Elena Marin: „Cum adică nu e vina ta? Tu ești responsabilă de raportul ăsta!"'
)
CURAT = (
    "[🏆 Scor: 4/10] Ai ales să te aperi, iar asta mută discuția de pe livrare pe vină.\n\n"
    'Ai fi putut spune: „Raportul a întârziat a treia oară; hai să stabilim un termen."'
)


def test_poarta_noua_pica_pe_un_evaluator_care_joaca() -> None:
    gasit = evaluatorul_joaca(JOACA)
    assert gasit is not None
    assert "Elena Marin" in gasit


def test_poarta_noua_trece_pe_un_evaluator_curat() -> None:
    """Un citat din vorbele omului sau o replică model NU înseamnă că evaluatorul joacă."""
    assert evaluatorul_joaca(CURAT) is None
