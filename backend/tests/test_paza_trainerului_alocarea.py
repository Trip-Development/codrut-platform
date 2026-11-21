"""Alocarea trainerului — plicul 242, §5.3.

Cine face un proiect nou din aplicație e alocat automat la el (altfel și-ar pierde
proiectul la a doua zi). Tabelul nou ține numai id-uri și date. Paza nu scrie în jurnal.
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from test_paza_trainerului_rute import _cont_trainer, _principal
from test_practice_router import make_test_client

SRC = Path(__file__).resolve().parents[1] / "src" / "codrut" / "modules"


@pytest.mark.asyncio
async def test_proiectul_nou_e_alocat_celui_care_il_face() -> None:
    from codrut.modules.companies.models import (
        Company,
        CompanyMembership,
        CompanyMembershipRole,
        ProjectTrainer,
    )

    marca = uuid.uuid4().hex[:8]
    async with SessionLocal() as s:
        firma = Company(name=f"Firma alocare {marca}")
        s.add(firma)
        await s.flush()
        facator = await _cont_trainer(s, marca, "facator")
        altul = await _cont_trainer(s, marca, "altul")
        for u in (facator, altul):
            s.add(CompanyMembership(
                company_id=firma.id, user_id=u.id, role=CompanyMembershipRole.owner,
            ))
        await s.commit()

    async with make_test_client(_principal(facator.id, facator.email)) as client:
        r = await client.post(
            f"/api/companies/{firma.id}/projects",
            json={"name": f"Proiect nou {marca}", "project_type": "training"},
        )
        assert r.status_code == 201, r.text
        proiect_id = r.json()["id"]
        r_setup = await client.get(f"/api/practice/projects/{proiect_id}/setup")
        assert r_setup.status_code == 200, r_setup.text

    async with SessionLocal() as s:
        randuri = (await s.execute(
            select(ProjectTrainer.user_id).where(
                ProjectTrainer.project_id == uuid.UUID(proiect_id)
            )
        )).scalars().all()
    assert randuri == [facator.id]

    async with make_test_client(_principal(altul.id, altul.email)) as client:
        r_altul = await client.get(f"/api/practice/projects/{proiect_id}/setup")
    assert r_altul.status_code == 403, r_altul.text
    assert r_altul.json()["error"]["code"] == "not_project_trainer"


def test_tabelul_tine_numai_id_uri_si_date() -> None:
    from sqlalchemy import UniqueConstraint

    from codrut.modules.companies.models import ProjectTrainer

    coloane = [c.name for c in ProjectTrainer.__table__.columns]
    assert sorted(coloane) == sorted(["id", "project_id", "user_id", "created_at", "updated_at"])
    unice = [
        tuple(c.name for c in u.columns)
        for u in ProjectTrainer.__table__.constraints
        if isinstance(u, UniqueConstraint)
    ]
    assert ("project_id", "user_id") in unice


def test_paza_nu_scrie_in_jurnal_si_temele_raman_singurul_apel_pe_rol() -> None:
    access = (SRC / "companies" / "access.py").read_text(encoding="utf-8")
    arbore = ast.parse(access)
    functii = [
        n for n in ast.walk(arbore)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "require_project_trainer"
    ]
    assert len(functii) == 1
    nume = {n.id for n in ast.walk(functii[0]) if isinstance(n, ast.Name)}
    assert "logger" not in nume and "logging" not in nume

    router = (SRC / "practice" / "router.py").read_text(encoding="utf-8")
    assert router.count("require_trainer_principal(principal)") == 1
    assert router.count("require_project_trainer(") == 9
