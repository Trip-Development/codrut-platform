"""Semnătura VAPID, adresa permisă și unealta cheilor — plicul 252 (L3-P2), §6.2.10 și §2.7."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from codrut.modules.practice import web_push as wp
from codrut.tools import chei_notificare


@pytest.mark.parametrize("endpoint,gazda", [
    ("https://fcm.googleapis.com/fcm/send/a", "fcm.googleapis.com"),
    ("https://web.push.apple.com/QGx", "web.push.apple.com"),
    ("https://updates.push.services.mozilla.com/wpush/v2/x", "updates.push.services.mozilla.com"),
    ("https://wns2-par02p.notify.windows.com/w/?token=x", "wns2-par02p.notify.windows.com"),
])
def test_gazdele_cunoscute(endpoint, gazda) -> None:
    assert wp.gazda_permisa(endpoint) == gazda


@pytest.mark.parametrize("endpoint", [
    "http://fcm.googleapis.com/x", "https://fcm.googleapis.com./x",
    "https://fcm.googleapis.com:443/x", "https://fcm.googleapis.com@rau.ro/x",
    "https://rau.ro\\@fcm.googleapis.com/x", "https://xn--fcm-0na.googleapis.com/x",
    "https://Fcm.googleapis.com/x", "https://a:b@fcm.googleapis.com/x",
    "https://notify.windows.com/x", "https://.notify.windows.com/x", "nu e adresa", "",
])
def test_gazdele_refuzate(endpoint) -> None:
    assert wp.gazda_permisa(endpoint) is None


def test_semnatura_are_64_de_octeti_base64url_fara_egal() -> None:
    privata, publica = wp.pereche_noua()
    antet = wp.semnatura_vapid(
        "https://fcm.googleapis.com/x", privata, publica, "https://test.cody.example",
        datetime(2026, 1, 14, 8, 5, tzinfo=UTC),
    )
    jwt = antet[len("vapid t="):].split(", k=")[0]
    semnatura = jwt.split(".")[2]
    assert "=" not in jwt
    assert len(wp.din_b64url(semnatura)) == 64


def test_cheile_nepotrivite_sau_stricate_ridica() -> None:
    p1, k1 = wp.pereche_noua()
    _, k2 = wp.pereche_noua()
    with pytest.raises(ValueError):
        wp.cheile(p1, k2)
    with pytest.raises(ValueError):
        wp.cheile("abc", k1)


@pytest.mark.asyncio
async def test_trimite_goala_refuza_gazda_straina_fara_cerere() -> None:
    import httpx

    cereri = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: cereri.append(r)))
    with pytest.raises(ValueError):
        await wp.trimite_goala(client, "https://rau.example/x", "vapid t=x, k=y")
    assert cereri == []
    await client.aclose()


def test_unealta_scrie_exact_doua_randuri(capsys) -> None:
    chei_notificare.main()
    iesire = capsys.readouterr().out
    randuri = iesire.splitlines()
    assert len(randuri) == 2
    tipar = re.compile(
        r"^CODRUT_PUSH_VAPID_(PRIVATE_KEY=[A-Za-z0-9_-]{43}|PUBLIC_KEY=[A-Za-z0-9_-]{87})$"
    )
    assert all(tipar.match(r) for r in randuri)
    privata = randuri[0].split("=", 1)[1]
    publica = randuri[1].split("=", 1)[1]
    wp.cheile(privata, publica)
