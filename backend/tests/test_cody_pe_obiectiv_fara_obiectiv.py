"""Paza principală a plicului 244: fără obiectiv, instrucțiunile sunt octet cu octet cele de azi.

Amprentele de mai jos (`AMPRENTE`) au fost calculate pe baza `9d3ea9c` (vârful plicului 240),
ÎNAINTE de orice schimbare (pasul A0, `.audit/cody-plic244/raw/A0-amprente-azi.txt`), cu
generatorul `_cazurile` din acest fișier. Chemarea fără argumentul nou și chemarea cu
`obiectiv=None` trebuie să dea exact aceleași șiruri.

Pe serviciu: o sesiune pornită fără `pe_obiectiv` (salut → „Da, hai.” → 2 replici, pe ambele
drumuri) nu trimite nimic din textele obiectivului, iar competența țintă (plicul 165) se
calculează ca azi.
"""

from __future__ import annotations

import hashlib
import os
import re

import pytest

BIBLIOTECA = os.environ.get("BIBLIOTECA_PATH", "")

PROFILURI = {
    "gol": None,
    "conduce": {"conduce_oameni": True, "nr_roleplay_anterioare": 1, "nr_sesiuni_anterioare": 2},
    "nu_conduce": {
        "conduce_oameni": False, "nr_roleplay_anterioare": 2, "nr_sesiuni_anterioare": 1,
    },
}
MEMORII = {
    "fara": None,
    "cu": [{
        "created_at": "2026-11-01T10:00:00",
        "relevance_score": 90,
        "relevant_competencies": ["Ascultare activă"],
        "personal_context": {"role": "coordonator", "team_size": "6"},
        "evolution_signals": {"progress": "pune întrebări înainte să răspundă"},
    }],
}
COMPETENTE_TINTA = {"fara": None, "ascultare": "Ascultare activă"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cazurile(**extra) -> list[tuple[str, str]]:
    """Toate ieșirile măsurate la A0. `extra` (de ex. `obiectiv=None`) merge numai la cele trei
    funcții care primesc parametrul nou."""
    from codrut.modules.practice.prompts import (
        bloc_de_distributie,
        get_prompts_pe_meserii,
        get_system_prompt_for_kind,
        regula_setupului_la_doua_apeluri,
    )

    out: list[tuple[str, str]] = []
    for kind in ("roleplay", "knowledge", "coaching"):
        for hl in range(5):
            for mem_k, mem in MEMORII.items():
                for prof_k, prof in PROFILURI.items():
                    text = get_system_prompt_for_kind(
                        kind,
                        name="Fox 34",
                        history_length=hl,
                        quiz_competency="mix" if kind == "knowledge" else None,
                        project_competencies=["Ascultare activă", "Feedback asertiv"],
                        memories=mem,
                        biblioteca_path=BIBLIOTECA,
                        profil_rol=prof,
                        **extra,
                    )
                    out.append((f"sys|{kind}|{hl}|{mem_k}|{prof_k}", text))
    for hl in range(5):
        for mem_k, mem in MEMORII.items():
            for tinta_k, tinta in COMPETENTE_TINTA.items():
                for prof_k, prof in PROFILURI.items():
                    actor, profesor = get_prompts_pe_meserii(
                        name="Fox 34",
                        history_length=hl,
                        memories=mem,
                        biblioteca_path=BIBLIOTECA,
                        profil_rol=prof,
                        competenta_tinta=tinta,
                        **extra,
                    )
                    cheie = f"{hl}|{mem_k}|{tinta_k}|{prof_k}"
                    out.append((f"actor|{cheie}", actor))
                    out.append((f"profesor|{cheie}", profesor))
    for prof_k, prof in PROFILURI.items():
        out.append((f"distributie|{prof_k}", bloc_de_distributie(prof, "Ion")))
        for tinta_k, tinta in COMPETENTE_TINTA.items():
            out.append((
                f"setup|{prof_k}|{tinta_k}",
                regula_setupului_la_doua_apeluri(prof, "Fox 34", tinta),
            ))
    return out


# --- A0, baza 9d3ea9c (lipite din raw/A0-amprente-azi.txt) ---
AMPRENTE: dict[str, str] = {
    "sys|roleplay|0|fara|gol":
        "e550a584d06531414ed9444442748e6bc548225f70fc9198bade3b7711a852ad",
    "sys|roleplay|0|fara|conduce":
        "e550a584d06531414ed9444442748e6bc548225f70fc9198bade3b7711a852ad",
    "sys|roleplay|0|fara|nu_conduce":
        "e550a584d06531414ed9444442748e6bc548225f70fc9198bade3b7711a852ad",
    "sys|roleplay|0|cu|gol":
        "b5fec8b9bb7c49de9ceb7037d4aa0b36ff4b2e664320182a9dfe93f5150b9ef0",
    "sys|roleplay|0|cu|conduce":
        "b5fec8b9bb7c49de9ceb7037d4aa0b36ff4b2e664320182a9dfe93f5150b9ef0",
    "sys|roleplay|0|cu|nu_conduce":
        "b5fec8b9bb7c49de9ceb7037d4aa0b36ff4b2e664320182a9dfe93f5150b9ef0",
    "sys|roleplay|1|fara|gol":
        "e550a584d06531414ed9444442748e6bc548225f70fc9198bade3b7711a852ad",
    "sys|roleplay|1|fara|conduce":
        "e550a584d06531414ed9444442748e6bc548225f70fc9198bade3b7711a852ad",
    "sys|roleplay|1|fara|nu_conduce":
        "e550a584d06531414ed9444442748e6bc548225f70fc9198bade3b7711a852ad",
    "sys|roleplay|1|cu|gol":
        "b5fec8b9bb7c49de9ceb7037d4aa0b36ff4b2e664320182a9dfe93f5150b9ef0",
    "sys|roleplay|1|cu|conduce":
        "b5fec8b9bb7c49de9ceb7037d4aa0b36ff4b2e664320182a9dfe93f5150b9ef0",
    "sys|roleplay|1|cu|nu_conduce":
        "b5fec8b9bb7c49de9ceb7037d4aa0b36ff4b2e664320182a9dfe93f5150b9ef0",
    "sys|roleplay|2|fara|gol":
        "7e291c97739c0000780a9690ed6b1474aa96dab0402c1670f8fcf8dec41c9088",
    "sys|roleplay|2|fara|conduce":
        "cbc7e65748f2342213cda6dbea53b73a790be1364b9d8904586bd3d3ef8b5752",
    "sys|roleplay|2|fara|nu_conduce":
        "183bfa858c49e7c3168f635ca2ffeb6cb7d50ef8f844fa1135a6ce7c12a48efe",
    "sys|roleplay|2|cu|gol":
        "7ab4d34feb423f9cefb6314b8bc4945b7a096b76f3522881c52da1707b9af5e6",
    "sys|roleplay|2|cu|conduce":
        "3b40df191dc15fef1bc4810a114ce8b34c2298d6ebab6e0a1f853065275eda77",
    "sys|roleplay|2|cu|nu_conduce":
        "9dd591d9a8b4e842712f43857374f3bf29d44e6e6c00c3d238c6cdd9805c2992",
    "sys|roleplay|3|fara|gol":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|3|fara|conduce":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|3|fara|nu_conduce":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|3|cu|gol":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|3|cu|conduce":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|3|cu|nu_conduce":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|4|fara|gol":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|4|fara|conduce":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|4|fara|nu_conduce":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|4|cu|gol":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|4|cu|conduce":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|roleplay|4|cu|nu_conduce":
        "45035da1e6944758cd872b3b446535e54702e05a4136befa996d6ecc8843171c",
    "sys|knowledge|0|fara|gol":
        "e2a6e10b9915e1287c7682220c15d805fb433aa54c1ffcb2d7317f8847163b55",
    "sys|knowledge|0|fara|conduce":
        "e2a6e10b9915e1287c7682220c15d805fb433aa54c1ffcb2d7317f8847163b55",
    "sys|knowledge|0|fara|nu_conduce":
        "e2a6e10b9915e1287c7682220c15d805fb433aa54c1ffcb2d7317f8847163b55",
    "sys|knowledge|0|cu|gol":
        "352de6a2743bd9241a1c5dff3404ffdbf624ad942c984c4e82f8ce142d463aa9",
    "sys|knowledge|0|cu|conduce":
        "352de6a2743bd9241a1c5dff3404ffdbf624ad942c984c4e82f8ce142d463aa9",
    "sys|knowledge|0|cu|nu_conduce":
        "352de6a2743bd9241a1c5dff3404ffdbf624ad942c984c4e82f8ce142d463aa9",
    "sys|knowledge|1|fara|gol":
        "e2a6e10b9915e1287c7682220c15d805fb433aa54c1ffcb2d7317f8847163b55",
    "sys|knowledge|1|fara|conduce":
        "e2a6e10b9915e1287c7682220c15d805fb433aa54c1ffcb2d7317f8847163b55",
    "sys|knowledge|1|fara|nu_conduce":
        "e2a6e10b9915e1287c7682220c15d805fb433aa54c1ffcb2d7317f8847163b55",
    "sys|knowledge|1|cu|gol":
        "352de6a2743bd9241a1c5dff3404ffdbf624ad942c984c4e82f8ce142d463aa9",
    "sys|knowledge|1|cu|conduce":
        "352de6a2743bd9241a1c5dff3404ffdbf624ad942c984c4e82f8ce142d463aa9",
    "sys|knowledge|1|cu|nu_conduce":
        "352de6a2743bd9241a1c5dff3404ffdbf624ad942c984c4e82f8ce142d463aa9",
    "sys|knowledge|2|fara|gol":
        "d059a620d832c3560140c2623c33af5e12543fa6408a81e179c66d48b0a1abe5",
    "sys|knowledge|2|fara|conduce":
        "d059a620d832c3560140c2623c33af5e12543fa6408a81e179c66d48b0a1abe5",
    "sys|knowledge|2|fara|nu_conduce":
        "d059a620d832c3560140c2623c33af5e12543fa6408a81e179c66d48b0a1abe5",
    "sys|knowledge|2|cu|gol":
        "1dc5cf4ea322238535720713c555f85cf109ff4cf46cccc1b2de0bf549385ff6",
    "sys|knowledge|2|cu|conduce":
        "1dc5cf4ea322238535720713c555f85cf109ff4cf46cccc1b2de0bf549385ff6",
    "sys|knowledge|2|cu|nu_conduce":
        "1dc5cf4ea322238535720713c555f85cf109ff4cf46cccc1b2de0bf549385ff6",
    "sys|knowledge|3|fara|gol":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|3|fara|conduce":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|3|fara|nu_conduce":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|3|cu|gol":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|3|cu|conduce":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|3|cu|nu_conduce":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|4|fara|gol":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|4|fara|conduce":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|4|fara|nu_conduce":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|4|cu|gol":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|4|cu|conduce":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|knowledge|4|cu|nu_conduce":
        "b395874562fb70c8fd835efadbbbe656e65a5fa397a5b6009c89c58732cfd0b9",
    "sys|coaching|0|fara|gol":
        "374f602adb7a0c0b9f680f5e1c2727776b7f61420ecfcd99e10d30835bb88941",
    "sys|coaching|0|fara|conduce":
        "2d673b8336b6093016c1fd0c368557ff282a87fc26002f7bf3c4be6ff5e00d07",
    "sys|coaching|0|fara|nu_conduce":
        "81759d3dc1823ab2440782db695c2ca8f79a2988b6852099d6cd2662c55bcaa3",
    "sys|coaching|0|cu|gol":
        "85f1f4155d748220c54cb625b24aa28e76a1df0cb9f2817614c4423166c3b0f2",
    "sys|coaching|0|cu|conduce":
        "224a703b7a9050910ec8e4ff422d850f5e2c26819c2bfbc295c43be8bc4e7305",
    "sys|coaching|0|cu|nu_conduce":
        "7460ae75b253af8ada41e26e6b586fd24ed25684cd50840b066f0258488030a3",
    "sys|coaching|1|fara|gol":
        "374f602adb7a0c0b9f680f5e1c2727776b7f61420ecfcd99e10d30835bb88941",
    "sys|coaching|1|fara|conduce":
        "2d673b8336b6093016c1fd0c368557ff282a87fc26002f7bf3c4be6ff5e00d07",
    "sys|coaching|1|fara|nu_conduce":
        "81759d3dc1823ab2440782db695c2ca8f79a2988b6852099d6cd2662c55bcaa3",
    "sys|coaching|1|cu|gol":
        "85f1f4155d748220c54cb625b24aa28e76a1df0cb9f2817614c4423166c3b0f2",
    "sys|coaching|1|cu|conduce":
        "224a703b7a9050910ec8e4ff422d850f5e2c26819c2bfbc295c43be8bc4e7305",
    "sys|coaching|1|cu|nu_conduce":
        "7460ae75b253af8ada41e26e6b586fd24ed25684cd50840b066f0258488030a3",
    "sys|coaching|2|fara|gol":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|2|fara|conduce":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|2|fara|nu_conduce":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|2|cu|gol":
        "67da9e32331eaa85953b9e942f4a20e17443e6fd258ef2c9678fdb403c7fd894",
    "sys|coaching|2|cu|conduce":
        "67da9e32331eaa85953b9e942f4a20e17443e6fd258ef2c9678fdb403c7fd894",
    "sys|coaching|2|cu|nu_conduce":
        "67da9e32331eaa85953b9e942f4a20e17443e6fd258ef2c9678fdb403c7fd894",
    "sys|coaching|3|fara|gol":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|3|fara|conduce":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|3|fara|nu_conduce":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|3|cu|gol":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|3|cu|conduce":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|3|cu|nu_conduce":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|4|fara|gol":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|4|fara|conduce":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|4|fara|nu_conduce":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|4|cu|gol":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|4|cu|conduce":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "sys|coaching|4|cu|nu_conduce":
        "9df266d4d0148f2d22055a3ccf5e6a51874357fe19b01f32c7ee1e5a9f6026c1",
    "actor|0|fara|fara|gol":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|0|fara|fara|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|fara|fara|conduce":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|0|fara|fara|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|fara|fara|nu_conduce":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|0|fara|fara|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|fara|ascultare|gol":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|0|fara|ascultare|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|fara|ascultare|conduce":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|0|fara|ascultare|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|fara|ascultare|nu_conduce":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|0|fara|ascultare|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|fara|gol":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|0|cu|fara|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|fara|conduce":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|0|cu|fara|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|fara|nu_conduce":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|0|cu|fara|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|ascultare|gol":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|0|cu|ascultare|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|ascultare|conduce":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|0|cu|ascultare|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|ascultare|nu_conduce":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|0|cu|ascultare|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|fara|gol":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|1|fara|fara|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|fara|conduce":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|1|fara|fara|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|fara|nu_conduce":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|1|fara|fara|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|ascultare|gol":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|1|fara|ascultare|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|ascultare|conduce":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|1|fara|ascultare|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|ascultare|nu_conduce":
        "f8c6253cd258bd5c51192efd4d41ff7caab3c732dc863ab2e88a2125f29c137b",
    "profesor|1|fara|ascultare|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|fara|gol":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|1|cu|fara|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|fara|conduce":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|1|cu|fara|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|fara|nu_conduce":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|1|cu|fara|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|ascultare|gol":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|1|cu|ascultare|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|ascultare|conduce":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|1|cu|ascultare|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|ascultare|nu_conduce":
        "3d969bb2aa19060f6beb063d3b9cc02a05508180cb91dc174e01de730fb24740",
    "profesor|1|cu|ascultare|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|2|fara|fara|gol":
        "880ec76326fb122fc5badd0e4235e1dbee1b3476c0cd723bf63365abfd9b4cdd",
    "profesor|2|fara|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|fara|fara|conduce":
        "faec94ff571212628ff217f636a897c7eac2d57c4d4a9126ba7e94f952426344",
    "profesor|2|fara|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|fara|fara|nu_conduce":
        "b5a88547d86b829842d5948754a6cf3a3d4d942f31b15dd7096bc93c0fbb2f76",
    "profesor|2|fara|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|fara|ascultare|gol":
        "1c5d28f552a2aec2ee79ca730454dc51fe4050b650f24dce120694194e78087c",
    "profesor|2|fara|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|fara|ascultare|conduce":
        "56ec58f5492d5dc2b96e17e96899cf1d22aca954533ee4ca0b42228432fe6892",
    "profesor|2|fara|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|fara|ascultare|nu_conduce":
        "8935ee01c4eca60a9f5dbac5dcd9424c7d8be4a3ae7e350ad27694f27ae44cf8",
    "profesor|2|fara|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|fara|gol":
        "cd4f662f67ebb8e497f2b02ead78ee740ac7cfda8d9915bfcaf4d5bca5fe76b2",
    "profesor|2|cu|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|fara|conduce":
        "3e61e84657bf275c0cdd41a521586960ee9ec7ea585eb1eff1a63e379d013f4e",
    "profesor|2|cu|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|fara|nu_conduce":
        "fd31460b23917fe0162d9f062fcad530e9d855012526540bc0a511f9d1580af9",
    "profesor|2|cu|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|ascultare|gol":
        "c044235c059d1c7e1ccd69bab25b4a50a543d026fbbecd78df5cde921dc8b3e5",
    "profesor|2|cu|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|ascultare|conduce":
        "8020048bd0dca4cbb0e40e68848c7097ea950cacffdebc25d7d14bf7429032ba",
    "profesor|2|cu|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|ascultare|nu_conduce":
        "6a072f5c607854a53fd145cfe52fd23eb81fbb82652b0d67b45258b24c9dab87",
    "profesor|2|cu|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|fara|gol":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|fara|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|fara|conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|fara|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|fara|nu_conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|fara|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|ascultare|gol":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|fara|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|ascultare|conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|fara|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|ascultare|nu_conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|fara|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|fara|gol":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|cu|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|fara|conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|cu|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|fara|nu_conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|cu|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|ascultare|gol":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|cu|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|ascultare|conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|cu|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|ascultare|nu_conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|3|cu|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|fara|gol":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|fara|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|fara|conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|fara|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|fara|nu_conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|fara|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|ascultare|gol":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|fara|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|ascultare|conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|fara|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|ascultare|nu_conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|fara|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|fara|gol":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|cu|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|fara|conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|cu|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|fara|nu_conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|cu|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|ascultare|gol":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|cu|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|ascultare|conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|cu|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|ascultare|nu_conduce":
        "516ce9d77b40656ff007d6a9cc6dec7cc573d1434b728e3d455b8cbc30eba8ed",
    "profesor|4|cu|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "distributie|gol":
        "a1cbff92b883224d75b7d144059f04ff6695dab879897942159629899e610166",
    "setup|gol|fara":
        "51a5b11daa0cbe4ba2d2674e3933ffc316d19abeb8998c27209d5c4871ef2897",
    "setup|gol|ascultare":
        "0816cc24bbd21c630c0c02844450c583a182659f5daf3d503c99bd10f9912240",
    "distributie|conduce":
        "2cfe79d8e892048389d3deb68ec8014339ccc3762c3cfdc25f6f93a03904ad0e",
    "setup|conduce|fara":
        "f8d0ecd809086fa7f43892413ab13dcaee0921e5d303b3cf83692d16479e32e5",
    "setup|conduce|ascultare":
        "704556a95eba91f310381157f4854f7644896ae7f4590efbfe8c49a39f566fc8",
    "distributie|nu_conduce":
        "2c29fe8558c2296f3d9cf95c3c618549f85106a96c6e85f4ed87ff60ad32bf26",
    "setup|nu_conduce|fara":
        "9f7e177026d2704a169d6a6a7942f1018051355ba6b12dd34447aa58a7bc9a6b",
    "setup|nu_conduce|ascultare":
        "d6b569c350582416cdfc154f0ec4868ea69589abd3092b041acaacc11b3eb72d",
}


def test_amprentele_sunt_ale_tuturor_cazurilor() -> None:
    chei = [k for k, _ in _cazurile()]
    assert len(chei) == len(set(chei))
    assert set(chei) == set(AMPRENTE)


def test_fara_argumentul_nou_instructiunile_sunt_cele_de_azi() -> None:
    diferite = [k for k, text in _cazurile() if _sha(text) != AMPRENTE.get(k)]
    assert diferite == []


def test_cu_obiectiv_none_instructiunile_sunt_cele_de_azi() -> None:
    diferite = [k for k, text in _cazurile(obiectiv=None) if _sha(text) != AMPRENTE.get(k)]
    assert diferite == []


# A0 pe serviciu (corecția 7): instrucțiunile trimise efectiv, în ordine (salut, „Da, hai.”, două
# replici), cu codul omului înlocuit cu <COD> — codul se trage la întâmplare; fără el, două rulări
# dau aceleași amprente (măsurat la A0).
AMPRENTE_SERVICIU: dict[bool, list[str]] = {
    True: [
        "94745a05a895cf5c9839cadee2d3fd7aff2c42310270ceca1c4912c462ec17a8",
        "dff84e9e9e571aea090ec921bc7fad1102b64e9f89f526e6aa1254da8cd27f0c",
        "0c588e09109ca3eec51f550c0afa07bbcbdf9a9694fc6a6a520798af5f437c72",
        "a1467ea2c6c4d40bb9beb6220aae8251cd6bafee830cdc2f5a8152c96a456d80",
        "0c588e09109ca3eec51f550c0afa07bbcbdf9a9694fc6a6a520798af5f437c72",
        "a1467ea2c6c4d40bb9beb6220aae8251cd6bafee830cdc2f5a8152c96a456d80",
    ],
    False: [
        "94745a05a895cf5c9839cadee2d3fd7aff2c42310270ceca1c4912c462ec17a8",
        "fa595d7a4b73c5f1b315f61ab8310074054c05eccde300a53764cc04acc07088",
        "afd6ef7a68abc4539ebf4f006288b281b0504fa241f68a11864e2ee186dfff37",
        "afd6ef7a68abc4539ebf4f006288b281b0504fa241f68a11864e2ee186dfff37",
    ],
}


_COD = re.compile(r"sub codul „([^”]+)”")


def _fara_cod(text: str | None) -> str:
    text = text or ""
    m = _COD.search(text)
    return text.replace(m.group(1), "<COD>") if m else text


SEMNE_OBIECTIV = ("OBIECTIVUL OMULUI", "AZI SCENA PORNEȘTE", "Semnul că a reușit")


async def _sesiune_obisnuita(doua_apeluri: bool):
    from redis.asyncio import Redis

    from codrut.core.config import Settings
    from codrut.core.database import SessionLocal
    from codrut.modules.practice.generation_provider import LocalGenerationProvider
    from codrut.modules.practice.models import PracticeSession, SessionKind
    from codrut.modules.practice.service import PracticeSessionService
    from test_competenta_tinta import _pregatire

    settings = Settings(generation_provider="local", practice_two_calls=doua_apeluri)
    furnizor = LocalGenerationProvider(settings)
    async with SessionLocal() as s:
        ctx = await _pregatire(
            s, {"Ascultare activă": 2, "Feedback asertiv": 0, "Limite sănătoase": 1}
        )
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        svc = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                     settings=settings)
        sed, _ = await svc.start_session(principal=ctx["principal"], project_id=ctx["project"].id,
                                         kind=SessionKind.roleplay)
        n_salut = len(furnizor.recorded_requests)
        for text in ("Da, hai.", "Înțeleg ce spui. Ce anume te îngrijorează?",
                     "Hai să stabilim împreună un termen."):
            await svc.add_participant_turn(principal=ctx["principal"], session_id=sed.id,
                                           text=text)
        sesiunea = await s.get(PracticeSession, sed.id)
        objective_id = sesiunea.objective_id if hasattr(sesiunea, "objective_id") else None
        cereri = list(furnizor.recorded_requests)
        await s.rollback()
        await redis.aclose()
    return cereri, n_salut, objective_id


