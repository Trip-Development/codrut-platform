"""Poarta 10: evaluatorul nu vorbește despre alt personaj decât cel al ședinței — plicul 118.

Defectul de la plicul 117 a trecut pe sub **toate cele opt porți**: nu e o replică de scenă, e
text curgător, corect, despre altcineva. Poarta 9 caută `Nume: „vorbire"`; asta caută numele,
oriunde în text.

Bucățile sunt copiate din `2026-09-20-memorie-despartita-gemini-3.8-flash.jsonl`, cu ședința și
pasul scrise lângă ele. **Cazurile sintetice nu se folosesc** — de două ori ne-au mințit.
"""

from __future__ import annotations

from codrut.tools.probe_automate import alt_personaj
from codrut.tools.probe_scenarii import COD_PARTICIPANT

# Textele de mai jos sunt reale, salvate înainte de plicul 138, când omul simulat se chema
# „Mihai". De la 138 spre model pleacă un cod, deci poarta primește explicit numele de atunci.
OMUL_DE_ATUNCI = "Mihai"

# roleplay:3, pasul 2 · ieșirea EVALUATORULUI. Personajul ședinței e Ioana Barbu; el își
# inventează alt scenariu, cu „Radu, managerul tău direct".
EVALUATORUL_INVENTEAZA = (
    'Uite contextul:  Ești la birou, iar managerul tău direct, Radu, vine la '
    'biroul tău destul de agitat și îți trântește pe masă un dosar:  *„Mihai, '
    'lasă tot ce faci acum. Am nevoie să preiei imediat raportul pentru '
    'clientul X și să fie gata până mâine la prânz. Știu că ești deja încărcat,'
    ' dar ești sing'
)

# roleplay:9, pasul 3 · ieșirea EVALUATORULUI. Evaluare curată: judecă ce a spus omul, fără să
# pomenească vreun personaj.
EVALUARE_CURATA = (
    'Ai arătat disponibilitate să asculți în loc să sari la atac, însă când ai '
    'spus „Înțeleg ce spui”, ai validat o nemulțumire neclară fără să aduci în '
    'discuție faptele reale: că datele nu ajunseseră la tine. În realitate, o '
    'astfel de reacție lasă impresia că îți asumi o vină pe care nu o ai și îl '
    'invită pe celălalt să continue repr'
)


def test_poarta_zece_pica_pe_personajul_inventat() -> None:
    assert alt_personaj(EVALUATORUL_INVENTEAZA, "Ioana Barbu", OMUL_DE_ATUNCI) == "Radu"


def test_poarta_zece_tace_pe_o_evaluare_curata() -> None:
    assert alt_personaj(EVALUARE_CURATA, "Vlad Constantin") is None


def test_poarta_zece_nu_prinde_personajul_sedintei() -> None:
    """Cel al ședinței e chiar cel despre care evaluatorul TREBUIE să vorbească."""
    text = "Ioana Barbu ți-a cerut cifrele, iar tu ai pasat responsabilitatea."
    assert alt_personaj(text, "Ioana Barbu") is None
    assert alt_personaj("Barbu a fost directă cu tine.", "Ioana Barbu") is None


def test_poarta_zece_nu_prinde_numele_omului() -> None:
    assert alt_personaj("Mihai, ai inversat rolurile.", "Ioana Barbu", OMUL_DE_ATUNCI) is None
    # de la plicul 138, omului i se spune pe cod
    assert alt_personaj(f"{COD_PARTICIPANT}, ai inversat rolurile.", "Ioana Barbu") is None


def test_poarta_zece_prinde_si_un_nume_din_lista_care_nu_e_al_sedintei() -> None:
    text = "Ai reacționat ca și cum Carmen Dobre ți-ar fi cerut socoteală."
    assert alt_personaj(text, "Ioana Barbu") == "Carmen Dobre"
