from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from redis.asyncio import Redis
from sqlalchemy import and_, func, or_, select, text

from codrut.core.config import Settings, get_settings
from codrut.core.database import engine
from codrut.modules.communications.models import EmailSend, EmailSendStatus


@dataclass(frozen=True)
class ReadinessCheck:
    component: str
    ok: bool
    code: str


@lru_cache
def expected_migration_heads() -> frozenset[str]:
    backend_root = Path(__file__).resolve().parents[4]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    return frozenset(ScriptDirectory.from_config(config).get_heads())


async def check_database(settings: Settings | None = None) -> ReadinessCheck:
    active_settings = settings or get_settings()
    try:
        async with asyncio.timeout(active_settings.readiness_timeout_seconds):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - readiness returns a stable non-sensitive code
        return ReadinessCheck("database", False, "database_unavailable")
    return ReadinessCheck("database", True, "ok")


async def check_redis(settings: Settings | None = None) -> ReadinessCheck:
    active_settings = settings or get_settings()
    redis = Redis.from_url(active_settings.redis_url, decode_responses=True)
    try:
        async with asyncio.timeout(active_settings.readiness_timeout_seconds):
            if not await redis.ping():
                return ReadinessCheck("redis", False, "redis_unavailable")
    except Exception:  # noqa: BLE001 - readiness returns a stable non-sensitive code
        return ReadinessCheck("redis", False, "redis_unavailable")
    finally:
        await redis.aclose()
    return ReadinessCheck("redis", True, "ok")


async def check_migration_head(settings: Settings | None = None) -> ReadinessCheck:
    active_settings = settings or get_settings()
    try:
        expected_heads = expected_migration_heads()
        async with asyncio.timeout(active_settings.readiness_timeout_seconds):
            async with engine.connect() as connection:
                result = await connection.execute(text("SELECT version_num FROM alembic_version"))
                database_heads = frozenset(str(value) for value in result.scalars().all())
    except Exception:  # noqa: BLE001 - readiness returns a stable non-sensitive code
        return ReadinessCheck("migration", False, "migration_state_unavailable")
    if not expected_heads or database_heads != expected_heads:
        return ReadinessCheck("migration", False, "migration_head_mismatch")
    return ReadinessCheck("migration", True, "ok")


async def publish_worker_heartbeat(redis: Redis, settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    await redis.set(
        active_settings.worker_heartbeat_key,
        f"{time.time():.6f}",
        ex=active_settings.worker_heartbeat_ttl_seconds,
    )


def worker_heartbeat_status(
    raw_heartbeat: str | None,
    *,
    now_epoch: float,
    ttl_seconds: int,
) -> ReadinessCheck:
    if raw_heartbeat is None:
        return ReadinessCheck("worker", False, "worker_heartbeat_missing")
    try:
        heartbeat_age = now_epoch - float(raw_heartbeat)
    except (TypeError, ValueError):
        return ReadinessCheck("worker", False, "worker_heartbeat_invalid")
    if heartbeat_age < 0 or heartbeat_age > ttl_seconds:
        return ReadinessCheck("worker", False, "worker_heartbeat_stale")
    return ReadinessCheck("worker", True, "ok")


async def check_worker_heartbeat(settings: Settings | None = None) -> ReadinessCheck:
    active_settings = settings or get_settings()
    redis = Redis.from_url(active_settings.redis_url, decode_responses=True)
    try:
        async with asyncio.timeout(active_settings.readiness_timeout_seconds):
            raw_heartbeat = await redis.get(active_settings.worker_heartbeat_key)
    except Exception:  # noqa: BLE001 - readiness returns a stable non-sensitive code
        return ReadinessCheck("worker", False, "worker_heartbeat_unavailable")
    finally:
        await redis.aclose()

    return worker_heartbeat_status(
        raw_heartbeat,
        now_epoch=time.time(),
        ttl_seconds=active_settings.worker_heartbeat_ttl_seconds,
    )


def outbox_backlog_status(
    pending_count: int,
    oldest_created_at: datetime | None,
    *,
    now: datetime,
    settings: Settings,
) -> ReadinessCheck:
    if pending_count > settings.outbox_backlog_max_pending:
        return ReadinessCheck("outbox", False, "outbox_backlog_exceeded")
    if oldest_created_at is not None:
        if oldest_created_at.tzinfo is None:
            oldest_created_at = oldest_created_at.replace(tzinfo=UTC)
        age_seconds = (now - oldest_created_at).total_seconds()
        if age_seconds > settings.outbox_backlog_max_age_seconds:
            return ReadinessCheck("outbox", False, "outbox_backlog_stale")
    return ReadinessCheck("outbox", True, "ok")


async def check_outbox_backlog(settings: Settings | None = None) -> ReadinessCheck:
    active_settings = settings or get_settings()
    now = datetime.now(UTC)
    due_filter = or_(
        and_(
            EmailSend.status == EmailSendStatus.queued,
            EmailSend.next_attempt_at <= now,
        ),
        and_(
            EmailSend.status == EmailSendStatus.dispatching,
            EmailSend.lease_expires_at <= now,
        ),
    )
    try:
        async with asyncio.timeout(active_settings.readiness_timeout_seconds):
            async with engine.connect() as connection:
                result = await connection.execute(
                    select(func.count(EmailSend.id), func.min(EmailSend.created_at)).where(
                        due_filter
                    )
                )
                pending_count, oldest_created_at = result.one()
    except Exception:  # noqa: BLE001 - readiness returns a stable non-sensitive code
        return ReadinessCheck("outbox", False, "outbox_state_unavailable")

    return outbox_backlog_status(
        int(pending_count or 0),
        oldest_created_at,
        now=now,
        settings=active_settings,
    )


async def collect_readiness_checks(
    settings: Settings | None = None,
) -> tuple[ReadinessCheck, ...]:
    active_settings = settings or get_settings()
    checks = (
        check_database,
        check_redis,
        check_migration_head,
        check_worker_heartbeat,
        check_outbox_backlog,
    )
    results: list[ReadinessCheck] = []
    for check in checks:
        results.append(await check(active_settings))
    return tuple(results)
