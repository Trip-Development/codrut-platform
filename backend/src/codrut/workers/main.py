import asyncio
import logging

from arq import cron
from arq.connections import RedisSettings

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.modules.communications.email_provider import build_email_provider
from codrut.modules.communications.service import CommunicationsService, EmailOutboxProcessor
from codrut.modules.forms import models as forms_models  # noqa: F401
from codrut.modules.health.service import publish_worker_heartbeat
from codrut.modules.identity import models as identity_models  # noqa: F401

logger = logging.getLogger(__name__)


async def health_check(ctx: dict) -> str:
    logger.debug("Worker health check context keys: %s", sorted(ctx.keys()))
    return "ok"


async def record_worker_heartbeat(ctx: dict) -> None:
    await publish_worker_heartbeat(ctx["redis"])


async def process_email_outbox(_ctx: dict) -> dict[str, int]:
    settings = get_settings()
    async with SessionLocal() as session:
        result = await EmailOutboxProcessor(
            session,
            build_email_provider(settings),
            settings,
        ).process_due()
    if result.claimed or result.failed:
        logger.info(
            "Email outbox batch claimed=%d accepted=%d retried=%d failed=%d "
            "cancelled=%d indeterminate=%d",
            result.claimed,
            result.accepted,
            result.retried,
            result.failed,
            result.cancelled,
            result.indeterminate,
        )
    return {
        "claimed": result.claimed,
        "accepted": result.accepted,
        "retried": result.retried,
        "failed": result.failed,
        "cancelled": result.cancelled,
        "indeterminate": result.indeterminate,
    }


async def purge_archived_campaign_recipients(_ctx: dict) -> dict[str, int]:
    settings = get_settings()
    totals = {"examined": 0, "purged": 0, "deferred": 0}
    while True:
        async with SessionLocal() as session:
            result = await CommunicationsService(session).purge_due_campaign_recipients(
                settings=settings,
                limit=100,
            )
            await session.commit()
        totals["examined"] += result.examined
        totals["purged"] += result.purged
        totals["deferred"] += result.deferred
        if result.examined < 100:
            break
    if totals["examined"]:
        logger.info(
            "Campaign contact purge examined=%d purged=%d deferred=%d",
            totals["examined"],
            totals["purged"],
            totals["deferred"],
        )
    return totals


async def review_email_suppressions(_ctx: dict) -> dict[str, int]:
    settings = get_settings()
    totals = {"examined": 0, "retained": 0, "needs_review": 0, "deleted": 0}
    while True:
        async with SessionLocal() as session:
            result = await CommunicationsService(session).review_due_email_suppressions(
                settings=settings,
                limit=100,
            )
            await session.commit()
        totals["examined"] += result.examined
        totals["retained"] += result.retained
        totals["needs_review"] += result.needs_review
        totals["deleted"] += result.deleted
        if result.examined < 100:
            break
    if totals["examined"]:
        logger.info(
            "Email suppression review examined=%d retained=%d needs_review=%d deleted=%d",
            totals["examined"],
            totals["retained"],
            totals["needs_review"],
            totals["deleted"],
        )
    return totals


class WorkerSettings:
    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [health_check]
    cron_jobs = [
        cron(
            record_worker_heartbeat,
            second=set(range(0, 60, 5)),
            run_at_startup=True,
            unique=False,
        ),
        cron(
            process_email_outbox,
            second=set(range(0, 60, 5)),
            run_at_startup=True,
            unique=False,
        ),
        cron(
            purge_archived_campaign_recipients,
            hour=2,
            minute=15,
            run_at_startup=False,
            unique=True,
        ),
        cron(
            review_email_suppressions,
            hour=2,
            minute=45,
            run_at_startup=False,
            unique=True,
        ),
    ]


async def main() -> None:
    from arq.worker import create_worker

    worker = create_worker(WorkerSettings)
    try:
        await worker.async_run()
    except asyncio.CancelledError:
        logger.info("Worker shutdown requested")


if __name__ == "__main__":
    asyncio.run(main())
