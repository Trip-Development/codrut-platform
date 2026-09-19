"""Unealta de probe automate — plicul 82. O poarta de regres, NU o dovada de calitate.

Ruleaza sesiuni scriptate (`probe_scenarii.py`) cu promptul si furnizorul aplicatiei, IN
MEMORIE: nu deschide nicio conexiune la baza de date si nu salveaza nimic. Verifica mecanic
sapte porti si numara 429-urile, erorile, durata si textul care intra si iese.

Se cheama din containerul backendului de proba; o comanda locala o porneste si tine socoteala
(`SPEC-CODY/UNELTE/probe-automate.py`). Scrie pe iesire UN RAND JSON pe sesiune terminata,
imediat — cine citeste poate fi oprit oricand fara sa piarda ce s-a terminat.

    python -m codrut.tools.probe_automate --sesiuni roleplay:1,knowledge:1,coaching:1 \
        [--model M] [--destinatie D] [--plafon-apeluri 260] [--plafon-minute 90]

Regulile de rulare: `SPEC-CODY/UNELTE/REGULI-PROBE-AUTOMATE.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime

import httpx

from codrut.contracts.generation import GenerationMessage, GenerationPurpose, GenerationRequest
from codrut.core.config import get_settings
from codrut.modules.practice.generation_provider import build_generation_provider
from codrut.modules.practice.prompts import (
    CODY_PROMPT_VERSION,
    NUME_PERSONAJ,
    _numele_personajului,
    get_system_prompt_for_kind,
)
from codrut.modules.practice.service import DESCHIDE_SESIUNEA
from codrut.tools.probe_metode_scoase import METODE_SCOASE
from codrut.tools.probe_scenarii import COMPETENTE_PROIECT, PARTICIPANT, SCENARII

MODURI = ("roleplay", "knowledge", "coaching")
PRENUME = PARTICIPANT.split()[0]

# ---------------------------------------------------------------- portile, ca functii pure

SCOR = re.compile(r"Scor:\s*\**\s*(\d+(?:[.,]\d+)?)\s*\**\s*/\s*10")
GHILIMELE = re.compile(r"[«„\"“]([^«»„”\"“]{6,400})[»”\"“]")
REPLICA_MODEL = re.compile(
    r"(ai fi putut (spune|zice|formula|încerca|întreba)|ai putea (spune|zice|formula)"
    r"|puteai (spune|zice)|(o )?variant[ăa] mai (bun[ăa]|clar[ăa])|ar fi sunat"
    r"|mai bine ar fi fost s[ăa] spui|încearc[ăa] (așa|ceva de genul))"
    r"[^\n]{0,200}?[«„\"“]",
    re.IGNORECASE,
)
NUME_INTERZISE = re.compile(
    r"\[\s*nume\s*\]|\buser\b|\bparticipant\b|\butilizator(ul)?\b", re.IGNORECASE
)
METODE = re.compile(r"\b(" + "|".join(map(re.escape, METODE_SCOASE)) + r")\b", re.IGNORECASE)


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

    p = {str(i): poarta() for i in range(1, 8)}
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
        metode = sorted({m.upper() for m in METODE.findall(r)})
        bifa("7", not metode, f"pas {nr_pas}: {', '.join(metode)}")
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
        mesaje = (
            (GenerationMessage(role="user", text=DESCHIDE_SESIUNEA),)
            if pas.text is None
            else (*istoric, GenerationMessage(role="user", text=pas.text))
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
                "din_cache": 0}
        try:
            rez = await furnizor.generate(cerere)
            u = rez.usage
            rand.update(raspuns=rez.text or "", oprire=rez.finish_reason, model=rez.model,
                        intrat=u.prompt_tokens, iesit=u.output_tokens, gandit=u.thought_tokens,
                        din_cache=u.cached_tokens)
        except Exception as err:
            # orice eroare se numara ca replica pierduta; nu opreste rularea
            rand["eroare"] = getattr(err, "code", None) or type(err).__name__
        rand["secunde"] = round(time.monotonic() - t0, 2)
        pasi.append(rand)
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


def scrie(obiect: dict) -> None:
    sys.stdout.write(json.dumps(obiect, ensure_ascii=False) + "\n")
    sys.stdout.flush()


async def main(argv: list[str] | None = None) -> int:
    reale = get_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sesiuni", required=True, help="lista ordonata, ex. roleplay:1,knowledge:1")
    ap.add_argument("--model", default=reale.vertex_actor_model)
    ap.add_argument("--destinatie", default=reale.vertex_region)
    ap.add_argument("--plafon-apeluri", type=int, default=260)
    ap.add_argument("--plafon-minute", type=float, default=90)
    a = ap.parse_args(argv)

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
    scrie({"tip": "cap", "model": a.model, "destinatie": a.destinatie,
           "furnizor": setari.generation_provider, "versiune_prompt": CODY_PROMPT_VERSION,
           "plafon_apeluri": a.plafon_apeluri, "plafon_minute": a.plafon_minute,
           "sesiuni_cerute": len(sesiuni),
           "inceput": datetime.now(UTC).isoformat(timespec="seconds")})

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
    scrie({"tip": "sfarsit", "motiv": motiv, "sesiuni_facute": facute,
           "sesiuni_cerute": len(sesiuni), "apeluri": apeluri,
           "http": {str(k): v for k, v in sorted(numarator.coduri.items())}})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except BrokenPipeError:
        # Cine citea a fost oprit (laptop inchis, legatura cazuta). Sesiunile terminate sunt
        # deja scrise la el; aici nu mai e nimic de salvat.
        sys.exit(0)
