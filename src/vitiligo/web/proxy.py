"""Restore the client-facing URL scheme behind trusted reverse proxies.

uvicorn runs with ``--no-proxy-headers`` (trusting forwarded headers from any
address would let clients spoof their IP), so behind a TLS-terminating proxy
every request looks like plain ``http``. Starlette builds absolute redirect
URLs (e.g. trailing-slash redirects) from that scheme, which would send
browsers to ``http://``. This middleware applies the same hop rule as the rate
limiter: the N-th ``X-Forwarded-Proto`` entry from the right was written by a
trusted proxy; anything else is ignored.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

_SCHEMES = frozenset({"http", "https"})


def forwarded_proto(header_value: str, trusted_proxy_hops: int) -> str | None:
    """Scheme reported by the outermost trusted proxy, or None if untrusted/absent."""
    if trusted_proxy_hops <= 0:
        return None
    entries = [e.strip().lower() for e in header_value.split(",") if e.strip()]
    if len(entries) < trusted_proxy_hops:
        return None
    proto = entries[-trusted_proxy_hops]
    return proto if proto in _SCHEMES else None


class ForwardedProtoMiddleware:
    """Set ``scope["scheme"]`` from a trusted ``X-Forwarded-Proto`` header."""

    def __init__(self, app: ASGIApp, *, trusted_proxy_hops: int) -> None:
        self.app = app
        self._hops = trusted_proxy_hops

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            raw = [v for k, v in scope.get("headers", []) if k == b"x-forwarded-proto"]
            proto = forwarded_proto(b",".join(raw).decode("latin-1"), self._hops)
            if proto is not None:
                scope = {**scope, "scheme": proto}
        await self.app(scope, receive, send)
