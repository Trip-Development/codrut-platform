import asyncio

from sqlalchemy import func, select

from codrut.core.database import SessionLocal
from codrut.modules.scoring.models import ResultPublication
from codrut.modules.scoring.publication import ResultPublicationService


async def reconcile_result_publications() -> tuple[int, int]:
    async with SessionLocal() as session:
        reconciled = await ResultPublicationService(session).reconcile_all()
        await session.commit()
        active = int(
            (
                await session.execute(
                    select(func.count(ResultPublication.id)).where(
                        ResultPublication.revoked_at.is_(None)
                    )
                )
            ).scalar_one()
        )
        return reconciled, active


def main() -> None:
    reconciled, active = asyncio.run(reconcile_result_publications())
    print(f"Reconciled {reconciled} scored assignments; {active} publications are active.")


if __name__ == "__main__":
    main()
