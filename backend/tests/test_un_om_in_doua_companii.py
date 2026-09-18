"""Regresia plicului 73: un om cu profil in doua companii nu mai face sa crape nimic.

Defectul a fost gasit si reparat o data, la plicul 30, pe drumul participantului: profilul se
cauta dupa cont SAU adresa, fara companie, cu `scalar_one_or_none`, deci un om cu profil in
doua companii dadea MultipleResultsFound si 500. Reparatia s-a oprit la primul loc din trei.
Celelalte doua — pornirea pe drumul trainerului si tabloul participantului — au ramas cu forma
veche, masurat pe proba la plicul 73 cu proba1 (profil si in „Pilot Cody", si in „test").

Regula de alegere e cea de la plicul 30: in compania proiectului cand exista una; profilul
legat de cont inaintea celui doar cu adresa; intre egali, cel mai vechi.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
)
from codrut.modules.identity.models import User, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
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


async def _om_in_doua_companii(session):
    """Doua companii, acelasi om (doar adresa, fara cont) in amandoua; proiectul e in a doua."""
    sufix = uuid.uuid4().hex[:8]
    adresa = f"om-{sufix}@exemplu-cody.ro"

    prima = Company(name=f"Prima {sufix}")
    a_doua = Company(name=f"A doua {sufix}")
    session.add_all([prima, a_doua])
    await session.flush()

    proiect = CompanyProject(
        company_id=a_doua.id,
        name=f"Training {sufix}",
        status=CompanyProjectStatus.active,
        project_type="training",
    )
    tema = PracticeTheme(slug=f"tema-{sufix}", name="Tema")
    session.add_all([proiect, tema])
    await session.flush()

    pachet = PracticeKnowledgePack(
        theme_id=tema.id,
        version=1,
        state=KnowledgePackState.approved,
        checksum=sufix,
        content_uri="memory://test",
    )
    session.add(pachet)
    await session.flush()

    session.add(
        PracticeProgramSettings(
            project_id=proiect.id,
            mode=ProgramMode.training,
            theme_id=tema.id,
            active_pack_id=pachet.id,
            usd_cap_per_participant=Decimal("3.00"),
        )
    )

    acum = datetime.now(UTC)
    in_prima = ParticipantProfile(
        company_id=prima.id, full_name="Om Test", email=adresa,
        created_at=acum - timedelta(hours=2),
    )
    in_a_doua = ParticipantProfile(
        company_id=a_doua.id, full_name="Om Test", email=adresa,
        created_at=acum - timedelta(hours=1),
    )
    session.add_all([in_prima, in_a_doua])
    await session.flush()
    return adresa, proiect, in_prima, in_a_doua


def _principal(adresa: str, rol: UserRole, user_id: uuid.UUID | None = None) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=user_id or uuid.uuid4(),
        email=adresa,
        role=rol,
        available_workspaces=(rol,),
        default_workspace=rol,
        session_token="test",
    )


@pytest.mark.asyncio
async def test_pornirea_pe_drumul_trainerului_alege_profilul_din_compania_proiectului() -> None:
    async with SessionLocal() as session:
        adresa, proiect, in_prima, in_a_doua = await _om_in_doua_companii(session)

        svc = PracticeSessionService(session=session)
        svc._prima_replica = AsyncMock(return_value=None)  # fara model in test
        sesiune, _ = await svc.start_trainer_session(
            _principal(adresa, UserRole.trainer), proiect.id, SessionKind.roleplay
        )

        assert sesiune.participant_profile_id == in_a_doua.id
        await session.rollback()


@pytest.mark.asyncio
async def test_tabloul_nu_crapa_nici_cu_proiect_nici_fara() -> None:
    async with SessionLocal() as session:
        adresa, proiect, _, _ = await _om_in_doua_companii(session)
        tablou = PracticeDashboardService(session=session)
        principal = _principal(adresa, UserRole.participant)

        fara = await tablou.get_participant_dashboard_data(principal=principal, project_id=None)
        cu = await tablou.get_participant_dashboard_data(principal=principal, project_id=proiect.id)

        assert isinstance(fara, dict)
        assert isinstance(cu, dict)
        await session.rollback()


@pytest.mark.asyncio
async def test_contul_cautat_dupa_id_sau_adresa_nu_mai_poate_crapa() -> None:
    """Id-ul principalului e al unui cont, adresa e a altuia: se ia contul cu id-ul exact."""
    async with SessionLocal() as session:
        sufix = uuid.uuid4().hex[:8]
        unu = User(email=f"unu-{sufix}@exemplu-cody.ro", password_hash="x", role=UserRole.participant)
        doi = User(email=f"doi-{sufix}@exemplu-cody.ro", password_hash="x", role=UserRole.participant)
        session.add_all([unu, doi])
        await session.flush()

        principal = _principal(doi.email, UserRole.participant, user_id=unu.id)
        date = await PracticeDashboardService(session=session).get_participant_dashboard_data(
            principal=principal, project_id=None
        )

        assert isinstance(date, dict)
        await session.rollback()
