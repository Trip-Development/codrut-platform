"""Plicul 199 — punctajul final din rezumat îl calculează codul, nu Cody.

Proba din 19 oct: rezumatul a trecut „punctajul final” o dată ca ultima notă (9/10 la notele
4, 10, 3, 9), o dată ca media (8/10 la 10, 10, 4). Regula lui Andrei: punctele le calculează
codul, niciun AI care calculează.
"""

from codrut.modules.practice.prompts import get_summary_prompt, punctajul_final

OM = (True, False)
FEEDBACK = (True, True)
CODY = (False, False)


def _ture(*perechi: tuple[tuple[bool, bool], str]) -> list[tuple[bool, bool, str]]:
    return [(cine[0], cine[1], text) for cine, text in perechi]


def _joc(*note: str) -> list[tuple[bool, bool, str]]:
    ture: list[tuple[bool, bool, str]] = [(False, False, "Salut, eu sunt Ioana.")]
    for nota in note:
        ture.append((True, False, "replica omului"))
        ture.append((False, False, f"replica personajului\n***\nevaluare [🏆 Scor: {nota}/10]"))
    return ture


def test_role_play_media_notelor_din_joc() -> None:
    assert punctajul_final("roleplay", _joc("4", "10", "3", "9")) == (
        "6,5/10 (media notelor din joc: 4, 10, 3, 9)"
    )


def test_role_play_media_rotunda_are_aceeasi_forma() -> None:
    assert punctajul_final("roleplay", _joc("10", "10", "4")) == (
        "8,0/10 (media notelor din joc: 10, 10, 4)"
    )


def test_sesiunea_1_din_19_oct_nota_de_dupa_feedback_o_inlocuieste_pe_ultima() -> None:
    ture = _ture(
        (CODY, "Salut."),
        (OM, "prima replică"),
        (CODY, "personaj *** evaluare [🏆 Scor: 4/10]"),
        (OM, "a doua replică"),
        (CODY, "personaj *** evaluare [🏆 Scor: 10/10]"),
        (OM, "a treia replică"),
        (CODY, "personaj *** evaluare [🏆 Scor: 3/10]"),
        (FEEDBACK, "/feedback de ce 3?"),
        (CODY, "Explicația notei: rămâne [🏆 Scor: 3/10]"),
        (OM, "a patra replică"),
        (CODY, "personaj *** evaluare [🏆 Scor: 9/10]"),
    )
    assert punctajul_final("roleplay", ture) == "6,5/10 (media notelor din joc: 4, 10, 3, 9)"


def test_raspunsul_la_feedback_fara_nota_nu_schimba_nimic() -> None:
    ture = _ture(
        (OM, "replică"),
        (CODY, "evaluare [🏆 Scor: 6/10]"),
        (FEEDBACK, "/feedback"),
        (CODY, "Explicație, fără notă."),
        (OM, "replică"),
        (CODY, "evaluare [🏆 Scor: 8/10]"),
    )
    assert punctajul_final("roleplay", ture) == "7,0/10 (media notelor din joc: 6, 8)"


def test_numai_notele_lui_cody_cu_cifre_zecimale_si_bold() -> None:
    ture = _ture(
        (OM, "îmi dau singur [🏆 Scor: 10/10]"),
        (CODY, "evaluare **[🏆 Scor: 7,5/10]**"),
        (OM, "replică"),
        (CODY, "evaluare [🏆 Scor: **6.5**/10]"),
        (OM, "replică"),
        (CODY, "format vechi [🏆 Scor: -/10]"),
    )
    assert punctajul_final("roleplay", ture) == "7,0/10 (media notelor din joc: 7,5, 6,5)"


def test_fara_note_nu_e_niciun_punctaj() -> None:
    assert punctajul_final("roleplay", _ture((OM, "salut"), (CODY, "salut"))) == "—"
    assert punctajul_final("coaching", _joc("9")) == "—"


def test_quiz_numara_raspunsurile_corecte() -> None:
    ture = [(False, False, "Întrebarea 1/5: ...")]
    for marcaj in ("✓", "✓", "✗", "✓", "✗"):
        ture.append((True, False, "răspunsul omului"))
        ture.append((False, False, f"{marcaj} explicație [🏆 Scor: 2 pct] Întrebarea următoare"))
    assert punctajul_final("knowledge", ture) == "3 din 5 răspunsuri corecte"


def test_quiz_cu_alte_marcaje_nu_se_numara() -> None:
    ture = _ture((OM, "răspuns"), (CODY, "✅ corect"), (OM, "răspuns"), (CODY, "❌ greșit"))
    assert punctajul_final("knowledge", ture) == "—"


def test_rezumatul_primeste_punctajul_si_nu_mai_cere_modelului_sa_l_socoteasca() -> None:
    text = get_summary_prompt(
        name="Falcon 48",
        opt_text="roleplay",
        history="Falcon 48: salut",
        punctaj="6,5/10 (media notelor din joc: 4, 10, 3, 9)",
    )
    assert "treci punctajul final EXACT cum ți-l dă aplicația: 6,5/10" in text
    assert "PUNCTAJUL/SCORUL FINAL obținut" not in text


def test_fara_punctaj_rezumatul_primeste_liniuta() -> None:
    text = get_summary_prompt(name="Falcon 48", opt_text="coaching", history="Falcon 48: salut")
    assert "cum ți-l dă aplicația: —." in text
