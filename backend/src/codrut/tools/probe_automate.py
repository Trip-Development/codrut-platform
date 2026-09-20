"""Unealta de probe automate — plicul 82. O poarta de regres, NU o dovada de calitate.

Ruleaza sesiuni scriptate (`probe_scenarii.py`) cu promptul si furnizorul aplicatiei, IN
MEMORIE: nu deschide nicio conexiune la baza de date si nu salveaza nimic. Verifica mecanic
sapte porti si numara 429-urile, erorile, durata si textul care intra si iese.

Se cheama din containerul backendului de proba; o comanda locala o porneste si tine socoteala
(`SPEC-CODY/UNELTE/probe-automate.py`). Scrie pe iesire UN RAND JSON pe sesiune terminata,
imediat, si acelasi rand in jurnalul din container (`--jurnal`).

Daca cine citeste dispare (laptop inchis, legatura cazuta), rularea NU se opreste: merge mai
departe pe server, in limita plafoanelor, si scrie in jurnal. Comanda de pe calculator strange
din jurnal, la urmatoarea pornire, tot ce s-a terminat intre timp. Masurat la plicul 82: cand
legatura se taie, iesirea procesului din container nu se inchide, deci procesul nu afla singur.

    python -m codrut.tools.probe_automate --sesiuni roleplay:1,knowledge:1,coaching:1 \
        --jurnal /tmp/probe_automate/X.jsonl \
        [--model M] [--destinatie D] [--plafon-apeluri 260] [--plafon-minute 90]

Regulile de rulare: `SPEC-CODY/UNELTE/REGULI-PROBE-AUTOMATE.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx

from codrut.contracts.generation import GenerationMessage, GenerationPurpose, GenerationRequest
from codrut.core.config import get_settings
from codrut.modules.practice.generation_provider import build_generation_provider
from codrut.modules.practice.prompts import (
    CODY_PROMPT_VERSION,
    NUME_PERSONAJ,
    _numele_personajului,
    get_prompts_pe_meserii,
    get_system_prompt_for_kind,
)
from codrut.modules.practice.service import DESCHIDE_SESIUNEA, SCENA_CELUILALT
from codrut.tools.probe_metode_scoase import METODE_INTERZISE, METODE_NUMARATE
from codrut.tools.probe_scenarii import COMPETENTE_PROIECT, PARTICIPANT, SCENARII

MODURI = ("roleplay", "knowledge", "coaching")
PRENUME = PARTICIPANT.split()[0]

# ---------------------------------------------------------------- portile, ca functii pure

SCOR = re.compile(r"Scor:\s*\**\s*(\d+(?:[.,]\d+)?)\s*\**\s*/\s*10")
GHILIMELE = re.compile(r"[«„\"“]([^«»„”\"“]{6,400})[»”\"“]")
REPLICA_MODEL = re.compile(
    r"(ai fi putut (spune|zice|formula|încerca|întreba)|ai putea (spune|zice|formula)"
    r"|puteai (spune|zice)|(o )?variant[ăa] mai (bun[ăa]|clar[ăa])|ar fi sunat"
    r"|mai bine ar fi fost s[ăa] spui|încearc[ăa] (așa|ceva de genul)"
    # unele modele o scriu ca titlu, nu ca fraza: „**Replica model:**" — plicul 102
    r"|replic[ăa] model)"
    # replica vine des pe randul urmator („Ai fi putut spune:\n„...”") — plicul 82
    r"[\s\S]{0,200}?[«„\"“]",
    re.IGNORECASE,
)
NUME_INTERZISE = re.compile(
    r"\[\s*nume\s*\]|\buser\b|\bparticipant\b|\butilizator(ul)?\b", re.IGNORECASE
)
METODE = re.compile(r"\b(" + "|".join(map(re.escape, METODE_INTERZISE)) + r")\b", re.IGNORECASE)
# se numara, nu se pedepsesc — hotararea lui Andrei din 19 septembrie (probe_metode_scoase.py)
NUMARATE = re.compile(
    r"\b(" + "|".join(map(re.escape, METODE_NUMARATE)) + r")\b", re.IGNORECASE
)


def scorul(text: str) -> float | None:
    m = SCOR.search(text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def _cuvinte(text: str) -> list[str]:
    return re.findall(r"[\wăâîșțşţ]+", (text or "").lower())


def are_citat(evaluare: str, replica_omului: str) -> bool:
    """Un segment intre ghilimele are cel putin 3 cuvinte la rand din replica omului."""
    om = _cuvinte(replica_omului)
    if len(om) < 3:
        return any(" ".join(om) in " ".join(_cuvinte(s)) for s in GHILIMELE.findall(evaluare))
    trigrame = {tuple(om[i:i + 3]) for i in range(len(om) - 2)}
    for segment in GHILIMELE.findall(evaluare or ""):
        c = _cuvinte(segment)
        if any(tuple(c[i:i + 3]) in trigrame for i in range(len(c) - 2)):
            return True
    return False


def are_replica_model(text: str) -> bool:
    return bool(REPLICA_MODEL.search(text or ""))


def personajul(text: str) -> str | None:
    """Primul nume din lista personajelor care apare in text (numele intreg sau de familie).

    Prenumele singur nu ajunge: prenumele omului apare si el in text, cand Cody i se adreseaza.
    """
    gasite = []
    for nume in NUME_PERSONAJ:
        familie = nume.split()[-1]
        m = re.search(rf"\b({re.escape(nume)}|{re.escape(familie)})\b", text or "")
        if m:
            gasite.append((m.start(), nume))
    return min(gasite)[1] if gasite else None


# Care poarta judeca ce apel, dupa despartire — plicul 112. Fara atribuire, depanarea se invarte
# in gol: vezi „poarta 2 a picat" si nu stii pe cine sa intrebi.
APELUL_VINOVAT = {
    "1": "amandoua", "2": "evaluator", "3": "evaluator", "4": "actor",
    "5": "amandoua", "6": "evaluator", "7": "amandoua", "9": "evaluator",
    "10": "evaluator", "11": "actor",
}


# ---------------------------------------------------------------- replica de scena

# Cine vorbeste in scena — folosit de poarta 4 (stransa) si de poarta 9 — plicul 115.
#
# Tiparul de azi al modelului, luat din texte adevarate, nu din inchipuire:
#   **Dan:** „Pai cum ce anume?…"
#   *Diana Ilie:*  Cum adica ce m-a deranjat?…
#   *Victor (se uita lung la tine, isi strange mapa la piept):*  „Nu ma deranjeaza nimic…"
# Deci: semne de ingrosare sau italice oriunde in jur, indicatie de scena in paranteze dupa nume,
# vorbirea pe randul urmator, si NUME DIN AFARA LISTEI de personaje.
#
# Ce n-are voie sa prinda, ca sa nu devina o alarma care suna mereu: titlurile pe care
# evaluatorul le scrie normal („Evaluare Cody:", „Scor:", „Replica model:", „Ies din rol:"),
# replica model („Ai fi putut spune: …") si citatul din vorbele omului („Mihai, ai spus: …" —
# acolo numele e urmat de virgula, nu de doua puncte).
_TITLURI = {
    "evaluare", "evaluarea", "evaluator", "scor", "scorul", "nota", "notă", "punctaj",
    "feedback", "replica", "replică", "observatie", "observație", "concluzie", "analiza",
    "analiză", "verdict", "recomandare", "sugestie", "exemplu", "alternativa", "alternativă",
    "varianta", "variantă", "context", "obiectiv", "situatie", "situație", "sfat", "atentie",
    "atenție", "important", "rezumat", "bilant", "bilanț", "motiv", "impact", "ies", "ieși",
    "iesi", "de", "ce", "cum", "ai", "pas", "total", "bine", "rau", "rău", "corect",
    # „**Cody:**" nu e un personaj: e evaluatorul care isi spune numele inaintea judecatii.
    # Masurat pe referinta cu un apel: 8 din cele 20 de evaluari incep asa, si toate sunt curate.
    "cody",
    # Titlurile SETUP-ului: „SETUP:", „Context:", „Contextul:", „Obiectiv:". Nu sunt personaje;
    # sunt rubricile cu care incepe scena. Masurat: fara ele, poarta 4 pica la pasul 2 in toate
    # cele 20 de sesiuni salvate, pe nimic.
    "setup", "contextul", "obiectivul", "scena", "scenă", "scenariu", "scenariul", "rol",
    "rolul", "situatia", "situația", "tu", "el", "ea", "personaj", "personajul",
    "gresit", "greșit", "asertivitate", "empatie", "claritate", "final", "concret", "acum",
}

_REPLICA_DE_SCENA = re.compile(
    r"(?m)^[ \t]*[*_]{0,2}\s*"
    r"(?P<nume>[A-ZĂÂÎȘȚ][\wăâîșțĂÂÎȘȚ.-]*(?:\s+[A-ZĂÂÎȘȚ][\wăâîșțĂÂÎȘȚ.-]*)?)"
    r"(?:\s*\([^)\n]{0,200}\))?"
    r"\s*[*_]{0,2}\s*:\s*[*_]{0,2}\s*(?:\n\s*)?[„\"“«\-—*\w]"
)


def replicile_de_scena(text: str) -> list[str]:
    """Numele celor care vorbesc in text, in ordine. Gol = nimeni nu joaca."""
    gasite = []
    for m in _REPLICA_DE_SCENA.finditer(text or ""):
        nume = m.group("nume").strip()
        if nume.split()[0].lower().strip(".:") in _TITLURI:
            continue
        gasite.append(nume)
    return gasite


def evaluatorul_joaca(text: str) -> str | None:
    """Poarta 9: evaluatorul nu vorbeste in numele niciunui personaj — plicul 115.

    Prima varianta (plicul 112) cerea un nume DIN LISTA, urmat imediat de ghilimele. A trecut
    10/10 peste 70 de replici in care evaluatorul chiar juca. Un instrument verificat pe un caz
    pe care nu-l intalneste niciodata nu e o masura, e o decoratie.
    """
    gasite = replicile_de_scena(text)
    return gasite[0] if gasite else None


def _acelasi_personaj(vorbitor: str, asteptat: str) -> bool:
    """Acelasi om, scris scurt sau intreg: „Diana Ilie", „Diana", „Ilie" — plicul 115.

    Prenumele OMULUI nu trece niciodata: asta e chiar ce pazea poarta 4 de la inceput.
    """
    v = {x.strip(".,:").lower() for x in vorbitor.split()}
    a = {x.strip(".,:").lower() for x in (asteptat or "").split()}
    if PRENUME.lower() in v:
        return False
    return bool(v & a)


# Numele pe care modelul le inventeaza cand n-are scena — masurate la plicul 117.
#
# Nu sunt in `NUME_PERSONAJ`: le scoate din el insusi. „Radu" a aparut in 23 de replici ale
# evaluatorului si intr-una singura a actorului, in aceeasi rulare.
NUME_INVENTATE = ("Radu", "Victor", "Dan", "Laura")


def alt_personaj(text: str, asteptat: str) -> str | None:
    """Poarta 10: evaluatorul nu vorbeste despre alt personaj decat cel al sedintei — plicul 118.

    Defectul de la plicul 117 a trecut pe sub toate cele opt porti, fiindca nu e o replica de
    scena — e text curgator, corect, despre altcineva. Poarta 9 cauta `Nume: „vorbire"`; asta
    cauta numele, oriunde in text.

    Ce NU prinde: prenumele omului si personajul sedintei, cu toate felurile de a-l scrie.
    """
    t = text or ""
    candidati = [n for n in NUME_PERSONAJ] + [n for n in NUME_INVENTATE]
    for nume in candidati:
        if _acelasi_personaj(nume, asteptat):
            continue
        for bucata in {nume, *nume.split()}:
            if bucata.lower() == PRENUME.lower() or len(bucata) < 4:
                continue
            if re.search(rf"\b{re.escape(bucata)}\b", t):
                return nume
    return None


# Poarta 11: actorul nu iese din rol — plicul 119.
#
# Promptul lui ii spunea, in primul rand, „esti simultan actor si Cody-ca-profesor" — propozitie
# ramasa din lumea dinainte de despartire. Facea exact ce i se cerea: la plicul 118 a iesit din
# rol la 10 pasi din 40, iar la `roleplay:5` la TOTI cei patru pasi de joc. Omul primea acolo o
# lectie de la actor SI o evaluare de la evaluator, si nicio scena curata.
#
# Prinde si `***` in iesirea actorului: acolo nu e al lui, e despartitorul cu care aplicatia
# lipeste cele doua apeluri. Daca il scrie el, si-a facut singur doua blocuri.
IESIRE_DIN_ROL = re.compile(
    r"(ies(?:im|i)?\s+(?:o |doua |două )?"
    r"(?:clip[ăa]|secund[ăa]|secunde)?\s*din\s+(?:rol|scen[ăa]|rolul)"
    r"|ie[șs]ire\s+din\s+rol"
    r"|pauz[ăa]\s+de\s+(?:rol|joc|scen[ăa])"
    r"|intervin\s+ca\s+(?:trainer|coach|cody)"
    r"|moment\s+de\s+coaching"
    r"|r[ăa]m[âa]n\s+(?:pu[țt]in\s+)?[îi]n\s+coaching"
    r"|\*\*\*)",
    re.IGNORECASE,
)


def actorul_iese_din_rol(text: str) -> str | None:
    m = IESIRE_DIN_ROL.search(text or "")
    return m.group(0).strip() if m else None


def portile(mod: str, pasi: list[dict], nr_rulare: int) -> dict[str, dict]:
    """Portile unei sesiuni. Fiecare: aplicabila, instante, trecute, picate."""
    def poarta(aplicabila=True):
        return {"aplicabila": aplicabila, "instante": 0, "trecute": 0, "picate": []}

    p = {str(i): poarta() for i in (1, 2, 3, 4, 5, 6, 7, 9, 10, 11)}
    p["7"]["numarate"] = {m: 0 for m in METODE_NUMARATE}
    # Poarta 9 se aplica numai cand evaluatorul a raspuns separat — adica la doua apeluri.
    p["9"]["aplicabila"] = any(x.get("text_evaluator") for x in pasi)
    p["10"]["aplicabila"] = p["9"]["aplicabila"] and mod == "roleplay"
    # poarta 11 se aplica numai cand actorul a raspuns separat (doua apeluri)
    p["11"]["aplicabila"] = any(x.get("text_actor") for x in pasi) and mod == "roleplay"
    for i in ("2", "3", "4", "6"):
        p[i]["aplicabila"] = mod == "roleplay"

    def bifa(nr, ok, detaliu):
        p[nr]["instante"] += 1
        p[nr]["trecute"] += bool(ok)
        if not ok:
            p[nr]["picate"].append(detaliu)

    for pas in pasi:
        r, fel, nr_pas = pas["raspuns"], pas["fel"], pas["pas"]
        bifa("1", bool(r.strip()) and not pas["eroare"], f"pas {nr_pas}: {pas['eroare'] or 'gol'}")
        if not r.strip():
            continue
        if pas.get("text_actor") and mod == "roleplay" and fel == "joc":
            iese = actorul_iese_din_rol(pas["text_actor"])
            bifa("11", iese is None, f"pas {nr_pas}: actorul iese din rol {iese!r}")
        if pas.get("text_evaluator"):
            joaca = evaluatorul_joaca(pas["text_evaluator"])
            bifa("9", joaca is None, f"pas {nr_pas}: evaluatorul joaca {joaca!r}")
            if mod == "roleplay":
                strain = alt_personaj(
                    pas["text_evaluator"], _numele_personajului(nr_rulare - 1, PRENUME)
                )
                bifa("10", strain is None, f"pas {nr_pas}: evaluatorul vorbeste despre {strain!r}")
        metode = sorted({m.upper() for m in METODE.findall(r)})
        bifa("7", not metode, f"pas {nr_pas}: {', '.join(metode)}")
        for m in NUMARATE.findall(r):
            p["7"]["numarate"][m.upper()] += 1
        interzise = sorted({m.group(0) for m in NUME_INTERZISE.finditer(r)})
        bifa("5", not interzise, f"pas {nr_pas}: {', '.join(interzise)}")
        if mod == "roleplay":
            sc = scorul(r)
            if fel == "joc":
                bifa("2", sc is not None, f"pas {nr_pas}: fara punctaj")
                if sc is not None and sc < 9:
                    unde = f"pas {nr_pas}: scor {sc:g}"
                    bifa("3", are_replica_model(r), f"{unde}, fara replica model")
                    bifa("6", are_citat(r, pas["om"] or ""), f"{unde}, fara citat")
            elif fel in ("salut", "pornire", "despartire"):
                bifa("2", sc is None, f"pas {nr_pas} ({fel}): punctat {sc:g}" if sc else "")
    salut = next((x for x in pasi if x["fel"] == "salut"), None)
    if salut and salut["raspuns"].strip():
        bifa("5", re.search(rf"\b{PRENUME}\b", salut["raspuns"]) is not None,
             "salutul nu contine numele omului")
    if mod == "roleplay":
        # Poarta 4, STRANSA — plicul 115.
        #
        # Pana azi lipea toti pasii sedintei si ii ajungea O SINGURA aparitie a numelui bun.
        # La `roleplay:8`, in masuratoarea din 20 septembrie, actorul a plecat de la Diana Ilie,
        # a alunecat la „Radu" doi pasi, s-a intors — si poarta a trecut. Acum se uita la
        # FIECARE pas in parte: cine vorbeste acolo trebuie sa fie personajul dat de aplicatie.
        asteptat = _numele_personajului(nr_rulare - 1, PRENUME)
        p["4"]["asteptat"] = asteptat
        vazuti: list[str] = []
        for pas in pasi:
            if pas["fel"] not in ("pornire", "joc") or not pas["raspuns"].strip():
                continue
            # Partea ACTORULUI. La doua apeluri e salvata separat. La un singur apel se ia
            # TOT raspunsul — plicul 117, partea A.
            #
            # Pana azi se lua `raspuns.split("***")[0]`, si asta taia tot ce urma dupa primul
            # despartitor: la un apel poarta ramanea cu UN SINGUR pas pe sedinta, in loc de cinci.
            # Asa s-a scris in raportul 115 „un apel 10/10, doua apeluri 2/10" — adevarat ca
            # rezultat, dar pus alaturi un pas masurat intr-o parte si cinci in cealalta.
            #
            # De ce tot textul, si nu o taiere mai destepta: la un apel exista un singur autor,
            # deci orice replica de scena de acolo e a lui. Masurat pe fisierul salvat
            # (`2026-09-20-fraza-andrei`): 44 de instante, toate trecute — nicio alarma falsa
            # din partea de evaluare.
            text = pas.get("text_actor") or pas["raspuns"]
            vorbitori = replicile_de_scena(text)
            if not vorbitori:
                continue
            vazuti.extend(vorbitori)
            straini = sorted({v for v in vorbitori if not _acelasi_personaj(v, asteptat)})
            bifa("4", not straini,
                 f"pas {pas['pas']}: joaca {', '.join(straini)}, nu {asteptat}")
        p["4"]["personaj"] = vazuti[0] if vazuti else None
    return p


# ---------------------------------------------------------------- rularea


def reevalueaza(cale: Path) -> int:
    """Recalculeaza portile pe textele salvate, cu regulile de acum. Niciun apel la model.

    Originalul ramane langa, cu sufixul `.inainte-de-reevaluare`; se scrie si ce s-a schimbat.
    """
    linii = cale.read_text(encoding="utf-8").splitlines()
    copie = cale.with_suffix(".inainte-de-reevaluare.jsonl")
    if not copie.exists():
        copie.write_text("\n".join(linii) + "\n", encoding="utf-8")
    noi = []
    for linie in linii:
        d = json.loads(linie)
        if d.get("tip") == "sesiune":
            vechi = {k: v["trecute"] for k, v in d["porti"].items()}
            d["porti"] = portile(d["mod"], d["pasi"], d["rulare"])
            dif = {k: (vechi[k], v["trecute"]) for k, v in d["porti"].items()
                   if vechi.get(k) != v["trecute"]}
            if dif:
                print(f"{d['id']}: poarta -> (trecute inainte, trecute acum) {dif}")
        noi.append(json.dumps(d, ensure_ascii=False))
    cale.write_text("\n".join(noi) + "\n", encoding="utf-8")
    return 0


class Numarator:
    """Numara fiecare raspuns HTTP de la Vertex, inclusiv reincercarile facute de aplicatie."""

    def __init__(self) -> None:
        self.coduri: Counter[int] = Counter()

    async def __call__(self, raspuns: httpx.Response) -> None:
        self.coduri[raspuns.status_code] += 1


async def o_sesiune(furnizor, setari, numarator, mod: str, nr: int, doua: bool = False) -> dict:
    scenariu = SCENARII[mod]
    profil = {
        "conduce_oameni": True,
        "functie": None,
        "nr_roleplay_anterioare": nr - 1,
        "nr_sesiuni_anterioare": (nr - 1) * len(MODURI) + MODURI.index(mod),
    }
    # Doua istorice, cand apelurile sunt doua — plicul 117. Exact ca aplicatia: replicile omului
    # intra la amandoua, replicile lui Cody numai cu bucata meseriei respective.
    istoric: list[GenerationMessage] = []
    istoric_evaluator: list[GenerationMessage] = []
    scena_in_asteptare = ""
    pasi = []
    inceput = time.monotonic()
    coduri_inainte = Counter(numarator.coduri)
    for i, pas in enumerate(scenariu, start=1):
        # Exact ca aplicatia (service.py): salutul la istoric 0, cu instructiunea de deschidere,
        # care nu se pastreaza; apoi istoricul are replica lui Cody + replica noua a omului.
        lungime = 0 if pas.text is None else len(istoric) + 1
        mesaje = (
            (GenerationMessage(role="user", text=DESCHIDE_SESIUNEA),)
            if pas.text is None
            else (*istoric, GenerationMessage(role="user", text=pas.text))
        )
        # Istoricul evaluatorului — plicul 117. Aceleasi replici ale omului, dar din replicile
        # lui Cody numai bucata lui.
        # Exact ca aplicatia (plicul 118): scena ajunge la evaluator INAINTEA replicii omului,
        # marcata ca vorba celuilalt din scena — nu ca replica lui.
        text_pentru_evaluator = pas.text
        if pas.text is not None and scena_in_asteptare:
            text_pentru_evaluator = f"{SCENA_CELUILALT}\n{scena_in_asteptare}\n\n{pas.text}"
        mesaje_evaluator = (
            (GenerationMessage(role="user", text=DESCHIDE_SESIUNEA),)
            if pas.text is None
            else (*istoric_evaluator, GenerationMessage(role="user", text=text_pentru_evaluator))
        )
        doua_apeluri = doua and mod == "roleplay"
        cerere_evaluator = None
        if doua_apeluri:
            prompt_actor, prompt_evaluator = get_prompts_pe_meserii(
                name=PARTICIPANT,
                history_length=lungime,
                memories=[],
                biblioteca_path=setari.biblioteca_path,
                profil_rol=profil,
            )
            cerere_evaluator = GenerationRequest(
                messages=tuple(mesaje_evaluator),
                system_instruction=prompt_evaluator,
                purpose=GenerationPurpose.evaluator,
                max_output_tokens=setari.vertex_max_output_tokens_evaluator,
                temperature=0.2,
                thinking_budget=setari.thinking_budget_evaluator,
            )
        cerere = GenerationRequest(
            messages=tuple(mesaje),
            system_instruction=prompt_actor if doua_apeluri else get_system_prompt_for_kind(
                kind=mod,
                name=PARTICIPANT,
                history_length=lungime,
                quiz_competency="mix" if mod == "knowledge" else None,
                project_competencies=COMPETENTE_PROIECT,
                memories=[],
                biblioteca_path=setari.biblioteca_path,
                profil_rol=profil,
            ),
            purpose=GenerationPurpose.actor,
            max_output_tokens=setari.vertex_max_output_tokens,
            temperature=0.7,
            thinking_budget=setari.thinking_budget_actor,
        )
        t0 = time.monotonic()
        rand = {"pas": i, "fel": pas.fel, "om": pas.text, "raspuns": "", "eroare": None,
                "oprire": None, "model": None, "intrat": 0, "iesit": 0, "gandit": 0,
                "din_cache": 0, "text_actor": "", "text_evaluator": "", "apeluri": 1}
        try:
            if not doua_apeluri:
                rez = await furnizor.generate(cerere)
                u = rez.usage
                rand.update(raspuns=rez.text or "", oprire=rez.finish_reason, model=rez.model,
                            intrat=u.prompt_tokens, iesit=u.output_tokens,
                            gandit=u.thought_tokens, din_cache=u.cached_tokens)
            else:
                # Exact ca aplicatia (service.py, plicul 112): in PARALEL, amandoua cu acelasi
                # transcript, si aplicatia lipeste personajul inaintea evaluarii.
                rez, rez_e = await asyncio.gather(
                    furnizor.generate(cerere), furnizor.generate(cerere_evaluator)
                )
                u, ue = rez.usage, rez_e.usage
                text_actor = (rez.text or "").strip()
                text_eval = (rez_e.text or "").strip()
                rand.update(
                    raspuns=f"{text_actor}\n\n***\n\n{text_eval}" if text_eval else text_actor,
                    text_actor=text_actor, text_evaluator=text_eval, apeluri=2,
                    oprire=rez.finish_reason, model=rez.model,
                    intrat=u.prompt_tokens + ue.prompt_tokens,
                    iesit=u.output_tokens + ue.output_tokens,
                    gandit=u.thought_tokens + ue.thought_tokens,
                    din_cache=u.cached_tokens + ue.cached_tokens,
                )
        except Exception as err:
            # orice eroare se numara ca replica pierduta; nu opreste rularea
            rand["eroare"] = getattr(err, "code", None) or type(err).__name__
        rand["secunde"] = round(time.monotonic() - t0, 2)
        pasi.append(rand)
        # Ca aplicatia (service.py, plicurile 64-65): o replica a omului ramasa fara raspuns
        # nu ajunge la model; urmatoarea ii ia locul. Deci dupa o eroare istoricul ramane
        # cum era — fara replica goala a lui Cody, care ar fi rupt conversatia.
        if rand["eroare"] or not rand["raspuns"]:
            continue
        if pas.text is not None:
            istoric.append(GenerationMessage(role="user", text=pas.text))
            istoric_evaluator.append(
                GenerationMessage(role="user", text=text_pentru_evaluator)
            )
            scena_in_asteptare = ""
        if doua_apeluri:
            # fiecare isi tine numai bucata lui; daca una lipseste, randul se sare
            if rand["text_actor"]:
                istoric.append(GenerationMessage(role="model", text=rand["text_actor"]))
                # scena asteapta urmatoarea replica a omului, ca sa plece odata cu ea
                scena_in_asteptare = rand["text_actor"].strip()
            if rand["text_evaluator"]:
                istoric_evaluator.append(
                    GenerationMessage(role="model", text=rand["text_evaluator"])
                )
        else:
            istoric.append(GenerationMessage(role="model", text=rand["raspuns"]))
    coduri = numarator.coduri - coduri_inainte
    return {
        "tip": "sesiune",
        "id": f"{mod}:{nr}",
        "mod": mod,
        "rulare": nr,
        "terminata": datetime.now(UTC).isoformat(timespec="seconds"),
        "secunde": round(time.monotonic() - inceput, 1),
        "apeluri": sum(x.get("apeluri", 1) for x in pasi),
        "http": {str(k): v for k, v in sorted(coduri.items())},
        "pasi": pasi,
        "porti": portile(mod, pasi, nr),
    }


class Iesire:
    """Un rand pe iesire si acelasi rand in jurnal. Iesirea poate muri; jurnalul, nu."""

    def __init__(self, jurnal: Path) -> None:
        jurnal.parent.mkdir(parents=True, exist_ok=True)
        self.jurnal = jurnal
        self.iesirea_traieste = True

    def __call__(self, obiect: dict) -> None:
        rand = json.dumps(obiect, ensure_ascii=False) + "\n"
        with self.jurnal.open("a", encoding="utf-8") as f:
            f.write(rand)
            f.flush()
            os.fsync(f.fileno())
        if self.iesirea_traieste:
            try:
                sys.stdout.write(rand)
                sys.stdout.flush()
            except (BrokenPipeError, OSError):
                self.iesirea_traieste = False  # continua doar in jurnal


async def main(argv: list[str] | None = None) -> int:
    reale = get_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sesiuni", help="lista ordonata, ex. roleplay:1,knowledge:1")
    ap.add_argument("--model", default=reale.vertex_actor_model)
    ap.add_argument("--destinatie", default=reale.vertex_region)
    ap.add_argument("--plafon-apeluri", type=int, default=260)
    ap.add_argument("--doua-apeluri", action="store_true",
                    help="despartirea actor/evaluator, plicul 112")
    ap.add_argument("--plafon-minute", type=float, default=90)
    ap.add_argument("--jurnal", type=Path,
                    help="fisierul din container unde se scrie fiecare sesiune terminata")
    ap.add_argument("--reevalueaza", type=Path, metavar="STARE.jsonl",
                    help="doar recalculeaza portile din textele salvate; niciun apel la model")
    a = ap.parse_args(argv)
    if a.reevalueaza:
        return reevalueaza(a.reevalueaza)
    if not (a.sesiuni and a.jurnal):
        ap.error("--sesiuni si --jurnal sunt obligatorii pentru o rulare")
    scrie = Iesire(a.jurnal)

    sesiuni = []
    for bucata in a.sesiuni.split(","):
        mod, nr = bucata.split(":")
        if mod not in SCENARII:
            ap.error(f"mod necunoscut: {mod}")
        sesiuni.append((mod, int(nr)))

    setari = reale.model_copy(update={
        "vertex_actor_model": a.model,
        "vertex_evaluator_model": a.model,
        "vertex_region": a.destinatie,
    })
    numarator = Numarator()
    client = httpx.AsyncClient(
        timeout=float(setari.vertex_timeout_seconds), event_hooks={"response": [numarator]}
    )
    furnizor = build_generation_provider(setari, client=client)
    inceput = datetime.now(UTC).isoformat(timespec="seconds")
    scrie({"tip": "cap", "model": a.model, "destinatie": a.destinatie,
           "furnizor": setari.generation_provider, "versiune_prompt": CODY_PROMPT_VERSION,
           "plafon_apeluri": a.plafon_apeluri, "plafon_minute": a.plafon_minute,
           "sesiuni_cerute": len(sesiuni),
           "inceput": inceput})

    termen = time.monotonic() + a.plafon_minute * 60
    apeluri = 0
    facute = 0
    motiv = "toate sesiunile cerute sunt terminate"
    try:
        for mod, nr in sesiuni:
            if time.monotonic() >= termen:
                motiv = "oprita la plafonul de timp"
                break
            if apeluri + len(SCENARII[mod]) > a.plafon_apeluri:
                motiv = "oprita la plafonul de apeluri"
                break
            rezultat = await o_sesiune(
                furnizor, setari, numarator, mod, nr, doua=a.doua_apeluri
            )
            apeluri += rezultat["apeluri"]
            facute += 1
            scrie(rezultat)
    finally:
        await client.aclose()
    scrie({"tip": "sfarsit", "motiv": motiv, "sesiuni_facute": facute, "inceput": inceput,
           "sfarsit_la": datetime.now(UTC).isoformat(timespec="seconds"),
           "sesiuni_cerute": len(sesiuni), "apeluri": apeluri,
           "http": {str(k): v for k, v in sorted(numarator.coduri.items())}})
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
