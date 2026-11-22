"""Paza principală a plicului 244: fără obiectiv, instrucțiunile sunt octet cu octet cele de azi.

Amprentele de mai jos (`AMPRENTE`) au fost calculate pe baza `9d3ea9c` (vârful plicului 240),
ÎNAINTE de orice schimbare (pasul A0, `.audit/cody-plic244/raw/A0-amprente-azi.txt`), cu
generatorul `_cazurile` din acest fișier. Chemarea fără argumentul nou și chemarea cu
`obiectiv=None` trebuie să dea exact aceleași șiruri.

Plicul 249 a schimbat NUMAI amprentele ieșirilor care conțin `actor.md` (90 din 219 și cele 8
cereri de actor pe serviciu; `.audit/cody-plic249/raw/A0-amprente.txt`): propoziția aprobată de
Andrei [esti-ai-fara-glume], la finalul lui `actor.md`.

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
        "1c8501b47a5347931bfd182d47d2f90282a419ec8d02feb07ad66888991fece6",
    "sys|roleplay|0|fara|conduce":
        "1c8501b47a5347931bfd182d47d2f90282a419ec8d02feb07ad66888991fece6",
    "sys|roleplay|0|fara|nu_conduce":
        "1c8501b47a5347931bfd182d47d2f90282a419ec8d02feb07ad66888991fece6",
    "sys|roleplay|0|cu|gol":
        "2662a99a809b1b12d62409f9db3e035a9a8f1695beec37cbed7ed6190825d0e4",
    "sys|roleplay|0|cu|conduce":
        "2662a99a809b1b12d62409f9db3e035a9a8f1695beec37cbed7ed6190825d0e4",
    "sys|roleplay|0|cu|nu_conduce":
        "2662a99a809b1b12d62409f9db3e035a9a8f1695beec37cbed7ed6190825d0e4",
    "sys|roleplay|1|fara|gol":
        "1c8501b47a5347931bfd182d47d2f90282a419ec8d02feb07ad66888991fece6",
    "sys|roleplay|1|fara|conduce":
        "1c8501b47a5347931bfd182d47d2f90282a419ec8d02feb07ad66888991fece6",
    "sys|roleplay|1|fara|nu_conduce":
        "1c8501b47a5347931bfd182d47d2f90282a419ec8d02feb07ad66888991fece6",
    "sys|roleplay|1|cu|gol":
        "2662a99a809b1b12d62409f9db3e035a9a8f1695beec37cbed7ed6190825d0e4",
    "sys|roleplay|1|cu|conduce":
        "2662a99a809b1b12d62409f9db3e035a9a8f1695beec37cbed7ed6190825d0e4",
    "sys|roleplay|1|cu|nu_conduce":
        "2662a99a809b1b12d62409f9db3e035a9a8f1695beec37cbed7ed6190825d0e4",
    "sys|roleplay|2|fara|gol":
        "31aecf2a2748de9dabde3dbc83e1b3632312b71c8c18ac094acdd4baf017c9a7",
    "sys|roleplay|2|fara|conduce":
        "f1b61fbc69a6616751c7edf650f0c8eeb29d8c40bf1da51c612f753a45ff5aa0",
    "sys|roleplay|2|fara|nu_conduce":
        "f832ef2e85bbab1074f7425d6d502628deb787f82bd59bcb6c8887b3304c2a9d",
    "sys|roleplay|2|cu|gol":
        "29dfc8e3b5de1959f6ca20e67d5806769cbe7788ec1e8ada7adca9fb4a65b158",
    "sys|roleplay|2|cu|conduce":
        "af7b7c4158af516f9844d64dc1111f56aac53c066264dbb268ddf15e2018acb7",
    "sys|roleplay|2|cu|nu_conduce":
        "3d7a4ab0f16af2243d9beccca9e7aaf1311890ac43b5c70bbf933d56cdff2027",
    "sys|roleplay|3|fara|gol":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|3|fara|conduce":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|3|fara|nu_conduce":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|3|cu|gol":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|3|cu|conduce":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|3|cu|nu_conduce":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|4|fara|gol":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|4|fara|conduce":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|4|fara|nu_conduce":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|4|cu|gol":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|4|cu|conduce":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
    "sys|roleplay|4|cu|nu_conduce":
        "eed719b43b7a5c412ba2ab353f145e18e7f98312d250b7b941fa971d75d63104",
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
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|0|fara|fara|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|fara|fara|conduce":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|0|fara|fara|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|fara|fara|nu_conduce":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|0|fara|fara|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|fara|ascultare|gol":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|0|fara|ascultare|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|fara|ascultare|conduce":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|0|fara|ascultare|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|fara|ascultare|nu_conduce":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|0|fara|ascultare|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|fara|gol":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|0|cu|fara|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|fara|conduce":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|0|cu|fara|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|fara|nu_conduce":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|0|cu|fara|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|ascultare|gol":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|0|cu|ascultare|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|ascultare|conduce":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|0|cu|ascultare|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|0|cu|ascultare|nu_conduce":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|0|cu|ascultare|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|fara|gol":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|1|fara|fara|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|fara|conduce":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|1|fara|fara|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|fara|nu_conduce":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|1|fara|fara|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|ascultare|gol":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|1|fara|ascultare|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|ascultare|conduce":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|1|fara|ascultare|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|fara|ascultare|nu_conduce":
        "2f2e6d6e341e75eb3bee1f5dd4430fb8ffcfecd7e927239deb03413edb79e12a",
    "profesor|1|fara|ascultare|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|fara|gol":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|1|cu|fara|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|fara|conduce":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|1|cu|fara|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|fara|nu_conduce":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|1|cu|fara|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|ascultare|gol":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|1|cu|ascultare|gol":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|ascultare|conduce":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|1|cu|ascultare|conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|1|cu|ascultare|nu_conduce":
        "b4f962baf65c6a22e69573781d9ef9abeba08709375d39bc87a10502ff1ebb82",
    "profesor|1|cu|ascultare|nu_conduce":
        "3d36203e6d7261c7e0333d8e369bddd0b5105efc03881c81642d38afd00d5481",
    "actor|2|fara|fara|gol":
        "49dc4bc010bc27b8134815ed9cbf24ca231e6bda5d5623da459a32db8f721927",
    "profesor|2|fara|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|fara|fara|conduce":
        "cc528aed982ae98768f18a5c0c081e62d68d690956c25701010fdc354741ceba",
    "profesor|2|fara|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|fara|fara|nu_conduce":
        "3ec5840227117f81e6ac6f5eb48555e7daed9e7cdf25e1bc40b2604d9e90baad",
    "profesor|2|fara|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|fara|ascultare|gol":
        "57baf98bf7d9ebf0acf93784ba4f61b5d886206ba8d0a614c1c099e5a3fa7a94",
    "profesor|2|fara|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|fara|ascultare|conduce":
        "7cde213522c394e9e7f76e82a5f73509d653b33fbc4e5e72c7a13fe33c5ff7ad",
    "profesor|2|fara|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|fara|ascultare|nu_conduce":
        "e1838015a0f1e3ffbaa4af0a420554af84918a546d2087372654d064ac099925",
    "profesor|2|fara|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|fara|gol":
        "1e580d554cb06c6629c1d294b8120fcad7c1e645caa641a1172aa4012091253f",
    "profesor|2|cu|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|fara|conduce":
        "498b15bda32bb66e225ae89f90504aae17900778669e8ef7136f155306d86f5d",
    "profesor|2|cu|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|fara|nu_conduce":
        "347c0f9730f8ec59d9be49fb5ff3270d6c80a7f373fe01074d89de9fc346f290",
    "profesor|2|cu|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|ascultare|gol":
        "33f2050d31e158be0e37daa9720d9df6c080aa8f5a17a2d20628292c392bf9aa",
    "profesor|2|cu|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|ascultare|conduce":
        "cd1fad363153ee996ddd6660088ae8bca7f1c10bead1c6e27c844506d87726bc",
    "profesor|2|cu|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|2|cu|ascultare|nu_conduce":
        "e29a44498b1356b78c742fb335d10c8e49ec5640d2d7b7b549b0c4f8d8596c87",
    "profesor|2|cu|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|fara|gol":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|fara|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|fara|conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|fara|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|fara|nu_conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|fara|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|ascultare|gol":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|fara|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|ascultare|conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|fara|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|fara|ascultare|nu_conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|fara|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|fara|gol":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|cu|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|fara|conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|cu|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|fara|nu_conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|cu|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|ascultare|gol":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|cu|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|ascultare|conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|cu|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|3|cu|ascultare|nu_conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|3|cu|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|fara|gol":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|fara|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|fara|conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|fara|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|fara|nu_conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|fara|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|ascultare|gol":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|fara|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|ascultare|conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|fara|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|fara|ascultare|nu_conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|fara|ascultare|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|fara|gol":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|cu|fara|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|fara|conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|cu|fara|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|fara|nu_conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|cu|fara|nu_conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|ascultare|gol":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|cu|ascultare|gol":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|ascultare|conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
    "profesor|4|cu|ascultare|conduce":
        "77eccd0a98208e27151008cfa3f4740817e85b8293abd3ce63925187f011fc62",
    "actor|4|cu|ascultare|nu_conduce":
        "181d4f313cf016b3c2e1b7b03f0dc4693154c42f8058ba1cad8fbd4267869941",
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
        "a3bc6ab125a5ad854a6885df332549cc6e92b5cbbca1194160fb8222591d7c27",
        "f51455f2a7348de1335332f6f69e1ba4d4b57a2862b8c2c8ab547529e28596ff",
        "d9ed3c265f5015f3b2d1fd10a01ba5dedf09dae102cc5edb3eda7793d8030cce",
        "a1467ea2c6c4d40bb9beb6220aae8251cd6bafee830cdc2f5a8152c96a456d80",
        "d9ed3c265f5015f3b2d1fd10a01ba5dedf09dae102cc5edb3eda7793d8030cce",
        "a1467ea2c6c4d40bb9beb6220aae8251cd6bafee830cdc2f5a8152c96a456d80",
    ],
    False: [
        "a3bc6ab125a5ad854a6885df332549cc6e92b5cbbca1194160fb8222591d7c27",
        "1e277b58d65dbd42e122801fa08a2588bada31328d131e3e9cc0aac8215974a9",
        "e9434d2ad0859b372b6be51baf0c1c35aece9dcc36773b43dd9d72fa1d250bf1",
        "e9434d2ad0859b372b6be51baf0c1c35aece9dcc36773b43dd9d72fa1d250bf1",
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
