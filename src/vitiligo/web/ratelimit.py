"""Simple in-memory rate limiting for public deployments.

Uses a sliding window per client IP. Sufficient for a single-process
Single-instance deployment; swap for Redis if we scale horizontally.

Client identity: by default the TCP peer address. Behind reverse proxies set
``trusted_proxy_hops`` to the number of proxies in front of the app; the
client is then the address the outermost trusted proxy appended to
``X-Forwarded-For``, counted from the right. Entries further left are written
by the client and are never trusted. Too small a value only makes clients
share a bucket (the proxy's address); too large a value lets clients spoof.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Above this many tracked clients, idle buckets are swept on the next request.
DEFAULT_MAX_TRACKED_CLIENTS = 10_000


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limit POST requests to ``/api/*`` per client IP."""

    def __init__(
        self,
        app: object,
        *,
        post_limit_per_minute: int = 30,
        window_seconds: int = 60,
        trusted_proxy_hops: int = 0,
        max_tracked_clients: int = DEFAULT_MAX_TRACKED_CLIENTS,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._limit = max(1, post_limit_per_minute)
        self._window = window_seconds
        self._proxy_hops = max(0, trusted_proxy_hops)
        self._max_clients = max(1, max_tracked_clients)
        self._hits: dict[str, deque[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method != "POST" or not request.url.path.startswith("/api/"):
            return await call_next(request)

        if request.url.path == "/api/health":
            return await call_next(request)

        client_ip = client_address(request, self._proxy_hops)
        now = time.monotonic()
        if client_ip not in self._hits and len(self._hits) >= self._max_clients:
            self._sweep(now)
        bucket = self._hits.setdefault(client_ip, deque())

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

    def _sweep(self, now: float) -> None:
        """Drop buckets with no hit inside the current window."""
        idle = [ip for ip, hits in self._hits.items() if not hits or now - hits[-1] > self._window]
        for ip in idle:
            del self._hits[ip]


def client_address(request: Request, trusted_proxy_hops: int = 0) -> str:
    """Rate-limit key for ``request`` (see module docstring)."""
    peer = request.client.host if request.client is not None else "unknown"
    if trusted_proxy_hops <= 0:
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    entries = [e.strip() for e in forwarded.split(",") if e.strip()]
    if len(entries) < trusted_proxy_hops:
        return peer
    return entries[-trusted_proxy_hops]
