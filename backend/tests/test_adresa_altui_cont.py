"""Regresia plicului 79: un profil legat de contul A nu ajunge la contul B doar prin adresa.

Exersarea cauta profilul dupa cont SAU adresa. Pe ramura adresei lua si profilurile legate de
ALT cont. Reparatie preventiva: pe proba, la plicul 79, 0 profiluri erau in situatia asta. Dar
e aceeasi regula pe care spatiul participantului o are de la plicul 75, pusa acum si aici.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.models import (
    KnowledgePackState,
    PracticeKnowledgePack,
    PracticeProgramSettings,
    PracticeTheme,
    ProgramMode,
    SessionKind,
)
from codrut.modules.practice.service import PracticeSessionService

NUMELE_PROFILULUI_LUI_A = "Profilul Contului A"


async def _profil_al_lui_a_cu_adresa_lui_b(session):
    sufix = uuid.uuid4().hex[:8]
    a = User(
        email=f"a-{sufix}@exemplu-cody.ro",
        password_hash="x",  # noqa: S106
        role=UserRole.participant,
    )
    b = User(
        email=f"b-{sufix}@exemplu-cody.ro",
        password_hash="x",  # noqa: S106
        role=UserRole.participant,
    )
    companie = Company(name=f"Companie {sufix}")
    session.add_all([a, b, companie])
    await session.flush()

    proiect = CompanyProject(
        company_id=companie.id, name=f"Training {sufix}",
        status=CompanyProjectStatus.active, project_type="training",
    )
    tema = PracticeTheme(slug=f"tema-{sufix}", name="Tema")
    session.add_all([proiect, tema])
    await session.flush()
    pachet = PracticeKnowledgePack(
        theme_id=tema.id, version=1, state=KnowledgePackState.approved,
        checksum=sufix, content_uri="memory://test",
    )
    session.add(pachet)
    await session.flush()
    session.add(PracticeProgramSettings(
        project_id=proiect.id, mode=ProgramMode.training, theme_id=tema.id,
        active_pack_id=pachet.id, is_enabled=True, usd_cap_per_participant=Decimal("3.00"),
    ))
    # legat de A, dar cu adresa lui B
    profil = ParticipantProfile(
        company_id=companie.id, user_id=a.id, full_name=NUMELE_PROFILULUI_LUI_A, email=b.email,
    )
    session.add(profil)
    await session.flush()
    session.add(ProjectMembership(
        company_id=companie.id, project_id=proiect.id,
        participant_profile_id=profil.id, active=True,
    ))
    await session.flush()
    return b, proiect, profil


def _principal(cont: User, rol: UserRole) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=cont.id, email=cont.email, role=rol,
        available_workspaces=(rol,), default_workspace=rol,
        consent_current=True, terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION, session_token="test",  # noqa: S106
    )


@pytest.mark.asyncio
async def test_profilul_pentru_istoric_si_replici_nu_e_al_altui_cont() -> None:
    async with SessionLocal() as session:
        b, _proiect, _profil = await _profil_al_lui_a_cu_adresa_lui_b(session)

        with pytest.raises(DomainError) as eroare:
            await PracticeSessionService(session=session)._resolve_participant_profile(
                _principal(b, UserRole.participant)
            )
        assert eroare.value.code == "participant_profile_not_found"
        await session.rollback()


@pytest.mark.asyncio
async def test_pornirea_participantului_nu_foloseste_profilul_altui_cont() -> None:
    async with SessionLocal() as session:
        b, proiect, _profil = await _profil_al_lui_a_cu_adresa_lui_b(session)
        svc = PracticeSessionService(session=session)
        svc._prima_replica = AsyncMock(return_value=None)

        with pytest.raises(DomainError):
            await svc.start_session(
                _principal(b, UserRole.participant), proiect.id, SessionKind.roleplay
            )
        await session.rollback()


# Drumul trainerului (start_trainer_session) NU e acoperit aici, dinadins — plicul 79.
# Cu ramura adresei ingustata, trainerul B n-ar mai gasi profilul si ar incerca sa creeze unul
# cu aceeasi adresa in aceeasi companie: incalcare de unicitate, 500. Ramura acolo ramane larga.


@pytest.mark.asyncio
async def test_tabloul_nu_arata_profilul_altui_cont() -> None:
    async with SessionLocal() as session:
        b, _proiect, _profil = await _profil_al_lui_a_cu_adresa_lui_b(session)

        date = await PracticeDashboardService(session=session).get_participant_dashboard_data(
            principal=_principal(b, UserRole.participant)
        )
        assert date["participant_name"] != NUMELE_PROFILULUI_LUI_A
        await session.rollback()
