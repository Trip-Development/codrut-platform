"""Pragurile copiate în ecran trebuie să fie ale serverului — plicul 177 (riscul 3 al lui 175).

`frontend/src/lib/praguri-puncte.ts` ține o copie a constantelor din `scoring.py` (barele de pe
Tablou, mesajul „încă X până la primele puncte”). Dacă una se schimbă fără cealaltă, ecranul ar
minți în tăcere. Se rulează din depozitul întreg (CI face checkout cu tot); fără fișier, testul
PICĂ — un „skip” ar face plasa inutilă.
"""

from __future__ import annotations

import re
from pathlib import Path

from codrut.modules.practice import scoring

FISIER = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "praguri-puncte.ts"


def test_pragurile_din_ecran_sunt_ale_serverului() -> None:
    assert FISIER.is_file(), f"lipsește {FISIER} — testul cere depozitul întreg (și frontend/)"
    text = FISIER.read_text(encoding="utf-8")
    valori = {m[1]: int(m[2]) for m in re.finditer(r"export const (\w+) = (\d+);", text)}
    for nume in ("NOTA_MINIMA", "PRAG_APLICARE", "PRAG_CONSOLIDARE", "PRAG_INTEGRARE"):
        assert nume in valori, f"{nume} lipsește din {FISIER.name}"
        server = getattr(scoring, nume)
        assert valori[nume] == server, f"{nume}: ecranul {valori[nume]}, serverul {server}"
