"""Ruta hărții echipei și modelele ei de răspuns — plicul 240 (L4-P1).

Stă în fișier separat ca `practice/router.py` și `schemas.py` (ale lui 236) să rămână neatinse.
Paza e cea din 242: trainerul alocat proiectului sau proprietarul platformei.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.modules.companies.access import require_project_trainer
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.harta_echipei import harta_echipei

router = APIRouter()


class Cifra(BaseModel):
    valoare: int | float | None
    motiv: Literal["prea_putini"] | None


class HartaSaptamana(BaseModel):
    saptamana: str
    au_exersat: Cifra


class HartaCompetenta(BaseModel):
    nume: str
    oameni: Cifra
    inceput: Cifra
    acum: Cifra


class HartaSlabe(BaseModel):
    nume: list[str] | None
    motiv: Literal["prea_putini"] | None


class HartaObiectiv(BaseModel):
    nr: int
    titlu: str
    oameni: int


class HartaObiective(BaseModel):
    si_au_ales: Cifra
    cele_mai_alese: list[HartaObiectiv]
    motiv: Literal["prea_putini", "fara_obiective"] | None


class HartaEchipeiResponse(BaseModel):
    project_id: UUID
    calculat_la: datetime
    prag_oameni: int
    invitati: Cifra
    au_exersat: Cifra
    pe_saptamani: list[HartaSaptamana]
    sesiuni: Cifra
    minute: Cifra
    competente: list[HartaCompetenta]
    cele_mai_slabe: HartaSlabe
    obiective: HartaObiective


@router.get("/projects/{project_id}/harta-echipei", response_model=HartaEchipeiResponse)
async def get_harta_echipei(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> HartaEchipeiResponse:
    """Harta echipei pentru HR — numai cifre de grup, prag de 5 oameni (plicul 240)."""
    await require_project_trainer(session, principal, project_id)
    date = await harta_echipei(session, project_id, acum=datetime.now(UTC))
    return HartaEchipeiResponse(**date)
