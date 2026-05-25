"""Simple in-memory rate limiting for public deployments.

Uses a sliding window per client IP. Sufficient for a single-process
Fly.io / Render instance; swap for Redis if we scale horizontally.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limit POST requests to ``/api/*`` per client IP."""

    def __init__(
        self,
        app: object,
        *,
        post_limit_per_minute: int = 30,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._limit = max(1, post_limit_per_minute)
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method != "POST" or not request.url.path.startswith("/api/"):
            return await call_next(request)

        if request.url.path == "/api/health":
            return await call_next(request)

        client_ip = _client_ip(request)
        now = time.monotonic()
        bucket = self._hits[client_ip]

        while bucket and now - bucket[0] > self._window:
            bucket.popleft()

        if len(bucket) >= self._limit:
            retry_after = max(1, int(self._window - (now - bucket[0])))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded ({self._limit} POST requests per minute).",
                },
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        return await call_next(request)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"
