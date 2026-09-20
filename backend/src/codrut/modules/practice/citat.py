"""Citatul din cuvintele omului: il pune aplicatia, nu modelul — plicurile 106, 108, 109.

De ce exista fisierul asta. Evaluarea lui Cody trebuie sa se sprijine pe cuvintele omului,
citate. Cerinta a stat trei zile in `evaluare.md`, ca text pentru model, si modelul ieftin o
respecta doar 3 sesiuni din 10: copia gresit, taia, sau povestea in loc sa citeze (plicul 104).

Aici se face altfel: replica omului intra in prompt numerotata pe propozitii, modelul scrie
NUMARUL propozitiei pe care o judeca, iar propozitia o pune aplicatia, cuvant cu cuvant. Textul
citat nu mai trece prin model, deci nu mai poate fi stricat de el. Masurat: 3/10 -> 9/10
(plicul 107).

Ce nu se ascunde: numarul lipsa sau numarul inexistent se intorc ca motiv si se numara.
"""

from __future__ import annotations

import re

MARCAJ = re.compile(r"\[(\d{1,2})\]")
SUB_9 = re.compile(r"Scor:\s*\**\s*(\d+(?:[.,]\d+)?)\s*\**\s*/\s*10")


def _cuvinte(text: str) -> list[str]:
    return re.findall(r"[\wăâîșțşţ]+", (text or "").lower())


def propozitii(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if p.strip()]


def propozitii_numerotate(text: str) -> str:
    """Blocul care intra in prompt dupa replica omului.

    Gol cand replica are o singura propozitie: nu e nimic de ales, iar aplicatia o pune singura.
    Masurat pe replicile adevarate ale oamenilor (plicul 106): 121 din 230 au o singura
    propozitie, deci la mai mult de jumatate modelul nici nu e intrebat.
    """
    lista = propozitii(text)
    if len(lista) <= 1:
        return ""
    randuri = "\n".join(f"[{i}] {p}" for i, p in enumerate(lista, 1))
    return f"\n\nCe a spus omul, pe propoziții:\n{randuri}"


def pune_citatul(raspuns: str, replica_omului: str) -> tuple[str, str]:
    """Intoarce (textul pentru om, motivul). Motiv gol = totul in regula."""
    lista = propozitii(replica_omului)
    nota = SUB_9.search(raspuns or "")
    sub_noua = bool(nota) and float(nota.group(1).replace(",", ".")) < 9
    gasite = MARCAJ.findall(raspuns or "")

    if not gasite:
        if sub_noua and len(lista) == 1:
            return f"«{lista[0]}» — {raspuns.lstrip()}", ""
        return raspuns, "fara numar" if sub_noua else ""

    def inlocuieste(m: re.Match) -> str:
        i = int(m.group(1))
        return f"«{lista[i - 1]}»" if 1 <= i <= len(lista) else m.group(0)

    nou = MARCAJ.sub(inlocuieste, raspuns)
    rele = [n for n in gasite if not 1 <= int(n) <= len(lista)]
    return nou, f"numar inexistent: {', '.join(rele)}" if rele else ""


# --- repetarea o sterge aplicatia, nu i-o mai cerem modelului — plicul 108 -------------------

# Dupa «citatul pus de aplicatie» modelul repeta uneori aceleasi cuvinte, cu ghilimelele lui,
# adesea intr-o paranteza: «X» (Replica ta: „X") — …  Se sterge NUMAI repetarea asta.
_REPETARE = re.compile(
    r"\s*(?:\(\s*)?(?:[Rr]eplica ta\s*:\s*)?[„\"]([^„”\"]{4,400})[”\"]\s*(?:\))?"
)


