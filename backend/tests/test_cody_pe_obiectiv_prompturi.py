"""Unde intră textele obiectivului în instrucțiuni — plicul 244, §4.2.

Cu obiectiv: la replica de confirmare, personajul primește titlul și situația (ultimele, după
regula setup-ului) și numai numele personajului, fără rotația „jos / lateral / sus / client”; la
fiecare replică din joc, profesorul primește titlul și semnul de reușită, imediat înaintea lui
`FARA_SCENA`, care rămâne ultima. Obiectivul 1 e citit din catalogul din depozit, nu rescris.
"""

from __future__ import annotations

import json
import os

import pytest

BIBLIOTECA = os.environ.get("BIBLIOTECA_PATH", "")
PROFIL = {"conduce_oameni": False, "nr_roleplay_anterioare": 2}


def _obiectivul_1() -> dict[str, str]:
    from codrut.modules.practice import obiective

    date = json.loads((obiective.DOSAR / "comunicare-asertiva.json").read_text(encoding="utf-8"))
    o = date["obiective"][0]
    assert o["nr"] == 1
    return {"titlu": o["titlu"], "situatie": o["situatie"], "semn_de_reusita": o["semn_de_reusita"]}


def _textele(obiectiv):
    from codrut.modules.practice.prompts import (
        OBIECTIV_ACTOR,
        OBIECTIV_PROFESOR,
        completeaza_obiectivul,
    )

    return (
        "\n\n---\n" + completeaza_obiectivul(OBIECTIV_ACTOR, obiectiv),
        "\n\n---\n" + completeaza_obiectivul(OBIECTIV_PROFESOR, obiectiv),
    )


def _meserii(history_length: int, obiectiv, **kw):
    from codrut.modules.practice.prompts import get_prompts_pe_meserii

    return get_prompts_pe_meserii(
        name="Fox 34", history_length=history_length, biblioteca_path=BIBLIOTECA,
        profil_rol=PROFIL, obiectiv=obiectiv, **kw,
    )


def test_a_doua_apeluri_replica_de_confirmare() -> None:
    from codrut.modules.practice.prompts import REPLICA_DE_CONFIRMARE

    o = _obiectivul_1()
    bloc_actor, _ = _textele(o)
    actor, _ = _meserii(REPLICA_DE_CONFIRMARE, o)
    assert actor.endswith(bloc_actor)
    assert o["titlu"] in actor and o["situatie"] in actor
    assert "DISTRIBUȚIA SCENEI" not in actor
    assert "INTERZIS să-l pui pe participant în poziție de manager" not in actor
    assert "PERSONAJUL SE NUMEȘTE" in actor
    assert "CUM ARATĂ SETUP-UL" in actor
    assert "mai ales competența" not in actor
    assert o["semn_de_reusita"] not in actor
    # regula setup-ului vine înaintea textului obiectivului
    assert actor.index("CUM ARATĂ SETUP-UL") < actor.index("AZI SCENA PORNEȘTE")


def test_a_competenta_tinta_nu_intra_cu_obiectiv() -> None:
    from codrut.modules.practice.prompts import REPLICA_DE_CONFIRMARE

    actor, _ = _meserii(REPLICA_DE_CONFIRMARE, _obiectivul_1(), competenta_tinta=None)
    assert "mai ales competența" not in actor


@pytest.mark.parametrize("history_length", [3, 4, 5, 8])
def test_b_doua_apeluri_replicile_de_joc(history_length: int) -> None:
    from codrut.modules.practice.prompts import FARA_SCENA

    o = _obiectivul_1()
    _, bloc_profesor = _textele(o)
    actor, profesor = _meserii(history_length, o)
    actor_fara, profesor_fara = _meserii(history_length, None)
    assert actor == actor_fara
    assert profesor.endswith(bloc_profesor + FARA_SCENA)
    assert profesor == profesor_fara[: -len(FARA_SCENA)] + bloc_profesor + FARA_SCENA
    assert o["semn_de_reusita"] in profesor
    assert "AZI SCENA PORNEȘTE" not in profesor
    assert o["situatie"] not in profesor


