"""Plicul 259 — banca rulează și cazurile pe obiectiv (O01, O02, O03 cu a/b/c), cu `--obiectiv`.

Hotărârea lui Andrei [praguri-obiectiv] (23 nov 2026, 11:22): „da” — 4 din 4 (cu 3 din 3
inclus), nota minimă 7 la O03-c. Numai furnizorul fals; zero apeluri.

Paznicii (t1, t2, t15) sunt verzi și pe baza dinaintea plicului, dinadins: fără `--obiectiv`,
cererile băncii trebuie să rămână octet cu octet cele de azi. Materialul Bibliotecii se
înlocuiește în paznici cu un text fix (`_MATERIAL`), ca amprenta să nu depindă de calculator.
"""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal

import pytest

from codrut.core.config import get_settings
from codrut.modules.practice import prompts as prompts_mod
from codrut.tools.banca import rulare_banca as rb
from codrut.tools.probe_automate import PaznicDeNume

N = 106  # apeluri_planificate(False) pe baza 4994d98 (K0 d)
N_DOAR_ACTOR = 17
NOI = 13  # O01 (1 + 4), O02 (1 + 4), O03-a/b/c
# amprentele de pe baza 4994d98, luate în R0 (raw/R0-rosu.txt), cu materialul fix
AMPRENTA_A01 = "c9ff33e42a76decb7a825d763d1e34097a2383bbdbc59fe6651d2f052ee15891"
AMPRENTA_A04 = "58536e00e1777dba2b1366b9c86783d7e9a0e1d7c79b3784391a850bd081b97e"
AMPRENTA_P01_A = "9b1232cabbc14bfe0460d0d864c0b294d5ac792b7540cc0fc81cf2678c501ed6"
# dicționarul PRAGURI de pe baza 4994d98 (R0), fără cheile noi
PRAGURI_BAZA = {
    "actor_conversatii_min": 11,
    "actor_doar_actor_min": 4,
    "profesor_bune_min": 10, "scor_bun": 8,
    "profesor_slabe_min": 10, "scor_slab": 5,
    "perechi_min": 10, "diferenta_pereche": 3,
    "porti_profesor_procent": 90,
    "stabilitate_replica_max": 1,
    "inchidere_banda_min": 7,
    "stabilitate_inchidere_max": 15,
    "rezumat_min": 4,
}
CRIT_O3 = "obiectiv: O01–O03 (cheia 244)"
CRIT_O4 = "obiectiv: toate, cu O03-c"
_MATERIAL = "MATERIAL FIX PENTRU AMPRENTĂ"


def _json(nume: str) -> dict:
    return json.loads((rb.CAZURI / nume).read_text(encoding="utf-8"))


def _cazurile_obiectiv() -> dict:
    return _json("obiectiv.json")


def _catalogul() -> dict[int, dict]:
    from codrut.modules.practice import obiective

    date = obiective.citeste_catalog("comunicare-asertiva")
    return {o["nr"]: o for o in date["obiective"]}


