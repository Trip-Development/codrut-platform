"""Regresia plicului 93: omul fara nicio nota nu vede pe tablou notele altora.

Tabloul participantului avea o rezerva: daca omul n-avea nicio nota, lua ultimele 150 de note
din toata baza, ale oricui, si calcula din ele harta competentelor, nivelurile, seria si XP-ul.
Masurat pe proba la plicul 93: trei conturi fara note vedeau 6 competente din 7 cu niveluri
„INTEGRARE" si „CONSOLIDARE", si unul un „XP total" de 11305 — suma notelor altora.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.competency_aliases import CANONICAL_COMPETENCIES
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.models import CompetencyScore


def _principal(cont: User) -> SessionPrincipal:
    return SessionPrincipal(
        user_id=cont.id, email=cont.email, role=UserRole.participant,
        consent_current=True, terms_accepted_at=datetime.now(UTC),
        session_token="test",  # noqa: S106
    )


async def _doi_oameni(session):
    """Unul cu note pe fiecare competenta canonica, in zile diferite; celalalt fara nicio nota."""
    sufix = uuid.uuid4().hex[:8]
    cu_note = User(
        email=f"cu-note-{sufix}@exemplu-cody.ro",
        password_hash="x",  # noqa: S106
        role=UserRole.participant,
    )
    fara_note = User(
        email=f"fara-note-{sufix}@exemplu-cody.ro",
        password_hash="x",  # noqa: S106
        role=UserRole.participant,
    )
    session.add_all([cu_note, fara_note])
    await session.flush()

    acum = datetime.now(UTC)
    for zi in range(3):
        for nume in CANONICAL_COMPETENCIES:
            session.add(CompetencyScore(
                user_id=cu_note.id, score=90, level=3, conversation_id=f"sesiune-{sufix}-{zi}",
                competency_name=nume, source_type="roleplay",
                created_at=acum - timedelta(days=zi),
            ))
    await session.flush()
    return cu_note, fara_note


@pytest.mark.asyncio
async def test_omul_fara_note_nu_primeste_nimic_din_notele_altora() -> None:
    async with SessionLocal() as session:
        _cu_note, fara_note = await _doi_oameni(session)

        tablou = await PracticeDashboardService(session).get_participant_dashboard_data(
            principal=_principal(fara_note)
        )

        cu_date = [
            c["name"] for c in tablou["competencies"]
            if c["total_roleplays"] or c["average_score"]
        ]
        assert cu_date == []
        assert tablou["xp_today"] == 0
        assert tablou["xp_total"] == 0
        assert tablou["streak_days"] == 0
        await session.rollback()


@pytest.mark.asyncio
async def test_omul_cu_note_isi_vede_notele_lui() -> None:
    async with SessionLocal() as session:
        cu_note, _fara_note = await _doi_oameni(session)

        tablou = await PracticeDashboardService(session).get_participant_dashboard_data(
            principal=_principal(cu_note)
        )

        cu_date = [c for c in tablou["competencies"] if c["total_roleplays"]]
        assert len(cu_date) == len(CANONICAL_COMPETENCIES)
        assert all(c["average_score"] == 90 for c in cu_date)
        await session.rollback()
