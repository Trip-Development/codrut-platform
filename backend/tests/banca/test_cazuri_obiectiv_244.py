"""Cazurile de bancă „pe obiectiv” — plicul 244, testul 7 (numai cazurile; rularea = alt plic).

Fișierele noi nu intră în `FISIERE_CAZURI`: `--banca` și `--doar-actor` rămân exact cum sunt
(105 / 16 apeluri), deci etalonul 238 rămâne comparabil.
"""

from __future__ import annotations

import json

from codrut.tools.banca import rulare_banca as rb


def _json(nume: str) -> dict:
    return json.loads((rb.CAZURI / nume).read_text(encoding="utf-8"))


def _catalogul() -> dict[int, dict]:
    from codrut.modules.practice import obiective

    date = json.loads((obiective.DOSAR / "comunicare-asertiva.json").read_text(encoding="utf-8"))
    return {o["nr"]: o for o in date["obiective"]}


def test_fisierele_sunt_json_valid_cu_id_urile_o01_o03() -> None:
    cazuri = _json("obiectiv.json")
    cheia = _json("cheia_obiectiv.json")
    assert [c["id"] for c in cazuri["actor"]] == ["O01", "O02"]
    assert [c["id"] for c in cazuri["profesor_replica"]] == ["O03"]
    assert cheia["actor"]["cazuri"] == ["O01", "O02"]
    assert sorted(cheia["profesor_replica"]) == ["O03-a", "O03-b", "O03-c"]
    for c in cazuri["actor"]:
        assert len(c["replici"]) == 4
        assert len(c["cuvinte_situatie"]) == 3
    o3 = cazuri["profesor_replica"][0]
    assert o3["scena"].startswith("{personaj}:")
    assert all(o3[k] for k in ("a", "b", "c"))


def test_obiectiv_nr_exista_in_catalog_si_cuvintele_sunt_din_situatie() -> None:
    catalog = _catalogul()
    cazuri = _json("obiectiv.json")
    for c in (*cazuri["actor"], *cazuri["profesor_replica"]):
        assert c["obiectiv_nr"] in catalog
    for c in cazuri["actor"]:
        situatia = catalog[c["obiectiv_nr"]]["situatie"].lower()
        assert sum(1 for w in c["cuvinte_situatie"] if w.lower() in situatia) >= 2


def test_poarta_de_nume_zero_pe_amandoua() -> None:
    paznic = rb.PaznicDeNume(None, [])
    for nume in ("obiectiv.json", "cheia_obiectiv.json"):
        assert paznic.numara((rb.CAZURI / nume).read_text(encoding="utf-8")) == 0


def test_banca_de_azi_ramane_neschimbata() -> None:
    assert rb.FISIERE_CAZURI == (
        "actor.json", "profesor_replica.json", "inchidere.json", "rezumat.json",
    )
    assert rb.apeluri_planificate(False) == 105
    assert rb.apeluri_planificate(True) == 16