def _amprenta(cereri) -> str:
    h = hashlib.sha256()
    for c in cereri:
        h.update(json.dumps([c.system_instruction, [[m.role, m.text] for m in c.messages]],
                            ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()


@pytest.fixture
def material_fix(monkeypatch):
    monkeypatch.setattr(prompts_mod, "get_core_material", lambda *_a, **_k: (_MATERIAL, 0))


class _Scrie:
    def __init__(self) -> None:
        self.randuri: list[dict] = []

    def __call__(self, obiect: dict) -> None:
        self.randuri.append(obiect)


async def _ruleaza(furnizor, *, obiectiv: bool):
    scrie = _Scrie()
    kw = {"obiectiv": True} if obiectiv else {}
    verdict = await rb.ruleaza(PaznicDeNume(furnizor, []), get_settings(), scrie,
                               doar_actor=False, plafon=10**6,
                               amprenta_rularii={"furnizor": "fals"}, **kw)
    return verdict, scrie.randuri


def _sesiuni(randuri: list[dict], prefix: str = "banca:") -> list[dict]:
    return [{k: v for k, v in r.items() if k not in ("terminata", "secunde")}
            for r in randuri if r.get("tip") == "sesiune" and r["id"].startswith(prefix)
            and not r["id"].startswith("banca:obiectiv:")]


# ---------------------------------------------------------------- paznicii (verzi și pe bază)


async def test_t1_paza_actorul_fara_obiectiv_neschimbat(material_fix) -> None:
    setari = get_settings()
    cazuri = rb.citeste_cazurile()
    conv = {c["id"]: c for c in cazuri["actor"]["conversatii"]}
    for idc, asteptat in (("A01", AMPRENTA_A01), ("A04", AMPRENTA_A04)):
        m = rb._Masoara()
        await rb.conversatie_actor(m, setari, conv[idc], cazuri["actor"]["salut"])
        assert _amprenta(m.cereri) == asteptat, idc


def test_t2_paza_profesorul_fara_obiectiv_neschimbat(material_fix) -> None:
    scena = rb.citeste_cazurile()["profesor_replica"]["scene"][0]
    assert scena["id"] == "P01"
    cerere = rb._cerere_profesor(get_settings(), scena, scena["a"])
    assert _amprenta([cerere]) == AMPRENTA_P01_A


def test_t15_paznicul_de_nume_zero_pe_fisierele_obiectiv() -> None:
    paznic = PaznicDeNume(None, [])
    for nume in ("obiectiv.json", "cheia_obiectiv.json"):
        assert paznic.numara((rb.CAZURI / nume).read_text(encoding="utf-8")) == 0


# ---------------------------------------------------------------- funcțiile noi


def test_t3_obiectivul_cazului_din_catalog() -> None:
    cazuri, cata = _cazurile_obiectiv(), _catalogul()
    o1, o2 = cazuri["actor"]
    o3 = cazuri["profesor_replica"][0]
    for caz, nr in ((o1, 1), (o2, 8), (o3, 2)):
        ob = rb.obiectivul_cazului(caz)
        assert set(ob) == {"titlu", "situatie", "semn_de_reusita"}
        assert ob == {k: cata[nr][k] for k in ("titlu", "situatie", "semn_de_reusita")}
    with pytest.raises(ValueError):
        rb.obiectivul_cazului({"obiectiv_nr": 999})
    c, k = rb.citeste_cazurile_obiectiv()
    assert c == cazuri and k == _json("cheia_obiectiv.json")


async def test_t4_cererea_de_setup_la_o01() -> None:
    setari = get_settings()
    o1 = _cazurile_obiectiv()["actor"][0]
    ob = rb.obiectivul_cazului(o1)
    salut = _cazurile_obiectiv()["salut"]
    m = rb._Masoara()
    rez = await rb.conversatie_obiectiv(m, setari, o1, salut, ob)
    assert len(m.cereri) == 5
    setup = m.cereri[0]
    asteptat, _ = prompts_mod.get_prompts_pe_meserii(
        name=rb.COD_PARTICIPANT, history_length=prompts_mod.REPLICA_DE_CONFIRMARE, memories=[],
        biblioteca_path=setari.biblioteca_path, profil_rol=rb._profil(o1["nr"]),
        competenta_tinta=None, obiectiv=ob)
    assert setup.system_instruction == asteptat
    assert setup.system_instruction.endswith(
        "\n\n---\n" + prompts_mod.completeaza_obiectivul(prompts_mod.OBIECTIV_ACTOR, ob))
    assert [(x.role, x.text) for x in setup.messages] == [("model", salut),
                                                          ("user", rb.PORNIRE_OM)]
    # jocul: istoricul fix = salut, „Da, hai.”, setup-ul fără regie
    joc = m.cereri[1]
    assert [x.role for x in joc.messages[:3]] == ["model", "user", "model"]
    assert joc.messages[2].text == rb.fara_regie(rez["pasi"][0]["raspuns"])
    assert rez["pasi"][0]["fel"] == "setup" and rez["pasi"][0]["pas"] == 0


def test_t5_profesorul_pe_obiectiv_la_o03_a() -> None:
    o3 = _cazurile_obiectiv()["profesor_replica"][0]
    ob = rb.obiectivul_cazului(o3)
    cerere = rb._cerere_profesor(get_settings(), o3, o3["a"], obiectiv=ob)
    bloc = prompts_mod.completeaza_obiectivul(prompts_mod.OBIECTIV_PROFESOR, ob)
    assert cerere.system_instruction.endswith("\n\n---\n" + bloc + prompts_mod.FARA_SCENA)
    fara = rb._cerere_profesor(get_settings(), o3, o3["a"])
    assert bloc not in fara.system_instruction


def test_t6_regula_setupului() -> None:
    from codrut.tools.banca.reguli_actor import setup_pe_obiectiv as f

    cuv = ["vineri", "raport", "urgent"]
    bun = ("Obiectivul tău: să spui nu.\n\nE vineri, ora cinci, iar șeful vine cu un raport "
           "urgent.\n\nMihai: „Am nevoie de el până diseară.”")
    assert f(bun, "Mihai", cuv) is None  # (a)
    assert f("", "Mihai", cuv) == "setup gol"
    assert f(bun.replace("Obiectivul tău", "Ținta"), "Mihai", cuv) == (
        "lipsește «Obiectivul tău»")  # (b)
    assert f("OBIECTIVUL TĂU: x\n\nvineri raport urgent\n\nMihai: „da”", "Mihai", cuv) is None
    assert f(bun, "Ana", cuv) == "nu se încheie cu replica lui Ana"  # (c)
    unul = "Obiectivul tău: x\n\nE vineri și e liniște.\n\nMihai: „Ai un minut?”"
    assert f(unul, "Mihai", cuv) == "cuvintele situației: 1 din 3 (vineri)"  # (d)
    # (e) început de cuvânt, fără deosebire de litere
    prinse = "Obiectivul tău: x\n\nVINERI, Raportului îi lipsesc tabelele.\n\nMihai: „Deci?”"
    assert f(prinse, "Mihai", ["vineri", "raport", "tabel"]) is None
    # (f) nu se prind: „neurgent”, „vinerea”, „rapoartele”
    neprinse = "Obiectivul tău: x\n\nNeurgent, vinerea, rapoartele.\n\nMihai: „Deci?”"
    assert f(neprinse, "Mihai", cuv) == "cuvintele situației: 0 din 3 ()"


# ---------------------------------------------------------------- rularea și verdictul


async def test_t7_t8_bun_cu_si_fara_obiectiv() -> None:
    cu, rand_cu = await _ruleaza(rb.FurnizorFals("bun"), obiectiv=True)
    fara, rand_fara = await _ruleaza(rb.FurnizorFals("bun"), obiectiv=False)
    # t7
    assert cu["verdict"] == "TRECE", {k: v for k, v in cu["criterii"].items() if not v["trece"]}
    assert cu["criterii"][CRIT_O3]["valoare"] == "3/3" and cu["criterii"][CRIT_O3]["trece"]
    assert cu["criterii"][CRIT_O4]["valoare"] == "4/4" and cu["criterii"][CRIT_O4]["trece"]
    ids = [r["id"] for r in rand_cu if r.get("tip") == "sesiune"
           and r["id"].startswith("banca:obiectiv:")]
    assert ids == ["banca:obiectiv:O01", "banca:obiectiv:O02", "banca:obiectiv:O03-a",
                   "banca:obiectiv:O03-b", "banca:obiectiv:O03-c"]
    o01 = next(r for r in rand_cu if r.get("id") == "banca:obiectiv:O01")
    assert o01["apeluri"] == 5
    assert o01["pasi"][0]["raspuns"].startswith("Obiectivul tău")
    assert cu["apeluri"] == N + NOI and fara["apeluri"] == N
    o1 = _cazurile_obiectiv()["actor"][0]
    r = await rb.conversatie_obiectiv(rb.FurnizorFals("bun"), get_settings(), o1,
                                      _cazurile_obiectiv()["salut"], rb.obiectivul_cazului(o1))
    assert r["pasi"][0]["fel"] == "setup"
    assert r["criterii"]["setup_pe_obiectiv"][0] is True
    # t8: cazurile de azi neatinse
    assert _sesiuni(rand_cu) == _sesiuni(rand_fara)
    assert CRIT_O3 not in fara["criterii"] and CRIT_O4 not in fara["criterii"]
    assert {k: v for k, v in cu["criterii"].items() if k not in (CRIT_O3, CRIT_O4)} == (
        fara["criterii"])
    assert fara["criterii"]["actor: conversații care trec tot"]["valoare"] == "12/12"
    assert fara["criterii"]["profesor: bune ≥ 8/10"]["valoare"] == "12/12"


async def test_t9_stricat_cu_obiectiv_pica_inainte_de_cazurile_noi() -> None:
    v, randuri = await _ruleaza(rb.FurnizorFals("stricat"), obiectiv=True)
    assert v["verdict"] == "PICĂ"
    assert not [r for r in randuri if str(r.get("id", "")).startswith("banca:obiectiv:")]
    assert v["criterii"][CRIT_O3]["valoare"] == "0/3" and not v["criterii"][CRIT_O3]["trece"]
    assert v["criterii"][CRIT_O4]["valoare"] == "0/4" and not v["criterii"][CRIT_O4]["trece"]


class _ProfesorSase(rb.FurnizorFals):
    """Profesorul dă 6 la replica pe jumătate bună (O03-c)."""

    def _profesor(self, ultimul: str) -> str:
        c = _cazurile_obiectiv()["profesor_replica"][0]["c"]
        if ultimul.rsplit("\n\n", 1)[-1] == c:
            return "Scor: 6/10\nCeri exemple, dar încă nu propui nimic."
        return super()._profesor(ultimul)


class _FaraEticheta(rb.FurnizorFals):
    """La O01, setup-ul n-are «Obiectivul tău»; rândul personajului rămâne."""

    def _actor(self, cerere) -> str:
        text = super()._actor(cerere)
        titlu = _catalogul()[1]["titlu"]
        if text.startswith("Obiectivul tău") and titlu in (cerere.system_instruction or ""):
            return text.split("\n\n", 1)[1]
        return text


async def test_t10_o03_c_sub_prag_pica() -> None:
    v, _ = await _ruleaza(_ProfesorSase("bun"), obiectiv=True)
    assert v["criterii"][CRIT_O3]["valoare"] == "3/3" and v["criterii"][CRIT_O3]["trece"]
    assert v["criterii"][CRIT_O4]["valoare"] == "3/4" and not v["criterii"][CRIT_O4]["trece"]
    assert v["verdict"] == "PICĂ"


async def test_t11_setup_fara_eticheta_pica() -> None:
    v, _ = await _ruleaza(_FaraEticheta("bun"), obiectiv=True)
    picate = {(r["caz"], r["criteriu"]) for r in v["tabel"] if not r["trece"]}
    assert ("O01", "setup_pe_obiectiv") in picate
    assert ("O02", "setup_pe_obiectiv") not in picate
    assert v["criterii"][CRIT_O3]["valoare"] == "2/3"
    assert v["verdict"] == "PICĂ"


def test_t12_apeluri_planificate() -> None:
    assert rb.apeluri_planificate(False) == N
    assert rb.apeluri_planificate(True) == N_DOAR_ACTOR
    assert rb.apeluri_planificate(False, obiectiv=True) == N + NOI
    # plafonul implicit (160) acoperă banca întreagă cu cazurile pe obiectiv
    assert N + NOI <= 160


async def test_t13_steagul_obiectiv(tmp_path) -> None:
    j1 = tmp_path / "a" / "b.jsonl"
    j1.parent.mkdir()
    assert await rb.main(["--obiectiv", "--doar-actor", "--jurnal", str(j1)]) == 2
    assert not j1.exists()
    j2 = tmp_path / "c" / "d.jsonl"
    j2.parent.mkdir()
    assert await rb.main(["--obiectiv", "--jurnal", str(j2)]) == 0
    randuri = [json.loads(x) for x in j2.read_text(encoding="utf-8").splitlines()]
    cap = randuri[0]
    assert cap["tip"] == "cap" and cap["obiectiv"] is True
    assert cap["apeluri_planificate"] == N + NOI
    assert randuri[-1]["apeluri"] == N + NOI
    j3 = tmp_path / "e" / "f.jsonl"
    j3.parent.mkdir()
    assert await rb.main(["--jurnal", str(j3)]) == 0
    cap = json.loads(j3.read_text(encoding="utf-8").splitlines()[0])
    assert cap["obiectiv"] is False and cap["apeluri_planificate"] == N


def test_t14_pragurile_noi_si_cele_vechi_neschimbate() -> None:
    assert rb.PRAGURI["obiectiv_o01_o03_min"] == 3
    assert rb.PRAGURI["obiectiv_toate_min"] == 4
    assert rb.PRAGURI["scor_partial"] == 7
    vechi = {k: v for k, v in rb.PRAGURI.items()
             if k not in ("obiectiv_o01_o03_min", "obiectiv_toate_min", "scor_partial")}
    assert vechi == PRAGURI_BAZA


async def test_t16_costul_maxim_pe_obiectiv_e_pesimist() -> None:
    from codrut.contracts.generation import GenerationPurpose
    from codrut.modules.practice.pricing import estimate_pessimistic_cost

    setari = get_settings()
    cu = await rb.cost_maxim(setari, doar_actor=False, obiectiv=True)
    fara = await rb.cost_maxim(setari, doar_actor=False)
    assert cu["apeluri"] == N + NOI and fara["apeluri"] == N
    m = rb._Masoara()
    await rb.ruleaza(m, setari, lambda _r: None, doar_actor=False, plafon=10**6,
                     amprenta_rularii={}, obiectiv=True)
    suma = Decimal("0")
    for c in m.cereri[N:]:
        caractere = len(c.system_instruction or "") + sum(len(x.text) for x in c.messages)
        intrat = math.ceil(caractere / rb.CARACTERE_PE_UNITATE)
        if c.purpose == GenerationPurpose.actor:
            # numai salutul e fix; setup-ul e generat (corecția 5)
            ale_lui = sum(1 for x in c.messages if x.role == "model") - 1
            intrat += max(0, ale_lui) * c.max_output_tokens
        suma += estimate_pessimistic_cost(intrat, c.max_output_tokens, c.thinking_budget or 0,
                                          setari, model=rb._modelul_cererii(setari, c))
    diferenta = Decimal(str(cu["usd"])) - Decimal(str(fara["usd"]))
    assert abs(diferenta - suma) < Decimal("0.000001")
    assert suma > 0
