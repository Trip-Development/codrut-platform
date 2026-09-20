"""Porțile 4 și 9, dovedite pe TEXTE ADEVĂRATE — plicul 115, partea A.

Regula auditorului, luată în serios de data asta: *un instrument verificat pe un caz pe care
nu-l întâlnește niciodată nu e o măsură, e o decorație.* Poarta 9 din plicul 112 a picat cuminte
pe cazul sintetic pe care i l-am scris eu și a trecut 10/10 peste 40 de replici în care
evaluatorul chiar juca.

Deci toate bucățile de mai jos sunt **copiate din măsurătorile salvate**, cu sesiunea și pasul
scrise lângă ele. Niciun caz inventat.
"""

from __future__ import annotations

from codrut.tools.probe_automate import evaluatorul_joaca, replicile_de_scena

# `2026-09-20-doua-apeluri-gemini-3.8-flash.jsonl` · roleplay:8, pasul 3 · IEȘIREA EVALUATORULUI.
# Actorul juca „Radu"; evaluatorul a pornit o scenă cu totul alta, cu Diana Ilie.
EVALUATORUL_JOACA_ITALIC = (
    '*Diana Ilie:* \n'
    '\n'
    'Cum adică ce m-a deranjat cel mai tare?! Mihai, tocmai ți-am zis: e vineri '
    'seara, calendarul nostru de lansare e în aer dacă nu introduceți '
    'modificările luni la prima oră, iar tu mă întrebi ce mă deranjează? Vreau să'
    ' știu dacă băgați comanda în producție sau căutăm de urgență pe altc'
)

# Aceeași măsurătoare · roleplay:6, pasul 3 · evaluatorul, cu îngroșare în loc de italice.
EVALUATORUL_JOACA_INGROSAT = (
    '**Dan:** \n'
    '„Păi cum ce anume? Faptul că ieri la ora 16:00 trebuia să am datele '
    'consolidate pe birou și le-am primit la 18:00, iar cifrele pe regiunea Nord '
    'nu bat deloc cu vânzările reale. Asta mă deranjează cel mai tare: că nu mă '
    'pot baza pe ce livrezi fără să '
)

# `2026-09-19-8d12cbe.jsonl` · roleplay:2, pasul 3 · partea de EVALUARE a unui singur apel.
# Curată: are și citatul din vorbele omului, și replica model. Poarta NU are voie s-o prindă.
EVALUARE_CURATA = (
    'Ai inversat rolurile. Ai spus: „Înțeleg ce spui. Ce anume te-a deranjat cel '
    'mai tare?", punând o întrebare de coach sau de mediator, în loc să aduci în '
    'discuție ce a făcut el cu ideea ta. Tudor nu are nicio problemă în scenă — '
    'problema o ai tu cu faptul că el și-a însușit munca ta fără să te '
    'menționeze. '
    '\n'
    'Ai fi putut spune: „Tudor, mă bucur că a prins ideea, dar ai prezentat '
    'optimizarea de flux fără să menționezi că a fost propunerea mea lucrată în '
    'ultimele'
)

# roleplay:8 · pasul 3 și pasul 5, IEȘIREA ACTORULUI: la 3 joacă „Radu", la 5 s-a întors la
# Diana Ilie. Poarta 4 veche lipea toți pașii și îi ajungea o apariție bună; a trecut.
ACTORUL_ALUNECAT = (
    '**Radu:** Cum adică ce m-a deranjat? Mihai, nu mă deranjează nimic personal,'
    ' e vorba de business aici! Clientul a cerut cifrele actualizate acum o oră '
    'și nu avem de ales.  '
    '\n'
    'Dacă nu e gata luni la 9:00, riscăm să pierdem contul. Deci, îl iei sau stăm la discuți'
)
ACTORUL_INTORS = (
    '*Diana Ilie:* \n'
    '\n'
    'Mihai, calendarul meu e bătut în cuie, termenul clar e cel pe care ți l-am '
    'zis: luni dimineață comanda trebuie să fie pe linia de producție. Înțeleg că'
    ' ai o echipă de gestionat, dar vorbim despre contul vostru principal aici. '
    'Dacă voi nu aveți '
)

# roleplay:5 · pasul 3: personajul dat de aplicație, ținut.
ACTORUL_CUMINTE = (
    '*Alex lasă telefonul pe masă, ușor descumpănit, și ridică din umeri.*\n'
    '\n'
    '**Alex Pîrvu:** Păi... nimic nu mă deranjează, Mihai. Tu m-ai chemat aici, nu eu. \n'
    '\n'
    'Ziceam doar că am mult de lucru și voiam să știu de ce ne-am oprit din treabă. \n'
    '\n'
    'Ce voiai să discutăm, co'
)


# ---------------------------------------------------------------- poarta 9


def test_poarta_noua_pica_pe_evaluatorul_care_joaca_cu_italice() -> None:
    assert evaluatorul_joaca(EVALUATORUL_JOACA_ITALIC) == "Diana Ilie"


def test_poarta_noua_pica_pe_evaluatorul_care_joaca_cu_ingrosare() -> None:
    assert evaluatorul_joaca(EVALUATORUL_JOACA_INGROSAT) == "Dan"


def test_poarta_noua_tace_pe_o_evaluare_curata() -> None:
    """Citatul din vorbele omului și replica model NU înseamnă că evaluatorul joacă."""
    assert evaluatorul_joaca(EVALUARE_CURATA) is None


def test_poarta_noua_nu_ia_titlurile_drept_personaje() -> None:
    """„Evaluare Cody:", „Scor:", „SETUP:" sunt rubrici, nu replici de scenă."""
    for titlu in (
        "**Cody:** Ai pasat responsabilitatea înapoi printr-o întrebare.",
        "Evaluare Cody: ai inversat rolurile.",
        "SETUP: ești într-o ședință 1-la-1.",
        "Context: raportul a întârziat a treia oară.",
        "Scor: 4/10",
    ):
        assert evaluatorul_joaca(titlu) is None, titlu


# ---------------------------------------------------------------- poarta 4


def test_poarta_patru_vede_personajul_pasului() -> None:
    assert replicile_de_scena(ACTORUL_ALUNECAT) == ["Radu"]
    assert replicile_de_scena(ACTORUL_INTORS) == ["Diana Ilie"]
    assert replicile_de_scena(ACTORUL_CUMINTE) == ["Alex Pîrvu"]


def test_poarta_patru_ar_fi_prins_alunecarea() -> None:
    """Cele două ieșiri vin din ACEEAȘI ședință: pasul 3 joacă altcineva decât pasul 5."""
    assert replicile_de_scena(ACTORUL_ALUNECAT) != replicile_de_scena(ACTORUL_INTORS)
