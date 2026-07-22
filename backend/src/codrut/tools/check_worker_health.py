import asyncio

from codrut.modules.health.service import check_worker_heartbeat


async def _main() -> int:
    result = await check_worker_heartbeat()
    return 0 if result.ok else 1


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
