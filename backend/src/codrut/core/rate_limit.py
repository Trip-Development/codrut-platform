import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from fastapi import FastAPI, Request, Response
from starlette import status

from codrut.core.config import Settings, get_settings
from codrut.core.errors import error_response

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int | None = None


class RateLimiter(Protocol):
    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        ...


class NoopRateLimiter:
    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        return RateLimitDecision(allowed=True)


class RedisRateLimiter:
    def __init__(self, redis_url: str) -> None:
        self.redis_url = redis_url
        self._client = None

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        redis = await self._redis()
        window = int(time.time()) // window_seconds
        redis_key = f"codrut:rate:{key}:{window}"
        count = await redis.incr(redis_key)
        if count == 1:
            await redis.expire(redis_key, window_seconds)
        return RateLimitDecision(
            allowed=count <= limit,
            retry_after_seconds=window_seconds if count > limit else None,
        )

    async def _redis(self):
        if self._client is None:
            from redis.asyncio import Redis

            self._client = Redis.from_url(self.redis_url, decode_responses=True)
        return self._client


def build_rate_limiter(settings: Settings) -> RateLimiter:
    if settings.rate_limit_backend == "redis":
        return RedisRateLimiter(settings.redis_url)
    return NoopRateLimiter()


def install_rate_limit_middleware(
    app: FastAPI,
    *,
    settings: Settings | None = None,
    limiter: RateLimiter | None = None,
) -> None:
    active_settings = settings or get_settings()
    app.state.rate_limiter = limiter or build_rate_limiter(active_settings)

    @app.middleware("http")
    async def rate_limit_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not active_settings.rate_limit_enabled or not is_rate_limited_request(request):
            return await call_next(request)

        rate_limiter: RateLimiter = request.app.state.rate_limiter
        decision = await rate_limiter.hit(
            rate_limit_key(request),
            limit=active_settings.rate_limit_max_requests,
            window_seconds=active_settings.rate_limit_window_seconds,
        )
        if decision.allowed:
            return await call_next(request)

        headers = {}
        if decision.retry_after_seconds is not None:
            headers["Retry-After"] = str(decision.retry_after_seconds)
        return error_response(
            request,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="rate_limited",
            message="Too many requests.",
            headers=headers,
        )


def is_rate_limited_request(request: Request) -> bool:
    if request.method.upper() not in UNSAFE_METHODS:
        return False
    return request.url.path.startswith("/api/")


def rate_limit_key(request: Request) -> str:
    client_ip = forwarded_client_ip(request)
    if client_ip is None:
        client_ip = request.client.host if request.client else "unknown"
    path = rate_limit_path_family(request.url.path)
    return f"{client_ip}:{request.method.upper()}:{path}"


def forwarded_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for:
        return None
    return forwarded_for.split(",", 1)[0].strip() or None


def rate_limit_path_family(path: str) -> str:
    if path.startswith("/api/communications/campaigns/recipients/") and path.endswith("/events"):
        return "/api/communications/campaigns/recipients/:recipient_id/events"
    if path.startswith("/api/communications/campaigns/unsubscribe/"):
        return "/api/communications/campaigns/unsubscribe/:token"
    return path
