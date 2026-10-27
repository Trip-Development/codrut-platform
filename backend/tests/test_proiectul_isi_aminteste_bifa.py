"""Plicul 197 — pagina de setări a proiectului își amintește bifa.

Andrei, 22 oct: „Dau click pe arata rezultatele pentru participanti, salvez. dar cand dau
refresh, casuta apare din nou nemarcata.” Salvarea scria bifa, dar `get_project_by_id` și
`list_all_projects` construiau răspunsul de mână și o lăsau pe dinafară (împreună cu cele
4 chei de șabloane), deci pagina pornea mereu nebifată.
"""

import uuid

import pytest

from codrut.modules.companies.schemas import (
    CompanyCreateRequest,
    CompanyProjectCreateRequest,
    CompanyProjectUpdateRequest,
)
from test_company_service import FakeCompanyRepository, make_service

CHEI_DE_SABLON = {
    "leadership_invitation_template_key": "invitatie-leadership-test",
    "member_invitation_template_key": "invitatie-membri-test",
    "leadership_reminder_template_key": "reminder-leadership-test",
    "member_reminder_template_key": "reminder-membri-test",
}


async def _proiect_salvat(arata_rezultatele: bool):
    repository = FakeCompanyRepository()
    service = make_service(repository)
    owner_id = uuid.uuid4()
    company = await service.create_company(owner_id, CompanyCreateRequest(name="Client"))
    project = await service.create_project(
        owner_id,
        company.id,
        CompanyProjectCreateRequest(name="Proiect de test"),
    )
    await service.update_project(
        owner_id,
        company.id,
        project.id,
        CompanyProjectUpdateRequest(show_participant_results=arata_rezultatele),
    )
    # Cheile de șablon direct pe model: prin update_project, validatorul de șabloane
    # ar căuta în bază și ar pica pe FakeSession.
    salvat = next(item for item in repository.projects if item.id == project.id)
    for cheie, valoare in CHEI_DE_SABLON.items():
        setattr(salvat, cheie, valoare)
    return service, project.id


@pytest.mark.parametrize("arata_rezultatele", [True, False])
async def test_proiectul_citit_dupa_id_isi_aminteste_bifa(arata_rezultatele: bool) -> None:
    service, project_id = await _proiect_salvat(arata_rezultatele)

    raspuns = await service.get_project_by_id(project_id)

    assert raspuns.show_participant_results is arata_rezultatele


@pytest.mark.parametrize("arata_rezultatele", [True, False])
async def test_lista_proiectelor_isi_aminteste_bifa(arata_rezultatele: bool) -> None:
    service, project_id = await _proiect_salvat(arata_rezultatele)

    raspuns = next(item for item in await service.list_all_projects() if item.id == project_id)

    assert raspuns.show_participant_results is arata_rezultatele


async def test_proiectul_citit_dupa_id_si_lista_poarta_cheile_de_sablon() -> None:
    service, project_id = await _proiect_salvat(True)

    dupa_id = await service.get_project_by_id(project_id)
    din_lista = next(item for item in await service.list_all_projects() if item.id == project_id)

    for raspuns in (dupa_id, din_lista):
        assert {cheie: getattr(raspuns, cheie) for cheie in CHEI_DE_SABLON} == CHEI_DE_SABLON
