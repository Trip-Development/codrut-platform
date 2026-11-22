"""„Nimic pe nume” pentru sesiunile pe obiectiv — plicul 244, testul 5.

După o sesiune pe obiectiv, cu replici, paginile trainerului și tabloul omului nu conțin nici
id-ul, nici titlul, nici situația, nici semnul de reușită al obiectivului. Răspunsul de pornire
n-are câmp nou, iar serviciul nu scrie nimic despre obiectiv în jurnal.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from test_practice_router import make_test_client, setup_practice_context

CATALOG = "comunicare-asertiva"
SERVICE = (
    Path(__file__).resolve().parents[1] / "src" / "codrut" / "modules" / "practice" / "service.py"
)
CAMPURI_DE_AZI = [
    "cody_alias", "ended_at", "first_turn", "id", "kind", "pack_id", "participant_profile_id",
    "program_settings_id", "prompt_version", "scenario_id", "started_at", "state", "turn_count",
]


async def _raspunsurile(ctx) -> dict[str, str]:
    proiect, profil = ctx["project"].id, ctx["profile"].id
    out: dict[str, str] = {}
    async with make_test_client(ctx["trainer"], trainer_direct_entry=True) as trainer:
        for cale in (
            f"/api/practice/projects/{proiect}/room",
            f"/api/practice/projects/{proiect}/participants/{profil}",
            f"/api/practice/projects/{proiect}/evolution",
            f"/api/practice/projects/{proiect}/invitations",
            f"/api/practice/projects/{proiect}/harta-echipei",
            "/api/practice/trainer/sessions",
        ):
            r = await trainer.get(cale)
            out[cale] = r.text
    async with make_test_client(ctx["participant"]) as omul:
        for cale in (
            f"/api/practice/dashboard?project_id={proiect}",
            f"/api/practice/participant/dashboard?project_id={proiect}",
        ):
            r = await omul.get(cale)
            assert r.status_code == 200, cale
            out[cale] = r.text
    return out


@pytest.mark.asyncio
async def test_dupa_o_sesiune_pe_obiectiv_nimic_nu_ajunge_la_trainer() -> None:
    from codrut.modules.practice.models import PracticeObjective, PracticeProgramSettings

    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)
    async with SessionLocal() as session:
        setari = (await session.execute(
            select(PracticeProgramSettings)
            .where(PracticeProgramSettings.project_id == ctx["project"].id)
        )).scalar_one()
        setari.objective_catalog = CATALOG
        await session.commit()
        o = (await session.execute(
            select(PracticeObjective)
            .where(PracticeObjective.catalog == CATALOG, PracticeObjective.order_index == 1)
        )).scalar_one()
        semne = [str(o.id), o.title, o.situation, o.success_sign]

    proiect = ctx["project"].id
    async with make_test_client(ctx["participant"]) as omul:
        r = await omul.post(f"/api/practice/projects/{proiect}/obiectiv",
                            json={"objective_id": str(o.id)})
        assert r.status_code == 200
        r = await omul.post("/api/practice/sessions", json={
            "project_id": str(proiect), "kind": "roleplay", "pe_obiectiv": True,
        })
        assert r.status_code == 201, r.text
        assert sorted(r.json()) == CAMPURI_DE_AZI
        sesiune = r.json()["id"]
        for text in ("Da, hai.", "Azi la cinci nu-l mai pot începe; ți-l dau luni la prânz."):
            t = await omul.post(f"/api/practice/sessions/{sesiune}/turns", json={"text": text})
            assert t.status_code == 200, t.text

    for cale, text in (await _raspunsurile(ctx)).items():
        try:
            citit = json.dumps(json.loads(text), ensure_ascii=False)
        except ValueError:
            citit = text
        for semn in semne:
            assert semn not in text, (cale, semn)
            assert semn not in citit, (cale, semn)


def test_raspunsul_de_pornire_n_are_camp_nou() -> None:
    from codrut.modules.practice.schemas import PracticeSessionResponse

    assert sorted(PracticeSessionResponse.model_fields) == CAMPURI_DE_AZI


def test_serviciul_nu_scrie_obiectivul_in_jurnal() -> None:
    text = SERVICE.read_text(encoding="utf-8")
    randuri = [r for r in text.splitlines() if "logger." in r]
    assert not [r for r in randuri if re.search(r"objective|obiectiv", r, re.I)]
    # niciun `logger.` în blocurile scrise de plicul 244
    for bloc in re.findall(r"# Plicul 244.*?(?=\n\n)", text, re.S):
        assert "logger." not in bloc
