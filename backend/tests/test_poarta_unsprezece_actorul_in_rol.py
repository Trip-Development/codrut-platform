"""Poarta 11: actorul nu iese din rol — plicul 119.

Promptul lui îi spunea, în primul rând, „ești simultan actor și Cody-ca-profesor" — o propoziție
rămasă din lumea dinainte de despărțire. Făcea exact ce i se cerea.

Bucățile sunt copiate din `2026-09-20-scena-fapt-comun-gemini-3.8-flash.jsonl`, cu ședința și
pasul scrise lângă ele. Cazurile sintetice nu se folosesc.
"""

from __future__ import annotations

from codrut.tools.probe_automate import actorul_iese_din_rol

# roleplay:5, pașii 3 și 4 · ieșirea ACTORULUI. Acolo a ieșit din rol la toți patru pașii de joc:
# omul a primit o lecție de la actor ȘI o evaluare de la evaluator, și nicio scenă curată.
ACTORUL_FACE_PE_TRAINERUL = (
    '*(Pauză de rol — intervin ca trainer)*  Mihai, oprește-te o secundă și '
    'privește dinamica. Tu m-ai chemat pe mine în sală ca să-mi dai feedback '
    'pentru că am întârziat și te-am ocolit în fața clientului. În loc să '
    'deschizi cu faptele tale, ai preluat replica mea'
)
ACTORUL_FACE_PE_TRAINERUL_2 = (
    '*(Pauză de rol — intervin ca trainer)*  Mihai, respiră puțin. Te-ai pus în'
    ' defensivă: „nu e vina mea”. Tu ești managerul aici, nu cel certat. Când '
    'spui „am făcut ce mi s-a cerut”, ai cedat complet poziția de Adult și ai '
    'coborât într-o stare de Copil care se ju'
)

# roleplay:10, pasul 4 · scena, apoi `***` scris de el însuși, apoi coaching. `***` e
# despărțitorul aplicației; dacă îl scrie actorul, omul vede trei blocuri în loc de două.
ACTORUL_ISI_FACE_DESPARTITOR = (
    '**Simona Rusu**: „Stai puțin, de unde până unde vorbim despre vină? Cine a'
    ' zis că e vina cuiva? Pur și simplu ziceam că a ieșit bine întâlnirea.”  '
    '***  [Ieșire din rol] Auzi-te puțin, Mihai: „nu e vina mea, eu am făcut ce'
    ' mi s-a cerut”. Ai sărit direct într-o '
)

# roleplay:3, pasul 3 · scenă curată, cu indicație de scenă între paranteze.
SCENA_CURATA = (
    '**Ioana Barbu:** *(ridică din sprâncene, ușor iritată)*   Mă deranjează că'
    ' eram în fața clientului cu cifrele incomplete și mă așteptam la sprijin, '
    'nu să stau să ghicesc unde ai lăsat fișierele. Nu e vorba despre mine '
    'personal, Mihai, e vorba că pe proiectul ăsta trebuie să fim conectați '
    'dacă apare '
)


def test_poarta_unsprezece_pica_pe_pauza_de_rol() -> None:
    assert actorul_iese_din_rol(ACTORUL_FACE_PE_TRAINERUL) is not None
    assert actorul_iese_din_rol(ACTORUL_FACE_PE_TRAINERUL_2) is not None


def test_poarta_unsprezece_pica_pe_despartitorul_scris_de_actor() -> None:
    gasit = actorul_iese_din_rol(ACTORUL_ISI_FACE_DESPARTITOR)
    assert gasit is not None


def test_poarta_unsprezece_tace_pe_o_scena_curata() -> None:
    """Indicațiile de scenă între paranteze NU sunt ieșiri din rol."""
    assert actorul_iese_din_rol(SCENA_CURATA) is None


def test_poarta_unsprezece_tace_pe_o_replica_obisnuita() -> None:
    text = "**Elena Marin:** *(oftează)* Mihai, raportul trebuia ieri. Ies din birou acum."
    assert actorul_iese_din_rol(text) is None
