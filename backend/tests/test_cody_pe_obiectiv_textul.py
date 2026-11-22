"""Textele lui Cody pe obiectiv — plicul 244, aprobate de Andrei ([l1-p3-text], 21 nov 10:21).

Cele două fișiere sunt blocurile din `SPEC-CODY/FISE/L1-P3-text-propus.md` (amprenta fișei
`852baba9…`), scoase programatic, octet cu octet (poarta J0). Nimeni nu le reformulează: orice
schimbare a lor schimbă amprenta de aici și cere „da”-ul lui Andrei.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

PROMPTS = (
    Path(__file__).resolve().parents[1] / "src" / "codrut" / "modules" / "practice" / "prompts"
)

AMPRENTA_OBIECTIV_ACTOR = "677aefb6df5dcc68fe378d85fcec9992f1cdfc8d815bf5f5ab35f9351d1024c8"
AMPRENTA_OBIECTIV_PROFESOR = "3acdc60c070dd79e3b33d52e01ceea305bbf189f310796fcbc7139feea6b4898"
# `actor.md` nu se atinge de plicul 244 (aceeași valoare ca în paza lui); plicul 249 i-a adăugat
# propoziția aprobată [esti-ai-fara-glume] la final
AMPRENTA_ACTOR_MD_AZI = "e0bb998ce837bc24f51ca507cb9334aa1e2d3f581ed48f0d5ebc5c9b06cf43a4"


def _sha(cale: Path) -> str:
    return hashlib.sha256(cale.read_bytes()).hexdigest()


def test_textele_au_amprentele_aprobate() -> None:
    assert _sha(PROMPTS / "obiectiv-actor.md") == AMPRENTA_OBIECTIV_ACTOR
    assert _sha(PROMPTS / "obiectiv-profesor.md") == AMPRENTA_OBIECTIV_PROFESOR


def test_locurile_de_completat_sunt_exact_cele_din_plic() -> None:
    actor = (PROMPTS / "obiectiv-actor.md").read_text(encoding="utf-8")
    profesor = (PROMPTS / "obiectiv-profesor.md").read_text(encoding="utf-8")
    assert re.findall(r"\{[^}]*\}", actor) == ["{titlu}", "{situatie}"]
    assert re.findall(r"\{[^}]*\}", profesor) == ["{titlu}", "{semn_de_reusita}"]
    for text in (actor, profesor):
        assert text.count("{") == text.count("}") == len(re.findall(r"\{[^}]*\}", text))
        assert not re.search("[şţŞŢ]", text)
        assert text.endswith("\n") and not text.endswith("\n\n")


def test_textele_se_citesc_din_fisiere() -> None:
    from codrut.modules.practice.prompts import OBIECTIV_ACTOR, OBIECTIV_PROFESOR

    assert OBIECTIV_ACTOR == (PROMPTS / "obiectiv-actor.md").read_text(encoding="utf-8").strip()
    assert OBIECTIV_PROFESOR == (
        (PROMPTS / "obiectiv-profesor.md").read_text(encoding="utf-8").strip()
    )


def test_actor_md_neschimbat() -> None:
    from test_promptul_de_la_un_apel_nu_se_atinge import AMPRENTA_ACTOR_MD

    assert AMPRENTA_ACTOR_MD == AMPRENTA_ACTOR_MD_AZI
    assert _sha(PROMPTS / "actor.md") == AMPRENTA_ACTOR_MD_AZI
