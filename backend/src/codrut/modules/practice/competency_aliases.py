from __future__ import annotations

import re
import unicodedata

# Cele 7 competențe canonice din metodologia Andrei Văcaru / Codruț
CANONICAL_COMPETENCIES = [
    "Ascultare activă",
    "Reformulare activă",
    "Verificarea înțelegerii",
    "Exprimarea asertivă a nevoilor și limitelor",
    "Gestionarea propriilor reacții emoționale",
    "Gestionarea reacțiilor celorlalți",
    "Feedback constructiv",
]

# Dicționar complet de aliasuri (variante fără diacritice, engleză, prescurtări)
COMPETENCY_ALIASES: dict[str, str] = {
    # 1. Ascultare activă
    "ascultare activa": "Ascultare activă",
    "ascultare activă": "Ascultare activă",
    "ascultare": "Ascultare activă",
    "active listening": "Ascultare activă",
    "active_listening": "Ascultare activă",
    "active-listening": "Ascultare activă",
    "listening": "Ascultare activă",

    # 2. Reformulare activă
    "reformulare activa": "Reformulare activă",
    "reformulare activă": "Reformulare activă",
    "reformulare": "Reformulare activă",
    "reformularea": "Reformulare activă",
    "active reframing": "Reformulare activă",
    "paraphrasing": "Reformulare activă",
    "reformulation": "Reformulare activă",

    # 3. Verificarea înțelegerii
    "verificarea intelegerii": "Verificarea înțelegerii",
    "verificarea înțelegerii": "Verificarea înțelegerii",
    "verificare intelegere": "Verificarea înțelegerii",
    "verificare înțelegere": "Verificarea înțelegerii",
    "verificarea": "Verificarea înțelegerii",
    "checking understanding": "Verificarea înțelegerii",
    "check understanding": "Verificarea înțelegerii",
    "clarification": "Verificarea înțelegerii",

    # 4. Exprimarea asertivă a nevoilor și limitelor
    "exprimarea asertiva a nevoilor si limitelor": "Exprimarea asertivă a nevoilor și limitelor",
    "exprimarea asertivă a nevoilor și limitelor": "Exprimarea asertivă a nevoilor și limitelor",
    "exprimare asertiva": "Exprimarea asertivă a nevoilor și limitelor",
    "exprimare asertivă": "Exprimarea asertivă a nevoilor și limitelor",
    "asertivitate": "Exprimarea asertivă a nevoilor și limitelor",
    "asertiv": "Exprimarea asertivă a nevoilor și limitelor",
    "assertiveness": "Exprimarea asertivă a nevoilor și limitelor",
    "nevoi si limite": "Exprimarea asertivă a nevoilor și limitelor",
    "nevoi și limite": "Exprimarea asertivă a nevoilor și limitelor",
    "limite": "Exprimarea asertivă a nevoilor și limitelor",

    # 5. Gestionarea propriilor reacții emoționale
    "gestionarea propriilor reactii emotionale": "Gestionarea propriilor reacții emoționale",
    "gestionarea propriilor reacții emoționale": "Gestionarea propriilor reacții emoționale",
    "gestionare emotii proprii": "Gestionarea propriilor reacții emoționale",
    "gestionare emoții proprii": "Gestionarea propriilor reacții emoționale",
    "emotii proprii": "Gestionarea propriilor reacții emoționale",
    "emoții proprii": "Gestionarea propriilor reacții emoționale",
    "reactii emotionale": "Gestionarea propriilor reacții emoționale",
    "reacții emoționale": "Gestionarea propriilor reacții emoționale",
    "autocontrol": "Gestionarea propriilor reacții emoționale",
    "self emotional management": "Gestionarea propriilor reacții emoționale",
    "managing own emotions": "Gestionarea propriilor reacții emoționale",
    "emotional regulation": "Gestionarea propriilor reacții emoționale",

    # 6. Gestionarea reacțiilor celorlalți
    "gestionarea reactiilor celorlalti": "Gestionarea reacțiilor celorlalți",
    "gestionarea reacțiilor celorlalți": "Gestionarea reacțiilor celorlalți",
    "gestionare reactii ceilalti": "Gestionarea reacțiilor celorlalți",
    "gestionare reacții ceilalți": "Gestionarea reacțiilor celorlalți",
    "reactii ceilalti": "Gestionarea reacțiilor celorlalți",
    "reacții ceilalți": "Gestionarea reacțiilor celorlalți",
    "gestionarea interlocutorului": "Gestionarea reacțiilor celorlalți",
    "managing others emotions": "Gestionarea reacțiilor celorlalți",
    "handling emotional reactions": "Gestionarea reacțiilor celorlalți",

    # 7. Feedback constructiv
    "feedback constructiv": "Feedback constructiv",
    "feedback": "Feedback constructiv",
    "constructive feedback": "Feedback constructiv",
    "oferire feedback": "Feedback constructiv",
    "feedback pozitiv si corectiv": "Feedback constructiv",
    "feedback pozitiv și corectiv": "Feedback constructiv",
}


def _strip_accents(text: str) -> str:
    """Elimină diacriticele dintr-un text pentru comparare robustă."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def normalize_competency_name(name: str) -> str:
    """Normalizează șirul: lowercase, fără caractere speciale, fără spații multiple."""
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    return " ".join(cleaned.split())


def match_comp(raw_name: str | None) -> str | None:
    """Potrivește un nume brut de competență la una dintre cele 7 competențe canonice.

    Returnează numele canonic sau None dacă nu este o competență (ex. 'Quiz', 'Test').
    """
    if not raw_name:
        return None

    raw_clean = raw_name.strip()
    if not raw_clean:
        return None

    # Excludere explicită a non-competențelor
    norm_low = raw_clean.lower()
    if norm_low in ("quiz", "cunostinte", "cunoștințe", "test", "test in", "test out", "test-in", "test-out"):
        return None

    # 1. Potrivire exactă cu o competență canonică
    for can in CANONICAL_COMPETENCIES:
        if raw_clean == can:
            return can

    # 2. Potrivire directă în dicționarul de aliasuri
    if norm_low in COMPETENCY_ALIASES:
        return COMPETENCY_ALIASES[norm_low]

    # 3. Potrivire cu text normalizat (fără spații multiple/punctație)
    normalized = normalize_competency_name(raw_clean)
    if normalized in COMPETENCY_ALIASES:
        return COMPETENCY_ALIASES[normalized]

    # 4. Potrivire fără diacritice
    stripped = _strip_accents(normalized)
    for alias, canonical in COMPETENCY_ALIASES.items():
        if _strip_accents(alias) == stripped:
            return canonical

    # 5. Potrivire substring/fuzzy pe competențele canonice
    for can in CANONICAL_COMPETENCIES:
        can_stripped = _strip_accents(can.lower())
        if can_stripped in stripped or stripped in can_stripped:
            return can

    return None
