"""Plicul 97: personajul nu se repeta doua sesiuni la rand.

Cand numele de pe randul omului avea prenumele participantului, se sarea la urmatorul — dar
sesiunea urmatoare ajungea la acelasi urmator. Pe om il cheama Mihai, in lista e „Mihai Șerban":
la sesiunile 4 si 5 ale masuratorii de referinta, Carmen Dobre de doua ori. Masurat la plicul 97:
toate cele 12 prenume din lista produceau o repetare. Interdictia de la plicul 48 ramane:
personajul nu poarta niciodata prenumele omului.
"""

import pytest

from codrut.modules.practice.prompts import NUME_PERSONAJ, _numele_personajului

PRENUME = sorted({nume.split()[0] for nume in NUME_PERSONAJ}) + ["Andrei", ""]


@pytest.mark.parametrize("prenume", PRENUME)
def test_doua_sesiuni_la_rand_nu_dau_acelasi_personaj(prenume: str) -> None:
    sir = [_numele_personajului(n, prenume) for n in range(3 * len(NUME_PERSONAJ))]

    repetari = [n for n in range(1, len(sir)) if sir[n] == sir[n - 1]]
    assert repetari == []


@pytest.mark.parametrize("prenume", PRENUME)
def test_personajul_nu_poarta_niciodata_prenumele_omului(prenume: str) -> None:
    for n in range(3 * len(NUME_PERSONAJ)):
        nume = _numele_personajului(n, prenume)
        assert nume in NUME_PERSONAJ
        if prenume:
            assert nume.split()[0].lower() != prenume.lower()
