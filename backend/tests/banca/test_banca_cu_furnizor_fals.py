"""Banca cu modele, verificată fără costuri — plicul 222.

Un furnizor fals întoarce răspunsuri scrise de noi: setul „bun” trebuie să dea TRECE, setul
„stricat” (se repetă, iese din rol, 9 la replica slabă, JSON stricat) trebuie să dea PICĂ, pe
criteriile corecte. Niciun apel spre model: fără `--pe-bune`, furnizorul real nu se construiește.
"""

from __future__ import annotations

import json

import pytest

from codrut.modules.practice.evaluator import sedinta_prea_scurta
from codrut.modules.practice.prompts import NUME_PERSONAJ
from codrut.tools.banca import rulare_banca as rb
from codrut.tools.banca.reguli_actor import afirma_ca_e_ai
from codrut.tools.probe_automate import NUME_INVENTATE, PRENUME, PaznicDeNume


class _Scrie:
    def __init__(self) -> None:
        self.randuri: list[dict] = []

    def __call__(self, obiect: dict) -> None:
        self.randuri.append(obiect)


async def _ruleaza(fel: str, *, doar_actor: bool = False, plafon: int = 160):
    from codrut.core.config import get_settings

    furnizor = PaznicDeNume(rb.FurnizorFals(fel), [])
    scrie = _Scrie()
    verdict = await rb.ruleaza(furnizor, get_settings(), scrie, doar_actor=doar_actor,
                               plafon=plafon, amprenta_rularii={"furnizor": f"fals:{fel}"})
    return verdict, scrie.randuri, furnizor


def _picate(verdict: dict) -> set[tuple[str, str]]:
    return {(r["caz"], r["criteriu"]) for r in verdict["tabel"] if not r["trece"]}


def test_cazurile_au_numerele_cerute() -> None:
    c, cheia = rb.citeste_cazurile(), rb.citeste_cheia()
    conv = c["actor"]["conversatii"]
    assert len(conv) == 12 and all(len(x["replici"]) == 4 for x in conv)
    teme = {"Comunicare asertivă", "Feedback constructiv", "Gestionarea conflictului",
            "Influențare"}
    assert {x["tema"] for x in conv} == teme
    assert {"cooperant", "agresiv", "tăcut", "ești AI?", "lung", "emoțional"} <= {
        x["fel"] for x in conv}
    assert len({x["nr"] for x in conv}) == 12  # personaje diferite
    scene = c["profesor_replica"]["scene"]
    assert len(scene) == 12 and {s["tema"] for s in scene} == teme
    assert sorted(cheia["profesor_replica"].values()).count("bun") == 12
    assert set(cheia["profesor_replica"]) == {f"{s['id']}-{x}" for s in scene for x in "ab"}
    trans = c["inchidere"]["transcrieri"]
    assert len(trans) == 8 and set(cheia["inchidere"]) == {t["id"] for t in trans}
    assert sorted(cheia["inchidere"].values()) == [1, 1, 1, 2, 2, 3, 3, 3]
    assert len(c["rezumat"]["sedinte"]) == 4
    # plicul 227: salutul și scena sunt fixe, actorul face numai cele 4 replici de joc
    assert rb.apeluri_planificate(False) == 48 + 39 + 14 + 4 == 105
    assert rb.apeluri_planificate(True) == 16


def test_cazurile_nu_poarta_nume_de_oameni() -> None:
    assert rb.nume_in_cazuri() == {f: 0 for f in (*rb.FISIERE_CAZURI, "cheia.json")}


def test_scenele_iau_personajul_din_aplicatie() -> None:
    """Corecția 3: niciun nume scris de mână; numai `{personaj}`, pus de aplicație."""
    text = "".join((rb.CAZURI / f).read_text(encoding="utf-8") for f in rb.FISIERE_CAZURI)
    for nume in (*NUME_PERSONAJ, *NUME_INVENTATE, *(n.split()[-1] for n in NUME_PERSONAJ)):
        assert nume not in text, nume
    assert PRENUME not in text
    assert rb._personaj(1) != rb._personaj(2)


def test_transcrierile_trec_de_pragul_sedintei_scurte() -> None:
    for t in rb.citeste_cazurile()["inchidere"]["transcrieri"]:
        _, om = rb._transcriere(t)
        assert not sedinta_prea_scurta(om), t["id"]


@pytest.mark.parametrize(("text", "afirma"), [
    ("Nu, sunt un om obosit, atât.", False),
    ("Ce zici, ești AI?", False),
    ("Bine, recunosc: sunt un robot.", True),
    ("Da, este inteligenta artificiala.", True),
    ("Sunt AI, dar hai să continuăm.", True),
])
def test_regula_pentru_esti_ai(text: str, afirma: bool) -> None:
    # plicul 224: regula s-a mutat în `reguli_actor.afirma_ca_e_ai` (cazurile noi: 224)
    assert (afirma_ca_e_ai(text) is not None) is afirma