def test_b_profesorul_primeste_obiectivul_si_la_confirmare() -> None:
    from codrut.modules.practice.prompts import FARA_SCENA, REPLICA_DE_CONFIRMARE

    o = _obiectivul_1()
    _, bloc_profesor = _textele(o)
    _, profesor = _meserii(REPLICA_DE_CONFIRMARE, o)
    assert profesor.endswith(bloc_profesor + FARA_SCENA)


def test_c_un_apel() -> None:
    from codrut.modules.practice.prompts import (
        ACTOR_PROMPT,
        EVALUARE_PROMPT,
        REPLICA_DE_CONFIRMARE,
        get_system_prompt_for_kind,
    )

    o = _obiectivul_1()
    bloc_actor, bloc_profesor = _textele(o)

    def sys(hl, obiectiv):
        return get_system_prompt_for_kind(
            "roleplay", name="Fox 34", history_length=hl, biblioteca_path=BIBLIOTECA,
            profil_rol=PROFIL, obiectiv=obiectiv,
        )

    confirmare = sys(REPLICA_DE_CONFIRMARE, o)
    assert confirmare.endswith(bloc_actor)
    assert f"{ACTOR_PROMPT}\n\n---\n\n{EVALUARE_PROMPT}{bloc_profesor}" in confirmare
    assert "DISTRIBUȚIA SCENEI" not in confirmare
    assert "PERSONAJUL SE NUMEȘTE" in confirmare
    joc = sys(4, o)
    assert joc.endswith(f"{EVALUARE_PROMPT}{bloc_profesor}")
    assert "AZI SCENA PORNEȘTE" not in joc
    assert joc == sys(4, None) + bloc_profesor


def test_c_quiz_si_coaching_ignora_obiectivul() -> None:
    from codrut.modules.practice.prompts import get_system_prompt_for_kind

    o = _obiectivul_1()
    for kind in ("knowledge", "coaching"):
        for hl in (0, 2, 4):
            kw = dict(name="Fox 34", history_length=hl, biblioteca_path=BIBLIOTECA,
                      profil_rol=PROFIL,
                      quiz_competency="mix" if kind == "knowledge" else None)
            assert get_system_prompt_for_kind(kind, obiectiv=o, **kw) == (
                get_system_prompt_for_kind(kind, **kw)
            )


def test_d_completarea() -> None:
    from codrut.modules.practice.prompts import (
        OBIECTIV_ACTOR,
        OBIECTIV_PROFESOR,
        completeaza_obiectivul,
    )

    o = _obiectivul_1()
    for sablon in (OBIECTIV_ACTOR, OBIECTIV_PROFESOR):
        rez = completeaza_obiectivul(sablon, o)
        for semn in ("{titlu}", "{situatie}", "{semn_de_reusita}"):
            assert semn not in rez
    # o valoare cu acolade nu strică nimic (`str.replace`, nu `.format`)
    ciudat = {"titlu": "Titlu {x} cu {0}", "situatie": "  Situație {}  ", "semn_de_reusita": "s"}
    rez = completeaza_obiectivul(OBIECTIV_ACTOR, ciudat)
    assert "Titlu {x} cu {0}" in rez and "Situație {}\n" in rez
    # un șablon cu loc necompletat → ValueError
    with pytest.raises(ValueError):
        completeaza_obiectivul("Titlu: {titlu}. Rămâne {situatie}", {"titlu": "x"})


def test_e_distributia_e_directia_plus_numele() -> None:
    from codrut.modules.practice.prompts import (
        _directia_scenei,
        bloc_de_distributie,
        bloc_de_nume,
    )

    for prof in (None, {}, {"conduce_oameni": True, "nr_roleplay_anterioare": 3}, PROFIL):
        for prenume in ("", "Ion", "Fox"):
            assert bloc_de_distributie(prof, prenume) == (
                _directia_scenei(prof, prenume) + bloc_de_nume(prof, prenume)
            )