def sterge_repetarea(text: str, puse: list[str] | None = None) -> tuple[str, list[str]]:
    """Scoate citatele modelului care repeta EXACT ce tocmai a pus aplicatia.

    Nu se atinge nimic altceva: nici replicile personajului din scena (care sunt tot intre
    ghilimele si repeta adesea vorbele omului), nici un citat cu ALTE cuvinte, nici judecata lui
    Cody. Masurat la plicul 108, in fereastra pe care stergerea o atinge: din 27 de repetari,
    22 repetau exact citatul pus — celelalte 5 aveau alte cuvinte, si RAMAN. Una dintre ele era
    chiar un al doilea citat adevarat din vorbele omului.

    Mai bine o repetare ramasa decat o taietura intr-un text care nu era repetare.
    """
    if puse is None:
        puse = re.findall(r"«([^»]{3,400})»", text or "")
    normal = {" ".join(_cuvinte(x)) for x in puse}
    if not normal:
        return text, []
    sterse: list[str] = []

    def poate(m: re.Match) -> str:
        continut = " ".join(_cuvinte(m.group(1)))
        if continut and continut in normal:
            sterse.append(m.group(1))
            return " "
        return m.group(0)

    # Se cauta numai IMEDIAT dupa citatul pus. Ferestrele NU se suprapun: daca doua citate stau
    # aproape unul de altul, a doua fereastra incepe de unde s-a terminat prima — altfel textul
    # dintre ele s-ar scrie de doua ori. Asa a fost prima oara, si a stricat 10 replici din 37
    # la plicul 108; niciuna din cele sapte porti n-a vazut-o, numai citirea cu ochiul. De aia
    # exista acum si poarta 8 (`text_dublat`).
    rezultat: list[str] = []
    pozitie = 0
    for citat in re.finditer(r"«[^»]{3,400}»", text or ""):
        if citat.start() < pozitie:
            continue  # citatul asta a intrat deja in fereastra dinainte
        rezultat.append(text[pozitie:citat.end()])
        urmatorul = text.find("«", citat.end())
        capat = min(citat.end() + 200, len(text) if urmatorul == -1 else urmatorul)
        rezultat.append(_REPETARE.sub(poate, text[citat.end():capat], count=1))
        pozitie = capat
    rezultat.append(text[pozitie:])
    return "".join(rezultat), sterse


def repetare_ramasa(text: str) -> int:
    """Cate citate ale modelului repeta INCA, exact, un citat pus de aplicatie."""
    _, sterse = sterge_repetarea(text)
    return len(sterse)


# Pragul e MASURAT, nu ales: pe 1.348 de replici curate (14 rulari salvate) si pe cele 70 ale
# rularii stricate de la plicul 108. La 20 de caractere: zero alarme false, 9 din cele 10 replici
# stricate prinse. Sub 8 caractere apar alarme false (11), iar peste 40 — cifra din plicul 109 —
# scad si prinderile (8 din 10). A zecea replica stricata are o bucata de 6 caractere („ — Ai ");
# niciun prag care o prinde nu e curat, deci poarta 8 NU o vede. Scris ca atare.
PRAG_DUBLARE = 20


def text_dublat(text: str, minim: int = PRAG_DUBLARE) -> str | None:
    """Poarta 8: o bucata de text scrisa de doua ori, a doua oara imediat dupa prima.

    Semnatura defectului care a stricat 10 replici din 37 la plicul 108 si pe care nicio poarta
    nu l-a vazut: ele cauta nota, citatul, numele, metodele — niciuna nu citeste textul ca text.

    Se cere ca a doua copie sa inceapa EXACT unde se termina prima. O repetare la distanta nu e
    un defect: un citat pus de aplicatie si replica personajului din scena repeta des aceleasi
    cuvinte, la cateva randuri distanta, si asta e in regula.

    Intoarce bucata gasita, sau None.
    """
    t = text or ""
    cheie_lungime = min(25, minim)
    for i in range(len(t) - 2 * minim + 1):
        cheie = t[i:i + cheie_lungime]
        k = t.find(cheie, i + minim)
        while k != -1 and k - i <= 400:
            if t[k:k + (k - i)] == t[i:k]:
                return t[i:k]
            k = t.find(cheie, k + 1)
    return None
