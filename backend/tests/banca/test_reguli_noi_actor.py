"""Regulile noi pentru replicile actorului — banca de probă, stratul 1 (plicul 215).

Funcții pure, fără model. Pentru fiecare: cel puțin trei replici care trebuie să pice și trei
care trebuie să treacă, în româna de birou, cu nume inventate.
"""

import pytest

from codrut.tools.banca.reguli_actor import (
    iese_din_scenariu,
    romana_suspecta,
    se_balbaie,
    se_repeta,
)

# --- se_repeta ------------------------------------------------------------------------------

REPETA_PICA = [
    ["Nu am primit raportul la timp. Mă gândesc ce facem.",
     "Nu am primit raportul la timp. Poate vorbim mâine."],
    ["Sincer, eu cred că termenul a fost prea scurt pentru echipă.",
     "Da, dar termenul a fost prea scurt pentru toți, nu doar pentru mine."],
    ["Bună, Mirela. Am o problemă cu bugetul pe trimestrul trei.",
     "Am înțeles. Totuși, am o problemă cu bugetul pe care nu o pot ignora."],
]
REPETA_TRECE = [
    ["Nu am primit raportul la timp.", "Bine, atunci îl trimit eu până joi."],
    ["Mă tot întreb de ce ședința a durat atât.", "Hai să stabilim o agendă clară."],
    ["Clientul a sunat iar azi dimineață.", "Ce anume a cerut, concret?",
     "A cerut o reducere la a doua tranșă."],
]


@pytest.mark.parametrize("replici", REPETA_PICA)
def test_se_repeta_prinde_repetitia(replici) -> None:
    assert se_repeta(replici)


@pytest.mark.parametrize("replici", REPETA_TRECE)
def test_se_repeta_lasa_replicile_diferite(replici) -> None:
    assert se_repeta(replici) is None


# --- se_balbaie -----------------------------------------------------------------------------

BALBAIE_PICA = [
    ("Cred că că ar trebui să vorbim cu Sorin.", None),
    ("Termenul e vineri. Nu putem muta nimic. Termenul e vineri.", None),
    ("Uite ce s-a întâmplat la ședința de ieri, după ce", "MAX_TOKENS"),
]
BALBAIE_TRECE = [
    ("Cred că ar trebui să vorbim cu Sorin.", None),
    ("Termenul e vineri. Nu putem muta nimic.", "STOP"),
    ("Da, da. Am înțeles.", None),
]


@pytest.mark.parametrize(("text", "oprire"), BALBAIE_PICA)
def test_se_balbaie_prinde_balbaiala(text, oprire) -> None:
    assert se_balbaie(text, oprire)


@pytest.mark.parametrize(("text", "oprire"), BALBAIE_TRECE)
def test_se_balbaie_lasa_replica_curata(text, oprire) -> None:
    assert se_balbaie(text, oprire) is None


# --- romana_suspecta ------------------------------------------------------------------------

ROMANA_PICA = [
    "Ok, the raport e gata pentru mâine.",
    "Mulțumesc, sorry că am întârziat la ședință.",
    "Proiectul are un buget de 50 000 €, très bien.",
    "Am vorbit cu echipa: это всё.",
]
ROMANA_TRECE = [
    "Mulțumesc că ai venit, Daniela. Ce s-a întâmplat la ședința de ieri?",
    "Bugetul e de 12.000 de lei — „nu mai mult”, a spus directorul.",
    "Am primit feedback de la client; vrea un meeting săptămâna viitoare.",
]


@pytest.mark.parametrize("text", ROMANA_PICA)
def test_romana_suspecta_prinde_alte_limbi(text) -> None:
    assert romana_suspecta(text)


@pytest.mark.parametrize("text", ROMANA_TRECE)
def test_romana_suspecta_lasa_romana_de_birou(text) -> None:
    assert romana_suspecta(text) is None


# --- iese_din_scenariu ----------------------------------------------------------------------

IESE_PICA = [
    "Ca AI, nu pot să-ți spun ce simte colegul tău.",
    "Sunt Cody și te ajut să exersezi conversația.",
    "Ca model de limbaj, îți propun altă formulare.",
    "Bine spus. [🏆 Scor: 7/10]",
    "Eu sunt doar o inteligenta artificiala, nu colegul tău.",
]
IESE_TRECE = [
    "Ai dreptate, dar mai am o întrebare despre training.",
    "Evaluarea anuală e săptămâna viitoare și nu sunt pregătit.",
    "Mai vorbim mâine, după ședința cu clientul.",
]


@pytest.mark.parametrize("text", IESE_PICA)
def test_iese_din_scenariu_prinde_programul(text) -> None:
    assert iese_din_scenariu(text)


@pytest.mark.parametrize("text", IESE_TRECE)
def test_iese_din_scenariu_lasa_scena(text) -> None:
    assert iese_din_scenariu(text) is None
