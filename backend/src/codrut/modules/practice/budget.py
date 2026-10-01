from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.models import User
from codrut.modules.practice.conturi_test import (
    CONTURI_DE_TEST,
    PLAFON_LUNAR_CONT_TEST_USD,
    contul_de_test_al_sedintei,
)
from codrut.modules.practice.models import (
    BudgetReservationState,
    PracticeBudgetReservation,
    PracticeProgramSettings,
    PracticeSession,
)


class BudgetExceeded(DomainError):
    def __init__(
        self,
        message: str = "Budget cap exceeded for practice program",
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(message=message, code="budget_exceeded", details=details)


def _cheltuiala() -> Any:
    """Cat tine azi o rezervare: rezervat sau, daca s-a decontat, cat a costat de fapt."""
    return case(
        (
            PracticeBudgetReservation.state == BudgetReservationState.reserved,
            PracticeBudgetReservation.reserved_usd,
        ),
        (
            PracticeBudgetReservation.state == BudgetReservationState.settled,
            func.coalesce(
                PracticeBudgetReservation.actual_usd,
                PracticeBudgetReservation.reserved_usd,
            ),
        ),
        else_=Decimal("0.0000"),
    )


def _sedintele_conturilor_de_test() -> Any:
    """Id-urile sedintelor care apartin unui cont de test (prin cont legat sau prin profil)."""
    return (
        select(PracticeSession.id)
        .join(
            ParticipantProfile,
            ParticipantProfile.id == PracticeSession.participant_profile_id,
        )
        .outerjoin(User, User.id == ParticipantProfile.user_id)
        .where(
            or_(
                func.lower(User.email).in_(CONTURI_DE_TEST),
                func.lower(ParticipantProfile.email).in_(CONTURI_DE_TEST),
            )
        )
    )


async def plafonul_programului(
    session: AsyncSession,
    program_settings: PracticeProgramSettings,
) -> Decimal:
    """Punga proiectului: membrii activi FARA conturile de test x plafonul pe membru.

    Formula era scrisa in patru locuri (prima replica, replicile, inchiderea, evaluarea).
    Acum e aici, o singura data — altfel excluderea conturilor de test ar fi trebuit tinuta
    minte in patru locuri, si al cincilea ar fi uitat-o.
    """
    profiluri_de_test = (
        select(ParticipantProfile.id)
        .outerjoin(User, User.id == ParticipantProfile.user_id)
        .where(
            or_(
                func.lower(User.email).in_(CONTURI_DE_TEST),
                func.lower(ParticipantProfile.email).in_(CONTURI_DE_TEST),
            )
        )
    )
    activi = (
        await session.execute(
            select(func.count(ProjectMembership.id)).where(
                ProjectMembership.project_id == program_settings.project_id,
                ProjectMembership.active.is_(True),
                ProjectMembership.participant_profile_id.not_in(profiluri_de_test),
            )
        )
    ).scalar_one() or 0
    return Decimal(activi) * program_settings.usd_cap_per_participant


async def _cheltuit_de_contul_de_test_luna_asta(session: AsyncSession) -> Decimal:
    """Cat a consumat contul de test in luna calendaristica curenta (UTC), pe TOATE proiectele."""
    acum = datetime.now(UTC)
    inceputul_lunii = acum.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        await session.execute(
            select(func.coalesce(func.sum(_cheltuiala()), Decimal("0.0000"))).where(
                PracticeBudgetReservation.session_id.in_(_sedintele_conturilor_de_test()),
                PracticeBudgetReservation.created_at >= inceputul_lunii,
            )
        )
    ).scalar_one()


