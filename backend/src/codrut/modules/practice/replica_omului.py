"""Replica așa cum o vede omul — plicul 249.

Hotărârea lui Andrei [esti-ai-reparatie] (21 nov, 19:32), după proba lui pe live:
(a) codul scoate indicațiile de regie de felul „*Revine în rol:*” (rânduri întregi, nimic altceva);
(b) la replica la care actorul a răspuns cu fraza aprobată la 228, partea de notă nu se arată,
    deci recunoașterea apare o singură dată;
(c) banca judecă replica întreagă, construită de ACESTE funcții, nu de o copie a lor.

Funcții pure: fără bază de date, fără apeluri. Le folosesc serviciul și banca.
"""

from __future__ import annotations

import re
import unicodedata

# Fraza din paragraful 228 al `actor.md` (textul dintre «»), scrisă aici de un script care a
# citit-o din fișierul de pe baza bd146a2. Testul verifică că e tot cea din `ACTOR_PROMPT`.
FRAZA_RECUNOASTERE = "Sunt Cody, partenerul tău de exersare — un AI."

# ---------------------------------------------------------------- (a) regia

_VERBE_REVENIRE = r"revine|revin|revenind|revenire|reintra|reintru|reintrand"
_VERBE_IESIRE = r"iese|ies|iesind|iesire|intra|intru|intrand"
_ROL = r"rol|rolul|personaj|personajul"
# corecția 1 a controlorului: „scenă” numai după revine/reintră („*Iese din scenă.*” e regie de
# teatru a personajului, nu ieșirea lui Cody din rol)
_INDICATIA = (
    rf"(?:(?:{_VERBE_REVENIRE})\s+(?:in|din)\s+(?:{_ROL}|scena)"
    rf"|(?:{_VERBE_IESIRE})\s+(?:in|din)\s+(?:{_ROL}))"
)
_DESCHIDE = r"[\*_\(\[]*"
_INCHIDE = r"[\*_\)\]]*"
_RAND_DE_REGIE = re.compile(
    rf"^(?P<d>{_DESCHIDE})\s*{_INDICATIA}\s*[:.]?\s*(?P<i>{_INCHIDE})\s*[:.]?$"
)
# în bancă, oriunde în text: cu învelitoare înainte, sau urmată de „:”
INDICATIE_ORIUNDE = re.compile(
    rf"(?:[\*_\(\[]\s*{_INDICATIA}\b|\b{_INDICATIA}\s*:|\(\s*{_INDICATIA}\s*\))"
)


def fara_diacritice(text: str) -> str:
    """Litere mici, fără diacritice (ă/â→a, î→i, ș/ş→s, ț/ţ→t), ca regia să se prindă oricum."""
    descompus = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in descompus if not unicodedata.combining(c))


def _e_rand_de_regie(rand: str) -> bool:
    curat = rand.strip()
    m = _RAND_DE_REGIE.match(fara_diacritice(curat))
    if not m:
        return False
    # un rând fără semne („Revin în rol.”) poate fi vorba personajului — rămâne
    return bool(m.group("d") or m.group("i")) or curat.endswith(":")


def fara_regie(text: str | None) -> str:
    """Textul fără rândurile întregi care sunt o indicație de ieșire/intrare în rol.

    Fără niciun astfel de rând, textul se întoarce octet cu octet. Cu unul scos: `\\r\\n` → `\\n`,
    rândurile goale strânse la unul, capetele tăiate. „***” nu se atinge aici
    (`_fara_despartitor`).
    """
    if not text:
        return text or ""
    randuri = text.replace("\r\n", "\n").split("\n")
    pastrate = [r for r in randuri if not _e_rand_de_regie(r)]
    if len(pastrate) == len(randuri):
        return text
    return re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", "\n".join(pastrate)).strip()


def randuri_de_regie(text: str | None) -> int:
    """Câte rânduri scoate `fara_regie` (pentru jurnalul băncii)."""
    return sum(1 for r in (text or "").replace("\r\n", "\n").split("\n") if _e_rand_de_regie(r))


# ---------------------------------------------------------------- (b) recunoașterea


def _tipar_frazei() -> re.Pattern[str]:
    """Fraza, cu spații oricâte (și ` `), cu „-”/„–” în loc de „—”, între ghilimele sau nu,
    cu sau fără punctul de la final (corecția 2)."""
    fara_punct = FRAZA_RECUNOASTERE.rstrip(".")
    bucati = []
    for cuvant in fara_punct.split(" "):
        bucati.append(r"[—–-]" if cuvant == "—" else re.escape(cuvant))
    return re.compile(
        r"[«„\"“]?" + r"[\s ]+".join(bucati) + r"\.?[»”\"“]?"
    )


_FRAZA = _tipar_frazei()


def contine_recunoasterea(text: str | None) -> bool:
    """Fraza aprobată la 228 e în text. Altă formulare („Da, sunt un AI”) nu contează aici —
    o prinde banca."""
    return bool(text) and _FRAZA.search(text) is not None


def fara_recunoastere(text: str | None) -> str:
    """Textul fără fraza de recunoaștere (pentru istoricul profesorului)."""
    rest = _FRAZA.sub("", text or "")
    return re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", rest).strip()


# corecția 2: recunoașterea sare nota numai dacă omul chiar a întrebat de AI
_TERMENI_OM = re.compile(
    r"\bAI\b|\b(?i:robo[țţt]\w*|bo[țţt]i?|bot(?:ul|ii)?|om|ma[șşs]in[ăa]\w*"
    r"|inteligen[țţt][ăa]\s+artificial[ăa])\b"
)


def intreaba_de_ai(replica_om: str | None) -> bool:
    """Replica omului vorbește despre AI / robot / bot / om / mașină / inteligență artificială."""
    return bool(replica_om) and _TERMENI_OM.search(replica_om) is not None


def sare_nota(text_personaj: str | None, replica_om: str | None) -> bool:
    """La replica asta nu se arată nota: actorul a spus fraza, iar omul a întrebat de AI."""
    return contine_recunoasterea(text_personaj) and intreaba_de_ai(replica_om)


def replica_omului(
    text_actor: str,
    text_profesor: str | None,
    *,
    doua_apeluri: bool,
    replica_om: str | None = None,
) -> tuple[str, bool]:
    """`(textul pe care îl vede omul, se_noteaza)`, exact ca serviciul.

    La două apeluri: personajul fără regie și fără „***”; dacă sare nota → numai personajul;
    altfel personaj + „***” + profesor (sau textul de lipsă). La un apel: răspunsul fără regie.
    `replica_om=None` = nu se știe ce a scris omul: se ia numai fraza (cum cerea plicul înainte
    de corecția 2); serviciul și banca o dau întotdeauna.
    """
    # importul aici: `service.py` importă modulul ăsta, deci nu se poate invers la încărcare
    from codrut.modules.practice.service import EVALUARE_NELIVRATA, _fara_despartitor

    if not doua_apeluri:
        return fara_regie(text_actor), True
    personaj = _fara_despartitor(fara_regie(text_actor))
    a_intrebat = True if replica_om is None else intreaba_de_ai(replica_om)
    if contine_recunoasterea(personaj) and a_intrebat:
        return personaj, False
    evaluarea = (text_profesor or "").strip() or EVALUARE_NELIVRATA
    return f"{personaj}\n\n***\n\n{evaluarea}", True
