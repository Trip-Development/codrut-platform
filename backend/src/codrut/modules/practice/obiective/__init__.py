"""Cataloagele de obiective de aplicare — plicul 230 (Cody 2.0, linia 1, L1-P1).

Un catalog = lista de obiective a unui training (întâi cele 12 de comunicare asertivă, aprobate
de Andrei pe 17–18 nov 2026). Textele stau în fișierul JSON de lângă acest modul, copiat octet cu
octet din aprobare; aici nu se scrie și nu se reformulează niciun text.

Încărcarea e o funcție comună, care se poate chema de oricâte ori: o folosește migrarea
`0071_practice_objectives` (ca la urcarea pe live să nu rămână niciun pas de mână) și testele.
Scrie cu un `sa.table(...)` declarat aici, NU cu clasele din `models.py`: migrarea nu trebuie să
depindă de cum arată modelele mai târziu.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, insert

from codrut.modules.practice.competency_aliases import CANONICAL_COMPETENCIES

DOSAR = Path(__file__).resolve().parent
CATALOG_COMUNICARE_ASERTIVA = "comunicare-asertiva"


class CatalogInvalid(ValueError):
    """Fișierul unui catalog nu are forma cerută; nu se scrie nimic."""


def citeste_catalog(cheie: str) -> dict[str, Any]:
    """Citește JSON-ul catalogului `cheie` din pachet."""
    cale = DOSAR / f"{cheie}.json"
    return json.loads(cale.read_text(encoding="utf-8"))


def valideaza_catalog(date: dict[str, Any]) -> None:
    """Aceleași verificări ca la poarta J0 a plicului 230. Ridică `CatalogInvalid`."""
    for camp in ("catalog", "nume"):
        if not isinstance(date.get(camp), str) or not date[camp].strip():
            raise CatalogInvalid(f"câmpul „{camp}” lipsește sau e gol")
    obiective = date.get("obiective")
    if not isinstance(obiective, list) or not obiective:
        raise CatalogInvalid("lista de obiective lipsește sau e goală")
    if [o.get("nr") for o in obiective] != list(range(1, len(obiective) + 1)):
        raise CatalogInvalid("numerele obiectivelor nu sunt 1…N, fără goluri")
    for o in obiective:
        for camp in ("titlu", "semn_de_reusita"):
            if not isinstance(o.get(camp), str) or not o[camp].strip():
                raise CatalogInvalid(f"obiectivul {o['nr']}: „{camp}” e gol")
        # situația poate fi goală la alte traininguri (ecranul nu arată atunci rândul)
        if not isinstance(o.get("situatie"), str):
            raise CatalogInvalid(f"obiectivul {o['nr']}: „situatie” nu e text")
        competente = o.get("competente")
        if not isinstance(competente, list) or not 1 <= len(competente) <= 7:
            raise CatalogInvalid(f"obiectivul {o['nr']}: competențele trebuie să fie 1–7")
        straine = [c for c in competente if c not in CANONICAL_COMPETENCIES]
        if straine:
            lista = ", ".join(map(str, straine))
            raise CatalogInvalid(f"obiectivul {o['nr']}: competențe din afara celor 7: {lista}")


def _tabelul() -> sa.TableClause:
    return sa.table(
        "practice_objectives",
        sa.column("id", sa.Uuid()),
        sa.column("catalog", sa.String()),
        sa.column("catalog_name", sa.String()),
        sa.column("order_index", sa.Integer()),
        sa.column("title", sa.Text()),
        sa.column("situation", sa.Text()),
        sa.column("success_sign", sa.Text()),
        sa.column("competencies", JSONB()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )


def incarca_catalog(conexiune: sa.engine.Connection, date: dict[str, Any]) -> int:
    """Pune sau actualizează obiectivele catalogului, după (`catalog`, `order_index`).

    Întâi validează tot; un catalog greșit nu scrie nimic. Întoarce câte obiective a scris.
    """
    valideaza_catalog(date)
    tabel = _tabelul()
    acum = datetime.now(UTC)
    for o in date["obiective"]:
        valori = {
            "catalog_name": date["nume"],
            "title": o["titlu"],
            "situation": o["situatie"],
            "success_sign": o["semn_de_reusita"],
            "competencies": list(o["competente"]),
            "is_active": True,
            "updated_at": acum,
        }
        cerere = insert(tabel).values(
            id=uuid.uuid4(), catalog=date["catalog"], order_index=o["nr"], created_at=acum,
            **valori,
        ).on_conflict_do_update(index_elements=["catalog", "order_index"], set_=valori)
        conexiune.execute(cerere)
    return len(date["obiective"])
