"""Regresia plicului 75: aceeasi persoana, doua usi, acelasi profil.

Exersarea gasea profilul dupa cont SAU adresa; spatiul participantului doar dupa cont. Un
profil venit din import de lista, cu adresa dar nelegat de cont, era gasit de exersare si
negasit de spatiul participantului. Legarea automata se face doar la crearea contului si la
deschiderea unei invitatii, deci cine avea deja cont cand a fost importat ramanea nelegat.
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
from codrut.modules.participants.service import ParticipantWorkspaceService
from codrut.modules.practice.models import (
    KnowledgePackState,
    PracticeKnowledgePack,
    PracticeProgramSettings,
    PracticeTheme,
    ProgramMode,
    SessionKind,
)
from codrut.modules.practice.service import PracticeSessionService


async def _cont_si_profil_nelegat(session):
    """Un cont existent si, in compania proiectului, un profil cu aceeasi adresa, nelegat."""
    sufix = uuid.uuid4().hex[:8]
    adresa = f"om-{sufix}@exemplu-cody.ro"
    cont = User(email=adresa, password_hash="x", role=UserRole.participant)  # noqa: S106
    companie = Company(name=f"Companie {sufix}")
    session.add_all([cont, companie])
    await session.flush()

    proiect = CompanyProject(
        company_id=companie.id,
        name=f"Training {sufix}",
        status=CompanyProjectStatus.active,
        project_type="training",
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
    session.add(
        PracticeProgramSettings(
            project_id=proiect.id, mode=ProgramMode.training, theme_id=tema.id,
            active_pack_id=pachet.id, is_enabled=True, usd_cap_per_participant=Decimal("3.00"),
        )
    )
    profil = ParticipantProfile(company_id=companie.id, full_name="Om Test", email=adresa)
    session.add(profil)
    await session.flush()
    session.add(
        ProjectMembership(
            company_id=companie.id, project_id=proiect.id,
            participant_profile_id=profil.id, active=True,
        )
    )
    # omul de test și-a dat acordul la prima intrare — plicul 139
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    from codrut.modules.practice.acord import AMPRENTA
    from codrut.modules.practice.models import PracticeConsent

    session.add(PracticeConsent(
        participant_profile_id=profil.id, project_id=proiect.id, text_hash=AMPRENTA,
        accepted_at=_dt.now(_UTC),
    ))
    await session.flush()
    return cont, proiect, profil


@pytest.mark.asyncio
async def test_spatiul_participantului_gaseste_profilul_nelegat() -> None:
    async with SessionLocal() as session:
        cont, _proiect, profil = await _cont_si_profil_nelegat(session)
        assert profil.user_id is None

        rezumat = await ParticipantWorkspaceService(session).get_workspace_summary(cont.id)

        assert rezumat.participant_profile_id == profil.id
        await session.rollback()


@pytest.mark.asyncio
async def test_exersarea_gaseste_acelasi_profil() -> None:
    async with SessionLocal() as session:
        cont, proiect, profil = await _cont_si_profil_nelegat(session)
        principal = SessionPrincipal(
            user_id=cont.id, email=cont.email, role=UserRole.participant,
            available_workspaces=(UserRole.participant,), default_workspace=UserRole.participant,
            consent_current=True, terms_accepted_at=datetime.now(UTC),
            terms_version=CURRENT_TERMS_VERSION, session_token="test",  # noqa: S106
        )
        svc = PracticeSessionService(session=session)
        svc._prima_replica = AsyncMock(return_value=None)  # fara model in test

        sesiune, _ = await svc.start_session(principal, proiect.id, SessionKind.roleplay)

        assert sesiune.participant_profile_id == profil.id
        await session.rollback()


@pytest.mark.asyncio
async def test_un_profil_legat_de_alt_cont_nu_apare_doar_fiindca_are_aceeasi_adresa() -> None:
    async with SessionLocal() as session:
        cont, _proiect, profil = await _cont_si_profil_nelegat(session)
        altcineva = User(
            email=f"altul-{uuid.uuid4().hex[:8]}@exemplu-cody.ro",
            password_hash="x", role=UserRole.participant,  # noqa: S106
        )
        session.add(altcineva)
        await session.flush()
        profil.user_id = altcineva.id  # acum e al altui cont, desi adresa e a primului
        await session.flush()

        with pytest.raises(DomainError) as eroare:
            await ParticipantWorkspaceService(session).get_workspace_summary(cont.id)

        assert eroare.value.code == "participant_profile_not_found"
        await session.rollback()
