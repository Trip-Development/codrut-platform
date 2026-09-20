"""Citatul pus de aplicatie si poarta 8 — plicurile 106, 108, 109.

Textele de proba sunt scrise aici, dupa forma masurata in rularile salvate; nu se copiaza
sesiuni adevarate si nu apare niciun nume de participant real.
"""

from __future__ import annotations

from codrut.modules.practice.citat import (
    propozitii_numerotate,
    pune_citatul,
    repetare_ramasa,
    sterge_repetarea,
    text_dublat,
)

DOUA = "Nu sunt de acord cu termenul. Am nevoie de încă două zile ca să iasă bine."
UNA = "Păi nu e vina mea, eu am făcut ce mi s-a cerut."


def test_blocul_numerotat_apare_doar_cand_e_de_ales() -> None:
    bloc = propozitii_numerotate(DOUA)
    assert "[1] Nu sunt de acord cu termenul." in bloc
    assert "[2] Am nevoie de încă două zile ca să iasă bine." in bloc
    # o singura propozitie: nu se intreaba modelul, aplicatia pune singura
    assert propozitii_numerotate(UNA) == ""


def test_numarul_devine_propozitia_adevarata() -> None:
    text, motiv = pune_citatul("[🏆 Scor: 4/10] [2] — ai cerut timp fara sa spui de ce.", DOUA)
    assert "«Am nevoie de încă două zile ca să iasă bine.»" in text
    assert motiv == ""


def test_numarul_inexistent_nu_se_ascunde() -> None:
    _, motiv = pune_citatul("[🏆 Scor: 4/10] [7] — observatie.", DOUA)
    assert motiv == "numar inexistent: 7"


def test_fara_numar_sub_noua_se_numara() -> None:
    _, motiv = pune_citatul("[🏆 Scor: 4/10] observatie fara citat.", DOUA)
    assert motiv == "fara numar"


def test_de_la_noua_in_sus_nu_se_cere_citat() -> None:
    _, motiv = pune_citatul("[🏆 Scor: 9/10] a mers bine.", DOUA)
    assert motiv == ""


def test_o_singura_propozitie_o_pune_aplicatia_singura() -> None:
    text, motiv = pune_citatul("[🏆 Scor: 3/10] ai pasat responsabilitatea.", UNA)
    assert text.startswith(f"«{UNA}»")
    assert motiv == ""


def test_stergerea_scoate_doar_repetarea_exacta() -> None:
    text = '«Înțeleg ce spui.» („Înțeleg ce spui") – o validare care sună a cedare.'
    nou, sterse = sterge_repetarea(text)
    assert len(sterse) == 1
    assert "„Înțeleg ce spui" not in nou
    assert "«Înțeleg ce spui.»" in nou
    assert "o validare care sună a cedare." in nou
    assert repetare_ramasa(nou) == 0


def test_stergerea_nu_atinge_un_citat_cu_alte_cuvinte() -> None:
    """Al doilea citat, adevarat, din alta propozitie a omului — masurat la plicul 108."""
    text = '«Când se întâmplă asta, rămân fără timp.» Dar „nu e vina mea" arată pasarea.'
    nou, sterse = sterge_repetarea(text)
    assert sterse == []
    assert nou == text


def test_stergerea_nu_atinge_replica_personajului_din_scena() -> None:
    text = (
        'Elena: „Cum adică nu e vina ta? Tu ești responsabilă de raportul ăsta!"\n\n***\n\n'
        '«Înțeleg ce spui.» – validare neutră.'
    )
    nou, sterse = sterge_repetarea(text)
    assert sterse == []
    assert nou == text


def test_doua_citate_apropiate_nu_dubleaza_textul() -> None:
    """Defectul de la plicul 108: ferestrele se suprapuneau si textul se scria de doua ori."""
    text = (
        '«Înțeleg ce spui.» „Înțeleg ce spui" – validare neutră. '
        '«Ce anume te-a deranjat?» „Ce anume te-a deranjat" – ai ales să întrebi, dar atenție.'
    )
    nou, sterse = sterge_repetarea(text)
    assert len(sterse) == 2
    assert text_dublat(nou) is None
    assert nou.count("validare neutră") == 1
    assert nou.count("ai ales să întrebi") == 1


# ---------------------------------------------------------------- poarta 8

STRICAT = (
    '«Ce anume te-a deranjat cel mai tare?» – Ai ales să întrebi, dar atenție: în acest '
    'scenariu, TU ești cel ca – Ai ales să întrebi, dar atenție: în acest scenariu, TU ești '
    'cel care trebuie să dea feedback pentru întârziere.'
)
REPARAT = (
    '«Ce anume te-a deranjat cel mai tare?» – Ai ales să întrebi, dar atenție: în acest '
    'scenariu, TU ești cel care trebuie să dea feedback pentru întârziere.'
)


def test_poarta_opt_pica_pe_textul_stricat() -> None:
    gasit = text_dublat(STRICAT)
    assert gasit is not None
    assert "Ai ales să întrebi" in gasit


def test_poarta_opt_trece_pe_textul_reparat() -> None:
    assert text_dublat(REPARAT) is None


def test_poarta_opt_nu_da_alarma_la_o_repetare_departata() -> None:
    """Citatul pus si replica personajului repeta des aceleasi cuvinte, la distanta. E in regula."""
    text = (
        'Elena: „Nu am avut timp pentru raportul ăsta, chiar deloc."\n\n***\n\n'
        'Ai lăsat-o să schimbe subiectul. «Nu am avut timp pentru raportul ăsta, chiar deloc.»'
    )
    assert text_dublat(text) is None
