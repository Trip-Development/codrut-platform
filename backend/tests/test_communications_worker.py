from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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
