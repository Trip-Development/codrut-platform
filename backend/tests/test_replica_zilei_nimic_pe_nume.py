"""„O replică pe zi”: nimic pe nume — plicul 236 (L2-P1), testul 6.

Replica zilei a unui om nu ajunge la trainer, la HR sau la șef: după o replică, paginile
trainerului și tabloul omului sunt identice cu cele de dinainte și nu conțin nici id-ul
situației, nici textul replicii, nici al profesorului. Rutele noi nu primesc un id de om.
Profesorul e fals (ruta e ocolită spre `ProfesorFals`): niciun apel spre model.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.main import create_app
from codrut.modules.practice.models import PracticeProgramSettings
from test_practice_router import make_test_client, setup_practice_context
from test_replica_zilei_profesor import ProfesorFals

TEXT_PROFESOR = "Răspuns inventat al profesorului, unic pentru test. [🏆 Scor: 6/10]"
REPLICA = "Replica inventată a omului, unică pentru test."


async def _instantaneu(ctx) -> dict[str, tuple[int, str]]:
    proiect, profil = ctx["project"].id, ctx["profile"].id
    out: dict[str, tuple[int, str]] = {}
    async with make_test_client(ctx["trainer"], trainer_direct_entry=True) as trainer:
        for cale in (
            f"/api/practice/projects/{proiect}/room",
            f"/api/practice/projects/{proiect}/participants/{profil}",
            f"/api/practice/projects/{proiect}/evolution",
            f"/api/practice/projects/{proiect}/invitations",
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
async def test_dupa_replica_zilei_paginile_trainerului_si_tabloul_nu_se_schimba(
    monkeypatch,
) -> None:
    from codrut.modules.practice import router as ruta

    monkeypatch.setattr(ruta, "build_generation_provider", lambda _s: ProfesorFals(TEXT_PROFESOR))
    monkeypatch.setenv("CODRUT_REPLICA_ZILEI_RASPUNS_IN_FUNDAL", "false")  # plicul 267: calea veche
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)
    async with SessionLocal() as session:
        setari = (await session.execute(
            select(PracticeProgramSettings)
            .where(PracticeProgramSettings.project_id == ctx["project"].id)
        )).scalar_one()
        setari.objective_catalog = "comunicare-asertiva"
        await session.commit()
    # pe drumul omului, codul lui se dă la ecranul de acord (`starea_acordului`), înainte de
    # orice replică; fixtura sare peste ecran, deci omul îl deschide aici, înainte de fotografie
    async with make_test_client(ctx["participant"]) as omul:
        acord = await omul.get(f"/api/practice/projects/{ctx['project'].id}/acord")
        assert acord.status_code == 200 and acord.json()["acordat"] is True

    inainte = await _instantaneu(ctx)
    for cale, (cod, _) in inainte.items():
        assert cod == 200, cale

    proiect = ctx["project"].id
    async with make_test_client(ctx["participant"]) as omul:
        stare = (await omul.get(f"/api/practice/projects/{proiect}/replica-zilei")).json()
        situatie = stare["situatie"]
        r = await omul.post(
            f"/api/practice/projects/{proiect}/replica-zilei",
            json={"situation_id": situatie["id"], "replica": REPLICA},
        )
        assert r.status_code == 200, r.text
        assert r.json()["azi"]["raspuns"] == TEXT_PROFESOR
        assert r.json()["azi"]["nota"] == 6.0

    dupa = await _instantaneu(ctx)
    assert dupa == inainte
    for _, text in dupa.values():
        for urma in (situatie["id"], REPLICA, TEXT_PROFESOR, situatie["text"]):
            assert urma not in text
            assert json.dumps(urma)[1:-1] not in text


def test_rutele_noi_nu_primesc_id_de_om() -> None:
    cai = create_app().openapi()["paths"]
    noi = sorted(
        (metoda, cale) for cale, metode in cai.items()
        if "replica-zilei" in cale for metoda in metode
    )
    assert noi == [
        ("get", "/api/practice/projects/{project_id}/replica-zilei"),
        ("post", "/api/practice/projects/{project_id}/replica-zilei"),
    ]
    for cale, metode in cai.items():
        if "replica-zilei" in cale:
            for detalii in metode.values():
                parametri = {p["name"] for p in detalii.get("parameters", [])}
                assert parametri == {"project_id"}, cale
    from codrut.modules.practice.schemas import PracticeDailyReplyRequest

    assert set(PracticeDailyReplyRequest.model_fields) == {"situation_id", "replica"}
