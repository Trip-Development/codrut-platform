"""„O replică pe zi”: seria iertătoare — plicul 236 (L2-P1), testul 4.

Săptămâna = luni–duminică (ISO). O zi ratată pe săptămână nu rupe seria; a doua, da. Ziua de azi
nu e ratată până nu trece; zilele dinaintea primei replici nu sunt „ratate”.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

JOI = date(2026, 11, 19)


def _zile(*zile: int, luna: int = 11) -> set[date]:
    return {date(2026, luna, z) for z in zile}


def _interval(de_la: date, pana_la: date, fara: set[date] = frozenset()) -> set[date]:
    out, z = set(), de_la
    while z <= pana_la:
        if z not in fara:
            out.add(z)
        z += timedelta(days=1)
    return out


@pytest.mark.parametrize(
    ("zile", "azi", "serie"),
    [
        pytest.param(set(), JOI, 0, id="a-nimic"),
        pytest.param(_zile(16, 17, 18, 19), JOI, 4, id="b-luni-joi"),
        pytest.param(_zile(16, 17, 18), JOI, 3, id="c-azi-inca-nimic"),
        pytest.param(_zile(16, 17, 19), JOI, 3, id="d-miercuri-ratata"),
        pytest.param(_zile(16, 19), JOI, 1, id="e-doua-ratate-aceeasi-saptamana"),
        pytest.param(
            _interval(date(2026, 11, 2), JOI, fara={date(2026, 11, 4), date(2026, 11, 12)}),
            JOI, 16, id="f-cate-una-pe-saptamana",
        ),
        pytest.param(_interval(date(2026, 11, 9), date(2026, 11, 15)), JOI, 0, id="g-fara-azi"),
        pytest.param(
            _interval(date(2026, 11, 9), date(2026, 11, 15)) | {JOI}, JOI, 1, id="g-cu-azi"
        ),
        pytest.param(_zile(15, 16), date(2026, 11, 17), 2, id="h-duminica-luni"),
        pytest.param(_zile(18), JOI, 1, id="i-o-singura-ieri"),
    ],
)
def test_seria(zile, azi, serie) -> None:
    from codrut.modules.practice.replica_zilei import seria

    assert seria(zile, azi) == serie
