"""Fiecare apel plătește la prețurile modelului lui — plicul 120, partea A.

Până azi exista o singură pereche de patru prețuri, luată din mediu. Cu două modele în aceeași
replică — actorul ieftin, evaluatorul scump — paza ar număra greșit:

- cu prețurile modelului scump, actorul e socotit de 3 ori mai scump decât e, și economia nu se
  vede deloc;
- cu prețurile celui ieftin, **evaluatorul e socotit de 3 ori mai ieftin decât e**, iar asta e
  chiar accidentul din 19 septembrie, când plafonul Google s-a atins într-o zi.
"""

from __future__ import annotations

from decimal import Decimal

from codrut.contracts.generation import TokenUsage
from codrut.core.config import Settings
from codrut.modules.practice.pricing import estimate_cost

FOLOSINTA = TokenUsage(
    prompt_tokens=1_000_000, cached_tokens=0, output_tokens=1_000_000, thought_tokens=0
)

SCUMP = "gemini-3.8-flash"
IEFTIN = "gemini-3.1-flash-lite"


def _setari(**peste: object) -> Settings:
    return Settings(
        _env_file=None,
        vertex_actor_model=SCUMP,
        vertex_evaluator_model=SCUMP,
        **peste,  # type: ignore[arg-type]
    )


def test_doua_modele_nu_mai_costa_la_fel() -> None:
    """Roșul plicului: până azi ieșea același cost pentru amândouă."""
    s = _setari()
    scump = estimate_cost(FOLOSINTA, s, model=SCUMP)
    ieftin = estimate_cost(FOLOSINTA, s, model=IEFTIN)

    assert scump == Decimal("4.500000")  # 0,75 intrare + 3,75 ieșire
    assert ieftin == Decimal("1.750000")  # 0,25 intrare + 1,50 ieșire
    assert ieftin < scump


def test_modelul_scump_ramane_exact_cat_era() -> None:
    """Nimic nu se schimbă cât timp rulează un singur model."""
    s = _setari()
    assert estimate_cost(FOLOSINTA, s, model=SCUMP) == estimate_cost(FOLOSINTA, s, model=None)


def test_un_model_necunoscut_plateste_cel_mai_scump_pret_stiut() -> None:
    """Nu trece tăcut: ia prețul cel mai scump din tabel și se scrie un rând în jurnal."""
    s = _setari()
    necunoscut = estimate_cost(FOLOSINTA, s, model="gemini-9.9-necunoscut")
    cel_mai_scump = max(
        estimate_cost(FOLOSINTA, s, model=m) for m in (SCUMP, IEFTIN, "gemini-2.5-pro")
    )
    assert necunoscut == cel_mai_scump


def test_ramura_pro_a_intrat_in_tabel() -> None:
    """Prețurile lui «pro» erau scrise în cod — boala de la plicul 101."""
    s = _setari()
    pro = estimate_cost(FOLOSINTA, s, model="gemini-2.5-pro")
    assert pro == Decimal("6.250000")  # 1,25 intrare + 5,00 ieșire


def test_tabelul_se_poate_schimba_din_mediu_fara_comitere() -> None:
    """Lecția plicului 101: prețurile nu se mai îmbătrânesc în cod."""
    s = _setari(prices_by_model='{"gemini-3.1-flash-lite": [9, 9, 9, 9]}')
    assert estimate_cost(FOLOSINTA, s, model=IEFTIN) == Decimal("18.000000")


def test_un_amestec_de_apeluri_da_suma_preturilor_lor() -> None:
    """Socoteala zilei, cerută de plicul 120, punctul A2.3.

    Trei apeluri ale actorului ieftin și două ale evaluatorului scump: totalul trebuie să fie
    suma prețurilor lor, nu totul la unul singur.
    """
    s = _setari()
    actor = estimate_cost(FOLOSINTA, s, model=IEFTIN)
    evaluator = estimate_cost(FOLOSINTA, s, model=SCUMP)

    adevarul = actor * 3 + evaluator * 2
    totul_la_actor = actor * 5
    totul_la_evaluator = evaluator * 5

    assert adevarul == Decimal("14.250000")
    assert totul_la_actor < adevarul < totul_la_evaluator
    # cât de departe erau cele două greșeli pe care le repară plicul
    assert totul_la_actor / adevarul < Decimal("0.62")
    assert totul_la_evaluator / adevarul > Decimal("1.57")
