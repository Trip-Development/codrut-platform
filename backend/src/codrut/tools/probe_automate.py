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
from codrut.modules.practice.citat import (
    propozitii_numerotate,
    pune_citatul,
    sterge_repetarea,
    text_dublat,
)
from codrut.modules.practice.generation_provider import build_generation_provider
from codrut.modules.practice.prompts import (
    CODY_PROMPT_VERSION,
    NUME_PERSONAJ,
    _numele_personajului,
    get_system_prompt_for_kind,
)
from codrut.modules.practice.service import DESCHIDE_SESIUNEA
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


def portile(mod: str, pasi: list[dict], nr_rulare: int) -> dict[str, dict]:
    """Cele sapte porti pentru o sesiune. Fiecare: aplicabila, instante, trecute, picate."""
    def poarta(aplicabila=True):
        return {"aplicabila": aplicabila, "instante": 0, "trecute": 0, "picate": []}

    p = {str(i): poarta() for i in range(1, 9)}
    p["7"]["numarate"] = {m: 0 for m in METODE_NUMARATE}
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
        # Poarta 8 (plicul 109): o bucata de text scrisa de doua ori, lipite. Celelalte sapte
        # porti citesc textul dupa ce cauta in el nota, citatul, numele sau metodele — niciuna
        # nu-l citeste CA TEXT, si de aia defectul de la plicul 108 a trecut prin toate.
        dublat = text_dublat(r)
        bifa("8", dublat is None, f"pas {nr_pas}: scris de doua ori: {(dublat or '')[:60]!r}")
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
        scena = " ".join(x["raspuns"] for x in pasi if x["fel"] in ("pornire", "joc"))
        gasit = personajul(scena)
        asteptat = _numele_personajului(nr_rulare - 1, PRENUME)
        p["4"]["personaj"] = gasit
        p["4"]["asteptat"] = asteptat
        bifa("4", gasit is not None and gasit.split()[0] != PRENUME,
             f"personaj {gasit or 'negasit in lista'}")
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


async def o_sesiune(furnizor, setari, numarator, mod: str, nr: int) -> dict:
    scenariu = SCENARII[mod]
    profil = {
        "conduce_oameni": True,
        "functie": None,
        "nr_roleplay_anterioare": nr - 1,
        "nr_sesiuni_anterioare": (nr - 1) * len(MODURI) + MODURI.index(mod),
    }
    istoric: list[GenerationMessage] = []
    pasi = []
    inceput = time.monotonic()
    coduri_inainte = Counter(numarator.coduri)
    for i, pas in enumerate(scenariu, start=1):
        # Exact ca aplicatia (service.py): salutul la istoric 0, cu instructiunea de deschidere,
        # care nu se pastreaza; apoi istoricul are replica lui Cody + replica noua a omului.
        lungime = 0 if pas.text is None else len(istoric) + 1
        # Exact ca aplicatia (service.py): replica de ACUM intra numerotata pe propozitii, cele
        # din istoric raman cum le-a scris omul — istoricul aplicatiei vine din baza.
        text_pentru_model = (
            pas.text + propozitii_numerotate(pas.text)
            if pas.text is not None and mod == "roleplay"
            else pas.text
        )
        mesaje = (
            (GenerationMessage(role="user", text=DESCHIDE_SESIUNEA),)
            if pas.text is None
            else (*istoric, GenerationMessage(role="user", text=text_pentru_model))
        )
        cerere = GenerationRequest(
            messages=tuple(mesaje),
            system_instruction=get_system_prompt_for_kind(
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
                "din_cache": 0, "motiv_citat": "", "sterse": 0}
        try:
            rez = await furnizor.generate(cerere)
            u = rez.usage
            # Tot ca aplicatia: citatul il pune aplicatia in locul numarului, apoi isi sterge
            # singura repetarea exacta. Portile vad textul pe care l-ar vedea si omul.
            text_final, motiv, sterse = rez.text or "", "", []
            if mod == "roleplay":
                text_final, motiv = pune_citatul(text_final, pas.text or "")
                text_final, sterse = sterge_repetarea(text_final)
            rand.update(raspuns=text_final, oprire=rez.finish_reason, model=rez.model,
                        intrat=u.prompt_tokens, iesit=u.output_tokens, gandit=u.thought_tokens,
                        din_cache=u.cached_tokens, motiv_citat=motiv, sterse=len(sterse))
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
        istoric.append(GenerationMessage(role="model", text=rand["raspuns"]))
    coduri = numarator.coduri - coduri_inainte
    return {
        "tip": "sesiune",
        "id": f"{mod}:{nr}",
        "mod": mod,
        "rulare": nr,
        "terminata": datetime.now(UTC).isoformat(timespec="seconds"),
        "secunde": round(time.monotonic() - inceput, 1),
        "apeluri": len(pasi),
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
            rezultat = await o_sesiune(furnizor, setari, numarator, mod, nr)
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
