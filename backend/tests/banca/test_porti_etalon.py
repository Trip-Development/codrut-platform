"""Etalonul porților uneltei de probe — banca de probă, stratul 1 (plicul 215).

Pentru fiecare din cele zece porți din `probe_automate.portile()`, un exemplu care trebuie să
treacă și unul care trebuie să pice. Numai texte inventate. Nu dublează
`test_probe_automate_porti.py` (funcțiile de citire) și nici `test_portile_pe_texte_adevarate.py`
(textele salvate): aici se judecă o ședință întreagă, prin `portile()`.
"""

import pytest

from codrut.modules.practice.prompts import _numele_personajului
from codrut.tools.probe_automate import PRENUME, portile

NR_RULARE = 1
PERSONAJ = _numele_personajului(NR_RULARE - 1, PRENUME)
STRAIN = "Bogdan Pop" if "Bogdan" not in PERSONAJ else "Horia Dinu"

OM = "Nu am primit raportul de vânzări la timp și clientul a fost nemulțumit."
EVALUARE_BUNA = (
    "Ai deschis bine. Ai spus „raportul de vânzări la timp”, concret. "
    "Ai fi putut spune: „Hai să stabilim un termen clar.” [🏆 Scor: 7/10]"
)


def _pas(nr, fel="joc", raspuns="Bine, să vedem.", om=OM, eroare=None,
         text_actor=None, text_evaluator=None):
    return {"pas": nr, "fel": fel, "om": om, "raspuns": raspuns, "eroare": eroare,
            "text_actor": text_actor, "text_evaluator": text_evaluator}


def _judeca(poarta: str, pasi: list[dict]) -> tuple[int, int]:
    p = portile("roleplay", pasi, NR_RULARE)[poarta]
    assert p["aplicabila"], f"poarta {poarta} nu s-a aplicat"
    return p["trecute"], p["instante"]


CAZURI = [
    # (poarta, pașii, trebuie să treacă)
    ("1", [_pas(3, raspuns=EVALUARE_BUNA)], True),
    ("1", [_pas(3, raspuns="", eroare="vertex_network_error")], False),
    ("2", [_pas(3, raspuns=EVALUARE_BUNA)], True),
    ("2", [_pas(3, raspuns="Ai deschis bine conversația, ai fost concret.")], False),
    ("3", [_pas(3, raspuns=EVALUARE_BUNA)], True),
    ("3", [_pas(3, raspuns="Ai spus „raportul de vânzări la timp”. [🏆 Scor: 6/10]")], False),
    ("4", [_pas(2, fel="pornire", raspuns=f"**{PERSONAJ}:** „Bună, ai un minut?”")], True),
    ("4", [_pas(2, fel="pornire", raspuns=f"**{STRAIN}:** „Bună, ai un minut?”")], False),
    ("5", [_pas(1, fel="salut", om=None, raspuns="Salut. Începem când ești gata.")], True),
    ("5", [_pas(1, fel="salut", om=None, raspuns="Bună ziua, participant. Începem?")], False),
    ("6", [_pas(3, raspuns=EVALUARE_BUNA)], True),
    ("6", [_pas(3, raspuns="Ai fi putut spune: „Hai să stabilim un termen.” "
                           "[🏆 Scor: 6/10]")], False),
    ("7", [_pas(3, raspuns=EVALUARE_BUNA)], True),
    ("7", [_pas(3, raspuns="Folosește metoda sandwich data viitoare. " + EVALUARE_BUNA)], False),
    ("9", [_pas(3, raspuns="x", text_evaluator=EVALUARE_BUNA)], True),
    ("9", [_pas(3, raspuns="x", text_evaluator=f"**{STRAIN}:** „Nu e vina mea.”")], False),
    ("10", [_pas(3, raspuns="x", text_evaluator=EVALUARE_BUNA)], True),
    ("10", [_pas(3, raspuns="x", text_evaluator="Radu ar fi reacționat altfel. "
                                                  + EVALUARE_BUNA)], False),
    ("11", [_pas(3, raspuns="x", text_actor=f"**{PERSONAJ}:** „Da, recunosc că am greșit.”")],
     True),
    ("11", [_pas(3, raspuns="x", text_actor="Ies din rol o clipă: ai fost foarte clar.")],
     False),
]


@pytest.mark.parametrize(("poarta", "pasi", "trece"), CAZURI,
                         ids=[f"poarta{c[0]}-{'trece' if c[2] else 'pica'}" for c in CAZURI])
def test_etalonul_portii(poarta, pasi, trece) -> None:
    trecute, instante = _judeca(poarta, pasi)
    assert instante >= 1
    assert (trecute == instante) is trece


def test_etalonul_acopera_toate_cele_zece_porti() -> None:
    porti = {c[0] for c in CAZURI}
    assert porti == {"1", "2", "3", "4", "5", "6", "7", "9", "10", "11"}
    for p in porti:
        assert {c[2] for c in CAZURI if c[0] == p} == {True, False}
