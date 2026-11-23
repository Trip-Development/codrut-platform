"""Plicul 255 — contul de test, aceeași regulă la ședințe și la bani.

`contul_de_test_al_sedintei` (Python) dă întâietate contului legat: dacă profilul e legat de un
cont, contează adresa contului; adresa scrisă pe profil contează numai dacă profilul nu e legat.
`_sedintele_conturilor_de_test` (SQL, în `budget.py`) trebuie să recunoască exact aceleași
ședințe. Până la 255 era „SAU”: un profil legat de un cont obișnuit, cu adresa de test scrisă
pe el (cazul C), ieșea din punga proiectului și intra în frâna contului de test.

Fără model, fără `start_session`, fără commit (afară de curățarea banilor rămași ai contului de
test, ca în 173): fiecare test se încheie cu `rollback`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, or_, select

from codrut.core.database import SessionLocal
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.budget import (
    BudgetExceeded,
    _cheltuit_de_contul_de_test_luna_asta,
    _profilurile_conturilor_de_test,
    _sedintele_conturilor_de_test,
    plafonul_programului,
    reserve,
)
from codrut.modules.practice.conturi_test import CONTURI_DE_TEST, contul_de_test_al_sedintei
from codrut.modules.practice.models import (
    PracticeBudgetReservation,
    PracticeSession,
    SessionKind,
    SessionState,
)
from test_practice_session_flow import create_test_context

ADRESA_DE_TEST = sorted(CONTURI_DE_TEST)[0]

# caz -> (adresa pe profil, contul legat, e de test?)
CAZURI = {
    "A": ("test", None, True),
    "B": ("om", "test", True),
    "C": ("test", "obisnuit", False),
    "D": ("andreyvacaru+lidera@gmail.com", None, False),
    "E": ("om", None, False),
    "F": ("test", "test", True),
}


# ------------------------------------------------------------------------------- ajutoarele


async def _contul_de_test(s) -> User:
    """Contul `users` cu adresa de test; refolosit dacă există (ca în 173)."""
    cont = (await s.execute(select(User).where(User.email == ADRESA_DE_TEST))).scalars().first()
    if cont is None:
        cont = User(
            id=uuid.uuid4(),
            email=ADRESA_DE_TEST,
            password_hash="x",  # noqa: S106
            role=UserRole.participant,
        )
        s.add(cont)
        await s.flush()
    return cont


async def _cont_obisnuit(s) -> User:
    cont = User(
        id=uuid.uuid4(),
        email=f"cont-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",  # noqa: S106
        role=UserRole.participant,
    )
    s.add(cont)
    await s.flush()
    return cont


def _adresa(caz: str) -> str:
    adresa = CAZURI[caz][0]
    if adresa == "test":
        return ADRESA_DE_TEST
    if adresa == "om":
        return f"om-{uuid.uuid4().hex[:8]}@example.com"
    return adresa


async def _leaga(s, profil: ParticipantProfile, caz: str) -> None:
    legat = CAZURI[caz][1]
    if legat == "test":
        profil.user_id = (await _contul_de_test(s)).id
    elif legat == "obisnuit":
        profil.user_id = (await _cont_obisnuit(s)).id
    await s.flush()


async def _sedinta(s, ctx, profil_id) -> uuid.UUID:
    sedinta = PracticeSession(
        program_settings_id=ctx["program_settings"].id,
        participant_profile_id=profil_id,
        pack_id=ctx["pack"].id,
        kind=SessionKind.roleplay,
        state=SessionState.open,
        started_at=datetime.now(UTC),
        turn_count=0,
    )
    s.add(sedinta)
    await s.flush()
    return sedinta.id


async def _caz_in_firma_lui(s, caz: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Cazul pe profilul fixturii, într-o firmă nouă (corecția 1). Întoarce (profil, ședință)."""
    ctx = await create_test_context(s)
    profil = ctx["profile"]
    profil.email = _adresa(caz)
    await s.flush()
    await _leaga(s, profil, caz)
    return profil.id, await _sedinta(s, ctx, profil.id)


async def _profil_membru(s, ctx, caz: str) -> uuid.UUID:
    """Încă un profil al cazului, membru activ în proiectul contextului (ca `_al_doilea_om`)."""
    profil = ParticipantProfile(
        company_id=ctx["company"].id,
        full_name=f"Caz {caz} {uuid.uuid4().hex[:8]}",
        email=_adresa(caz),
    )
    s.add(profil)
    await s.flush()
    s.add(
        ProjectMembership(
            company_id=ctx["company"].id,
            project_id=ctx["project"].id,
            participant_profile_id=profil.id,
            active=True,
        )
    )
    await s.flush()
    await _leaga(s, profil, caz)
    return profil.id


async def _curata_banii_contului_de_test(s) -> None:
    """Corecția 3: rezervările rămase ale contului de test (frâna de 25 $ e pe toată luna) se
    șterg și se salvează la început, ca `_curata_banii_contului_de_test` din 173."""
    await s.execute(
        delete(PracticeBudgetReservation).where(
            or_(
                PracticeBudgetReservation.session_id.in_(_sedintele_conturilor_de_test()),
                PracticeBudgetReservation.participant_profile_id.in_(
                    _profilurile_conturilor_de_test()
                ),
            )
        )
    )
    await s.commit()


