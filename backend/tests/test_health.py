from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from codrut.core.config import Settings
from codrut.core.database import engine
from codrut.core.request_id import REQUEST_ID_HEADER
from codrut.main import create_app
from codrut.modules.health.service import (
    ReadinessCheck,
    check_database,
    check_migration_head,
    check_outbox_backlog,
    check_redis,
    outbox_backlog_status,
    worker_heartbeat_status,
)


def test_health_live() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health/live", headers={REQUEST_ID_HEADER: "req-health"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "req-health"
    assert response.json() == {"status": "ok"}


def _healthy_checks() -> tuple[ReadinessCheck, ...]:
    return tuple(
        ReadinessCheck(component, True, "ok")
        for component in ("database", "redis", "migration", "worker", "outbox")
    )


def test_health_ready_reports_each_required_component(monkeypatch: pytest.MonkeyPatch) -> None:
    async def healthy() -> tuple[ReadinessCheck, ...]:
        return _healthy_checks()

    monkeypatch.setattr("codrut.modules.health.service.collect_readiness_checks", healthy)
    client = TestClient(create_app())

    response = client.get("/api/health/ready", headers={REQUEST_ID_HEADER: "req-ready"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "req-ready"
    assert response.json() == {
        "status": "ok",
        "checks": {
            "database": "ok",
            "redis": "ok",
            "migration": "ok",
            "worker": "ok",
            "outbox": "ok",
        },
    }


@pytest.mark.parametrize(
    ("component", "code"),
    [
        ("database", "database_unavailable"),
        ("redis", "redis_unavailable"),
        ("migration", "migration_head_mismatch"),
        ("worker", "worker_heartbeat_stale"),
        ("outbox", "outbox_backlog_stale"),
    ],
)
def test_health_ready_fails_closed_for_required_components(
    monkeypatch: pytest.MonkeyPatch,
    component: str,
    code: str,
) -> None:
    async def unhealthy() -> tuple[ReadinessCheck, ...]:
        checks = list(_healthy_checks())
        index = next(i for i, check in enumerate(checks) if check.component == component)
        checks[index] = ReadinessCheck(component, False, code)
        return tuple(checks)

    monkeypatch.setattr("codrut.modules.health.service.collect_readiness_checks", unhealthy)
    client = TestClient(create_app())

    response = client.get("/api/health/ready", headers={REQUEST_ID_HEADER: "req-unready"})

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service_not_ready",
            "message": "One or more required services are not ready.",
            "request_id": "req-unready",
            "details": [{"component": component, "code": code}],
        }
    }


def test_worker_heartbeat_rejects_missing_invalid_future_and_stale_values() -> None:
    assert worker_heartbeat_status(None, now_epoch=100, ttl_seconds=30).code == (
        "worker_heartbeat_missing"
    )
    assert worker_heartbeat_status("invalid", now_epoch=100, ttl_seconds=30).code == (
        "worker_heartbeat_invalid"
    )
    assert worker_heartbeat_status("101", now_epoch=100, ttl_seconds=30).code == (
        "worker_heartbeat_stale"
    )
    assert worker_heartbeat_status("69", now_epoch=100, ttl_seconds=30).code == (
        "worker_heartbeat_stale"
    )
    assert worker_heartbeat_status("70", now_epoch=100, ttl_seconds=30).ok is True


def test_outbox_backlog_rejects_excessive_depth_and_age() -> None:
    now = datetime(2026, 7, 19, tzinfo=UTC)
    settings = Settings(
        outbox_backlog_max_pending=10,
        outbox_backlog_max_age_seconds=300,
    )

    assert outbox_backlog_status(11, None, now=now, settings=settings).code == (
        "outbox_backlog_exceeded"
    )
    assert outbox_backlog_status(
        1,
        now - timedelta(seconds=301),
        now=now,
        settings=settings,
    ).code == "outbox_backlog_stale"
    assert outbox_backlog_status(
        10,
        now - timedelta(seconds=300),
        now=now,
        settings=settings,
    ).ok is True


@pytest.mark.asyncio
async def test_readiness_dependencies_match_the_local_stack() -> None:
    try:
        assert (await check_database()).ok is True
        assert (await check_redis()).ok is True
        assert (await check_migration_head()).ok is True
        assert (await check_outbox_backlog()).ok is True
    finally:
        await engine.dispose()
