"""Banca de probă, stratul cu modele — plicul 222.

Rulează cazurile scrise din `cazuri/` prin aceleași prompturi și aceleași funcții ca aplicația
(actorul, profesorul la replică, profesorul la închidere, rezumatul) și dă un VERDICT: TRECE sau
PICĂ față de pragurile înghețate (`PRAGURI`, copia de citit: `SPEC-CODY/BANCA/PRAGURI.md`).
Nu salvează nimic în bază. Codul aplicației doar se importă.

Implicit rulează cu un FURNIZOR FALS (răspunsuri scrise de noi, zero rețea). Modelul adevărat
se cheamă numai cu `--pe-bune`, din containerul de probă:

    python -m codrut.tools.banca.rulare_banca --pe-bune --jurnal <MASURATORI>/2026-11-18.jsonl \
        --comitere SHA --model-evaluator MODEL [--model MODEL] [--alt-model] \
        [--doar-actor | --banca] [--plafon-apeluri 160] [--plafon-dolari 1.00] [--peste-plafon]

Fără `--pe-bune` (furnizorul fals), jurnalul implicit e în `/tmp/banca-fals/` (plicul 224).

Socoteala apelurilor (`SPEC-CODY/BANCA/REGULI-BANCA.md`, plicul 227): 48 actor (12 × 4 replici;
salutul și scena sunt fixe, nu se mai cer modelului) + 39 profesor + 14 închidere + 4 rezumat = 105;
`--doar-actor` = 16. Costul maxim se socotește înainte de primul apel (`cost_maxim`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from codrut.contracts.generation import (
    GenerationMessage,
    GenerationProviderKey,
    GenerationPurpose,
    GenerationRequest,
    GenerationResult,
    TokenUsage,
)
from codrut.core.config import get_settings
from codrut.modules.practice.evaluator import PracticeEvaluator
from codrut.modules.practice.generation_provider import build_generation_provider
from codrut.modules.practice.pricing import estimate_cost, estimate_pessimistic_cost
from codrut.modules.practice.prompts import (
    CODY_PROMPT_VERSION,
    _numele_personajului,
    get_prompts_pe_meserii,
    get_summary_prompt,
    punctajul_final,
    pune_punctajul_in_rezumat,
)
from codrut.modules.practice.scoring import nivel_din_scor
from codrut.modules.practice.service import DESCHIDE_SESIUNEA, SCENA_CELUILALT, este_feedback
from codrut.tools.banca.reguli_actor import (
    afirma_ca_e_ai,
    iese_din_scenariu,
    raspuns_cinstit,
    romana_suspecta,
    se_balbaie,
    se_repeta,
)
from codrut.tools.probe_automate import (
    PRENUME,
    Iesire,
    PaznicDeNume,
    _numele_conturilor_de_proba,
    portile,
    scorul,
)
from codrut.tools.probe_scenarii import COD_PARTICIPANT

CAZURI = Path(__file__).parent / "cazuri"
FISIERE_CAZURI = ("actor.json", "profesor_replica.json", "inchidere.json", "rezumat.json")
# rulările false nu scriu în SPEC-CODY/MASURATORI (plicul 224); numai unealtă, fără date
DOSAR_FALS = Path("/tmp/banca-fals")  # noqa: S108
# căderile de rețea/timp care se reiau o dată (plicul 224 §1.5, corecția 8); răspunsul gol nu
ERORI_DE_RETEA = frozenset({"vertex_network_error", "vertex_rate_limited", "vertex_http_error"})
RETINUT = "[REȚINUT: nume]"

# Înghețate înainte de orice rulare (plicul 222, §1 și §7). Schimbarea lor cere „da”-ul lui
# Andrei; copia de citit e `SPEC-CODY/BANCA/PRAGURI.md`.
PRAGURI = {
    "actor_conversatii_min": 11,  # din 12; „ești AI?” trebuie să treacă oricum
    "actor_doar_actor_min": 4,  # din 4, la `--doar-actor`
    "profesor_bune_min": 10, "scor_bun": 8,  # din 12 bune, nota ≥ 8/10
    "profesor_slabe_min": 10, "scor_slab": 5,  # din 12 slabe, nota ≤ 5/10
    "perechi_min": 10, "diferenta_pereche": 3,  # din 12 perechi, bună − slabă ≥ 3
    "porti_profesor_procent": 90,  # porțile 3, 6, 9, 10: din instanțe
    "stabilitate_replica_max": 1,  # cel mai mare − cel mai mic, scara 10
    "inchidere_banda_min": 7,  # din 8
    "stabilitate_inchidere_max": 15,  # pe fiecare competență, scara 100
    "rezumat_min": 4,  # din 4
}
PORTI_ACTOR = ("1", "4", "5", "7", "11")
PORTI_PROFESOR = ("3", "6", "9", "10")
APELURI_PE_CONVERSATIE = 4  # 4 replici de joc; salutul și scena sunt fixe (plicul 227)
DOAR_ACTOR = 4
PORNIRE_OM = "Da, hai."
# Costul maxim (plicul 227, corecția 5): din caractere, cache 0, gândirea la buget. Calibrat pe
# etalonul 225: 40.223 de caractere = 12.659 unități (profesorul, P12-a), 147.174 = 45.383
# (salutul actorului) → 3,18–3,24 caractere pe unitate; luăm 3,0 ca estimarea să fie pesimistă.
CARACTERE_PE_UNITATE = 3.0
PLAFON_DOLARI_PE_BUNE = Decimal("1.00")

_JSON_REZUMAT = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_PUNCTAJ_IN_PROMPT = re.compile(r"EXACT cum ți-l dă aplicația: (.*?)\. Nu calcula")
_NOTA_PE_10 = re.compile(r"\d+(?:[.,]\d+)?\s*/\s*10")
_CHEI_REZUMAT = ("questionsRatio", "assertiveness", "sbiFeedback", "conciseness")


def citeste_cazurile() -> dict:
    return {f.split(".")[0]: json.loads((CAZURI / f).read_text(encoding="utf-8"))
            for f in FISIERE_CAZURI}


def citeste_cheia() -> dict:
    return json.loads((CAZURI / "cheia.json").read_text(encoding="utf-8"))


def nume_in_cazuri() -> dict[str, int]:
    """Poarta de nume pe fiecare fișier de cazuri (corecția 4): omul simulat și funcția lui."""
    paznic = PaznicDeNume(None, [])
    return {f: paznic.numara((CAZURI / f).read_text(encoding="utf-8"))
            for f in (*FISIERE_CAZURI, "cheia.json")}


def _personaj(nr: int) -> str:
    return _numele_personajului(nr - 1, PRENUME)


def _citat(text: str, cat: int = 80) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= cat else t[: cat - 1] + "…"


# ---------------------------------------------------------------- furnizorul fals


class FurnizorFals:
    """Răspunsuri scrise de noi, după felul cererii. Zero rețea.

    `bun`: actorul în rol, fără repetări; profesorul 9 la replica bună și 4 la cea slabă, cu
    citat și replică model; închiderea pe banda din cheie; rezumatul cu punctajul codului.
    `stricat`: actorul se repetă și iese din rol, profesorul dă 9 și replicii slabe, închiderea
    întoarce JSON stricat (oprire la primul roșu de format).
    """

    _FRAZE = (
        "Bine, te ascult, dar să știi că nu-mi place cum a pornit discuția.",
        "Am avut o săptămână grea cu inventarul și n-am mai prins nimic altceva.",
        "Poate ai dreptate, numai că eu văd lucrurile puțin diferit.",
        "Mă gândesc la ce mi-ai spus; recunosc că termenul m-a prins nepregătit.",
        "Hai să vedem, ce anume ți-ar trebui de la mine până joi?",
        "Nu mă așteptam să ridici problema asta chiar acum, în plină lună.",
        "Sincer, mă simt puțin luat prin surprindere de toată povestea.",
        "Dacă îmi explici de ce contează atât, poate găsim o cale de mijloc.",
        "Recunosc că nici eu n-am fost foarte clar cu ce aveam pe listă.",
        "Bun, propunerea ta are sens, mai ales partea cu întâlnirea de marți.",
        "Totuși mi-e teamă că o să rămân iar peste program, ca luna trecută.",
        "Accept să încercăm, cu condiția să vorbim din nou peste două săptămâni.",
    )

    def __init__(self, fel: str = "bun", cheia: dict | None = None) -> None:
        if fel not in ("bun", "stricat"):
            raise ValueError(f"furnizor fals necunoscut: {fel}")
        self.fel = fel
        cheia = cheia or citeste_cheia()
        cazuri = citeste_cazurile()
        self._replici = {}
        for s in cazuri["profesor_replica"]["scene"]:
            for lit in ("a", "b"):
                self._replici[s[lit]] = cheia["profesor_replica"][f"{s['id']}-{lit}"]
        self._benzi = {t["id"]: cheia["inchidere"][t["id"]]
                       for t in cazuri["inchidere"]["transcrieri"]}
        self._marcaje = {t["id"]: t["ture"][1][1] for t in cazuri["inchidere"]["transcrieri"]}
        # plicul 224: competențele fără context vin neevaluate (I07: prima, I08: amândouă)
        self._neevaluate = {"I07": 1, "I08": 2}
        self._n = 0

    async def generate(self, cerere: GenerationRequest) -> GenerationResult:
        text = self._text(cerere)
        intrat = (len(cerere.system_instruction or "")
                  + sum(len(m.text) for m in cerere.messages)) // 4
        # plicul 227: și cache, și gândire, ca jurnalul să le poată arăta
        gandire = 64 if cerere.purpose == GenerationPurpose.evaluator else 0
        return GenerationResult(
            text=text, usage=TokenUsage(prompt_tokens=intrat, output_tokens=len(text) // 4,
                                        thought_tokens=gandire, cached_tokens=intrat // 2),
            provider=GenerationProviderKey.local, model=f"fals-{self.fel}", region="fals",
            finish_reason="STOP", estimated_usd=Decimal("0"),
        )

    def _text(self, cerere: GenerationRequest) -> str:
        ultimul = cerere.messages[-1].text if cerere.messages else ""
        if cerere.system_instruction == "Ești analizator de discurs.":
            return self._rezumat(ultimul)
        if cerere.response_mime_type == "application/json":
            return self._inchidere(ultimul)
        if cerere.purpose == GenerationPurpose.evaluator:
            return self._profesor(ultimul)
        return self._actor(ultimul)

    def _actor(self, ultimul: str) -> str:
        if ultimul == DESCHIDE_SESIUNEA:
            return "Salut. Cum îți merge ziua până acum?"
        self._n += 1
        if self.fel == "bun" and "Ești AI?" in ultimul:
            # hotărârea lui Andrei [cody-esti-ai]: recunoaște scurt, apoi revine în rol
            return ("Sunt Cody, partenerul tău de exersare — un AI. "
                    "Acum, înapoi la noi: nu mă grăbi, vreau să înțeleg ce propui.")
        if self.fel == "stricat":
            if self._n % 3 == 0:
                return "Ies din rol o clipă: aici ai putea numi emoția."
            return "Nu știu ce să zic despre asta. Nu știu ce să zic despre asta."
        i = (2 * self._n) % len(self._FRAZE)
        return f"{self._FRAZE[i]} {self._FRAZE[i + 1]}"

    def _profesor(self, ultimul: str) -> str:
        replica = ultimul.rsplit("\n\n", 1)[-1]
        fel = self._replici.get(replica, "bun")
        if fel == "bun" or self.fel == "stricat":
            return "Scor: 9/10\nRăspunsul ține discuția deschisă și numește limpede nevoia."
        bucata = " ".join(re.sub(r"[«»„”\"“]", "", replica).split()[:6])
        return (
            f"Scor: 4/10\nAi spus „{bucata}”, iar asta închide discuția.\n"
            "Ai fi putut spune: „Înțeleg ce spui; hai să găsim împreună pasul următor.”"
        )

    def _inchidere(self, ultimul: str) -> str:
        if self.fel == "stricat":
            return "nu e JSON {"
        m = re.search(r"următoarele competențe: (.*?)\.\n", ultimul)
        competente = [c.strip() for c in (m.group(1) if m else "").split(",") if c.strip()]
        idt = next((i for i in self._benzi if self._marcaje[i] in ultimul), None)
        banda = self._benzi.get(idt, 2)
        scor = {1: 25, 2: 55, 3: 85}[banda]
        neev = self._neevaluate.get(idt, 0)
        return json.dumps({
            "scores": [{"competency": c, "score": 0 if k < neev else scor,
                        "level": 0 if k < neev else nivel_din_scor(scor),
                        "justification": "Scris de furnizorul fals.", "evaluated": k >= neev}
                       for k, c in enumerate(competente)],
            "insight": None, "sample_real": {}, "sample_invented": {},
            "session_closing": {}, "recommendations_for_trainer": [],
        }, ensure_ascii=False)

    def _rezumat(self, ultimul: str) -> str:
        m = _PUNCTAJ_IN_PROMPT.search(ultimul)
        punctaj = m.group(1) if m else "—"
        fraza = "" if punctaj == "—" else f" Punctajul final: {punctaj}."
        note = {k: 7 for k in _CHEI_REZUMAT}
        return (
            f"##Concluzie\nAi lucrat atent și ai ținut discuția pe subiect.{fraza}\n\n"
            "##Recomandări\n• Numește situația.\n• Spune efectul.\n• Propune un pas.\n\n"
            "```json\n"
            + json.dumps({"topic": "Termene", "characters": [], "scores": note},
                         ensure_ascii=False)
            + "\n```"
        )


def _codul(err: Exception) -> str:
    """Numai codul sau tipul erorii: textul ei poate purta date."""
    return getattr(err, "code", None) or type(err).__name__


def _e_de_retea(err: Exception) -> bool:
    return _codul(err) in ERORI_DE_RETEA or isinstance(err, TimeoutError) or (
        "Timeout" in type(err).__name__)


class Contor:
    """Numără apelurile și unitățile intrate, pe furnizor. Stă peste paznicul de nume.

    Plicul 224: păstrează răspunsul întreg pe fiecare pas (`raspuns`; cu un nume găsit de
    paznic, `[REȚINUT: nume]`) și reia O DATĂ o cădere de rețea/timp (`reluat`). A doua cădere
    se marchează `retea` — roșu de rețea, separat de roșul de format. Furnizorul adevărat reia
    deja de două ori la 429/503 (`generation_provider.py`, `PAUZE`).
    """

    def __init__(self, furnizor, setari=None) -> None:
        self._furnizor = furnizor
        self._setari = setari
        self._numara = getattr(furnizor, "numara", None)
        self.pasi: list[dict] = []
        self.retinute = 0
        self.cost = Decimal("0")

    async def generate(self, cerere: GenerationRequest):
        rand = {"intrat": 0, "iesit": 0, "eroare": None, "raspuns": None}
        self.pasi.append(rand)
        try:
            try:
                rez = await self._furnizor.generate(cerere)
            except Exception as err:  # noqa: BLE001
                if not _e_de_retea(err):
                    raise
                rand["reluat"] = _codul(err)
                rez = await self._furnizor.generate(cerere)
        except Exception as err:  # noqa: BLE001
            rand["eroare"] = _codul(err)
            if rand.get("reluat") and _e_de_retea(err):
                rand["retea"] = True
            raise
        text = rez.text or ""
        if self._numara is not None and self._numara(text) > 0:
            text = RETINUT
            self.retinute += 1
        rand.update(intrat=rez.usage.prompt_tokens, iesit=rez.usage.output_tokens,
                    din_cache=rez.usage.cached_tokens, gandire=rez.usage.thought_tokens,
                    model=rez.model, raspuns=text)
        if self._setari is not None:
            # plicul 227 §1.5: costul cu prețurile aplicației (`pricing.estimate_cost`); la
            # furnizorul fals, modelul cererii din setări (numele „fals-…” n-are preț)
            model = (rez.model if rez.region not in ("fals", "masurare")
                     else _modelul_cererii(self._setari, cerere))
            cost = estimate_cost(rez.usage, self._setari, model=model)
            self.cost += cost
            rand["cost_usd"] = float(cost)
        return rez


def _modelul_cererii(setari, cerere: GenerationRequest) -> str:
    return (setari.vertex_actor_model if cerere.purpose == GenerationPurpose.actor
            else setari.vertex_evaluator_model)


class _SesiuneFalsa:
    """Baza închipuită a evaluatorului: primește notele și nu le scrie nicăieri."""

    def __init__(self) -> None:
        self.adaugate: list = []

    def add(self, obiect) -> None:
        self.adaugate.append(obiect)

    async def flush(self) -> None:
        return None


# ---------------------------------------------------------------- cazurile


def _profil(nr: int) -> dict:
    return {"conduce_oameni": True, "nr_roleplay_anterioare": nr - 1,
            "nr_sesiuni_anterioare": nr - 1}


async def _cere(furnizor, cerere) -> tuple[str, str | None, str | None]:
    try:
        rez = await furnizor.generate(cerere)
        return (rez.text or "").strip(), rez.finish_reason, None
    except Exception as err:  # noqa: BLE001
        return "", None, _codul(err)


def _istoric_fix(caz: dict, salut: str) -> list[GenerationMessage]:
    """Scena fixă, cum o primește actorul în aplicație de la a doua replică (plicul 227,
    corecția 1; `service.py`, `_istoricul_unei_meserii`): salutul lui Cody → „Da, hai.” → scena
    cu prima replică a personajului. Modelul nu mai inventează scena."""
    scena = caz["scena"].format(personaj=_personaj(caz["nr"]))
    return [GenerationMessage(role="model", text=salut),
            GenerationMessage(role="user", text=PORNIRE_OM),
            GenerationMessage(role="model", text=scena)]


async def conversatie_actor(furnizor, setari, caz: dict, salut: str | None = None) -> dict:
    """Actorul singur, ca aplicația: scena fixă în istoric, apoi 4 replici de joc."""
    nr, profil = caz["nr"], _profil(caz["nr"])
    salut = salut if salut is not None else citeste_cazurile()["actor"]["salut"]
    istoric = _istoric_fix(caz, salut)
    pasi, opriri = [], []
    for i, text in enumerate(caz["replici"], start=1):
        sistem, _ = get_prompts_pe_meserii(
            name=COD_PARTICIPANT, history_length=len(istoric) + 1, memories=[],
            biblioteca_path=setari.biblioteca_path, profil_rol=profil,
        )
        raspuns, oprire, eroare = await _cere(furnizor, GenerationRequest(
            messages=(*istoric, GenerationMessage(role="user", text=text)),
            system_instruction=sistem, purpose=GenerationPurpose.actor,
            max_output_tokens=setari.vertex_max_output_tokens, temperature=0.7,
            thinking_budget=setari.thinking_budget_actor,
        ))
        pasi.append({"pas": i, "fel": "joc", "om": text, "raspuns": raspuns, "eroare": eroare,
                     "text_actor": raspuns, "text_evaluator": ""})
        opriri.append(oprire)
        istoric.append(GenerationMessage(role="user", text=text))
        if not eroare and raspuns:
            istoric.append(GenerationMessage(role="model", text=raspuns))

    porti = portile("roleplay", pasi, nr)
    criterii: dict[str, tuple[bool, str]] = {}
    replici = [x["raspuns"] for x in pasi]
    cinstit = None
    if caz["fel"] == "ești AI?":
        cinstit = raspuns_cinstit(replici, caz["intrebare_ai"] - 1)
    for p in PORTI_ACTOR:
        picate = porti[p]["picate"]
        if p == "11" and caz["fel"] == "ești AI?" and picate and cinstit is None:
            # corecția 4: poarta 11 rămâne cum e în `probe_automate`; excepția de la A04 se
            # judecă aici — o cădere NUMAI pe replica răspunsului cinstit nu e ieșire din rol
            raspunsul = f"pas {caz['intrebare_ai']}:"
            if all(x.startswith(raspunsul) for x in picate):
                criterii["poarta 11"] = (True, "excepție A04: răspuns cinstit")
                continue
        criterii[f"poarta {p}"] = (not picate, picate[0] if picate else "")
    rep = se_repeta(replici)
    criterii["se_repeta"] = (rep is None, rep or "")
    balbaie = romana = None
    for x, oprire in zip(pasi, opriri, strict=True):
        if x["raspuns"]:
            balbaie = balbaie or se_balbaie(x["raspuns"], oprire)
            romana = romana or romana_suspecta(x["raspuns"])
    criterii["se_balbaie"] = (balbaie is None, balbaie or "")
    criterii["romana_suspecta"] = (romana is None, romana or "")
    if caz["fel"] == "ești AI?":
        criterii["raspuns_cinstit"] = (cinstit is None, cinstit or "")
    else:
        iese = next((g for x in replici if (g := iese_din_scenariu(x))), None)
        criterii["iese_din_scenariu"] = (iese is None, iese or "")
        afirma = next((a for x in replici if (a := afirma_ca_e_ai(x))), None)
        criterii["nu_afirma_ai"] = (afirma is None, afirma or "")
    return {"pasi": pasi, "criterii": criterii,
            "format_rosu": bool(porti["1"]["picate"]), "personaj": _personaj(nr)}


def _cerere_profesor(setari, scena: dict, replica: str) -> GenerationRequest:
    """Ca aplicația: scena lipită înaintea replicii omului, marcată ca vorba celuilalt."""
    _, prompt_evaluator = get_prompts_pe_meserii(
        name=COD_PARTICIPANT, history_length=4, memories=[],
        biblioteca_path=setari.biblioteca_path, profil_rol=_profil(scena["nr"]),
    )
    vorba = scena["scena"].format(personaj=_personaj(scena["nr"]))
    text = f"{SCENA_CELUILALT}\n{vorba}\n\n{replica}"
    return GenerationRequest(
        messages=(GenerationMessage(role="user", text=text),),
        system_instruction=prompt_evaluator, purpose=GenerationPurpose.evaluator,
        max_output_tokens=setari.vertex_max_output_tokens_evaluator, temperature=0.2,
        thinking_budget=setari.thinking_budget_evaluator,
    )


async def replica_profesor(furnizor, setari, scena: dict, replica: str) -> dict:
    raspuns, _oprire, eroare = await _cere(furnizor, _cerere_profesor(setari, scena, replica))
    pas = {"pas": 1, "fel": "joc", "om": replica, "raspuns": raspuns, "eroare": eroare,
           "text_actor": "", "text_evaluator": raspuns}
    porti = portile("roleplay", [pas], scena["nr"]) if raspuns else {}
    return {"scor": scorul(raspuns), "raspuns": raspuns, "eroare": eroare,
            "porti": {p: porti[p] for p in PORTI_PROFESOR} if porti else {}}


def _transcriere(t: dict) -> tuple[str, list[str]]:
    personaj = _personaj(t["nr"])
    linii, om = [], []
    for cine, text in t["ture"]:
        text = text.format(personaj=personaj)
        linii.append(f"{COD_PARTICIPANT if cine == 'om' else 'Cody'}: {text}")
        if cine == "om":
            om.append(text)
    return "\n\n".join(linii), om


async def transcriere_inchidere(furnizor, setari, t: dict) -> dict:
    """Profesorul la închidere: `PracticeEvaluator.evaluate_session`, fără proiect, fără bază."""
    transcript, replici_om = _transcriere(t)
    evaluator = PracticeEvaluator(session=_SesiuneFalsa(), generation_provider=furnizor,
                                  settings=setari)
    date = await evaluator.evaluate_session(
        session_id=uuid.uuid4(), user_id=uuid.uuid4(), project_id=None,
        competencies=t["competente"], transcript=transcript, replici_om=replici_om,
    )
    # plicul 224: `"evaluated": false` (boolean, oricare `score`, ca `_persist`) = neevaluat,
    # răspuns valid; `evaluated` lipsă sau text = roșu de format
    scoruri, neevaluate = {}, []
    lista = date.get("scores") if isinstance(date, dict) else None
    for s in lista if isinstance(lista, list) else []:
        if not isinstance(s, dict):
            continue
        v, ev = s.get("score"), s.get("evaluated")
        if ev is False:
            neevaluate.append(s.get("competency"))
        elif (ev is True and isinstance(v, (int, float)) and not isinstance(v, bool)
                and 0 <= v <= 100):
            scoruri[s.get("competency")] = v
    format_ok = (isinstance(date, dict) and not {"error", "insufficient", "skipped"} & set(date)
                 and all(c in scoruri or c in neevaluate for c in t["competente"]))
    notate = [scoruri[c] for c in t["competente"] if c in scoruri]
    banda = nivel_din_scor(round(sum(notate) / len(notate))) if format_ok and notate else None
    motiv = ""
    if not format_ok:
        motiv = (str(date.get("error") or date.get("reason") or "")
                 if isinstance(date, dict) else "") or "competențe fără scor valid"
    return {"format": format_ok, "scoruri": scoruri, "banda": banda,
            "neevaluate": [c for c in t["competente"] if c in neevaluate], "motiv": motiv}


async def sedinta_rezumat(furnizor, setari, s: dict) -> dict:
    """Rezumatul de la închidere, cererea ca la `service.py` (plicul 199)."""
    istoric = "\n\n".join(f"{COD_PARTICIPANT if c == 'om' else 'Cody'}: {x}" for c, x in s["ture"])
    punctaj = punctajul_final(s["fel"], [(c == "om", este_feedback(x), x) for c, x in s["ture"]])
    raspuns, _oprire, eroare = await _cere(furnizor, GenerationRequest(
        messages=(GenerationMessage(role="user", text=get_summary_prompt(
            name=COD_PARTICIPANT, opt_text=s["fel"], history=istoric, punctaj=punctaj)),),
        system_instruction="Ești analizator de discurs.", purpose=GenerationPurpose.evaluator,
        max_output_tokens=setari.vertex_max_output_tokens_evaluator, temperature=0.2,
        thinking_budget=setari.thinking_budget_evaluator,
    ))
    # datoria din 226: ce vede omul = textul trecut prin funcția care pune nota codului
    raspuns = pune_punctajul_in_rezumat(raspuns, punctaj) or ""
    date = None
    m = _JSON_REZUMAT.search(raspuns)
    if m:
        try:
            date = json.loads(m.group(1))
        except json.JSONDecodeError:
            date = None
    note = (date or {}).get("scores") if isinstance(date, dict) else None
    json_ok = isinstance(note, dict) and all(
        isinstance(note.get(k), (int, float)) and not isinstance(note.get(k), bool)
        and 1 <= note[k] <= 10 for k in _CHEI_REZUMAT)
    fara_json = _JSON_REZUMAT.sub("", raspuns)
    if punctaj == "—":
        punctaj_ok = not _NOTA_PE_10.search(fara_json)
    else:
        punctaj_ok = punctaj.split(" (")[0] in fara_json
    return {"json": json_ok, "punctaj": punctaj, "punctaj_ok": punctaj_ok, "eroare": eroare,
            "raspuns": raspuns}


# ---------------------------------------------------------------- rularea și verdictul


def amprenta(setari, comitere: str, furnizor: str) -> dict:
    return {"model_actor": setari.vertex_actor_model,
            "model_evaluator": setari.vertex_evaluator_model,
            "destinatie": setari.vertex_region, "prompt_version": CODY_PROMPT_VERSION,
            "comitere": comitere, "furnizor": furnizor}


def apeluri_planificate(doar_actor: bool, cazuri: dict | None = None) -> int:
    c = cazuri or citeste_cazurile()
    actor = (DOAR_ACTOR if doar_actor else len(c["actor"]["conversatii"])) * APELURI_PE_CONVERSATIE
    if doar_actor:
        return actor
    st_p, st_i = c["profesor_replica"]["stabilitate"], c["inchidere"]["stabilitate"]
    return (actor + 2 * len(c["profesor_replica"]["scene"])
            + len(st_p["replici"]) * st_p["repetari"]
            + len(c["inchidere"]["transcrieri"]) + len(st_i["transcrieri"]) * st_i["repetari"]
            + len(c["rezumat"]["sedinte"]))


def rulari_de_azi(dosar: Path, ziua: str) -> int:
    """Câte cazuri ale băncii s-au terminat azi, în orice jurnal din dosar (plafonul zilei)."""
    n = 0
    for f in sorted(dosar.glob("*.jsonl")):
        for linie in f.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(linie)
            except json.JSONDecodeError:
                continue
            if (d.get("tip") == "sesiune" and str(d.get("id", "")).startswith("banca:")
                    and d.get("terminata", "").startswith(ziua)):
                n += 1
    return n


class _Oprire(Exception):
    pass


async def ruleaza(furnizor, setari, scrie, *, doar_actor: bool, plafon: int,
                  amprenta_rularii: dict) -> dict:
    """Ieftin întâi; oprire la primul roșu de format sau la plafon. Întoarce verdictul."""
    cazuri, cheia = citeste_cazurile(), citeste_cheia()
    contor = Contor(furnizor, setari)
    tabel: list[dict] = []
    stare = {"apeluri": 0, "motiv": "toate cazurile sunt terminate", "format_rosu": None,
             "retea_rosu": None}

    def rand(caz, criteriu, ok, citat=""):
        tabel.append({"caz": caz, "criteriu": criteriu, "trece": bool(ok),
                      "citat": _citat(citat)})

    async def un_caz(id_caz: str, cost: int, coro_fn):
        if stare["apeluri"] + cost > plafon:
            stare["motiv"] = "oprită la plafonul de apeluri"
            raise _Oprire
        inainte = len(contor.pasi)
        t0 = time.monotonic()
        rez = await coro_fn()
        pasi = contor.pasi[inainte:]
        apeluri = len(pasi) + sum(1 for p in pasi if p.get("reluat"))
        stare["apeluri"] += apeluri
        scrie({"tip": "sesiune", "id": f"banca:{id_caz}", "mod": "banca",
               "terminata": datetime.now(UTC).isoformat(timespec="seconds"),
               "secunde": round(time.monotonic() - t0, 1), "apeluri": apeluri,
               "pasi": pasi, "amprenta": amprenta_rularii,
               "rezultat": {k: v for k, v in rez.items() if k not in ("pasi", "raspuns")}})
        retea = next((p["eroare"] for p in pasi if p.get("retea")), None)
        if retea:
            stare["retea_rosu"] = f"{id_caz}: {retea}"
            stare["motiv"] = "oprită la roșu de rețea"
            raise _Oprire
        return rez

    def rosu_de_format(caz, ce):
        stare["format_rosu"] = f"{caz}: {ce}"
        stare["motiv"] = "oprită la primul roșu de format"
        raise _Oprire

    actor_ok: dict[str, bool] = {}
    profesor: dict[str, dict] = {}
    stab_p: dict[str, list[float]] = {}
    inchidere: dict[str, dict] = {}
    stab_i: dict[str, list[dict]] = {}
    rezumate: dict[str, dict] = {}
    conversatii = cazuri["actor"]["conversatii"][: DOAR_ACTOR if doar_actor else None]
    try:
        for caz in conversatii:
            r = await un_caz(f"actor:{caz['id']}", APELURI_PE_CONVERSATIE,
                             lambda caz=caz: conversatie_actor(contor, setari, caz,
                                                               cazuri["actor"]["salut"]))
            for nume, (ok, citat) in r["criterii"].items():
                rand(caz["id"], nume, ok, citat)
            actor_ok[caz["id"]] = all(ok for ok, _ in r["criterii"].values())
            if r["format_rosu"]:
                rosu_de_format(caz["id"], "actorul n-a răspuns (poarta 1)")
        if not doar_actor:
            for scena in cazuri["profesor_replica"]["scene"]:
                for lit in ("a", "b"):
                    idr = f"{scena['id']}-{lit}"
                    r = await un_caz(f"profesor:{idr}", 1, lambda s=scena, x=scena[lit]:
                                     replica_profesor(contor, setari, s, x))
                    profesor[idr] = r
                    if r["scor"] is None:
                        rand(idr, "format (Scor: N/10)", False, r["eroare"] or r["raspuns"])
                        rosu_de_format(idr, "profesorul n-a dat nota")
                    fel = cheia["profesor_replica"][idr]
                    ok = (r["scor"] >= PRAGURI["scor_bun"] if fel == "bun"
                          else r["scor"] <= PRAGURI["scor_slab"])
                    rand(idr, f"nota {fel}", ok, f"{r['scor']:g}/10")
                    for p, v in r["porti"].items():
                        if v["instante"]:
                            rand(idr, f"poarta {p}", not v["picate"],
                                 v["picate"][0] if v["picate"] else "")
            scene = {s["id"]: s for s in cazuri["profesor_replica"]["scene"]}
            st = cazuri["profesor_replica"]["stabilitate"]
            for idr in st["replici"]:
                stab_p[idr] = [profesor[idr]["scor"]]
                for k in range(st["repetari"]):
                    scena = scene[idr.split("-")[0]]
                    r = await un_caz(f"profesor-stabil:{idr}:{k + 1}", 1, lambda s=scena, i=idr:
                                     replica_profesor(contor, setari, s, s[i.split("-")[1]]))
                    if r["scor"] is None:
                        rosu_de_format(idr, "profesorul n-a dat nota (stabilitate)")
                    stab_p[idr].append(r["scor"])
            for t in cazuri["inchidere"]["transcrieri"]:
                r = await un_caz(f"inchidere:{t['id']}", 1,
                                 lambda t=t: transcriere_inchidere(contor, setari, t))
                inchidere[t["id"]] = r
                rand(t["id"], "format (JSON + scor 0–100 pe fiecare competență)", r["format"],
                     r["motiv"])
                if not r["format"]:
                    rosu_de_format(t["id"], "închiderea fără format")
                # plicul 224: banda din competențele notate; la cazurile din
                # `inchidere_neevaluat_permis` (I07, I08), toate neevaluate = trece
                permise = set(cheia.get("inchidere_neevaluat_permis", {}).get(t["id"], []))
                toate_neev = (r["banda"] is None and bool(r["neevaluate"])
                              and set(r["neevaluate"]) == set(t["competente"]))
                ok = r["banda"] == cheia["inchidere"][t["id"]] or (
                    toate_neev and set(r["neevaluate"]) <= permise)
                rand(t["id"], f"banda {cheia['inchidere'][t['id']]}", ok,
                     "toate neevaluate" if toate_neev else f"banda {r['banda']}")
                inchidere[t["id"]]["banda_ok"] = ok
                if r["neevaluate"]:
                    rand(t["id"], "neevaluate (numărate)", True, ", ".join(r["neevaluate"]))
            trans = {t["id"]: t for t in cazuri["inchidere"]["transcrieri"]}
            st = cazuri["inchidere"]["stabilitate"]
            for idt in st["transcrieri"]:
                stab_i[idt] = [inchidere[idt]["scoruri"]]
                for k in range(st["repetari"]):
                    r = await un_caz(f"inchidere-stabil:{idt}:{k + 1}", 1, lambda t=trans[idt]:
                                     transcriere_inchidere(contor, setari, t))
                    if not r["format"]:
                        rosu_de_format(idt, "închiderea fără format (stabilitate)")
                    stab_i[idt].append(r["scoruri"])
            for s in cazuri["rezumat"]["sedinte"]:
                r = await un_caz(f"rezumat:{s['id']}", 1,
                                 lambda s=s: sedinta_rezumat(contor, setari, s))
                rezumate[s["id"]] = r
                rand(s["id"], "JSON valid (4 note 1–10)", r["json"], r["eroare"] or "")
                if not r["json"]:
                    rosu_de_format(s["id"], "rezumatul fără JSON valid")
                rand(s["id"], "punctajul codului, exact", r["punctaj_ok"], r["punctaj"])
    except _Oprire:
        pass

    verdict = _verdict(doar_actor, cazuri, cheia, stare, actor_ok, profesor, stab_p,
                       inchidere, stab_i, rezumate)
    return {"tip": "verdict", "verdict": verdict["verdict"], "criterii": verdict["criterii"],
            "motiv": stare["motiv"], "format_rosu": stare["format_rosu"],
            "retea_rosu": stare["retea_rosu"], "apeluri": stare["apeluri"],
            "cost_usd": float(contor.cost),
            "raspunsuri_retinute": contor.retinute, "amprenta": amprenta_rularii,
            "tabel": tabel}


def _verdict(doar_actor, cazuri, cheia, stare, actor_ok, profesor, stab_p, inchidere, stab_i,
             rezumate) -> dict:
    P = PRAGURI
    crit: dict[str, dict] = {}

    def pune(nume, valoare, prag, ok):
        crit[nume] = {"valoare": valoare, "prag": prag, "trece": bool(ok)}

    complet = (stare["format_rosu"] is None and stare["retea_rosu"] is None
               and stare["motiv"].startswith("toate"))
    pune("rulare completă, fără roșu de format", stare["motiv"], "toate cazurile", complet)
    trec = sum(actor_ok.values())
    if doar_actor:
        pune("actor: conversații care trec tot", f"{trec}/{len(actor_ok)}",
             f"≥ {P['actor_doar_actor_min']}", trec >= P["actor_doar_actor_min"])
    else:
        pune("actor: conversații care trec tot", f"{trec}/{len(actor_ok)}",
             f"≥ {P['actor_conversatii_min']}", trec >= P["actor_conversatii_min"])
    ai = [c["id"] for c in cazuri["actor"]["conversatii"] if c["fel"] == "ești AI?"]
    pune("actor: „ești AI?” rămâne în rol", [actor_ok.get(i) for i in ai], "trece",
         all(actor_ok.get(i) for i in ai))
    if not doar_actor:
        bune = [r["scor"] for i, r in profesor.items()
                if cheia["profesor_replica"][i] == "bun" and r["scor"] is not None]
        slabe = [r["scor"] for i, r in profesor.items()
                 if cheia["profesor_replica"][i] == "slab" and r["scor"] is not None]
        nb = sum(s >= P["scor_bun"] for s in bune)
        ns = sum(s <= P["scor_slab"] for s in slabe)
        pune("profesor: bune ≥ 8/10", f"{nb}/12", f"≥ {P['profesor_bune_min']}",
             nb >= P["profesor_bune_min"])
        pune("profesor: slabe ≤ 5/10", f"{ns}/12", f"≥ {P['profesor_slabe_min']}",
             ns >= P["profesor_slabe_min"])
        perechi = sum(
            1 for s in cazuri["profesor_replica"]["scene"]
            if (profesor.get(f"{s['id']}-a") or {}).get("scor") is not None
            and (profesor.get(f"{s['id']}-b") or {}).get("scor") is not None
            and profesor[f"{s['id']}-a"]["scor"] - profesor[f"{s['id']}-b"]["scor"]
            >= P["diferenta_pereche"])
        pune("profesor: perechi bună − slabă ≥ 3", f"{perechi}/12", f"≥ {P['perechi_min']}",
             perechi >= P["perechi_min"])
        for p in PORTI_PROFESOR:
            inst = sum(r["porti"].get(p, {}).get("instante", 0) for r in profesor.values())
            tr = sum(r["porti"].get(p, {}).get("trecute", 0) for r in profesor.values())
            pune(f"profesor: poarta {p}", f"{tr}/{inst}", f"≥ {P['porti_profesor_procent']}%",
                 inst == 0 or tr * 100 >= P["porti_profesor_procent"] * inst)
        var_p = max((max(v) - min(v) for v in stab_p.values() if v), default=None)
        pune("profesor: stabilitate (max − min)", var_p, f"≤ {P['stabilitate_replica_max']}",
             var_p is not None and var_p <= P["stabilitate_replica_max"])
        benzi = sum(1 for r in inchidere.values() if r.get("banda_ok"))
        pune("închidere: banda", f"{benzi}/8", f"≥ {P['inchidere_banda_min']}",
             benzi >= P["inchidere_banda_min"])
        pune("închidere: format", f"{sum(r['format'] for r in inchidere.values())}/8", "8/8",
             len(inchidere) == 8 and all(r["format"] for r in inchidere.values()))
        nr_neev = sum(len(r["neevaluate"]) for r in inchidere.values())
        pune("închidere: neevaluate (numărate)",
             f"{nr_neev} ({', '.join(i for i, r in inchidere.items() if r['neevaluate'])})",
             "se numără; „de confirmat la etalon (Andrei)”", True)
        # plicul 224: o competență neevaluată într-o repetare se sare și se raportează
        var_i, sarite = None, 0
        for rulari in stab_i.values():
            for c in sorted({c for r in rulari for c in r}):
                valori = [r[c] for r in rulari if c in r]
                sarite += len(rulari) - len(valori)
                var_i = max(var_i or 0, max(valori) - min(valori))
        pune("închidere: stabilitate (max − min)",
             var_i if not sarite else f"{var_i} (sărite: {sarite})",
             f"≤ {P['stabilitate_inchidere_max']}",
             var_i is not None and var_i <= P["stabilitate_inchidere_max"])
        nr_rez = sum(r["json"] and r["punctaj_ok"] for r in rezumate.values())
        pune("rezumat: JSON + punctajul codului", f"{nr_rez}/4", f"≥ {P['rezumat_min']}",
             nr_rez >= P["rezumat_min"])
    return {"verdict": "TRECE" if all(c["trece"] for c in crit.values()) else "PICĂ",
            "criterii": crit}


def tabel_markdown(verdict: dict) -> str:
    linii = [f"# Banca de probă — VERDICT: {verdict['verdict']}", "",
             f"Amprenta: `{json.dumps(verdict['amprenta'], ensure_ascii=False)}`",
             f"Apeluri: {verdict['apeluri']} · cost: {verdict.get('cost_usd', 0):.4f} $ · "
             f"{verdict['motiv']}"
             + (f" · roșu de format: {verdict['format_rosu']}" if verdict["format_rosu"] else "")
             + (f" · roșu de rețea: {verdict['retea_rosu']}" if verdict.get("retea_rosu") else "")
             + (f" · răspunsuri reținute (nume): {verdict['raspunsuri_retinute']}"
                if verdict.get("raspunsuri_retinute") else ""),
             "", "| criteriu | valoare | prag | trece |", "|---|---|---|---|"]
    linii += [f"| {n} | {c['valoare']} | {c['prag']} | {'da' if c['trece'] else 'NU'} |"
              for n, c in verdict["criterii"].items()]
    linii += ["", "| caz | criteriu | trece / pică | citat scurt |", "|---|---|---|---|"]
    linii += [f"| {r['caz']} | {r['criteriu']} | {'trece' if r['trece'] else 'PICĂ'} | "
              f"{r['citat'].replace('|', '/')} |" for r in verdict["tabel"]]
    return "\n".join(linii) + "\n"


class _Masoara:
    """Cererile băncii, construite exact ca la rulare, cu răspunsurile furnizorului fals „bun”.
    Nu cheamă nimic: `_text` e o funcție pură a furnizorului fals."""

    def __init__(self) -> None:
        self._fals = FurnizorFals("bun")
        self.cereri: list[GenerationRequest] = []

    async def generate(self, cerere: GenerationRequest) -> GenerationResult:
        self.cereri.append(cerere)
        return GenerationResult(
            text=self._fals._text(cerere), usage=TokenUsage(), provider=GenerationProviderKey.local,
            model="masurare", region="masurare", finish_reason="STOP", estimated_usd=Decimal("0"))


def preturile(setari) -> dict[str, dict[str, float]]:
    """Cele patru prețuri pe milion folosite de `estimate_cost`, pe modelele rulării."""
    m = 1_000_000
    rez = {}
    for model in dict.fromkeys((setari.vertex_actor_model, setari.vertex_evaluator_model)):
        def pret(u: TokenUsage, model=model) -> float:
            return float(estimate_cost(u, setari, model=model))
        rez[model] = {"intrare": pret(TokenUsage(prompt_tokens=m)),
                      "din_cache": pret(TokenUsage(prompt_tokens=m, cached_tokens=m)),
                      "iesire": pret(TokenUsage(output_tokens=m)),
                      "gandire": pret(TokenUsage(thought_tokens=m))}
    return rez


async def cost_maxim(setari, *, doar_actor: bool) -> dict:
    """Costul cel mai mare posibil, înainte de primul apel (plicul 227, corecția 5).

    Fiecare cerere a rulării se construiește ca la rulare (0 apeluri), se numără caracterele
    (÷ `CARACTERE_PE_UNITATE`), iar la actor se adaugă, pe fiecare replică a lui din istoric,
    tot plafonul de ieșire (răspunsurile adevărate sunt mai lungi decât cele false). Ieșirea =
    plafonul cererii, gândirea = bugetul cererii, cache 0. Reluările la rețea nu se socotesc.
    """
    masoara = _Masoara()
    await ruleaza(masoara, setari, lambda _r: None, doar_actor=doar_actor, plafon=10**6,
                  amprenta_rularii={})
    total = Decimal("0")
    pe_model: dict[str, Decimal] = {}
    for c in masoara.cereri:
        caractere = len(c.system_instruction or "") + sum(len(m.text) for m in c.messages)
        intrat = math.ceil(caractere / CARACTERE_PE_UNITATE)
        if c.purpose == GenerationPurpose.actor:
            ale_lui = sum(1 for m in c.messages if m.role == "model") - 2  # fără salut și scenă
            intrat += max(0, ale_lui) * c.max_output_tokens
        model = _modelul_cererii(setari, c)
        cost = estimate_pessimistic_cost(intrat, c.max_output_tokens, c.thinking_budget or 0,
                                         setari, model=model)
        total += cost
        pe_model[model] = pe_model.get(model, Decimal("0")) + cost
    return {"apeluri": len(masoara.cereri), "usd": float(total),
            "pe_model": {k: float(v) for k, v in pe_model.items()}}


def _sub_masuratori(cale: Path) -> bool:
    return "MASURATORI" in cale.resolve().parts or "MASURATORI" in cale.parts


def _opriri_pe_bune(a, reale) -> list[str]:
    """Plicul 224 §1.2 (corecția 5): la `--pe-bune` rularea nu pleacă pe setări nepotrivite."""
    opriri = []
    if reale.generation_provider != "vertex":
        opriri.append(f"generation_provider = {reale.generation_provider}, nu vertex")
    if not a.comitere:
        opriri.append("--comitere lipsește")
    if not a.model_evaluator:
        opriri.append("--model-evaluator e obligatoriu la --pe-bune")
    if not a.alt_model:
        if a.model and a.model != reale.vertex_actor_model:
            opriri.append(f"--model {a.model} ≠ setările ({reale.vertex_actor_model})")
        if a.model_evaluator and a.model_evaluator != reale.vertex_evaluator_model:
            opriri.append(f"--model-evaluator {a.model_evaluator} ≠ setările "
                          f"({reale.vertex_evaluator_model})")
    if not a.jurnal:
        opriri.append("--jurnal e obligatoriu la --pe-bune")
    return opriri


async def main(argv: list[str] | None = None) -> int:
    reale = get_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    fel = ap.add_mutually_exclusive_group()
    fel.add_argument("--doar-actor", action="store_true", help="4 conversații, 16 apeluri")
    fel.add_argument("--banca", action="store_true", help="tot (implicit)")
    ap.add_argument("--pe-bune", action="store_true",
                    help="cheamă modelul adevărat; fără el, furnizorul fals (0 apeluri)")
    ap.add_argument("--furnizor-fals", choices=("bun", "stricat"), default="bun")
    ap.add_argument("--jurnal", type=Path,
                    help="fișierul JSONL al rulării (fals: implicit /tmp/banca-fals)")
    ap.add_argument("--plafon-apeluri", type=int, default=160)
    ap.add_argument("--plafon-dolari", type=Decimal, default=None,
                    help="oprire înainte de primul apel dacă costul maxim îl depășește "
                         f"(implicit {PLAFON_DOLARI_PE_BUNE} la --pe-bune; "
                         "la fals numai dacă e dat)")
    ap.add_argument("--peste-plafon", action="store_true",
                    help="a doua rulare în aceeași zi")
    ap.add_argument("--comitere", default=None, help="obligatoriu la --pe-bune")
    ap.add_argument("--model", default=None, help="implicit: modelul actorului din setări")
    ap.add_argument("--model-evaluator", default=None,
                    help="modelul profesorului; obligatoriu la --pe-bune")
    ap.add_argument("--alt-model", action="store_true",
                    help="modele diferite de setări, cu bună știință (al doilea motor, S3)")
    ap.add_argument("--destinatie", default=reale.vertex_region)
    ap.add_argument("--verifica-nume", action="store_true",
                    help="numai poarta de nume pe fișierele de cazuri")
    a = ap.parse_args(argv)
    if a.verifica_nume:
        gasite = nume_in_cazuri()
        print(json.dumps(gasite, ensure_ascii=False))
        return 3 if any(gasite.values()) else 0
    if a.pe_bune:
        opriri = _opriri_pe_bune(a, reale)
        if opriri:
            for o in opriri:
                print(f"OPRESC: {o}", file=sys.stderr)
            return 2
    else:
        if a.jurnal is not None and _sub_masuratori(a.jurnal):
            print("OPRESC: o rulare falsă nu scrie în MASURATORI (implicit /tmp/banca-fals/)",
                  file=sys.stderr)
            return 2
        if a.jurnal is None:
            momentul = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
            a.jurnal = DOSAR_FALS / f"banca-fals-{a.furnizor_fals}-{momentul}.jsonl"
    ziua = datetime.now(UTC).date().isoformat()
    if a.jurnal.parent.exists() and rulari_de_azi(a.jurnal.parent, ziua) and not a.peste_plafon:
        print(f"OPRESC: banca a mai rulat azi ({ziua}); a doua rulare cere --peste-plafon",
              file=sys.stderr)
        return 4
    model = a.model or reale.vertex_actor_model
    setari = reale.model_copy(update={
        "vertex_actor_model": model,
        "vertex_evaluator_model": a.model_evaluator or reale.vertex_evaluator_model,
        "vertex_region": a.destinatie,
    })
    maxim = await cost_maxim(setari, doar_actor=a.doar_actor)
    plafon_usd = a.plafon_dolari if a.plafon_dolari is not None else (
        PLAFON_DOLARI_PE_BUNE if a.pe_bune else None)
    print(f"COST MAXIM: {maxim['usd']:.4f} $ pentru {maxim['apeluri']} apeluri "
          f"(plafon: {plafon_usd if plafon_usd is not None else '—'} $)", file=sys.stderr)
    if plafon_usd is not None and Decimal(str(maxim["usd"])) > plafon_usd:
        print(f"OPRESC: costul maxim {maxim['usd']:.4f} $ depășește plafonul de {plafon_usd} $ "
              "(--plafon-dolari)", file=sys.stderr)
        return 5
    scrie = Iesire(a.jurnal)
    client = None
    if a.pe_bune:
        import httpx

        client = httpx.AsyncClient(timeout=float(setari.vertex_timeout_seconds))
        furnizor = PaznicDeNume(build_generation_provider(setari, client=client),
                                await _numele_conturilor_de_proba())
        cine = setari.generation_provider
    else:
        furnizor = PaznicDeNume(FurnizorFals(a.furnizor_fals), [])
        cine = f"fals:{a.furnizor_fals}"
    amp = amprenta(setari, a.comitere or "necunoscută", cine)
    planificat = apeluri_planificate(a.doar_actor)
    scrie({"tip": "cap", "amprenta": amp,
           "setari": {"model_actor": reale.vertex_actor_model,
                      "model_evaluator": reale.vertex_evaluator_model,
                      "generation_provider": reale.generation_provider},
           "alt_model": a.alt_model, "plafon_apeluri": a.plafon_apeluri,
           "apeluri_planificate": planificat, "doar_actor": a.doar_actor,
           "preturi": preturile(setari), "cost_maxim_usd": maxim["usd"],
           "cost_maxim_pe_model": maxim["pe_model"],
           "plafon_dolari": float(plafon_usd) if plafon_usd is not None else None,
           "inceput": datetime.now(UTC).isoformat(timespec="seconds")})
    try:
        verdict = await ruleaza(furnizor, setari, scrie, doar_actor=a.doar_actor,
                                plafon=a.plafon_apeluri, amprenta_rularii=amp)
    finally:
        if client is not None:
            await client.aclose()
    verdict["nume_trimise"] = furnizor.gasite
    scrie(verdict)
    a.jurnal.with_suffix(".md").write_text(tabel_markdown(verdict), encoding="utf-8")
    if furnizor.gasite:
        return 3
    return 0 if verdict["verdict"] == "TRECE" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
