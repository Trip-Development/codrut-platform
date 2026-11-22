"""Web Push fără bibliotecă nouă: semnătura VAPID și trimiterea GOALĂ — plicul 252 (L3-P2).

Mesajul pleacă gol (zero octeți): textul notificării e scris în `public/sw.js`, pe telefon.
Serviciul telefonului (Google / Apple / Mozilla / Microsoft) primește numai adresa anonimă a
browserului, ora și semnătura noastră; în semnătură, la „cine trimite”, stă adresa aplicației.

Cheile: privata = 32 de octeți, publica = punctul necomprimat P-256 de 65 de octeți, ambele
base64url fără `=`. Nicio funcție de aici nu scrie o cheie în jurnal.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

GAZDE_PERMISE = frozenset({
    "fcm.googleapis.com",
    "web.push.apple.com",
    "updates.push.services.mozilla.com",
})
SUFIX_WINDOWS = ".notify.windows.com"
VALABILITATE = timedelta(hours=12)


class _FaraAdreseDeTelefon(logging.Filter):
    """`httpx` scrie la INFO „HTTP Request: POST <adresa>”.

    Adresa telefonului nu intră în jurnal: rândurile cu gazdele serviciilor se opresc aici.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        text = record.getMessage()
        return not (
            any(g in text for g in GAZDE_PERMISE) or SUFIX_WINDOWS in text
        )


logging.getLogger("httpx").addFilter(_FaraAdreseDeTelefon())


def b64url(date: bytes) -> str:
    return base64.urlsafe_b64encode(date).rstrip(b"=").decode("ascii")


def din_b64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def gazda_permisa(endpoint: str) -> str | None:
    """Gazda adresei, dacă e una din serviciile cunoscute; altfel None. Citită o singură dată.

    Se cer: `https`, fără port, fără nume/parolă, gazda cu litere mici și fără punct la sfârșit,
    egală cu una din listă sau terminată în `.notify.windows.com`.
    """
    try:
        url = httpx.URL(endpoint)
    except (httpx.InvalidURL, TypeError, ValueError):
        return None
    gazda = url.host
    if url.scheme != "https" or url.port is not None or url.userinfo:
        return None
    if not gazda or gazda != gazda.lower() or gazda.endswith(".") or "\\" in endpoint:
        return None
    # autoritatea scrisă în adresă trebuie să fie EXACT gazda (fără port, nume, alte litere)
    if not endpoint.startswith("https://") or endpoint[8:].split("/", 1)[0] != gazda:
        return None
    if gazda in GAZDE_PERMISE or (
        gazda.endswith(SUFIX_WINDOWS) and len(gazda) > len(SUFIX_WINDOWS)
    ):
        return gazda
    return None


def gazda_pentru_jurnal(endpoint: str) -> str:
    """Numai gazda (fără cale), ca să se vadă dacă un telefon folosește altă gazdă."""
    try:
        return httpx.URL(endpoint).host or "?"
    except (httpx.InvalidURL, TypeError, ValueError):
        return "?"


def cheile(cheia_privata: str, cheia_publica: str) -> ec.EllipticCurvePrivateKey:
    """Citește perechea; ridică ValueError dacă nu se potrivesc sau sunt stricate."""
    privata = din_b64url(cheia_privata)
    publica = din_b64url(cheia_publica)
    if len(privata) != 32 or len(publica) != 65 or publica[0] != 4:
        raise ValueError("cheile notificarii au alta forma")
    cheie = ec.derive_private_key(int.from_bytes(privata, "big"), ec.SECP256R1())
    numere = cheie.public_key().public_numbers()
    if numere.x.to_bytes(32, "big") + numere.y.to_bytes(32, "big") != publica[1:]:
        raise ValueError("cheile notificarii nu se potrivesc")
    return cheie


def semnatura_vapid(
    endpoint: str, cheia_privata: str, cheia_publica: str, subiect: str, acum: datetime
) -> str:
    """Antetul `Authorization`: `vapid t=<jwt>, k=<cheia publică>`.

    JWT ES256; semnătura adusă din DER la forma r‖s de 64 de octeți.
    """
    cheie = cheile(cheia_privata, cheia_publica)
    url = httpx.URL(endpoint)
    antet = {"typ": "JWT", "alg": "ES256"}
    afirmatii = {
        "aud": f"https://{url.host}",
        "exp": int((acum + VALABILITATE).timestamp()),
        "sub": subiect,
    }
    de_semnat = ".".join(
        b64url(json.dumps(parte, separators=(",", ":")).encode("utf-8"))
        for parte in (antet, afirmatii)
    )
    der = cheie.sign(de_semnat.encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    semnatura = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return f"vapid t={de_semnat}.{b64url(semnatura)}, k={cheia_publica}"


async def trimite_goala(client: httpx.AsyncClient, endpoint: str, antet: str) -> int:
    """`POST endpoint` cu corp gol; întoarce codul de răspuns. Adresa se verifică din nou aici."""
    if gazda_permisa(endpoint) is None:
        raise ValueError("adresa notificarii nu e permisa")
    raspuns = await client.post(
        endpoint,
        content=b"",
        headers={
            "Authorization": antet,
            "TTL": "3600",
            "Urgency": "normal",
            "Content-Length": "0",
        },
    )
    return raspuns.status_code


def pereche_noua() -> tuple[str, str]:
    """(privata, publica), base64url — pentru `tools/chei_notificare.py`."""
    cheie = ec.generate_private_key(ec.SECP256R1())
    privata = cheie.private_numbers().private_value.to_bytes(32, "big")
    numere = cheie.public_key().public_numbers()
    publica = b"\x04" + numere.x.to_bytes(32, "big") + numere.y.to_bytes(32, "big")
    return b64url(privata), b64url(publica)
