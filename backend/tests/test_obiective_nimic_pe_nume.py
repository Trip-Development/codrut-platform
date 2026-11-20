"""„Nimic pe nume” — plicul 230 (L1-P1), testul 6.

Obiectivul ales de un om nu ajunge la trainer, la HR sau la șef pe nume: după o alegere, paginile
trainerului și tabloul omului sunt identice cu cele de dinainte și nu conțin nici id-ul, nici
titlul obiectivului. Rutele noi sunt numai ale omului, pentru el însuși.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.main import create_app
from codrut.modules.practice.models import PracticeProgramSettings
from test_practice_router import make_test_client, setup_practice_context

CATALOG = "comunicare-asertiva"


async def _instantaneu(ctx) -> dict[str, tuple[int, str]]:
    proiect, profil = ctx["project"].id, ctx["profile"].id
    out: dict[str, tuple[int, str]] = {}
    async with make_test_client(ctx["trainer"], trainer_direct_entry=True) as trainer:
        for cale in (
            f"/api/practice/projects/{proiect}/room",
            f"/api/practice/projects/{proiect}/participants/{profil}",
            f"/api/practice/projects/{proiect}/evolution",
            f"/api/practice/projects/{proiect}/invitations",
            # nu există o rută GET aici (numai POST, care pornește o ședință): se compară
            # răspunsul așa cum e, ca să se vadă dacă apare ceva nou
            "/api/practice/trainer/sessions",
        ):
            r = await trainer.get(cale)
            out[cale] = (r.status_code, r.text)
    async with make_test_client(ctx["participant"]) as omul:
        for cale in (
            f"/api/practice/dashboard?project_id={proiect}",
            f"/api/practice/participant/dashboard?project_id={proiect}",
        ):
            r = await omul.get(cale)
            out[cale] = (r.status_code, r.text)
    return out


@pytest.mark.asyncio
async def test_dupa_alegere_paginile_trainerului_si_tabloul_nu_se_schimba() -> None:
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)
    async with SessionLocal() as session:
        setari = (await session.execute(
            select(PracticeProgramSettings)
            .where(PracticeProgramSettings.project_id == ctx["project"].id)
        )).scalar_one()
        setari.objective_catalog = CATALOG
        await session.commit()

    inainte = await _instantaneu(ctx)
    for cale, (cod, _) in inainte.items():
        if "trainer/sessions" not in cale:
            assert cod == 200, cale

    proiect = ctx["project"].id
    async with make_test_client(ctx["participant"]) as omul:
        lista = (await omul.get(f"/api/practice/projects/{proiect}/obiective")).json()
        ales = lista["obiective"][1]
        r = await omul.post(
            f"/api/practice/projects/{proiect}/obiectiv", json={"objective_id": ales["id"]}
        )
        assert r.status_code == 200
        assert r.json()["curent"]["obiectiv"]["id"] == ales["id"]

    dupa = await _instantaneu(ctx)
    assert dupa == inainte
    for _, text in dupa.values():
        assert ales["id"] not in text
        assert json.dumps(ales["titlu"])[1:-1] not in text
        assert ales["titlu"] not in text


def test_rutele_noi_nu_primesc_id_de_om() -> None:
    cai = create_app().openapi()["paths"]
    noi = sorted(
        (metoda, cale) for cale, metode in cai.items()
        if cale.endswith(("/obiective", "/obiectiv")) for metoda in metode
    )
    assert noi == [
        ("get", "/api/practice/projects/{project_id}/obiectiv"),
        ("get", "/api/practice/projects/{project_id}/obiective"),
        ("post", "/api/practice/projects/{project_id}/obiectiv"),
    ]
    for cale, metode in cai.items():
        if cale.endswith(("/obiective", "/obiectiv")):
            for detalii in metode.values():
                parametri = {p["name"] for p in detalii.get("parameters", [])}
                assert parametri == {"project_id"}, cale
    from codrut.modules.practice.schemas import PracticeObjectiveChooseRequest

    assert set(PracticeObjectiveChooseRequest.model_fields) == {"objective_id"}
