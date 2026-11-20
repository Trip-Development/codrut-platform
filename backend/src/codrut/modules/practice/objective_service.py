"""Obiectivele de aplicare: lista proiectului și alegerea omului — plicul 230 (L1-P1).

Totul e al omului, pentru el însuși: omul se caută ca la acord (`profilul_in_proiect`), deci un
cont fără profil de participant în firma proiectului (inclusiv un trainer) e refuzat. Nicio
funcție de aici nu întoarce alegerea altcuiva și nu scrie nimic în jurnalul serverului.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.acord import profilul_in_proiect
from codrut.modules.practice.models import (
    PracticeObjective,
    PracticeObjectiveChoice,
    PracticeProgramSettings,
)


def _obiectivul(o: PracticeObjective) -> dict:
    return {
        "id": o.id,
        "nr": o.order_index,
        "titlu": o.title,
        "situatie": o.situation,
        "competente": list(o.competencies or []),
        "semn_de_reusita": o.success_sign,
    }


async def _catalogul_proiectului(session: AsyncSession, proiect_id: uuid.UUID) -> str | None:
    return (await session.execute(
        select(PracticeProgramSettings.objective_catalog)
        .where(PracticeProgramSettings.project_id == proiect_id)
    )).scalar_one_or_none()


async def _obiectivele_active(session: AsyncSession, catalog: str) -> list[PracticeObjective]:
    return list((await session.execute(
        select(PracticeObjective)
        .where(PracticeObjective.catalog == catalog, PracticeObjective.is_active.is_(True))
        .order_by(PracticeObjective.order_index)
    )).scalars().all())


async def lista_obiectivelor(
    session: AsyncSession, principal: SessionPrincipal, proiect_id: uuid.UUID
) -> dict:
    """Obiectivele active ale proiectului, în ordine; listă goală dacă proiectul n-are catalog."""
    await profilul_in_proiect(session, principal, proiect_id)
    catalog = await _catalogul_proiectului(session, proiect_id)
    if not catalog:
        return {"catalog": None, "catalog_name": None, "obiective": []}
    obiective = await _obiectivele_active(session, catalog)
    return {
        "catalog": catalog,
        "catalog_name": obiective[0].catalog_name if obiective else None,
        "obiective": [_obiectivul(o) for o in obiective],
    }


async def _alegerile(
    session: AsyncSession, profil_id: uuid.UUID, proiect_id: uuid.UUID
) -> list[tuple[PracticeObjectiveChoice, PracticeObjective]]:
    return [tuple(r) for r in (await session.execute(
        select(PracticeObjectiveChoice, PracticeObjective)
        .join(PracticeObjective, PracticeObjective.id == PracticeObjectiveChoice.objective_id)
        .where(
            PracticeObjectiveChoice.participant_profile_id == profil_id,
            PracticeObjectiveChoice.project_id == proiect_id,
        )
        .order_by(PracticeObjectiveChoice.chosen_at, PracticeObjectiveChoice.created_at)
    )).all()]


def _starea(alegeri: list[tuple[PracticeObjectiveChoice, PracticeObjective]]) -> dict:
    curent = next(((a, o) for a, o in alegeri if a.replaced_at is None), None)
    return {
        "curent": (
            {"obiectiv": _obiectivul(curent[1]), "aleasa_la": curent[0].chosen_at}
            if curent else None
        ),
        "prima_alegere_la": alegeri[0][0].chosen_at if alegeri else None,
        "istoric": [
            {
                "obiectiv_id": o.id,
                "titlu": o.title,
                "aleasa_la": a.chosen_at,
                "inlocuita_la": a.replaced_at,
            }
            for a, o in alegeri
        ],
    }


async def alegerea_mea(
    session: AsyncSession, principal: SessionPrincipal, proiect_id: uuid.UUID
) -> dict:
    """Alegerea curentă a omului pe proiect, data primei alegeri și istoricul."""
    profil = await profilul_in_proiect(session, principal, proiect_id)
    return _starea(await _alegerile(session, profil.id, proiect_id))


async def alege(
    session: AsyncSession,
    principal: SessionPrincipal,
    proiect_id: uuid.UUID,
    obiectiv_id: uuid.UUID,
) -> dict:
    """Omul își alege un obiectiv din lista proiectului; alegerea veche intră în istoric."""
    profil = await profilul_in_proiect(session, principal, proiect_id)
    catalog = await _catalogul_proiectului(session, proiect_id)
    if not catalog:
        raise DomainError(
            "Acest proiect nu are obiective de ales.", code="obiective_lipsa"
        )
    obiectiv = (await session.execute(
        select(PracticeObjective).where(
            PracticeObjective.id == obiectiv_id,
            PracticeObjective.catalog == catalog,
            PracticeObjective.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if obiectiv is None:
        raise DomainError(
            "Obiectivul ales nu e în lista acestui proiect.", code="obiectiv_nepermis"
        )

    alegeri = await _alegerile(session, profil.id, proiect_id)
    curent = next((a for a, _ in alegeri if a.replaced_at is None), None)
    if curent is not None and curent.objective_id == obiectiv.id:
        return _starea(alegeri)
    acum = datetime.now(UTC)
    if curent is not None:
        curent.replaced_at = acum
        await session.flush()  # întâi se închide alegerea veche (indexul unic parțial)
    session.add(PracticeObjectiveChoice(
        participant_profile_id=profil.id,
        project_id=proiect_id,
        objective_id=obiectiv.id,
        chosen_at=acum,
    ))
    await session.flush()
    return _starea(await _alegerile(session, profil.id, proiect_id))
