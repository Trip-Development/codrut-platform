"""Codul cu care Cody îl știe pe om — plicul 138.

Hotărârea lui Andrei, 23 septembrie: spre Google nu pleacă niciodată numele omului, ci un cod —
un animal în engleză și un număr din două cifre, cu spațiu: `Fox 34`. Codul se dă o singură dată,
la prima ședință de exersare, și rămâne al lui, ca tabloul de evoluție să nu se rupă.

Codul e un câmp separat (`ParticipantProfile.cody_alias`), NU numele anonim de la chestionare
(`anonymous_name`): cele două nu au voie să poată fi puse unul lângă altul.
"""

from __future__ import annotations

import re
import secrets
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.companies.models import ParticipantProfile

# 40 de animale obișnuite, ușor de citit și de ținut minte. Fără nimic care poate jigni sau face
# glume (fără „Pig", „Donkey", „Snake", „Rat", „Weasel", „Cow"...), fără nume care sunt și nume
# de oameni („Robin") și fără cuvinte cu al doilea înțeles. Lista întreagă e în raportul 138, ca
# Andrei să taie ce nu-i place.
ANIMALE: tuple[str, ...] = (
    "Fox", "Otter", "Owl", "Hawk", "Eagle", "Falcon", "Heron", "Swan",
    "Kiwi", "Wren", "Lark", "Raven", "Crane", "Stork", "Pelican", "Penguin",
    "Lynx", "Wolf", "Bear", "Deer", "Elk", "Moose", "Bison", "Horse",
    "Zebra", "Giraffe", "Gazelle", "Panda", "Koala", "Tiger", "Lion", "Leopard",
    "Jaguar", "Puma", "Dolphin", "Orca", "Seal", "Salmon", "Squirrel", "Hedgehog",
)

_INCERCARI = 50


def cod_nou() -> str:
    """Un cod la întâmplare: `Fox 34`. Numărul, de la 10 la 99."""
    return f"{secrets.choice(ANIMALE)} {10 + secrets.randbelow(90)}"


async def codul_omului(session: AsyncSession, profil: ParticipantProfile) -> str:
    """Codul omului; dacă n-are încă, i se dă acum unul, unic în toată aplicația.

    Unicitatea o ține și baza (`uq_participant_profiles_cody_alias`); aici doar se evită
    ciocnirea înainte să ajungă acolo. 3.600 de coduri posibile, deci o ciocnire e rară.
    """
    if profil.cody_alias:
        return profil.cody_alias
    for _ in range(_INCERCARI):
        cod = cod_nou()
        ocupat = (await session.execute(
            select(ParticipantProfile.id).where(ParticipantProfile.cody_alias == cod)
        )).first()
        if ocupat is None:
            profil.cody_alias = cod
            await session.flush()
            return cod
    raise RuntimeError("Nu s-a găsit un cod liber pentru Cody după 50 de încercări.")


def _fara_diacritice(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


# Cuvinte care stau chiar în promptul lui Cody („INTERZIS «user», «participant»...") și nu pot
# identifica pe nimeni. Un cont de probă numit „user 1" le are în nume; fără lista asta, poarta
# de nume suna pe regula lui Cody însăși — măsurat pe probă, la plicul 138: 18 alarme false.
CUVINTE_CARE_NU_SUNT_NUME = frozenset({"user", "participant", "utilizator", "utilizatorul",
                                       "trainer", "test", "cody"})


def _tipar_pentru_nume(nume: str) -> re.Pattern[str] | None:
    """Fiecare bucată din nume (prenume, nume, fiecare parte a unui nume cu cratimă), ca
    cuvânt întreg, fără să țină cont de litere mari și de diacritice."""
    bucati = {
        _fara_diacritice(b).lower()
        for b in re.split(r"[\s\-]+", nume or "")
        if len(b) >= 2
    } - CUVINTE_CARE_NU_SUNT_NUME
    if not bucati:
        return None
    alternative = "|".join(sorted((re.escape(b) for b in bucati), key=len, reverse=True))
    return re.compile(rf"(?<![\w])(?:{alternative})(?![\w])")


def ascunde_numele(text: str, nume: str, cod: str) -> str:
    """Textul, cu orice bucată din numele omului înlocuită de cod.

    Se folosește la ce a scris MODELUL despre om înainte de plicul 138 — memoria din ședințele
    vechi, scrisă pe vremea când numele pleca spre el și deci îl conține. Numai cuvinte întregi:
    „Ionelaș" nu e „Ionela". Căutarea se face pe textul fără diacritice, iar înlocuirea pe cel
    original, poziție cu poziție (scoaterea diacriticelor nu schimbă lungimea în română).
    """
    tipar = _tipar_pentru_nume(nume)
    if not text or tipar is None:
        return text
    simplu = _fara_diacritice(text).lower()
    if len(simplu) != len(text):
        # o literă care se descompune altfel decât în română: se lucrează pe textul simplu
        return tipar.sub(cod, simplu)
    bucati: list[str] = []
    ultim = 0
    for m in tipar.finditer(simplu):
        bucati.append(text[ultim:m.start()])
        bucati.append(cod)
        ultim = m.end()
    bucati.append(text[ultim:])
    # „Fox 34-Fox 34" dintr-un nume cu cratimă devine un singur cod
    return re.sub(rf"{re.escape(cod)}(?:-{re.escape(cod)})+", cod, "".join(bucati))
