from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.companies.models import ProjectMembership
from codrut.modules.practice.models import (
    BudgetReservationState,
    PracticeBudgetReservation,
    PracticeProgramSettings,
)


class BudgetExceeded(DomainError):
    def __init__(
        self,
        message: str = "Budget cap exceeded for practice program",
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(message=message, code="budget_exceeded", details=details)


async def reserve(
    session: AsyncSession,
    program_settings_id: uuid.UUID,
    estimated_usd: Decimal,
    session_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Reserve budget for a practice generation call before execution.

    1. Sums existing reserved + settled amounts for the program.
    2. Calculates cap = usd_cap_per_participant * active project participants.
    3. If current + estimated > cap, raises BudgetExceeded.
    4. Otherwise creates a PracticeBudgetReservation in 'reserved' state.
    """
    stmt_settings = select(PracticeProgramSettings).where(
        PracticeProgramSettings.id == program_settings_id
    )
    program_settings = (await session.execute(stmt_settings)).scalar_one_or_none()
    if program_settings is None:
        raise DomainError(
            f"Practice program settings not found: {program_settings_id}",
            code="program_settings_not_found",
        )

    spending_expr = case(
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
    sum_stmt = select(
        func.coalesce(func.sum(spending_expr), Decimal("0.0000"))
    ).where(
        PracticeBudgetReservation.program_settings_id == program_settings_id
    )
    current_spent_and_reserved: Decimal = (
        await session.execute(sum_stmt)
    ).scalar_one()

    count_stmt = select(func.count(ProjectMembership.id)).where(
        ProjectMembership.project_id == program_settings.project_id
    )
    active_participants_count: int = (
        await session.execute(count_stmt)
    ).scalar_one() or 0

    cap = (
        Decimal(active_participants_count)
        * program_settings.usd_cap_per_participant
    )

    if current_spent_and_reserved + estimated_usd > cap:
        raise BudgetExceeded(
            f"Budget cap exceeded for program {program_settings_id}: "
            f"current={current_spent_and_reserved}, estimated={estimated_usd}, cap={cap}",
            details={
                "program_settings_id": str(program_settings_id),
                "current_spent_and_reserved": str(current_spent_and_reserved),
                "estimated_usd": str(estimated_usd),
                "cap": str(cap),
                "active_participants_count": active_participants_count,
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
    stmt = select(PracticeBudgetReservation).where(
        PracticeBudgetReservation.id == reservation_id
    )
    reservation = (await session.execute(stmt)).scalar_one_or_none()
    if reservation is None:
        raise DomainError(
            f"Budget reservation not found: {reservation_id}",
            code="reservation_not_found",
        )
    reservation.state = BudgetReservationState.settled
    reservation.actual_usd = actual_usd
    await session.flush()


async def release(
    session: AsyncSession,
    reservation_id: uuid.UUID,
) -> None:
    """Release a reserved budget allocation when an operation fails or is aborted."""
    stmt = select(PracticeBudgetReservation).where(
        PracticeBudgetReservation.id == reservation_id
    )
    reservation = (await session.execute(stmt)).scalar_one_or_none()
    if reservation is None:
        raise DomainError(
            f"Budget reservation not found: {reservation_id}",
            code="reservation_not_found",
        )
    reservation.state = BudgetReservationState.released
    await session.flush()
