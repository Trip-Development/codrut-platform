"""Paza trainerului pe proiect — plicul 242, §5.2.

Hotărârea lui Andrei (21 nov 09:41): un trainer vede și schimbă NUMAI proiectele la care
e alocat; proprietarul platformei vede tot. Testele trec pe FIECARE din cele 9 rute de
trainer ale exersării care primesc un proiect.

Conturile sunt inventate: `alocat` (trainerul fixturii, pus pe proiect), `nealocat`
(trainer cu cont, `owner` în firma proiectului, dar nealocat — firma nu mai ajunge),
`strain` (trainer alocat la un proiect din altă firmă), `proprietar` (trainer cu
`is_platform_owner`, fără alocare), `participant` (omul fixturii).

Importurile noi (`ProjectTrainer`, `is_platform_owner`) se fac ÎN teste, ca roșul de
dinainte de cod să fie din motivul potrivit, nu o eroare de colectare.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from codrut.core.database import SessionLocal
from codrut.modules.identity.models import UserAccountType, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from test_practice_router import make_test_client, setup_practice_context

PAROLA_DE_TEST = "hash-de-test-nu-e-parola"  # noqa: S105


def _principal(user_id: uuid.UUID, email: str, role: UserRole = UserRole.trainer):
    return SessionPrincipal(
        user_id=user_id,
        email=email,
        role=role,
        account_type=UserAccountType.registered,
        access_mode="account",
        consent_current=True,
        terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION,
        session_token=f"tok-{uuid.uuid4().hex[:8]}",
    )


async def _cont_trainer(sesiune, marca: str, rol: str, *, proprietar: bool = False):
    from codrut.modules.identity.models import User

    u = User(
        id=uuid.uuid4(),
        email=f"{rol}-{marca}@example.com",
        password_hash=PAROLA_DE_TEST,
        role=UserRole.trainer,
    )
    if proprietar:
        u.is_platform_owner = True
    sesiune.add(u)
    await sesiune.flush()
    return u


async def _context_cu_alocare() -> dict:
    """Fixtura comună + alocarea trainerului fixturii (`alocat`)."""
    from codrut.modules.companies.models import ProjectTrainer

    async with SessionLocal() as sesiune:
        ctx = await setup_practice_context(sesiune)
        exista = (await sesiune.execute(
            select(func.count()).select_from(ProjectTrainer).where(
                ProjectTrainer.project_id == ctx["project"].id,
                ProjectTrainer.user_id == ctx["trainer"].user_id,
            )
        )).scalar_one()
        assert exista == 1, "fixtura comună trebuie să aloce trainerul (§5.0)"
    return ctx


async def _context_complet() -> dict:
    """Toate cele cinci conturi din §5.1, pe proiectul fixturii."""
    from codrut.modules.companies.models import (
        Company,
        CompanyMembership,
        CompanyMembershipRole,
        CompanyProject,
        CompanyProjectStatus,
        ProjectTrainer,
    )

    ctx = await _context_cu_alocare()
    marca = uuid.uuid4().hex[:8]
    async with SessionLocal() as sesiune:
        nealocat = await _cont_trainer(sesiune, marca, "nealocat")
        sesiune.add(CompanyMembership(
            company_id=ctx["company"].id,
            user_id=nealocat.id,
            role=CompanyMembershipRole.owner,
        ))
        strain = await _cont_trainer(sesiune, marca, "strain")
        alta_firma = Company(name=f"Alta firma {marca}")
        sesiune.add(alta_firma)
        await sesiune.flush()
        alt_proiect = CompanyProject(
            company_id=alta_firma.id,
            name=f"Alt proiect {marca}",
            project_type="training",
            status=CompanyProjectStatus.active,
        )
        sesiune.add(alt_proiect)
        await sesiune.flush()
        sesiune.add(ProjectTrainer(project_id=alt_proiect.id, user_id=strain.id))
        proprietar = await _cont_trainer(sesiune, marca, "proprietar", proprietar=True)
        # omul fixturii primește cont, ca nota trainerului să poată fi scrisă (azi: 201)
        from codrut.modules.companies.models import ParticipantProfile
        from codrut.modules.identity.models import User

        om = User(id=uuid.uuid4(), email=ctx["profile"].email, password_hash=PAROLA_DE_TEST,
                  role=UserRole.participant)
        sesiune.add(om)
        await sesiune.flush()
        profil = await sesiune.get(ParticipantProfile, ctx["profile"].id)
        profil.user_id = om.id
        await sesiune.commit()
        ctx["nealocat"] = _principal(nealocat.id, nealocat.email)
        ctx["strain"] = _principal(strain.id, strain.email)
        ctx["proprietar"] = _principal(proprietar.id, proprietar.email)
        ctx["alocat"] = ctx["trainer"]
    return ctx


def _cereri(ctx: dict) -> dict[str, tuple[str, str, dict | None]]:
    p = ctx["project"].id
    om = ctx["profile"].id
    tema = ctx["program_settings"].theme_id
    return {
        "1-setup-get": ("GET", f"/api/practice/projects/{p}/setup", None),
        "2-setup-put": ("PUT", f"/api/practice/projects/{p}/setup",
                        {"theme_id": str(tema), "max_sessions_per_day": 7}),
        "3-evolution": ("GET", f"/api/practice/projects/{p}/evolution", None),
        "4-room": ("GET", f"/api/practice/projects/{p}/room", None),
        "5-person": ("GET", f"/api/practice/projects/{p}/participants/{om}", None),
        "6-note": ("POST", f"/api/practice/projects/{p}/participants/{om}/notes",
                   {"note": "Notă de test a trainerului."}),
        "7-invitations-get": ("GET", f"/api/practice/projects/{p}/invitations", None),
        "8-invitations-post": ("POST", f"/api/practice/projects/{p}/invitations",
                               {"participant_profile_ids": [str(om)]}),
        "9-trainer-sessions": ("POST", "/api/practice/trainer/sessions",
                               {"project_id": str(p), "kind": "roleplay"}),
    }


RUTE = [
    "1-setup-get", "2-setup-put", "3-evolution", "4-room", "5-person", "6-note",
    "7-invitations-get", "8-invitations-post", "9-trainer-sessions",
]
CITESC = ["1-setup-get", "3-evolution", "4-room", "5-person", "7-invitations-get"]
SCRIU = ["2-setup-put", "6-note", "8-invitations-post", "9-trainer-sessions"]
COD_BUN = {r: 200 for r in RUTE} | {"6-note": 201, "9-trainer-sessions": 201}


async def _cere(principal, cerere, *, direct: bool = True):
    metoda, cale, corp = cerere
    async with make_test_client(principal, trainer_direct_entry=direct) as client:
        return await client.request(metoda, cale, json=corp)


async def _numaratoare(ctx: dict) -> dict:
    from codrut.modules.communications.models import EmailSend
    from codrut.modules.companies.models import ParticipantProfile
    from codrut.modules.identity.models import PasswordResetToken, User
    from codrut.modules.practice.models import PracticeProgramSettings, PracticeSession, TrainerNote

    async with SessionLocal() as s:
        async def n(stmt):
            return (await s.execute(stmt)).scalar_one()

        setari = (await s.execute(
            select(PracticeProgramSettings).where(
                PracticeProgramSettings.project_id == ctx["project"].id
            )
        )).scalars().one()
        return {
            "setari": (setari.max_sessions_per_day, setari.theme_id, setari.is_enabled),
            "note": await n(select(func.count()).select_from(TrainerNote)),
            "jetoane": await n(select(func.count()).select_from(PasswordResetToken)),
            "emailuri": await n(select(func.count()).select_from(EmailSend)),
            "conturi": await n(select(func.count()).select_from(User)),
            "sesiuni": await n(select(func.count()).select_from(PracticeSession)),
            "profiluri": await n(
                select(func.count()).select_from(ParticipantProfile).where(
                    ParticipantProfile.company_id == ctx["company"].id
                )
            ),
        }


# 1 + 2 + 3: nealocat și strain → 403 not_project_trainer, nimic scris, nimic scurs
@pytest.mark.asyncio
@pytest.mark.parametrize("cine", ["nealocat", "strain"])
@pytest.mark.parametrize("ruta", RUTE)
async def test_nealocat_si_strain_primesc_403(cine: str, ruta: str) -> None:
    ctx = await _context_complet()
    inainte = await _numaratoare(ctx)
    r = await _cere(ctx[cine], _cereri(ctx)[ruta])
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "not_project_trainer"
    dupa = await _numaratoare(ctx)
    assert dupa == inainte
    assert "update-password?token=" not in r.text
    if ruta in CITESC:
        assert ctx["profile"].full_name not in r.text
        assert ctx["profile"].email not in r.text


# 4: alocat → ca azi; pe rutele care citesc, același corp ca al proprietarului
@pytest.mark.asyncio
@pytest.mark.parametrize("ruta", RUTE)
async def test_alocat_trece_ca_azi(ruta: str) -> None:
    ctx = await _context_complet()
    r = await _cere(ctx["alocat"], _cereri(ctx)[ruta])
    assert r.status_code == COD_BUN[ruta], r.text
    if ruta in CITESC:
        r2 = await _cere(ctx["proprietar"], _cereri(ctx)[ruta])
        assert r2.status_code == 200, r2.text
        assert r2.json() == r.json()


# 5: proprietarul (nealocat) → ca alocat
@pytest.mark.asyncio
@pytest.mark.parametrize("ruta", RUTE)
async def test_proprietarul_vede_tot(ruta: str) -> None:
    ctx = await _context_complet()
    r = await _cere(ctx["proprietar"], _cereri(ctx)[ruta])
    assert r.status_code == COD_BUN[ruta], r.text


# 6: proiect inexistent → 404 project_not_found
@pytest.mark.asyncio
@pytest.mark.parametrize("cine", ["alocat", "nealocat", "proprietar"])
@pytest.mark.parametrize("ruta", RUTE)
async def test_proiect_inexistent_404(cine: str, ruta: str) -> None:
    ctx = await _context_complet()
    real = str(ctx["project"].id)
    metoda, cale, corp = _cereri(ctx)[ruta]
    fals = str(uuid.uuid4())
    cale = cale.replace(real, fals)
    if corp and "project_id" in corp:
        corp = {**corp, "project_id": fals}
    r = await _cere(ctx[cine], (metoda, cale, corp))
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "project_not_found"


# 7: participantul → ca azi (403 pe 1–8, 404 pe 9). Comportament care rămâne.
@pytest.mark.asyncio
@pytest.mark.parametrize("ruta", RUTE)
async def test_participantul_ca_azi(ruta: str) -> None:
    async with SessionLocal() as sesiune:
        ctx = await setup_practice_context(sesiune)
    r = await _cere(ctx["participant"], _cereri(ctx)[ruta])
    assert r.status_code == (404 if ruta == "9-trainer-sessions" else 403), r.text


# 8: fără sesiune → 401. Comportament care rămâne.
@pytest.mark.asyncio
@pytest.mark.parametrize("ruta", RUTE)
async def test_fara_sesiune_401(ruta: str) -> None:
    from httpx import ASGITransport, AsyncClient

    from codrut.api.dependencies import db_session
    from codrut.main import create_app

    async with SessionLocal() as sesiune:
        ctx = await setup_practice_context(sesiune)
    metoda, cale, corp = _cereri(ctx)[ruta]
    app = create_app()

    async def fara_baza():
        yield None

    app.dependency_overrides[db_session] = fara_baza
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.request(metoda, cale, json=corp)
    assert r.status_code == 401, r.text


# 9: /trainer/sessions cu semnalul oprit → 404, chiar și pentru alocat. Rămâne.
@pytest.mark.asyncio
async def test_sesiunea_trainerului_cu_semnalul_oprit() -> None:
    async with SessionLocal() as sesiune:
        ctx = await setup_practice_context(sesiune)
    r = await _cere(ctx["trainer"], _cereri(ctx)["9-trainer-sessions"], direct=False)
    assert r.status_code == 404, r.text


# 10: /themes rămâne numai pe rol (catalog comun)
@pytest.mark.asyncio
async def test_temele_raman_pe_rol() -> None:
    async with SessionLocal() as sesiune:
        ctx = await setup_practice_context(sesiune)
    for email in ("nealocat-teme@example.com", "strain-teme@example.com"):
        r = await _cere(_principal(uuid.uuid4(), email), ("GET", "/api/practice/themes", None))
        assert r.status_code == 200, r.text
    assert ctx["project"] is not None
