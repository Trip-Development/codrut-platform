import asyncio
import logging

from arq import cron
from arq.connections import RedisSettings

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.modules.communications.email_provider import build_email_provider
from codrut.modules.communications.service import EmailOutboxProcessor
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
        )
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
