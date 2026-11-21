"""Banca de probă pregătită pentru etalon — plicul 224 (din CONTROLOR DUPĂ 222 și 223).

1. `evaluated: false` (boolean) al profesorului la închidere = „neevaluat”, nu roșu de format.
2. La `--pe-bune`: modelul profesorului obligatoriu; modelele, furnizorul și comiterea verificate.
3. Răspunsurile întregi ale modelului se păstrează în fișierul de stare (paznicul de nume
   pe ele).
4. Regula „ești AI?”: „AI” cu majuscule, negația în rol trece, întrebarea trece.
5. Rulările false scriu în `/tmp/banca-fals/`; o cădere de rețea se reia o dată, a doua =
   roșu de rețea.
6. `service.py`: jurnalul rezumatului numai cu tipul erorii; `scores` care nu e dicționar nu
   pierde tot.
Niciun apel spre model: furnizorii sunt falși.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal

import pytest
from test_intariri_223 import MARCAJ, _inchide, _sinteza

from codrut.contracts.generation import (
    GenerationError,
    GenerationProviderKey,
    GenerationResult,
    TokenUsage,
)
from codrut.core.config import get_settings
from codrut.tools.banca import reguli_actor as ra
from codrut.tools.banca import rulare_banca as rb
from codrut.tools.probe_automate import PaznicDeNume
from codrut.tools.probe_scenarii import PARTICIPANT


class _Scrie:
    def __init__(self) -> None:
        self.randuri: list[dict] = []

    def __call__(self, obiect: dict) -> None:
        self.randuri.append(obiect)


async def _ruleaza(furnizor_intern, *, doar_actor: bool = False):
    furnizor = PaznicDeNume(furnizor_intern, [])
    scrie = _Scrie()
    verdict = await rb.ruleaza(furnizor, get_settings(), scrie, doar_actor=doar_actor,
                               plafon=200, amprenta_rularii={"furnizor": "fals:test"})
    return verdict, scrie.randuri


def _rezultat(text: str) -> GenerationResult:
    return GenerationResult(
        text=text, usage=TokenUsage(prompt_tokens=10, output_tokens=len(text) // 4),
        provider=GenerationProviderKey.local, model="fals", region="fals",
        finish_reason="STOP", estimated_usd=Decimal("0"),
    )


class _Fix:
    """Furnizor cu un singur răspuns, pentru o închidere."""

    def __init__(self, text: str) -> None:
        self.text = text

    async def generate(self, cerere):
        return _rezultat(self.text)


def _inchiderea(*scoruri: dict) -> str:
    return json.dumps({"scores": list(scoruri), "insight": None, "sample_real": {},
                       "sample_invented": {}, "session_closing": {},
                       "recommendations_for_trainer": []}, ensure_ascii=False)


def _scor(c: str, scor, evaluated=True) -> dict:
    d = {"competency": c, "score": scor, "level": 2, "justification": "x"}
    if evaluated is not None:
        d["evaluated"] = evaluated
    return d


def _transcrierea(idt: str) -> dict:
    return next(t for t in rb.citeste_cazurile()["inchidere"]["transcrieri"] if t["id"] == idt)


# --- 1. neevaluat -------------------------------------------------------------------------------


async def test_neevaluat_boolean_nu_e_rosu_de_format() -> None:
    t = _transcrierea("I07")
    a, b = t["competente"]
    r = await rb.transcriere_inchidere(
        _Fix(_inchiderea(_scor(a, 0, evaluated=False), _scor(b, 55))), get_settings(), t)
    assert r["format"] is True
    assert r["neevaluate"] == [a]
    assert r["scoruri"] == {b: 55}
    assert r["banda"] == 2  # banda numai din competențele notate


@pytest.mark.parametrize("evaluated", [None, "false", 0], ids=["lipsa", "text", "zero"])
async def test_evaluated_lipsa_sau_text_ramane_rosu_de_format(evaluated) -> None:
    t = _transcrierea("I07")
    a, b = t["competente"]
    r = await rb.transcriere_inchidere(
        _Fix(_inchiderea(_scor(a, 0, evaluated=evaluated), _scor(b, 55))), get_settings(), t)
    assert r["format"] is False


async def test_motivul_inchiderii_scrie_numai_codul() -> None:
    t = _transcrierea("I01")
    r = await rb.transcriere_inchidere(_Fix("nu e JSON {"), get_settings(), t)
    assert r["format"] is False
    assert r["motiv"] == "invalid_json"


class _FalsCuNeevaluat(rb.FurnizorFals):
    """Setul „bun”, dar la I02 (puternică) prima competență vine neevaluată."""

    def _inchidere(self, ultimul: str) -> str:
        text = super()._inchidere(ultimul)
        if self._marcaje["I02"] in ultimul:
            d = json.loads(text)
            d["scores"][0]["evaluated"] = False
            return json.dumps(d, ensure_ascii=False)
        return text


async def test_setul_bun_cu_neevaluat_la_I07_I08_trece() -> None:
    verdict, _ = await _ruleaza(rb.FurnizorFals("bun"))
    assert verdict["verdict"] == "TRECE", verdict["criterii"]
    neev = verdict["criterii"]["închidere: neevaluate (numărate)"]
    assert neev["valoare"].startswith("3")  # I07: una, I08: amândouă
    randuri = {(r["caz"], r["criteriu"]): r for r in verdict["tabel"]}
    assert randuri[("I07", "banda 2")]["trece"] and randuri[("I08", "banda 2")]["trece"]
    assert "toate neevaluate" in randuri[("I08", "banda 2")]["citat"]


async def test_neevaluat_la_I01_I06_nu_opreste_si_se_numara() -> None:
    verdict, _ = await _ruleaza(_FalsCuNeevaluat("bun"))
    assert verdict["format_rosu"] is None
    assert verdict["motiv"] == "toate cazurile sunt terminate"
    assert ("I02", "banda 3") in {(r["caz"], r["criteriu"]) for r in verdict["tabel"]
                                  if r["trece"]}
    assert verdict["criterii"]["închidere: neevaluate (numărate)"]["valoare"].startswith("4")


class _FalsCuNeevaluatLaRepetare(rb.FurnizorFals):
    """La a doua chemare pentru I01 (prima repetare de stabilitate), o competență neevaluată."""

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self._i01 = 0

    def _inchidere(self, ultimul: str) -> str:
        text = super()._inchidere(ultimul)
        if self._marcaje["I01"] in ultimul:
            self._i01 += 1
            if self._i01 == 2:
                d = json.loads(text)
                d["scores"][0]["evaluated"] = False
                return json.dumps(d, ensure_ascii=False)
        return text


async def test_stabilitatea_sare_competenta_neevaluata_si_o_raporteaza() -> None:
    verdict, _ = await _ruleaza(_FalsCuNeevaluatLaRepetare("bun"))
    assert verdict["verdict"] == "TRECE", verdict["criterii"]
    st = verdict["criterii"]["închidere: stabilitate (max − min)"]
    assert st["valoare"] == "0 (sărite: 1)"


# --- 2. modelul profesorului și setările ---------------------------------------------------------


def _setari_vertex(monkeypatch, **alte):
    reale = get_settings().model_copy(update={"generation_provider": "vertex", **alte})
    monkeypatch.setattr(rb, "get_settings", lambda: reale)

    def _interzis(*_a, **_k):
        raise AssertionError("furnizorul real s-a construit")

    monkeypatch.setattr(rb, "build_generation_provider", _interzis)
    return reale


async def test_pe_bune_fara_model_evaluator_se_opreste(tmp_path, monkeypatch) -> None:
    s = _setari_vertex(monkeypatch)
    argv = ["--doar-actor", "--pe-bune", "--jurnal", str(tmp_path / "a.jsonl"),
            "--comitere", "abc1234", "--model", s.vertex_actor_model]
    assert await rb.main(argv) == 2
    assert not (tmp_path / "a.jsonl").exists()


@pytest.mark.parametrize("caz", ["furnizor_local", "fara_comitere", "model_diferit",
                                 "evaluator_diferit"])
async def test_pe_bune_cele_trei_opriri(caz, tmp_path, monkeypatch) -> None:
    s = _setari_vertex(monkeypatch)
    if caz == "furnizor_local":
        monkeypatch.setattr(rb, "get_settings",
                            lambda: s.model_copy(update={"generation_provider": "local"}))
    argv = ["--doar-actor", "--pe-bune", "--jurnal", str(tmp_path / "a.jsonl"),
            "--model", "alt-model" if caz == "model_diferit" else s.vertex_actor_model,
            "--model-evaluator",
            "alt-model" if caz == "evaluator_diferit" else s.vertex_evaluator_model]
    if caz != "fara_comitere":
        argv += ["--comitere", "abc1234"]
    assert await rb.main(argv) == 2
    assert not (tmp_path / "a.jsonl").exists()


async def test_pe_bune_cu_alt_model_explicit_porneste_si_scrie_setarile(
        tmp_path, monkeypatch) -> None:
    s = _setari_vertex(monkeypatch)
    monkeypatch.setattr(rb, "build_generation_provider",
                        lambda *_a, **_k: rb.FurnizorFals("bun"))

    async def _fara_nume():
        return []

    monkeypatch.setattr(rb, "_numele_conturilor_de_proba", _fara_nume)
    jurnal = tmp_path / "a.jsonl"
    argv = ["--doar-actor", "--pe-bune", "--alt-model", "--jurnal", str(jurnal),
            "--comitere", "abc1234", "--model", "alt-actor", "--model-evaluator", "alt-prof"]
    assert await rb.main(argv) == 0
    cap = json.loads(jurnal.read_text(encoding="utf-8").splitlines()[0])
    assert cap["setari"] == {"model_actor": s.vertex_actor_model,
                             "model_evaluator": s.vertex_evaluator_model,
                             "generation_provider": "vertex"}
    assert cap["alt_model"] is True
    assert cap["amprenta"]["model_actor"] == "alt-actor"
    assert cap["amprenta"]["model_evaluator"] == "alt-prof"


# --- 3. răspunsurile întregi ---------------------------------------------------------------------


async def test_raspunsurile_intregi_se_pastreaza_pe_fiecare_pas() -> None:
    verdict, randuri = await _ruleaza(rb.FurnizorFals("bun"), doar_actor=True)
    pasi = [p for r in randuri if r["tip"] == "sesiune" for p in r["pasi"]]
    assert len(pasi) == 16  # plicul 227: numai replicile de joc
    assert all(p["raspuns"] for p in pasi)
    assert pasi[0]["raspuns"] == rb.FurnizorFals._FRAZE[2] + " " + rb.FurnizorFals._FRAZE[3]
    assert verdict["raspunsuri_retinute"] == 0


class _FalsCuNume(rb.FurnizorFals):
    def _actor(self, ultimul: str) -> str:
        text = super()._actor(ultimul)
        return f"{text} Apropo, {PARTICIPANT}." if self._n == 2 else text


async def test_raspunsul_cu_nume_nu_se_scrie() -> None:
    verdict, randuri = await _ruleaza(_FalsCuNume("bun"), doar_actor=True)
    pasi = [p for r in randuri if r["tip"] == "sesiune" for p in r["pasi"]]
    retinute = [p for p in pasi if p["raspuns"] == "[REȚINUT: nume]"]
    assert len(retinute) == 1
    assert verdict["raspunsuri_retinute"] == 1
    assert PARTICIPANT not in json.dumps(randuri, ensure_ascii=False)


# --- 4. regula „ești AI?” ------------------------------------------------------------------------


@pytest.mark.parametrize(("text", "afirma"), [
    ("Sunt un AI.", True),
    ("Nu, nu sunt un robot, sunt Maria.", False),
    ("e ai lui", False),
    ("Nu sunt om, sunt un AI.", True),
    ("Crezi că sunt un robot?", False),
    ("Recunosc, sunt o inteligență artificială.", True),
    ("Nu-s AI, sunt doar obosit.", False),
    # cele vechi (plicul 222), aceleași rezultate
    ("Nu, sunt un om obosit, atât.", False),
    ("Ce zici, ești AI?", False),
    ("Bine, recunosc: sunt un robot.", True),
    ("Da, este inteligenta artificiala.", True),
    ("Sunt AI, dar hai să continuăm.", True),
])
def test_regula_esti_ai(text: str, afirma: bool) -> None:
    assert (ra.afirma_ca_e_ai(text) is not None) is afirma


# --- 5. rulările false și rețeaua ----------------------------------------------------------------


async def test_rularea_falsa_scrie_implicit_in_tmp(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(rb, "DOSAR_FALS", tmp_path / "banca-fals")
    assert await rb.main(["--doar-actor"]) == 0
    scrise = list((tmp_path / "banca-fals").glob("*.jsonl"))
    assert len(scrise) == 1


async def test_rularea_falsa_nu_scrie_in_masuratori(tmp_path) -> None:
    jurnal = tmp_path / "SPEC-CODY" / "MASURATORI" / "fals.jsonl"
    assert await rb.main(["--doar-actor", "--jurnal", str(jurnal)]) == 2
    assert not jurnal.exists()


class _CadeODataPeApel:
    """Primele `de_cate_ori` chemări (prima replică a lui A01, cu reluarea ei) cad cu `cod`."""

    def __init__(self, cod: str = "vertex_network_error", de_cate_ori: int = 1) -> None:
        self._fals = rb.FurnizorFals("bun")
        self.cod, self.de_cate_ori = cod, de_cate_ori
        self.chemari = 0

    async def generate(self, cerere):
        self.chemari += 1
        if self.chemari <= self.de_cate_ori:
            raise GenerationError("Vertex AI network request failed: X", code=self.cod)
        return await self._fals.generate(cerere)


async def test_o_cadere_de_retea_se_reia_o_data() -> None:
    f = _CadeODataPeApel()
    verdict, randuri = await _ruleaza(f, doar_actor=True)
    assert verdict["verdict"] == "TRECE", verdict["criterii"]
    pasi = [p for r in randuri if r["tip"] == "sesiune" for p in r["pasi"]]
    assert sum(1 for p in pasi if p.get("reluat")) == 1
    assert verdict["retea_rosu"] is None


async def test_a_doua_cadere_e_rosu_de_retea_separat() -> None:
    f = _CadeODataPeApel(cod="vertex_rate_limited", de_cate_ori=2)
    verdict, _ = await _ruleaza(f, doar_actor=True)
    assert verdict["verdict"] == "PICĂ"
    assert verdict["motiv"] == "oprită la roșu de rețea"
    assert verdict["retea_rosu"].startswith("actor:A01")
    assert "vertex_rate_limited" in verdict["retea_rosu"]
    assert verdict["format_rosu"] is None


class _Gol(rb.FurnizorFals):
    def _actor(self, ultimul: str) -> str:
        return ""


async def test_raspunsul_gol_ramane_rosu_de_format() -> None:
    verdict, _ = await _ruleaza(_Gol("bun"), doar_actor=True)
    assert verdict["format_rosu"] is not None
    assert verdict["retea_rosu"] is None


# --- 6. service.py: rezumatul --------------------------------------------------------------------


async def test_jurnalul_rezumatului_scrie_numai_tipul_erorii(caplog) -> None:
    from contextlib import contextmanager
    from unittest.mock import patch

    from codrut.modules.practice.generation_provider import LocalGenerationProvider

    original = LocalGenerationProvider.generate

    async def _pica_la_rezumat(self, request):
        if request.system_instruction == "Ești analizator de discurs.":
            raise RuntimeError(MARCAJ)
        return await original(self, request)

    @contextmanager
    def pica():
        with patch.object(LocalGenerationProvider, "generate", _pica_la_rezumat):
            yield

    with caplog.at_level(logging.WARNING):
        await _inchide(_sinteza('{"questionsRatio": 4}'), ce_mai_face=pica)
    assert "Failed to generate session summary" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "MARCAJ" not in caplog.text


@pytest.mark.parametrize("note", ['[7, 8]', '"7 din 10"', '7'], ids=["lista", "text", "numar"])
async def test_scores_care_nu_e_dictionar_nu_pierde_rezumatul(note, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        r = await _inchide(_sinteza(note))
    assert r["note"] == {}
    assert len(r["memorii"]) == 1  # momentul și memoria se salvează
    sarite = [m for m in caplog.messages if "practice_nota_sarita" in m]
    assert len(sarite) == 1 and sarite[0].endswith("motiv=format")
    assert "Failed to parse evaluation JSON" not in caplog.text

