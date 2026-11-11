"""Reguli fixe pentru replicile actorului — banca de probă, stratul 1 (plicul 215).

Funcții pure, fără rețea și fără model. Fiecare întoarce motivul găsit (un fragment scurt)
sau `None` când replica trece.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

_CUVANT = re.compile(r"[a-zăâîșțşţ]+", re.IGNORECASE)
_PROPOZITIE = re.compile(r"[^.!?…\n]+[.!?…]?")
_DUBLAT = re.compile(r"\b([a-zăâîșțşţ]+)[ \t]+\1\b", re.IGNORECASE)

# litere admise: alfabetul românesc, cu ambele feluri de ș/ț
_LITERE_ROMANESTI = set("abcdefghijklmnopqrstuvwxyzăâîșțşţ")

# cuvinte englezești care n-au ce căuta într-o replică în română (listă scurtă, dinadins)
CUVINTE_ENGLEZESTI = (
    "the", "and", "you", "your", "please", "however", "thanks", "thank", "sorry",
    "because", "actually", "really", "without", "which",
)
_ENGLEZA = re.compile(r"\b(" + "|".join(CUVINTE_ENGLEZESTI) + r")\b", re.IGNORECASE)

_IESIRE = re.compile(
    r"\bCody\b"
    r"|\bAI\b"
    r"|\binteligen[țţt][ăa]\s+artificial[ăa]\b"
    r"|\bmodel(?:ul)?\s+de\s+limbaj\b"
    r"|Scor:\s*\d+(?:[.,]\d+)?\s*/\s*10",
    re.IGNORECASE,
)


def _cuvinte(text: str) -> list[str]:
    return [c.lower() for c in _CUVANT.findall(text or "")]


def _propozitii(text: str) -> list[str]:
    rez = []
    for p in _PROPOZITIE.findall(text or ""):
        curata = " ".join(_cuvinte(p))
        if len(curata.split()) >= 3:
            rez.append(curata)
    return rez


def se_repeta(replici: Sequence[str]) -> str | None:
    """Două replici la rând cu aceeași propoziție sau cu aceleași 4 cuvinte la rând."""
    for inainte, acum in zip(replici, replici[1:], strict=False):
        comune = set(_propozitii(inainte)) & set(_propozitii(acum))
        if comune:
            return sorted(comune)[0]
        a, b = _cuvinte(inainte), _cuvinte(acum)
        patru = {tuple(a[i:i + 4]) for i in range(len(a) - 3)}
        for i in range(len(b) - 3):
            if tuple(b[i:i + 4]) in patru:
                return " ".join(b[i:i + 4])
    return None


def se_balbaie(text: str, finish_reason: str | None = None) -> str | None:
    """Replica tăiată (`MAX_TOKENS`), un cuvânt dublat lipit sau o propoziție spusă de două ori."""
    if finish_reason == "MAX_TOKENS":
        return "MAX_TOKENS"
    # lipit = numai spațiu între ele: „că că” pică, „Da, da.” trece
    m = _DUBLAT.search(text or "")
    if m:
        return m.group(0)
    vazute: set[str] = set()
    for p in _propozitii(text):
        if p in vazute:
            return p
        vazute.add(p)
    return None


def romana_suspecta(text: str) -> str | None:
    """Litere din afara alfabetului românesc sau cuvinte englezești din lista scurtă."""
    for litera in text or "":
        if litera.isalpha() and litera.lower() not in _LITERE_ROMANESTI:
            return litera
    m = _ENGLEZA.search(text or "")
    return m.group(0) if m else None


def iese_din_scenariu(text: str) -> str | None:
    """Personajul vorbește ca un program: „Cody”, „AI”, „model de limbaj”, nota „Scor: N/10”.

    „AI” și „Cody” numai ca cuvânt întreg și cu majuscule la „AI” („ai”, „mai”, „training”
    trec). „Evaluare” nu se prinde: apare firesc în scenariile despre evaluarea anuală.
    """
    for m in _IESIRE.finditer(text or ""):
        if m.group(0).lower() == "ai" and m.group(0) != "AI":
            continue
        return m.group(0)
    return None