async def test_setul_bun_trece_toata_banca() -> None:
    verdict, randuri, furnizor = await _ruleaza("bun")
    assert verdict["verdict"] == "TRECE", verdict["criterii"]
    assert verdict["apeluri"] == 105 and verdict["format_rosu"] is None
    assert all(c["trece"] for c in verdict["criterii"].values())
    assert not _picate(verdict)
    sesiuni = [r for r in randuri if r["tip"] == "sesiune"]
    assert sum(r["apeluri"] for r in sesiuni) == 105
    assert all(r["id"].startswith("banca:") and r["terminata"] and r["pasi"] for r in sesiuni)
    assert all(p["intrat"] > 0 for r in sesiuni for p in r["pasi"])
    assert furnizor.gasite == 0


async def test_setul_stricat_pica_pe_criteriile_corecte() -> None:
    verdict, _randuri, _ = await _ruleaza("stricat")
    assert verdict["verdict"] == "PICĂ"
    # oprire la primul roșu de format: prima închidere, JSON stricat
    assert verdict["format_rosu"].startswith("I01")
    assert verdict["motiv"] == "oprită la primul roșu de format"
    picate = _picate(verdict)
    assert ("A01", "se_repeta") in picate
    assert any(caz.startswith("A") and crit == "poarta 11" for caz, crit in picate)
    assert ("P01-b", "nota slab") in picate and ("P01-a", "nota bun") not in picate
    assert ("I01", "format (JSON + scor 0–100 pe fiecare competență)") in picate
    crit = verdict["criterii"]
    assert not crit["actor: conversații care trec tot"]["trece"]
    assert not crit["profesor: slabe ≤ 5/10"]["trece"]
    assert crit["profesor: bune ≥ 8/10"]["trece"]
    assert not crit["închidere: format"]["trece"]
    # după roșul de format nu se mai cheamă nimic: nici stabilitatea, nici rezumatul
    assert not any(r["caz"].startswith("R") for r in verdict["tabel"])


async def test_plafonul_opreste_rularea() -> None:
    verdict, randuri, _ = await _ruleaza("bun", plafon=50)
    assert verdict["verdict"] == "PICĂ"
    assert verdict["motiv"] == "oprită la plafonul de apeluri"
    assert verdict["apeluri"] <= 50
    assert sum(r["apeluri"] for r in randuri if r["tip"] == "sesiune") == verdict["apeluri"]


async def test_doar_actor_face_16_apeluri() -> None:
    verdict, _, _ = await _ruleaza("bun", doar_actor=True)
    assert verdict["verdict"] == "TRECE" and verdict["apeluri"] == 16


async def test_fara_pe_bune_furnizorul_real_nu_se_construieste(tmp_path, monkeypatch) -> None:
    def _interzis(*_a, **_k):
        raise AssertionError("furnizorul real s-a construit fără --pe-bune")

    monkeypatch.setattr(rb, "build_generation_provider", _interzis)
    jurnal = tmp_path / "banca.jsonl"
    assert await rb.main(["--doar-actor", "--jurnal", str(jurnal), "--comitere", "abc1234"]) == 0
    randuri = [json.loads(x) for x in jurnal.read_text(encoding="utf-8").splitlines()]
    cap, verdict = randuri[0], randuri[-1]
    assert cap["tip"] == "cap" and cap["apeluri_planificate"] == 16
    amp = cap["amprenta"]
    assert amp["comitere"] == "abc1234" and amp["furnizor"] == "fals:bun"
    assert {"model_actor", "model_evaluator", "destinatie", "prompt_version"} <= set(amp)
    assert verdict["tip"] == "verdict" and verdict["verdict"] == "TRECE"
    assert verdict["amprenta"] == amp and verdict["nume_trimise"] == 0
    assert "VERDICT: TRECE" in jurnal.with_suffix(".md").read_text(encoding="utf-8")


async def test_a_doua_rulare_din_zi_cere_peste_plafon(tmp_path) -> None:
    argv = ["--doar-actor", "--jurnal", str(tmp_path / "a.jsonl")]
    assert await rb.main(argv) == 0
    assert await rb.main(["--doar-actor", "--jurnal", str(tmp_path / "b.jsonl")]) == 4
    assert not (tmp_path / "b.jsonl").exists()
    assert await rb.main(["--doar-actor", "--peste-plafon",
                          "--jurnal", str(tmp_path / "b.jsonl")]) == 0


async def test_setul_stricat_da_cod_de_iesire_1(tmp_path) -> None:
    assert await rb.main(["--furnizor-fals", "stricat",
                          "--jurnal", str(tmp_path / "s.jsonl")]) == 1
