from __future__ import annotations

import asyncio
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from codrut.modules.communications.service import (
    EmailOutboxBatchResult,
    EmailOutboxClaim,
)
from codrut.workers import main as worker


class AsyncSessionContext:
    def __init__(self, session: SimpleNamespace) -> None:
        self.session = session

    async def __aenter__(self) -> SimpleNamespace:
        return self.session

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _traceback: object,
    ) -> None:
        return None


class SessionFactory:
    def __init__(self) -> None:
        self.sessions: list[SimpleNamespace] = []

    def __call__(self) -> AsyncSessionContext:
        session = SimpleNamespace(commit=AsyncMock())
        self.sessions.append(session)
        return AsyncSessionContext(session)


class AsyncClientContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _traceback: object,
    ) -> None:
        return None


@pytest.mark.asyncio
async def test_email_worker_uses_bounded_isolated_claim_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = SessionFactory()
    claims = [
        EmailOutboxClaim(send_id=uuid4(), lease_token=f"lease-{index}")
        for index in range(3)
    ]
    active = 0
    maximum_active = 0
    coordinator = SimpleNamespace(
        claim_due=AsyncMock(
            return_value=(
                claims,
                EmailOutboxBatchResult(claimed=len(claims)),
            )
        )
    )

    class ClaimProcessor:
        async def process_claim(self, _claim: EmailOutboxClaim) -> str:
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            await asyncio.sleep(0)
            active -= 1
            return "accepted"

    processor_count = 0

    def processor_factory(*_args: object) -> object:
        nonlocal processor_count
        processor_count += 1
        return coordinator if processor_count == 1 else ClaimProcessor()

    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setattr(worker, "EmailOutboxProcessor", processor_factory)
    monkeypatch.setattr(worker, "build_email_provider", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(worker.httpx, "AsyncClient", lambda **_kwargs: AsyncClientContext())
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(
            email_outbox_batch_size=100,
            email_outbox_concurrency=2,
        ),
    )

    result = await worker.process_email_outbox({})

    assert result == {
        "claimed": 3,
        "accepted": 3,
        "retried": 0,
        "failed": 0,
        "cancelled": 0,
        "indeterminate": 0,
    }
    assert coordinator.claim_due.await_args.kwargs == {"limit": 100}
    assert maximum_active == 2
    assert len(factory.sessions) == 4


@pytest.mark.asyncio
async def test_email_worker_drains_one_thousand_unique_sandbox_claims_well_within_five_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = SessionFactory()
    pending = [
        EmailOutboxClaim(send_id=uuid4(), lease_token=f"lease-{index}")
        for index in range(1_000)
    ]
    processed: list[EmailOutboxClaim] = []
    active = 0
    maximum_active = 0

    class ThroughputProcessor:
        async def claim_due(
            self,
            *,
            limit: int,
        ) -> tuple[list[EmailOutboxClaim], EmailOutboxBatchResult]:
            claims = pending[:limit]
            del pending[:limit]
            return claims, EmailOutboxBatchResult(claimed=len(claims))

        async def process_claim(self, claim: EmailOutboxClaim) -> str:
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            await asyncio.sleep(0)
            processed.append(claim)
            active -= 1
            return "accepted"

    processor = ThroughputProcessor()
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setattr(worker, "EmailOutboxProcessor", lambda *_args: processor)
    monkeypatch.setattr(worker, "build_email_provider", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(worker.httpx, "AsyncClient", lambda **_kwargs: AsyncClientContext())
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(
            email_outbox_batch_size=100,
            email_outbox_concurrency=8,
        ),
    )

    started_at = monotonic()
    totals = [
        await worker.process_email_outbox({})
        for _batch_number in range(10)
    ]
    elapsed_seconds = monotonic() - started_at

    assert pending == []
    assert sum(result["claimed"] for result in totals) == 1_000
    assert sum(result["accepted"] for result in totals) == 1_000
    assert len({claim.send_id for claim in processed}) == 1_000
    assert maximum_active == 8
    assert elapsed_seconds < 300


def test_email_outbox_cron_is_unique_per_scheduled_run() -> None:
    cron_job = next(
        job
        for job in worker.WorkerSettings.cron_jobs
        if job.coroutine is worker.process_email_outbox
    )

    assert cron_job.unique is True
    assert cron_job.job_id is None


def test_worker_max_jobs_stays_within_validated_database_pool_budget() -> None:
    settings = worker.WorkerSettings.settings

    assert worker.WorkerSettings.max_jobs == settings.worker_max_jobs
    assert settings.email_outbox_concurrency + worker.WorkerSettings.max_jobs - 1 <= (
        settings.db_pool_size + settings.db_max_overflow
    )


@pytest.mark.asyncio
async def test_archive_worker_drains_more_than_one_hundred_due_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = SessionFactory()
    purge = AsyncMock(
        side_effect=[
            SimpleNamespace(examined=100, purged=98, deferred=2),
            SimpleNamespace(examined=7, purged=7, deferred=0),
        ]
    )
    service = SimpleNamespace(purge_due_campaign_recipients=purge)
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setattr(worker, "CommunicationsService", lambda _session: service)

    result = await worker.purge_archived_campaign_recipients({})

    assert result == {"examined": 107, "purged": 105, "deferred": 2}
    assert purge.await_count == 2
    assert all(call.kwargs["limit"] == 100 for call in purge.await_args_list)
    assert len(factory.sessions) == 2
    for session in factory.sessions:
        session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_suppression_review_worker_drains_more_than_one_hundred_due_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = SessionFactory()
    review = AsyncMock(
        side_effect=[
            SimpleNamespace(examined=100, retained=85, needs_review=5, deleted=10),
            SimpleNamespace(examined=3, retained=1, needs_review=1, deleted=1),
        ]
    )
    service = SimpleNamespace(review_due_email_suppressions=review)
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setattr(worker, "CommunicationsService", lambda _session: service)

    result = await worker.review_email_suppressions({})

    assert result == {
        "examined": 103,
        "retained": 86,
        "needs_review": 6,
        "deleted": 11,
    }
    assert review.await_count == 2
    assert all(call.kwargs["limit"] == 100 for call in review.await_args_list)
    assert len(factory.sessions) == 2
    for session in factory.sessions:
        session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delivery_mapping_cleanup_drains_more_than_one_hundred_expired_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = SessionFactory()
    review = AsyncMock(
        side_effect=[
            SimpleNamespace(
                examined=100,
                retained=0,
                needs_review=0,
                deleted=100,
            ),
            SimpleNamespace(
                examined=7,
                retained=0,
                needs_review=0,
                deleted=7,
            ),
        ]
    )
    service = SimpleNamespace(review_due_email_suppressions=review)
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setattr(worker, "CommunicationsService", lambda _session: service)

    result = await worker.review_email_suppressions({})

    assert result == {
        "examined": 107,
        "retained": 0,
        "needs_review": 0,
        "deleted": 107,
    }
    assert review.await_count == 2
    assert len(factory.sessions) == 2
    for session in factory.sessions:
        session.commit.assert_awaited_once()
