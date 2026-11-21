"""Migrările nu depind de cod și își țin datele înghețate — plicul 235 (230b), testele 3 și 4.

O migrare veche trebuie să dea același rezultat peste un an, oricum ar arăta atunci codul
aplicației sau fișierele JSON din pachet. De aceea: niciun import din `codrut`, niciun fișier
citit, iar obiectivele stau scrise în migrare. Paza 3 se aplică pe TOATE migrările, ca orice
migrare viitoare să fie prinsă automat.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

VERSIUNI = Path(__file__).resolve().parents[1] / "migrations" / "versions"
APELURI_INTERZISE = {"open", "Path", "read_text", "read_bytes", "load"}

# json.dumps(list(OBIECTIVE), ensure_ascii=False, sort_keys=True) din 0071, sha256 (corecția 4)
AMPRENTA_OBIECTIVE_0071 = "a78831d3812ffea09717b74a54df064c3694b8eb42ebe8f3e0b0ace3f35f383a"


def _numele_apelului(nod: ast.Call) -> str | None:
    if isinstance(nod.func, ast.Name):
        return nod.func.id
    if isinstance(nod.func, ast.Attribute):
        return nod.func.attr
    return None


def _ce_e_interzis(cale: Path) -> list[str]:
    arbore = ast.parse(cale.read_text(encoding="utf-8"), filename=str(cale))
    gasite: list[str] = []
    for nod in ast.walk(arbore):
        if isinstance(nod, ast.Import):
            gasite += [f"import {a.name}" for a in nod.names if a.name.split(".")[0] == "codrut"]
        elif isinstance(nod, ast.ImportFrom):
            if (nod.module or "").split(".")[0] == "codrut":
                gasite.append(f"from {nod.module} import …")
        elif isinstance(nod, ast.Call):
            nume = _numele_apelului(nod)
            if nume in APELURI_INTERZISE:
                if nume == "load" and not (
                    isinstance(nod.func, ast.Attribute)
                    and isinstance(nod.func.value, ast.Name)
                    and nod.func.value.id == "json"
                ):
                    continue
                gasite.append(f"apel {nume}() la rândul {nod.lineno}")
    return gasite


def test_cele_doua_migrari_de_obiective_exista() -> None:
    for nume in ("0071_practice_objectives.py", "0072_practice_objectives_fb.py"):
        assert (VERSIUNI / nume).is_file(), nume


@pytest.mark.parametrize(
    "cale", sorted(VERSIUNI.glob("*.py")), ids=lambda c: c.name
)
def test_nicio_migrare_nu_importa_din_codrut_si_nu_citeste_fisiere(cale: Path) -> None:
    assert _ce_e_interzis(cale) == []


def _incarca(nume: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"migrare_{nume}", VERSIUNI / f"{nume}.py")
    if spec is None or spec.loader is None:
        raise AssertionError(f"Migrarea {nume} nu se poate încărca.")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _json(cheie: str) -> dict:
    from codrut.modules.practice import obiective

    return json.loads((obiective.DOSAR / f"{cheie}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("migrare", "cheie"),
    [
        ("0071_practice_objectives", "comunicare-asertiva"),
        ("0072_practice_objectives_fb", "feedback"),
    ],
)
def test_datele_inghetate_sunt_cele_din_json(migrare: str, cheie: str) -> None:
    modul = _incarca(migrare)
    date = _json(cheie)
    assert modul.CATALOG == date["catalog"]
    assert modul.NUME == date["nume"]
    # aceleași chei și valori, aceeași ordine
    assert [list(o.items()) for o in modul.OBIECTIVE] == [
        list(o.items()) for o in date["obiective"]
    ]


def test_amprenta_obiectivelor_din_0071_e_fixata() -> None:
    modul = _incarca("0071_practice_objectives")
    text = json.dumps(list(modul.OBIECTIVE), ensure_ascii=False, sort_keys=True)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == AMPRENTA_OBIECTIVE_0071


def _revizia(cale: Path) -> str | None:
    arbore = ast.parse(cale.read_text(encoding="utf-8"), filename=str(cale))
    for nod in arbore.body:
        tinte: list[ast.expr] = []
        valoare: ast.expr | None = None
        if isinstance(nod, ast.Assign):
            tinte, valoare = list(nod.targets), nod.value
        elif isinstance(nod, ast.AnnAssign) and nod.value is not None:
            tinte, valoare = [nod.target], nod.value
        for tinta in tinte:
            if isinstance(tinta, ast.Name) and tinta.id == "revision":
                if isinstance(valoare, ast.Constant) and isinstance(valoare.value, str):
                    return valoare.value
    return None


@pytest.mark.parametrize(
    "cale", sorted(VERSIUNI.glob("*.py")), ids=lambda c: c.name
)
def test_id_ul_oricarei_migrari_incape_in_alembic_version(cale: Path) -> None:
    # alembic_version.version_num e varchar(32): un id mai lung oprește urcarea (oprirea 235).
    revizia = _revizia(cale)
    assert revizia is not None, cale.name
    assert len(revizia) <= 32, f"{revizia} are {len(revizia)} caractere"
