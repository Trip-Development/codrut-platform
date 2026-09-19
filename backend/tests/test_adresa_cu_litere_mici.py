"""Regresia plicului 81: adresa se scrie cu litere mici pe model, nu doar pe fiecare cale.

Legarea automata compara adresele fara majuscule; exersarea si spatiul participantului exact.
Azi e in regula numai fiindca fiecare cale face `.lower()`. Testul scrie o adresa cu litere mari
direct pe model — cum ar face o cale noua care uita — si o citeste inapoi din baza.
"""

import uuid

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.modules.companies.models import Company, ParticipantProfile
from codrut.modules.identity.models import User, UserRole


async def _adresa_din_baza(session, model, rand_id):
    rezultat = await session.execute(select(model.email).where(model.id == rand_id))
    return rezultat.scalar_one()


@pytest.mark.asyncio
async def test_adresa_contului_se_citeste_cu_litere_mici() -> None:
    sufix = uuid.uuid4().hex[:8]
    async with SessionLocal() as session:
        cont = User(
            email=f"  Ion.Popescu-{sufix}@Firma.ro ",
            password_hash="hash",  # noqa: S106
            role=UserRole.participant,
        )
        session.add(cont)
        await session.flush()

        citit = await _adresa_din_baza(session, User, cont.id)

        assert citit == f"ion.popescu-{sufix}@firma.ro"
        await session.rollback()


@pytest.mark.asyncio
async def test_adresa_profilului_se_citeste_cu_litere_mici_si_none_ramane_none() -> None:
    sufix = uuid.uuid4().hex[:8]
    async with SessionLocal() as session:
        companie = Company(name=f"Firma {sufix}")
        session.add(companie)
        await session.flush()
        cu_adresa = ParticipantProfile(
            company_id=companie.id,
            full_name="Ion Popescu",
            email=f"Ion.Popescu-{sufix}@Firma.ro",
        )
        fara_adresa = ParticipantProfile(
            company_id=companie.id, full_name="Fara Adresa", email=None
        )
        session.add_all([cu_adresa, fara_adresa])
        await session.flush()

        citit = await _adresa_din_baza(session, ParticipantProfile, cu_adresa.id)
        gol = await _adresa_din_baza(session, ParticipantProfile, fara_adresa.id)

        assert citit == f"ion.popescu-{sufix}@firma.ro"
        assert gol is None
        await session.rollback()
