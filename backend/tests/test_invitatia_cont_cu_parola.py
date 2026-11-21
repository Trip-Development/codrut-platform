"""Invitațiile de training și conturile care au deja parolă — plicul 242, §5.5.

Ce s-a găsit (controlor, 21 nov 09:34): „Trimite invitații” întorcea linkul de pus
parola și pentru un cont care își pusese deja parola — adică oricine putea primi linkul
de preluare a contului altuia. Acum: pentru un cont cu parolă nu se face link, linkurile
vechi nu se ating, nu pleacă niciun email. Conturile fără parolă — exact ca azi.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

MOTIV = (
    "Omul are deja cont cu parolă. Intră cu parola lui; dacă a uitat-o, "
    "folosește «Am uitat parola» la intrare."
)


async def _proiect_cu_om(s, marca: str):
    from codrut.modules.companies.models import (
        Company,
        CompanyProject,
        ParticipantProfile,
        ProjectMembership,
    )
    from codrut.modules.identity.models import User, UserRole

    firma = Company(id=uuid.uuid4(), name=f"Training {marca}")
    trainer = User(
        id=uuid.uuid4(),
        email=f"trainer-{marca}@example.com",
        password_hash="registered-password-hash",  # noqa: S106
        role=UserRole.trainer,
    )
    s.add_all([firma, trainer])
    await s.flush()
    proiect = CompanyProject(
        id=uuid.uuid4(), company_id=firma.id, name=f"Program {marca}", project_type="training",
    )
    profil = ParticipantProfile(
        id=uuid.uuid4(), company_id=firma.id,
        email=f"om-{marca}@example.com", full_name="Om Inventat",
    )
    s.add_all([proiect, profil])
    await s.flush()
    s.add(ProjectMembership(
        id=uuid.uuid4(), company_id=firma.id, project_id=proiect.id,
        participant_profile_id=profil.id,
    ))
    await s.flush()
    return proiect, profil, trainer


async def _numere(s, user_id, email):
    from codrut.modules.communications.models import EmailSend
    from codrut.modules.identity.models import PasswordResetToken

    jetoane = (await s.execute(
        select(func.count()).select_from(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id)
    )).scalar_one()
    emailuri = (await s.execute(
        select(func.count()).select_from(EmailSend).where(EmailSend.recipient_email == email)
    )).scalar_one()
    return jetoane, emailuri


@pytest.mark.asyncio
async def test_contul_cu_parola_nu_primeste_link() -> None:
    from codrut.core.database import SessionLocal, engine
    from codrut.modules.identity.models import (
        PasswordResetToken,
        User,
        UserAccountType,
        UserRole,
    )
    from codrut.modules.practice.room_service import PracticeInvitationsService

    await engine.dispose()
    try:
        async with SessionLocal() as s:
            marca = uuid.uuid4().hex[:8]
            proiect, profil, trainer = await _proiect_cu_om(s, marca)
            cont = User(
                id=uuid.uuid4(), email=profil.email,
                password_hash="parola-lui-pusa-de-el-hash",  # noqa: S106
                role=UserRole.participant, account_type=UserAccountType.registered,
            )
            s.add(cont)
            await s.flush()
            vechi = PasswordResetToken(
                user_id=cont.id, token_hash=uuid.uuid4().hex,
                expires_at=datetime.now(UTC) + timedelta(days=3),
            )
            s.add(vechi)
            await s.flush()
            inainte = await _numere(s, cont.id, profil.email)

            randuri = await PracticeInvitationsService(s).send(
                proiect.id, [profil.id], trainer_user_id=trainer.id,
            )
            await s.flush()

            assert randuri[0]["invite_url"] is None
            assert randuri[0]["email_queued"] is False
            assert randuri[0]["error"] == MOTIV
            assert await _numere(s, cont.id, profil.email) == inainte
            await s.refresh(vechi)
            assert vechi.used_at is None
            await s.refresh(profil)
            await s.refresh(cont)
            assert profil.user_id is None
            assert cont.account_type == UserAccountType.registered
            assert cont.password_hash == "parola-lui-pusa-de-el-hash"  # noqa: S105
            await s.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("fel", ["fara-cont", "cont-santier", "oaspete-santier"])
async def test_conturile_fara_parola_primesc_link_ca_azi(fel: str) -> None:
    from codrut.core.database import SessionLocal, engine
    from codrut.modules.identity.models import (
        SHADOW_ACCOUNT_PASSWORD_HASH,
        User,
        UserAccountType,
        UserRole,
    )
    from codrut.modules.practice.room_service import PracticeInvitationsService

    await engine.dispose()
    try:
        async with SessionLocal() as s:
            marca = uuid.uuid4().hex[:8]
            proiect, profil, trainer = await _proiect_cu_om(s, marca)
            if fel != "fara-cont":
                s.add(User(
                    id=uuid.uuid4(), email=profil.email,
                    password_hash=SHADOW_ACCOUNT_PASSWORD_HASH, role=UserRole.participant,
                    account_type=(UserAccountType.guest if fel == "oaspete-santier"
                                  else UserAccountType.registered),
                ))
                await s.flush()
            randuri = await PracticeInvitationsService(s).send(
                proiect.id, [profil.id], trainer_user_id=trainer.id,
            )
            await s.flush()
            assert randuri[0]["invite_url"] and "update-password?token=" in randuri[0]["invite_url"]
            assert randuri[0]["email_queued"] is True, randuri[0]["error"]
            cont = (await s.execute(
                select(User).where(User.email == profil.email)
            )).scalar_one()
            assert cont.account_type == UserAccountType.registered
            await s.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_prin_http_trainerul_alocat_nu_primeste_linkul_unui_cont_cu_parola() -> None:
    from codrut.core.database import SessionLocal
    from codrut.modules.identity.models import User, UserAccountType, UserRole
    from test_paza_trainerului_rute import _context_cu_alocare
    from test_practice_router import make_test_client

    ctx = await _context_cu_alocare()
    async with SessionLocal() as s:
        s.add(User(
            id=uuid.uuid4(), email=ctx["profile"].email,
            password_hash="parola-lui-pusa-de-el-hash",  # noqa: S106
            role=UserRole.participant, account_type=UserAccountType.registered,
        ))
        await s.commit()
    async with make_test_client(ctx["trainer"]) as client:
        r = await client.post(
            f"/api/practice/projects/{ctx['project'].id}/invitations",
            json={"participant_profile_ids": [str(ctx["profile"].id)]},
        )
    assert r.status_code == 200, r.text
    assert r.json()[0]["invite_url"] is None
    assert r.json()[0]["error"] == MOTIV
    assert "update-password?token=" not in r.text
