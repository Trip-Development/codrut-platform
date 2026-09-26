"""Regresia plicului 98: omul fara nicio nota afla de ce e gol tabloul.

Dupa plicul 93 tabloul lui era gol, corect dar mut. Sunt doua situatii si un singur text ar minti
pe unul dintre ei: omul neinscris nicaieri primeste textul de la plicul 78, omul inscris care
n-a exersat primeste textul lui Andrei din 19 septembrie. „Inscris" e definitia de la plicul 78.
Poarta plicului 93 ramane inchisa: niciunul nu primeste vreo nota a altcuiva.
"""

import uuid
from datetime import UTC, datetime

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.models import CompetencyScore

NEINSCRIS = "Nu ești încă înscris într-un proiect. Trainerul tău te adaugă, și apoi poți începe."
NEEXERSAT = (
    "Încă nu ai exersat. După prima sesiune vei vedea aici cum cresc competențele tale în "
    "funcție de cât și cum ai exersat."
)


def _principal(cont: User) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=cont.id, email=cont.email, role=UserRole.participant,
        consent_current=True, terms_accepted_at=datetime.now(UTC),
        session_token="test",  # noqa: S106
    )


def _cont(sufix: str, nume: str) -> User:
    return User(
        email=f"{nume}-{sufix}@exemplu-cody.ro",
        password_hash="x",  # noqa: S106
        role=UserRole.participant,
    )


async def _trei_oameni(session):
    """Unul neinscris nicaieri, unul inscris fara note, unul inscris cu note."""
    sufix = uuid.uuid4().hex[:8]
    neinscris, inscris, cu_note = (_cont(sufix, n) for n in ("neinscris", "inscris", "cu-note"))
    companie = Company(name=f"Companie {sufix}")
    session.add_all([neinscris, inscris, cu_note, companie])
    await session.flush()
    proiect = CompanyProject(
        company_id=companie.id, name=f"Training {sufix}",
        status=CompanyProjectStatus.active, project_type="training",
    )
    session.add(proiect)
    await session.flush()
    for cont in (inscris, cu_note):
        profil = ParticipantProfile(
            company_id=companie.id, user_id=cont.id, full_name="Om Test", email=cont.email,
        )
        session.add(profil)
        await session.flush()
        session.add(ProjectMembership(
            company_id=companie.id, project_id=proiect.id,
            participant_profile_id=profil.id, active=True,
        ))
    session.add(CompetencyScore(
        user_id=cu_note.id, project_id=proiect.id, score=90, level=3,
        conversation_id=f"sesiune-{sufix}", competency_name="Ascultare activă",
        source_type="roleplay",
    ))
    await session.flush()
    return neinscris, inscris, cu_note


def _fara_date_de_la_altii(tablou: dict) -> bool:
    return not any(c["total_roleplays"] or c["average_score"] for c in tablou["competencies"])


@pytest.mark.asyncio
async def test_fiecare_om_fara_note_afla_situatia_lui() -> None:
    async with SessionLocal() as session:
        neinscris, inscris, cu_note = await _trei_oameni(session)
        tablou = PracticeDashboardService(session)

        t_neinscris = await tablou.get_participant_dashboard_data(principal=_principal(neinscris))
        t_inscris = await tablou.get_participant_dashboard_data(principal=_principal(inscris))
        t_cu_note = await tablou.get_participant_dashboard_data(principal=_principal(cu_note))

        gol = t_neinscris.get("empty_state") or {}
        assert gol.get("kind") == "neinscris"
        assert f"{gol['title']} {gol['description']}" == NEINSCRIS

        gol = t_inscris.get("empty_state") or {}
        assert gol.get("kind") == "neexersat"
        assert f"{gol['title']} {gol['description']}" == NEEXERSAT

        assert "empty_state" not in t_cu_note
        # poarta plicului 93: nicio nota a altcuiva la cei fara note
        assert _fara_date_de_la_altii(t_neinscris) and _fara_date_de_la_altii(t_inscris)
        await session.rollback()
