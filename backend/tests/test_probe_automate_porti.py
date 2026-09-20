"""Portile uneltei de probe automate (plicul 82), pe texte fixe.

Nu judeca daca Cody e bun — verifica doar ca regulile de potrivire prind ce trebuie si NU
prind ce nu trebuie. O poarta care clasifica gresit e mai rea decat una care lipseste.
"""

from codrut.tools.probe_automate import (
    are_citat,
    are_replica_model,
    personajul,
    portile,
    scorul,
)

EVALUARE_SUB_9 = (
    "Elena Marin: Bine, dar raportul tot lipsește.\n\n"
    "**Evaluare:** Ai spus „eu am făcut ce mi s-a cerut”, iar asta mută discuția pe vină. "
    "Ai fi putut spune: «Îmi pare rău pentru întârziere, ți-l trimit până la 14.» "
    "— ar fi închis subiectul.\n[🏆 Scor: 6/10]"
)


def test_scorul_se_citeste_in_formele_intalnite() -> None:
    assert scorul("[🏆 Scor: 7/10]") == 7
    assert scorul("**Scor: 8,5/10**") == 8.5
    assert scorul("Scor: **9** / 10") == 9
    assert scorul("Nicio notă aici.") is None


def test_citatul_trebuie_sa_fie_din_cuvintele_omului() -> None:
    om = "Păi nu e vina mea, eu am făcut ce mi s-a cerut."
    assert are_citat(EVALUARE_SUB_9, om)
    assert not are_citat("Ai spus „altceva cu totul decât el”, iar asta...", om)
    # ghilimelele replicii-model nu sunt un citat din om
    assert not are_citat("Ai fi putut spune: «Îmi pare rău pentru întârziere.»", om)


def test_replica_model_cere_si_formularea_si_ghilimelele() -> None:
    assert are_replica_model(EVALUARE_SUB_9)
    # forma cea mai des intalnita la masuratoarea de referinta: replica pe randul urmator
    assert are_replica_model("Ai fi putut spune:\n„Carmen, hai să vedem ce lipsește.”")
    assert are_replica_model("Ai fi putut spune:  \n„Radu, înțeleg graba.”")
    # unele modele o scriu ca titlu — masurat la plicul 102, pe 3.1-flash-lite si 3.5-flash-lite
    assert are_replica_model("**Replica model:**\n„Elena, înțeleg că a fost o săptămână grea.”")
    assert are_replica_model("**Replică model:**\n„Înțeleg că a fost aglomerat.”")
    assert not are_replica_model("Ai fi putut fi mai orientat spre soluții.")
    assert not are_replica_model("Replica model lipsește de tot aici, fără citat.")


def test_personajul_se_gaseste_dupa_nume_nu_dupa_prenumele_omului() -> None:
    assert personajul("Mihai, astăzi joci cu Elena Marin, colega ta.") == "Elena Marin"
    assert personajul("Salut, Mihai. Cum îți merge ziua?") is None
    assert personajul("Șerban intră în birou.") == "Mihai Șerban"


def _pas(nr, fel, raspuns, om=None, eroare=None):
    return {"pas": nr, "fel": fel, "om": om, "raspuns": raspuns, "eroare": eroare}


def test_portile_unei_sesiuni_de_role_play() -> None:
    pasi = [
        _pas(1, "salut", "Salut, Mihai. Hai să lucrăm puțin. Ești gata de un joc de rol?"),
        _pas(2, "pornire", "Scena: Elena Marin, colega ta, te oprește pe hol.", "Da, hai."),
        _pas(3, "joc", EVALUARE_SUB_9, "Păi nu e vina mea, eu am făcut ce mi s-a cerut."),
        _pas(4, "joc", "Elena Marin: Bine.\n\n**Evaluare:** fără notă."),
        _pas(5, "despartire", "Zi faină și ție, Mihai!", "Mulțumesc, zi faină!"),
    ]

    p = portile("roleplay", pasi, 1)

    assert p["1"]["trecute"] == p["1"]["instante"] == 5
    assert p["2"]["picate"] == ["pas 4: fara punctaj"]
    assert p["3"]["trecute"] == p["6"]["trecute"] == 1
    # Poarta 4 se uita la FIECARE pas de joc, nu la toata sedinta lipita — plicul 115. Aici
    # sunt doi pasi in care vorbeste cineva, si la amandoi e personajul dat de aplicatie.
    # („Scena:" de la pasul 2 e o rubrica, nu un vorbitor.)
    assert p["4"]["personaj"] == "Elena Marin" and p["4"]["trecute"] == p["4"]["instante"] == 2
    assert p["5"]["picate"] == [] and p["7"]["picate"] == []


def test_portile_prind_numele_lipsa_si_metodele_scoase() -> None:
    pasi = [
        _pas(1, "salut", "Salut, [Nume]. Azi lucrăm cu metoda sandwich."),
        _pas(2, "pornire", "", "Da, hai.", eroare="vertex_rate_limited"),
    ]

    p = portile("coaching", pasi, 1)

    assert p["1"]["picate"] == ["pas 2: vertex_rate_limited"]
    assert p["7"]["picate"] == ["pas 1: SANDWICH"]
    assert "salutul nu contine numele omului" in p["5"]["picate"]


def test_adkar_si_oils_se_numara_dar_nu_pica_poarta() -> None:
    """Plicul 95: raman in quizurile intermediare, cu voia lui Andrei (19 septembrie)."""
    pasi = [_pas(1, "raspuns", "Întrebarea 3/10: În modelul ADKAR, ce urmează după Awareness? "
                               "Și în OILS, ce înseamnă O? Și încă o dată: ADKAR.")]

    p = portile("knowledge", pasi, 1)

    assert p["7"]["picate"] == [] and p["7"]["trecute"] == p["7"]["instante"] == 1
    assert p["7"]["numarate"] == {"ADKAR": 2, "OILS": 1}
    assert not p["2"]["aplicabila"] and p["2"]["instante"] == 0
