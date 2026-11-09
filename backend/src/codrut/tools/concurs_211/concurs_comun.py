"""Concursul modelelor, plicul 211: partea comună a scripturilor de variantă.

Scriptul de variantă pornește prin `--prin-scriptul` din unealta de pe Mac. Fixează varianta
ÎNAINTE de `get_settings()`, cronometrează fiecare apel și apoi cheamă unealta neschimbată.
Aplicația nu se atinge; totul trăiește în procesul uneltei.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any


class Cronometru:
    """Stă în fața furnizorului și ține cât a durat fiecare apel, pe meserii."""

    def __init__(self, furnizor: Any) -> None:
        self._furnizor = furnizor
        self.apeluri: list[dict[str, Any]] = []
        self.serie_429 = False

    async def generate(self, cerere: Any) -> Any:
        rand = {"meserie": cerere.purpose.value, "text": cerere.messages[-1].text, "eroare": None}
        t0 = time.monotonic()
        try:
            return await self._furnizor.generate(cerere)
        except Exception as err:
            rand["eroare"] = getattr(err, "code", None) or type(err).__name__
            # Furnizorul renunță abia după trei 429 la rând.
            self.serie_429 = self.serie_429 or rand["eroare"] == "vertex_rate_limited"
            raise
        finally:
            rand["secunde"] = round(time.monotonic() - t0, 2)
            self.apeluri.append(rand)

    def scoate(self, meserie: str, text: str | None, deschidere: str) -> dict[str, Any] | None:
        """Scoate apelul pasului: actorul primește textul întreg, evaluatorul îl are la capăt."""
        for i, rand in enumerate(self.apeluri):
            if rand["meserie"] != meserie:
                continue
            potrivit = rand["text"] == deschidere if text is None else rand["text"].endswith(text)
            if potrivit:
                return self.apeluri.pop(i)
        return None


def ruleaza(varianta: str, actor: str, evaluator: str, gandire_evaluator: int) -> None:
    os.environ["CODRUT_VERTEX_ACTOR_MODEL"] = actor
    os.environ["CODRUT_VERTEX_EVALUATOR_MODEL"] = evaluator
    os.environ["CODRUT_THINKING_BUDGET_EVALUATOR"] = str(gandire_evaluator)
    sys.path.insert(0, "/app/src")

    from codrut.core.config import get_settings
    from codrut.modules.practice.service import DESCHIDE_SESIUNEA
    from codrut.tools import probe_automate as pa

    reale = get_settings()
    stare: dict[str, Any] = {"cron": None, "iesire": None, "facute": 0, "apeluri": 0}
    construieste = pa.build_generation_provider

    def furnizor_cronometrat(setari: Any, client: Any = None) -> Cronometru:
        stare["cron"] = Cronometru(construieste(setari, client=client))
        return stare["cron"]

    class IesireCuVarianta(pa.Iesire):
        def __init__(self, jurnal: Any) -> None:
            super().__init__(jurnal)
            stare["iesire"] = self

        def __call__(self, obiect: dict) -> None:
            if obiect.get("tip") == "cap":
                obiect.update(
                    varianta=varianta,
                    actor=reale.vertex_actor_model,
                    evaluator=reale.vertex_evaluator_model,
                    thinking_budget_actor=reale.thinking_budget_actor,
                    thinking_budget_evaluator=reale.thinking_budget_evaluator,
                )
            super().__call__(obiect)

    o_sesiune = pa.o_sesiune

    async def sesiune_cronometrata(furnizor, setari, numarator, mod, nr, doua=False):
        cron = stare["cron"]
        if cron.serie_429:
            stare["iesire"]({
                "tip": "sfarsit", "motiv": "oprita curat: 429 in serie",
                "sesiuni_facute": stare["facute"], "sesiuni_cerute": 5,
                "sfarsit_la": datetime.now(UTC).isoformat(timespec="seconds"),
                "apeluri": stare["apeluri"],
                "http": {str(k): v for k, v in sorted(numarator.coduri.items())},
            })
            raise SystemExit(4)
        rezultat = await o_sesiune(furnizor, setari, numarator, mod, nr, doua=doua)
        for pas in rezultat["pasi"]:
            ale_actorului = cron.scoate("actor", pas["om"], DESCHIDE_SESIUNEA)
            ale_evaluatorului = cron.scoate("evaluator", pas["om"], DESCHIDE_SESIUNEA)
            pas["timp"] = {
                "actor": ale_actorului and ale_actorului["secunde"],
                "evaluator": ale_evaluatorului and ale_evaluatorului["secunde"],
                "eroare_actor": ale_actorului and ale_actorului["eroare"],
                "eroare_evaluator": ale_evaluatorului and ale_evaluatorului["eroare"],
            }
            if pas["apel_actor"] and ale_actorului:
                pas["apel_actor"]["secunde"] = ale_actorului["secunde"]
            if pas["apel_evaluator"] and ale_evaluatorului:
                pas["apel_evaluator"]["secunde"] = ale_evaluatorului["secunde"]
        stare["facute"] += 1
        stare["apeluri"] += rezultat["apeluri"]
        return rezultat

    pa.build_generation_provider = furnizor_cronometrat
    pa.Iesire = IesireCuVarianta
    pa.o_sesiune = sesiune_cronometrata
    # ultimele câștigă la argparse, deci varianta o fixează scriptul, nu comanda
    argv = [*sys.argv[1:], "--model", actor, "--model-evaluator", evaluator]
    sys.exit(asyncio.run(pa.main(argv)))
