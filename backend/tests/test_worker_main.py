import asyncio

import pytest

from codrut.workers import main as worker_main


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, tuple[str, int | None]] = {}

    async def set(self, key: str, value: str, *, ex: int | None = None) -> None:
        self.values[key] = (value, ex)


@pytest.mark.asyncio
async def test_worker_shutdown_does_not_emit_a_failure_traceback(monkeypatch) -> None:
    class CancelledWorker:
        async def async_run(self) -> None:
            raise asyncio.CancelledError

    monkeypatch.setattr("arq.worker.create_worker", lambda _settings: CancelledWorker())

    await worker_main.main()


@pytest.mark.asyncio
async def test_worker_records_expiring_heartbeat() -> None:
    redis = FakeRedis()

    await worker_main.record_worker_heartbeat({"redis": redis})

    value, ttl = redis.values[worker_main.get_settings().worker_heartbeat_key]
    assert float(value) > 0
    assert ttl == worker_main.get_settings().worker_heartbeat_ttl_seconds