@pytest.mark.asyncio
@pytest.mark.parametrize("doua_apeluri", [True, False])
async def test_sesiunea_obisnuita_nu_primeste_nimic_din_obiectiv(doua_apeluri: bool) -> None:
    from codrut.contracts.generation import GenerationPurpose

    cereri, n_salut, objective_id = await _sesiune_obisnuita(doua_apeluri)
    assert objective_id is None
    assert n_salut == 1
    # instrucțiunile trimise efectiv sunt cele de azi, octet cu octet (în afară de cod)
    assert [_sha(_fara_cod(c.system_instruction)) for c in cereri] == (
        AMPRENTE_SERVICIU[doua_apeluri]
    )
    for c in cereri:
        for semn in SEMNE_OBIECTIV:
            assert semn not in (c.system_instruction or "")
    confirmarea = cereri[n_salut]
    assert confirmarea.purpose == GenerationPurpose.actor
    if doua_apeluri:
        # competența țintă se calculează ca azi (plicul 165), lângă regula setup-ului
        assert "mai ales competența „Feedback asertiv”" in confirmarea.system_instruction
        assert "DISTRIBUȚIA SCENEI" in confirmarea.system_instruction
        # replicile de joc: actor + profesor, în paralel
        assert [c.purpose for c in cereri[n_salut + 1:]] == [
            GenerationPurpose.actor, GenerationPurpose.evaluator,
        ] * 2
    else:
        assert "mai ales competența" not in confirmarea.system_instruction
        assert "DISTRIBUȚIA SCENEI" in confirmarea.system_instruction
        assert len(cereri) == n_salut + 3
