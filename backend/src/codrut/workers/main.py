import asyncio
import logging

from arq.connections import RedisSettings

from codrut.core.config import get_settings

logger = logging.getLogger(__name__)


async def health_check(ctx: dict) -> str:
    logger.debug("Worker health check context keys: %s", sorted(ctx.keys()))
    return "ok"


class WorkerSettings:
    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [health_check]


async def main() -> None:
    from arq.worker import create_worker

    worker = create_worker(WorkerSettings)
    await worker.async_run()


if __name__ == "__main__":
    asyncio.run(main())