# ---------------------------------------------------------------------------------- testele


@pytest.mark.asyncio
async def test_aceeasi_regula_pe_toate_cazurile() -> None:
    async with SessionLocal() as s:
        try:
            sedinte = {caz: (await _caz_in_firma_lui(s, caz))[1] for caz in CAZURI}
            de_test_sql = set((await s.execute(_sedintele_conturilor_de_test())).scalars().all())
            gresite = []
            for caz, sid in sedinte.items():
                asteptat = CAZURI[caz][2]
                in_sql = sid in de_test_sql
                in_python = await contul_de_test_al_sedintei(s, sid) is not None
                if not (in_sql == in_python == asteptat):
                    gresite.append(
                        (caz, {"sql": in_sql, "python": in_python, "asteptat": asteptat})
                    )
            assert gresite == []
        finally:
            await s.rollback()


@pytest.mark.asyncio
async def test_profilurile_au_intaietatea_contului_legat() -> None:
    """Pază pe funcția lui 250: dintre cele 6 profiluri, de test sunt exact A, B, F."""
    async with SessionLocal() as s:
        try:
            profiluri = {caz: (await _caz_in_firma_lui(s, caz))[0] for caz in CAZURI}
            de_test = set((await s.execute(_profilurile_conturilor_de_test())).scalars().all())
            assert {caz for caz, pid in profiluri.items() if pid in de_test} == {"A", "B", "F"}
        finally:
            await s.rollback()


@pytest.mark.asyncio
async def test_omul_cu_adresa_de_test_pe_cont_obisnuit_consuma_din_punga() -> None:
    async with SessionLocal() as s:
        try:
            await _curata_banii_contului_de_test(s)
            ctx = await create_test_context(s, usd_cap_per_participant=Decimal("3.00"))
            profil_c = await _profil_membru(s, ctx, "C")
            # Pază: în `plafonul_programului` regula rămâne „SAU” (neschimbată de 255) — omul
            # din cazul C nu se numără la membri, deci punga e a omului fixturii singur.
            punga = await plafonul_programului(s, ctx["program_settings"])
            assert punga == Decimal("3.00")
            sid_c = await _sedinta(s, ctx, profil_c)
            sid_om = await _sedinta(s, ctx, ctx["profile"].id)
            await reserve(
                s, ctx["program_settings"].id, Decimal("3.00"), cap_usd=punga, session_id=sid_c
            )
            with pytest.raises(BudgetExceeded) as err:
                await reserve(
                    s, ctx["program_settings"].id, Decimal("0.01"), cap_usd=punga, session_id=sid_om
                )
            assert "cont_de_test" not in (err.value.details or {})
        finally:
            await s.rollback()


@pytest.mark.asyncio
async def test_omul_cu_adresa_de_test_pe_cont_obisnuit_nu_intra_in_frana_contului_de_test() -> None:
    async with SessionLocal() as s:
        try:
            await _curata_banii_contului_de_test(s)
            ctx = await create_test_context(s)
            profil_c = await _profil_membru(s, ctx, "C")
            sid_c = await _sedinta(s, ctx, profil_c)
            inainte = await _cheltuit_de_contul_de_test_luna_asta(s)
            await reserve(
                s,
                ctx["program_settings"].id,
                Decimal("1.00"),
                cap_usd=Decimal("1000.00"),
                session_id=sid_c,
            )
            dupa = await _cheltuit_de_contul_de_test_luna_asta(s)
            assert dupa - inainte == Decimal("0")
        finally:
            await s.rollback()


@pytest.mark.asyncio
async def test_contul_de_test_adevarat_ramane_pe_frana_lui() -> None:
    """Pază: A (nelegat, adresa de test) și F (legat de contul de test) rămân pe frâna lor."""
    async with SessionLocal() as s:
        try:
            await _curata_banii_contului_de_test(s)
            ctx = await create_test_context(s, usd_cap_per_participant=Decimal("3.00"))
            punga = await plafonul_programului(s, ctx["program_settings"])
            assert punga == Decimal("3.00")
            sid_a = await _sedinta(s, ctx, await _profil_membru(s, ctx, "A"))
            # F stă în firma lui: A și F poartă aceeași adresă (unicitatea firmă + adresă).
            _, sid_f = await _caz_in_firma_lui(s, "F")
            for sid, suma in ((sid_a, Decimal("1.00")), (sid_f, Decimal("2.00"))):
                inainte = await _cheltuit_de_contul_de_test_luna_asta(s)
                await reserve(s, ctx["program_settings"].id, suma, cap_usd=punga, session_id=sid)
                assert await _cheltuit_de_contul_de_test_luna_asta(s) - inainte == suma
            # Cheltuiala lui A și F nu e în punga proiectului: omul fixturii ia toată punga.
            sid_om = await _sedinta(s, ctx, ctx["profile"].id)
            assert await reserve(
                s, ctx["program_settings"].id, punga, cap_usd=punga, session_id=sid_om
            )
        finally:
            await s.rollback()
