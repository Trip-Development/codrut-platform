"""Plicul 170: fara vorbire, transcrierea nu mai inventeaza text.

Pe proba, 2 secunde de ton (220 Hz) ieseau transcrise „Bună ziua.", iar 3 secunde de tacere
si 2 de zgomot ieseau „00:00". Cu oprirea automata pe tacere, textul inventat se trimitea
singur in conversatie, ca replica a omului.

Promptul nu spunea nimic despre ce se face cand nu se aude vorbire. Acum spune. Vorbirea
inceata sau neclara se transcrie in continuare — aia NU are voie sa fie aruncata.

Fara retea si fara apeluri: testul citeste promptul.
"""

from codrut.modules.practice.generation_provider import TRANSCRIBE_PROMPT


def test_promptul_cere_text_gol_cand_nu_e_vorbire() -> None:
    assert "nu există deloc vorbire omenească" in TRANSCRIBE_PROMPT
    assert "returnează exact textul gol" in TRANSCRIBE_PROMPT
    # Cele patru feluri de sunet fara vorba, numite pe fata.
    for fel in ("tăcere", "zgomot", "muzică", "ton"):
        assert fel in TRANSCRIBE_PROMPT, fel


def test_vorbirea_inceata_nu_se_arunca() -> None:
    """Corectia 3 a controlorului: regula de mai sus nu are voie sa taie vorbirea slaba."""
    assert "Vorbirea încetă sau neclară se transcrie" in TRANSCRIBE_PROMPT


def test_promptul_e_tot_pentru_romana_si_fara_comentarii() -> None:
    """Regula noua nu a sters nimic din ce era inainte."""
    assert "limba română" in TRANSCRIBE_PROMPT
    assert "Returnează doar transcrierea." in TRANSCRIBE_PROMPT
    assert "Elimină bâlbele" in TRANSCRIBE_PROMPT
