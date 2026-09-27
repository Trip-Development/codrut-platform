"""Punctajul nou pe competență — plicul 165, partea B (hotărârea lui Andrei, 27 septembrie).

Puncte: contează numai role-play-urile; o zi (în ora României) = cel mult o notă numărată, cea mai
mare; sub 60 → 0, de la 60 → nota − 50; +25 prima reușită cu un tip nou de interlocutor; punctele
nu scad, fără plafon. Niveluri: Aplicare 100 · Consolidare 400 + 2 tipuri · Integrare 1.000 +
3 tipuri + 56 de zile de la prima notă.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from codrut.modules.practice.scoring import (
    ScoreEntry,
    compute_competency_evidence,
    puncte_pentru_nota,
    ziua_in_romania,
)

START = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
ROT = ("jos", "lateral", "sus", "client")


def nota(scor, zi=0, tip="jos", sursa="roleplay", ora=9):
    return ScoreEntry(score=scor, created_at=START.replace(hour=ora) + timedelta(days=zi),
                      source_type=sursa, interlocutor=tip)


def ev(intrari, zi=0):
    return compute_competency_evidence(intrari, today=(START + timedelta(days=zi)).date())


@pytest.mark.parametrize(("scor", "puncte"), [(0, 0), (59, 0), (60, 10), (70, 20), (80, 30),
                                                (90, 40), (100, 50)])
def test_3_nota_in_puncte(scor, puncte):
    assert puncte_pentru_nota(scor) == puncte


def test_1_numai_role_play():
    surse = ("cunostinte", "quiz", "knowledge", "test_in", "test_out")
    intrari = [nota(90, sursa=s) for s in surse]
    assert ev(intrari).points == 0
    assert ev([nota(90, sursa="roleplay", tip=None)]).points == 40
    assert ev([nota(90, sursa="session", tip=None)]).points == 40  # arhiva, fără ședință


def test_2_o_nota_pe_zi_cea_mai_mare():
    # aceeași zi: 70 și 90 → numai 90 (40), plus bonusul tipului o singură dată
    assert ev([nota(70, tip=None), nota(90, tip=None)]).points == 40
    # două zile: se adună
    assert ev([nota(70, 0, None), nota(90, 1, None)]).points == 20 + 40


def test_2_ziua_e_in_ora_romaniei():
    # 22:30 UTC = 01:30 a doua zi, la București
    assert ziua_in_romania(datetime(2026, 10, 1, 22, 30, tzinfo=UTC)) == date(2026, 10, 2)
    seara = ScoreEntry(score=90, created_at=datetime(2026, 10, 1, 22, 30, tzinfo=UTC),
                       source_type="roleplay")
    dimineata = ScoreEntry(score=70, created_at=datetime(2026, 10, 2, 6, 0, tzinfo=UTC),
                           source_type="roleplay")
    # aceeași zi românească → o singură notă (90)
    assert compute_competency_evidence([seara, dimineata], today=date(2026, 10, 2)).points == 40


def test_4_varietate_25_o_data_pe_tip_numai_peste_60():
    assert ev([nota(70, 0, "jos")]).points == 20 + 25
    assert ev([nota(70, 0, "jos"), nota(70, 1, "jos")]).points == 20 + 25 + 20
    assert ev([nota(70, 0, "jos"), nota(70, 1, "sus")]).points == (20 + 25) * 2
    assert ev([nota(50, 0, "jos")]).points == 0  # sub 60, nici bonus
    assert ev([nota(50, 0, "jos"), nota(70, 1, "jos")]).points == 20 + 25  # bonusul vine la reușită
    assert ev([nota(70, 0, "jos"), nota(70, 1, "sus")]).interlocutor_types == 2


def test_5_punctele_nu_scad():
    bune = [nota(90, 0, None), nota(90, 1, None)]
    assert ev(bune + [nota(10, 2, None)], zi=2).points == ev(bune, zi=2).points


def test_puncte_azi():
    intrari = [nota(90, 0, "jos"), nota(80, 3, "sus")]
    assert ev(intrari, zi=3).points_today == 30 + 25
    assert ev(intrari, zi=4).points_today == 0


def test_nivelurile_si_textele():
    # Conștientizare
    c = ev([nota(70, 0, "jos")])
    assert c.level == "CONȘTIENTIZARE" and c.points == 45
    assert c.why_not_higher == (
        "Pentru Aplicare: îți mai trebuie 55 puncte. Primești puncte la simulările în care nota "
        "ta la această competență e de cel puțin 60%.")
    assert ev([]).why_not_higher.startswith("Pentru Aplicare: îți mai trebuie 100 puncte.")
    # Aplicare, un singur tip
    a = ev([nota(100, z, "jos") for z in range(3)], zi=2)  # 75 + 50 + 50 = 175
    assert a.level == "APLICARE" and a.points == 175
    assert a.why_not_higher == ("Pentru Consolidare: îți mai trebuie 225 puncte și reușite cu cel "
                                "puțin 2 tipuri de interlocutor (ai 1).")
    # Aplicare cu puncte destule, dar un singur tip → numai partea lipsă
    a2 = ev([nota(100, z, "jos") for z in range(9)], zi=8)  # 75 + 8*50 = 475
    assert a2.level == "APLICARE"
    assert a2.why_not_higher == (
        "Pentru Consolidare: îți mai trebuie reușite cu cel puțin 2 tipuri de interlocutor (ai 1).")
    # Consolidare
    k = ev([nota(100, z, ROT[z % 2]) for z in range(8)], zi=7)  # 2 tipuri, 400+50
    assert k.level == "CONSOLIDARE"
    assert k.why_not_higher == (
        "Pentru Integrare: îți mai trebuie 550 puncte, reușite cu cel puțin 3 tipuri de "
        "interlocutor (ai 2) și 8 săptămâni de la prima simulare (mai sunt 49 zile).")
    # Integrare: 1.000 puncte, 3 tipuri, 56 de zile
    lung = [nota(100, z, ROT[z % 3]) for z in range(57)]
    assert ev(lung, zi=55).level == "CONSOLIDARE"  # 55 de zile: încă nu
    i = ev(lung, zi=56)
    assert i.level == "INTEGRARE"
    assert i.why_not_higher == (
        "Nivel maxim atins. Punctele cresc în continuare cu fiecare simulare reușită.")


def _simulare(nota_fixa, notate_pe_sedinta, zile=120, nr_comp=7):
    """Estimarea lui Andrei: o ședință pe zi, rotație pe 4 tipuri, `notate_pe_sedinta` din 7."""
    ordine = ["CONȘTIENTIZARE", "APLICARE", "CONSOLIDARE", "INTEGRARE"]
    praguri = {n: [] for n in ordine[1:]}
    for c in range(nr_comp):
        intrari, atins = [], {}
        for d in range(zile):
            if c in {(notate_pe_sedinta * d + i) % nr_comp for i in range(notate_pe_sedinta)}:
                intrari.append(nota(nota_fixa, d, ROT[d % 4]))
            nivel = ev(intrari, zi=d).level
            for n in ordine[1:]:
                if n not in atins and ordine.index(nivel) >= ordine.index(n):
                    atins[n] = d + 1
        for n, z in atins.items():
            praguri[n].append(z)
    return {n: (min(z), max(z)) for n, z in praguri.items()}


def test_simularea_estimarii_lui_andrei():
    # 4 din 7 competențe notate pe ședință (estimarea): ziua în care trece fiecare prag, min–max
    assert _simulare(85, 4) == {"APLICARE": (2, 4), "CONSOLIDARE": (15, 16),
                                "INTEGRARE": (57, 58)}
    assert _simulare(70, 4) == {"APLICARE": (4, 6), "CONSOLIDARE": (25, 27),
                                "INTEGRARE": (78, 79)}
    # 6 din 7 — cât s-a măsurat pe probă (5,88)
    assert _simulare(85, 6) == {"APLICARE": (2, 3), "CONSOLIDARE": (10, 11),
                                "INTEGRARE": (57, 58)}
    assert _simulare(70, 6) == {"APLICARE": (3, 4), "CONSOLIDARE": (17, 18),
                                "INTEGRARE": (57, 58)}
