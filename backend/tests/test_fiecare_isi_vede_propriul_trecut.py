"""Fiecare apel își citește în istoric numai bucata lui — plicul 117.

Două încercări de despărțire au eșuat la fel: evaluatorul juca scena, actorul dădea note. Cauza
nu era promptul, ci istoricul — amândouă apelurile primeau aceeași listă de mesaje, făcută din
textul LIPIT, deci fiecare își citea, marcată ca fiind a lui, și munca celuilalt.

Dovada din raportul 115: niciuna din cele 16 abateri nu era la pasul 3, primul pas de joc; toate
la 4, 5 și 6. Promptul ține la început, istoricul câștigă pe măsură ce se lungește.
"""

from __future__ import annotations

from dataclasses import dataclass

from codrut.modules.practice.models import TurnRole
from codrut.modules.practice.service import PracticeSessionService


@dataclass
class Replica:
    role: TurnRole
    text: str
    text_actor: str | None = None
    text_evaluator: str | None = None


SCENA = "**Elena Marin:** Bine, dar raportul tot lipsește."
EVALUARE = "Ai pasat responsabilitatea. [🏆 Scor: 4/10]"
LIPIT = f"{SCENA}\n\n***\n\n{EVALUARE}"

ISTORIC = [
    Replica(TurnRole.participant, "Salut."),
    Replica(TurnRole.actor, LIPIT, text_actor=SCENA, text_evaluator=EVALUARE),
    Replica(TurnRole.participant, "Păi nu e vina mea."),
    # Un raspuns dupa ea, ca sa nu fie orfana: replica omului ramasa fara raspuns e inlocuita
    # de cea de acum, si asta e regula plicurilor 64-65, aparata separat mai jos.
    Replica(TurnRole.actor, LIPIT, text_actor=SCENA, text_evaluator=EVALUARE),
]


def _istoric(meserie: str, turns=ISTORIC, acum: str = "Acum ce facem?"):
    serviciu = PracticeSessionService.__new__(PracticeSessionService)
    return [
        (m.role, m.text) for m in serviciu._istoricul_unei_meserii(turns, acum, meserie)
    ]


def test_actorul_nu_mai_vede_evaluarea() -> None:
    mesaje = _istoric("actor")
    assert ("model", SCENA) in mesaje
    assert all(EVALUARE not in text for _, text in mesaje)


def test_evaluatorul_vede_scena_dar_nu_ca_fiind_a_lui() -> None:
    """Plicul 118 schimbă ce apăra testul ăsta la 117, și dinadins.

    La 117 evaluatorului i s-a tăiat scena de tot — și atunci și-a inventat propriul scenariu:
    personajul inventat a apărut în 23 de replici ale lui și într-una a actorului. Scena nu e
    „bucata actorului", e FAPT COMUN.

    Acum o primește înapoi, dar niciodată ca replică a lui: apare numai în mesaje de rol „user",
    cu etichetă. Ce nu are voie să se întoarcă e ATRIBUIREA, nu conținutul.
    """
    mesaje = _istoric("evaluator")
    assert ("model", EVALUARE) in mesaje
    assert any(SCENA in text for rol, text in mesaje if rol == "user")
    assert all(SCENA not in text for rol, text in mesaje if rol == "model")
    assert any("[În scenă, celălalt personaj a spus:]" in text for _, text in mesaje)


def test_actorul_tot_nu_vede_evaluarea() -> None:
    """Istoricul actorului nu se atinge — el e curat: 0/40, și își ține personajul 41/41."""
    mesaje = _istoric("actor")
    assert all(EVALUARE not in text for _, text in mesaje)


def test_replicile_omului_ajung_la_amandoi_intregi() -> None:
    """Ele sunt ce s-a spus de fapt; nu se taie pentru nimeni.

    La evaluator, replica omului vine cu scena înaintea ei, deci se verifică prin cuprindere.
    """
    for meserie in ("actor", "evaluator"):
        mesaje = _istoric(meserie)
        assert any("Păi nu e vina mea." in text for rol, text in mesaje if rol == "user")
        assert mesaje[-1][0] == "user"
        assert mesaje[-1][1].endswith("Acum ce facem?")


def test_randurile_vechi_folosesc_textul_lipit() -> None:
    """Sesiunile începute înainte nu se strică: ele doar nu câștigă nimic."""
    vechi = [Replica(TurnRole.actor, LIPIT)]  # fără bucăți salvate
    for meserie in ("actor", "evaluator"):
        assert ("model", LIPIT) in _istoric(meserie, vechi)


def test_o_bucata_lipsa_sare_randul_in_loc_sa_readuca_amestecul() -> None:
    """Evaluare nelivrată: actorul își ia bucata, evaluatorul sare peste rând."""
    fara_evaluare = [Replica(TurnRole.actor, SCENA, text_actor=SCENA, text_evaluator="")]
    assert ("model", SCENA) in _istoric("actor", fara_evaluare)
    assert all(rol != "model" for rol, _ in _istoric("evaluator", fara_evaluare))


def test_lacatul_plicului_64_ramane() -> None:
    """Replicile „user" lipite se string, iar replica de acum ia locul orfanului."""
    lipite = [
        Replica(TurnRole.participant, "prima"),
        Replica(TurnRole.participant, "a doua"),
    ]
    mesaje = _istoric("actor", lipite, acum="a treia")
    assert mesaje == [("user", "a treia")]