async def reserve(
    session: AsyncSession,
    program_settings_id: uuid.UUID,
    estimated_usd: Decimal,
    cap_usd: Decimal,
    session_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Reserve budget for a practice generation call before execution.

    1. Sums existing reserved + settled amounts for the program.
    2. If current + estimated > cap_usd, raises BudgetExceeded.
    3. Otherwise creates a PracticeBudgetReservation in 'reserved' state.
    """
    spending_expr = _cheltuiala()

    # Contul de test (plicul 173): nu atinge punga proiectului, are frana lui lunara.
    adresa_de_test = await contul_de_test_al_sedintei(session, session_id)
    if adresa_de_test is not None:
        cheltuit_luna: Decimal = await _cheltuit_de_contul_de_test_luna_asta(session)
        if cheltuit_luna + estimated_usd > PLAFON_LUNAR_CONT_TEST_USD:
            raise BudgetExceeded(
                f"Plafonul lunar al contului de test a fost atins: "
                f"luna={cheltuit_luna}, estimat={estimated_usd}, "
                f"plafon={PLAFON_LUNAR_CONT_TEST_USD}",
                details={
                    "cont_de_test": True,
                    "program_settings_id": str(program_settings_id),
                    "current_spent_and_reserved": str(cheltuit_luna),
                    "estimated_usd": str(estimated_usd),
                    "cap_usd": str(PLAFON_LUNAR_CONT_TEST_USD),
                },
            )
    else:
        # Punga proiectului, FARA ce au consumat conturile de test. Rezervarile fara
        # `session_id` raman numarate: nu se stie al cui e consumul lor.
        sum_stmt = select(func.coalesce(func.sum(spending_expr), Decimal("0.0000"))).where(
            PracticeBudgetReservation.program_settings_id == program_settings_id,
            or_(
                PracticeBudgetReservation.session_id.is_(None),
                PracticeBudgetReservation.session_id.not_in(
                    _sedintele_conturilor_de_test()
                ),
            ),
        )
        current_spent_and_reserved: Decimal = (await session.execute(sum_stmt)).scalar_one()

        if current_spent_and_reserved + estimated_usd > cap_usd:
            raise BudgetExceeded(
                f"Budget cap exceeded for program {program_settings_id}: "
                f"current={current_spent_and_reserved}, estimated={estimated_usd}, cap={cap_usd}",
                details={
                    "program_settings_id": str(program_settings_id),
                    "current_spent_and_reserved": str(current_spent_and_reserved),
                    "estimated_usd": str(estimated_usd),
                    "cap_usd": str(cap_usd),
                },
            )

    reservation = PracticeBudgetReservation(
        program_settings_id=program_settings_id,
        session_id=session_id,
        reserved_usd=estimated_usd,
        state=BudgetReservationState.reserved,
    )
    session.add(reservation)
    await session.flush()
    return reservation.id


async def settle(
    session: AsyncSession,
    reservation_id: uuid.UUID,
    actual_usd: Decimal,
) -> None:
    """Settle an existing reservation with actual incurred cost."""
    stmt = select(PracticeBudgetReservation).where(PracticeBudgetReservation.id == reservation_id)
    reservation = (await session.execute(stmt)).scalar_one_or_none()
    if reservation is None:
        raise DomainError(
            f"Budget reservation not found: {reservation_id}",
            code="reservation_not_found",
        )
    if reservation.state != BudgetReservationState.reserved:
        raise DomainError(
            f"Cannot settle budget reservation in state '{reservation.state}'; expected 'reserved'",
            code="invalid_reservation_state",
        )
    reservation.state = BudgetReservationState.settled
    reservation.actual_usd = actual_usd
    await session.flush()


async def release(
    session: AsyncSession,
    reservation_id: uuid.UUID,
) -> None:
    """Release a reserved budget allocation when an operation fails or is aborted."""
    stmt = select(PracticeBudgetReservation).where(PracticeBudgetReservation.id == reservation_id)
    reservation = (await session.execute(stmt)).scalar_one_or_none()
    if reservation is None:
        raise DomainError(
            f"Budget reservation not found: {reservation_id}",
            code="reservation_not_found",
        )
    if reservation.state != BudgetReservationState.reserved:
        raise DomainError(
            f"Cannot release budget reservation in state '{reservation.state}'; "
            "expected 'reserved'",
            code="invalid_reservation_state",
        )
    reservation.state = BudgetReservationState.released
    await session.flush()
