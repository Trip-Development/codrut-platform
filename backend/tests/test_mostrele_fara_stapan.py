"""Regresia plicului 94: o mostra fara stapan nu ajunge pe tabloul nimanui.

Mostrele „asa ai spus" sunt replici adevarate, scoase din sesiunea unui om. Tabloul le lua pe
ale omului SI pe cele cu `user_id` gol, deci o mostra fara stapan aparea la oricine. Pe proba
erau zero randuri de felul asta (le poate scrie doar importul arhivei), deci reparatia e
preventiva — dar lacatul trebuie sa prinda ramura daca revine.
"""

import uuid
from datetime import UTC, datetime

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.models import SessionSample


def _principal(cont: User) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=cont.id, email=cont.email, role=UserRole.participant,
        consent_current=True, terms_accepted_at=datetime.now(UTC),
        session_token="test",  # noqa: S106
    )


async def _om_cu_mostra_si_o_mostra_fara_stapan(session):
    sufix = uuid.uuid4().hex[:8]
    om = User(
        email=f"om-{sufix}@exemplu-cody.ro",
        password_hash="x",  # noqa: S106
        role=UserRole.participant,
    )
    altul = User(
        email=f"altul-{sufix}@exemplu-cody.ro",
        password_hash="x",  # noqa: S106
        role=UserRole.participant,
    )
    session.add_all([om, altul])
    await session.flush()

    a_lui = SessionSample(
        user_id=om.id, conversation_id=f"sesiune-{sufix}",
        real_weak="replica lui", real_improved="replica lui, mai buna",
    )
    fara_stapan = SessionSample(
        user_id=None, conversation_id="legacy_samples_archive",
        real_weak="replica altcuiva", real_improved="replica altcuiva, mai buna",
    )
    session.add_all([a_lui, fara_stapan])
    await session.flush()
    return om, altul, a_lui, fara_stapan


@pytest.mark.asyncio
async def test_mostra_fara_stapan_nu_ajunge_pe_tabloul_nimanui() -> None:
    async with SessionLocal() as session:
        om, altul, a_lui, fara_stapan = await _om_cu_mostra_si_o_mostra_fara_stapan(session)
        tablou = PracticeDashboardService(session)

        ale_omului = await tablou.get_participant_dashboard_data(principal=_principal(om))
        ale_altuia = await tablou.get_participant_dashboard_data(principal=_principal(altul))

        assert [m["id"] for m in ale_omului["session_samples"]] == [str(a_lui.id)]
        assert ale_altuia["session_samples"] == []
        assert str(fara_stapan.id) not in {m["id"] for m in ale_omului["session_samples"]}
        await session.rollback()
