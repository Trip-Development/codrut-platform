from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from codrut.core.errors import DomainError

if TYPE_CHECKING:
    from redis.asyncio import Redis


def ensure_turn_length(text: str, max_chars_per_turn: int) -> None:
    """Verify turn character count does not exceed the allowed maximum."""
    if len(text) > max_chars_per_turn:
        raise DomainError(
            f"Turn text length ({len(text)}) exceeds maximum allowed "
            f"length of {max_chars_per_turn} characters",
            code="practice_turn_too_long",
        )


def ensure_daily_session_limit(sessions_today_count: int, max_sessions_per_day: int) -> None:
    """Verify participant has not exceeded daily session quota."""
    if sessions_today_count >= max_sessions_per_day:
        raise DomainError(
            f"Daily practice session limit of {max_sessions_per_day} reached",
            code="practice_daily_limit",
        )


def is_session_turn_limit_reached(turn_count: int, max_turns_per_session: int) -> bool:
    """Check if session has reached or exceeded max turn count."""
    return turn_count >= max_turns_per_session


@asynccontextmanager
async def acquire_generation_lock(
    redis: Redis,
    participant_profile_id: uuid.UUID,
    timeout_seconds: int,
) -> AsyncIterator[None]:
    """Acquire single-flight generation lock in Redis for a participant.

    Prevents concurrent generation requests across tabs/windows.
    Always releases the lock upon exit, even on exception.
    """
    key = f"codrut:practice:lock:{participant_profile_id}"
    acquired = await redis.set(key, "1", ex=timeout_seconds, nx=True)
    if not acquired:
        raise DomainError(
            "Generation is already in progress for this participant",
            code="practice_busy",
        )
    try:
        yield
    finally:
        await redis.delete(key)
