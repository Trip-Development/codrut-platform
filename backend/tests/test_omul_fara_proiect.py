"""Regresia plicului 78: omul fara proiect vede ce are de facut.

Pana la plicul 78 se adauga cate un context pentru fiecare profil, chiar gol. Un om cu profil
dar fara nicio inscriere si nicio sarcina primea „alege un context" dintr-o lista goala, sau
numele firmei afisat drept proiect. Iar daca scoteai doar contextele goale, alegerea
contextului dadea StopIteration, adica 500.

Acum: contextele fara legatura reala nu intra in lista, iar omul fara niciun context real
primeste o stare cu mesajul lui Andrei — nu o eroare, nu un selector gol.
"""

import uuid

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
from codrut.modules.participants.service import ParticipantWorkspaceService

# Textele lui Andrei, cuvant cu cuvant. Scrise aici de mana dinadins: testul pazeste si ca nu
# le rescrie nimeni.
NEINSCRIS_TITLU = "Nu ești încă înscris într-un proiect."
NEINSCRIS_DESCRIERE = "Trainerul tău te adaugă, și apoi poți începe."


async def _cont_cu_profiluri(session, *, inscris_in_a_doua: bool):
    """Un cont cu profil legat in doua companii; inscris (optional) doar in a doua."""
    sufix = uuid.uuid4().hex[:8]
    cont = User(email=f"om-{sufix}@exemplu-cody.ro", password_hash="x", role=UserRole.participant)
    prima = Company(name=f"Prima {sufix}")
    a_doua = Company(name=f"A doua {sufix}")
    session.add_all([cont, prima, a_doua])
    await session.flush()

    in_prima = ParticipantProfile(company_id=prima.id, user_id=cont.id, full_name="Om Test", email=cont.email)
    in_a_doua = ParticipantProfile(company_id=a_doua.id, user_id=cont.id, full_name="Om Test", email=cont.email)
    session.add_all([in_prima, in_a_doua])
    await session.flush()

    if inscris_in_a_doua:
        proiect = CompanyProject(
            company_id=a_doua.id, name=f"Proiect {sufix}",
            status=CompanyProjectStatus.active, project_type="training",
        )
        session.add(proiect)
        await session.flush()
        session.add(ProjectMembership(
            company_id=a_doua.id, project_id=proiect.id,
            participant_profile_id=in_a_doua.id, active=True,
        ))
        await session.flush()
    return cont, in_prima, in_a_doua


@pytest.mark.asyncio
async def test_omul_fara_nicio_inscriere_primeste_mesajul_nu_o_eroare() -> None:
    async with SessionLocal() as session:
        cont, _, _ = await _cont_cu_profiluri(session, inscris_in_a_doua=False)

        rezumat = await ParticipantWorkspaceService(session).get_workspace_summary(cont.id)

        assert rezumat.context_selection_required is False  # nu un selector gol
        assert rezumat.contexts == []
        assert rezumat.project_name is None                 # nici numele firmei
        assert rezumat.empty_state.title == NEINSCRIS_TITLU
        assert rezumat.empty_state.description == NEINSCRIS_DESCRIERE
        await session.rollback()


@pytest.mark.asyncio
async def test_contextul_gol_nu_mai_apare_langa_cel_real() -> None:
    async with SessionLocal() as session:
        cont, in_prima, in_a_doua = await _cont_cu_profiluri(session, inscris_in_a_doua=True)

        rezumat = await ParticipantWorkspaceService(session).get_workspace_summary(cont.id)

        assert [c.participant_profile_id for c in rezumat.contexts] == [in_a_doua.id]
        assert rezumat.participant_profile_id == in_a_doua.id
        await session.rollback()


@pytest.mark.asyncio
async def test_profilul_gol_cerut_pe_nume_primeste_mesajul_nu_500() -> None:
    """Un profil fara legatura reala, cerut explicit (ca la previzualizarea trainerului)."""
    async with SessionLocal() as session:
        cont, in_prima, _ = await _cont_cu_profiluri(session, inscris_in_a_doua=True)

        rezumat = await ParticipantWorkspaceService(session).get_workspace_summary(
            cont.id, participant_profile_id=in_prima.id
        )

        assert rezumat.empty_state.title == NEINSCRIS_TITLU
        assert rezumat.project_name is None
        await session.rollback()
